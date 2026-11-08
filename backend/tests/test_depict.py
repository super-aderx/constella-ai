"""The Brief's server side (depict): the code pre-checks, the fixed plan per card and the
registry that runs the cards in the background. No database or model: networks are made by hand
and the card run is faked."""

import asyncio
import logging

import pytest

from app import depict
from app.depict import CARDS, Busy, Registry, answer_card, precheck
from app.roles.analyst import Figure, Reply, Review, Scope
from app.roles.strategist import Campaign, Strategy
from app.tools import Run
from app.versions import v3

KEYS = [c.key for c in CARDS]


def pair(a: str, b: str, lift: float, co_orders: int = 50) -> dict:
    return {"a": a, "b": b, "lift": lift, "coOrders": co_orders}


def network(pairs: list[dict], communities: list[str], members: dict[str, int | None]) -> dict:
    items = [
        {"name": name, "orders": 100, "revenue": 0.0, "community": c, "bridge": False}
        for name, c in members.items()
    ]
    return {"items": items, "pairs": pairs, "communities": communities, "segments": []}


EMPTY = network([], [], {"吐司": None})
# 吐司 - 鮮乳 - 優格 in a line: one group, and 鮮乳 sits between the other two.
ONE_GROUP = network(
    [pair("吐司", "鮮乳", 2.0), pair("鮮乳", "優格", 1.5)],
    ["鮮乳 & 吐司"],
    {"吐司": 0, "鮮乳": 0, "優格": 0},
)
# Two pairs that touch nowhere: two groups, and nothing between them.
NO_BRIDGE = network(
    [pair("吐司", "果醬", 2.0), pair("啤酒", "洋芋片", 3.0)],
    ["吐司 & 果醬", "啤酒 & 洋芋片"],
    {"吐司": 0, "果醬": 0, "啤酒": 1, "洋芋片": 1},
)
# Two groups that 鮮乳 links, and 鮮乳 and 果醬 share 吐司 and 奶油 without a pair of their own.
RICH = network(
    [
        pair("吐司", "果醬", 3.0),
        pair("吐司", "奶油", 2.5),
        pair("果醬", "奶油", 2.0),
        pair("優格", "穀片", 2.2),
        pair("鮮乳", "吐司", 1.8),
        pair("鮮乳", "奶油", 1.5),
        pair("鮮乳", "優格", 1.4),
    ],
    ["吐司 & 果醬", "優格 & 穀片"],
    {"鮮乳": 0, "吐司": 0, "果醬": 0, "奶油": 0, "優格": 1, "穀片": 1},
)

NO_PAIRS = "No pairs bought together in this scope."
NO_COMBOS = "No combos with unused potential in this scope."
NO_GROUPS = "No groups of product types in this scope."
ONE = "Only one group of product types in this scope."
NO_BRIDGES = "No bridge product types in this scope."


def test_the_cards_are_the_eight_questions_in_order():
    assert KEYS == [
        "unrealized_combos",
        "best_pairs",
        "worst_pairs",
        "bestseller_causes",
        "community_key_items",
        "cross_community",
        "in_community_combos",
        "bridge_removal",
    ]
    assert [c.key for c in CARDS if c.strategy] == ["cross_community", "in_community_combos"]


def test_precheck_with_no_pairs():
    assert {k: precheck(k, EMPTY) for k in KEYS} == {
        "unrealized_combos": NO_COMBOS,
        "best_pairs": NO_PAIRS,
        "worst_pairs": NO_PAIRS,
        "bestseller_causes": NO_PAIRS,
        "community_key_items": NO_GROUPS,
        "cross_community": ONE,
        "in_community_combos": NO_GROUPS,
        "bridge_removal": NO_BRIDGES,
    }


def test_precheck_with_one_group():
    assert precheck("cross_community", ONE_GROUP) == ONE
    assert precheck("community_key_items", ONE_GROUP) is None
    assert precheck("in_community_combos", ONE_GROUP) is None
    assert precheck("bridge_removal", ONE_GROUP) is None


def test_precheck_with_no_bridge():
    assert precheck("bridge_removal", NO_BRIDGE) == NO_BRIDGES
    assert precheck("cross_community", NO_BRIDGE) is None
    assert precheck("best_pairs", NO_BRIDGE) is None


def test_precheck_lets_every_card_run_on_a_rich_network():
    assert {k: precheck(k, RICH) for k in KEYS} == dict.fromkeys(KEYS)


# The registry, with the card run faked.


def answer(text: str = "ok") -> v3.Answer:
    return v3.Answer(
        text=text,
        views=[],
        items=[],
        pairs=[],
        figures=[],
        options=[],
        ledger=[],
        review=Review(passed=True, caught=[], notes=[]),
        chart=None,
        plan=v3.Route(route="depict", strategy=False, chart=False),
        strategy=None,
    )


class Fake:
    """A card run that counts its calls, can be held at a gate, and fails for chosen keys."""

    def __init__(self, fail: tuple[str, ...] = ()):
        self.calls: list[tuple[str, int | None, str | None]] = []
        self.fail = set(fail)
        self.gate: asyncio.Event | None = None
        self.running = self.most = 0

    async def __call__(self, card, days, segment) -> v3.Answer:
        self.calls.append((card.key, days, segment))
        self.running += 1
        self.most = max(self.most, self.running)
        try:
            if self.gate:
                await self.gate.wait()
            if card.key in self.fail:
                raise RuntimeError("no model")
            return answer(f"{card.key} #{len(self.calls)}")
        finally:
            self.running -= 1


@pytest.fixture(autouse=True)
def networks(monkeypatch: pytest.MonkeyPatch) -> dict:
    """The network each scope reads: RICH unless a test sets another."""
    given: dict = {}
    monkeypatch.setattr(depict, "load_network", lambda days, segment: given.get(segment, RICH))
    return given


async def settle(registry: Registry) -> None:
    while registry._tasks:
        await asyncio.gather(*registry._tasks)


async def until(check) -> None:
    """Lets the background tasks run until `check()` holds. Each card reads its network in a
    worker thread, so this gives them real time, not just a turn of the loop."""
    for _ in range(2000):
        if check():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("never happened")


def states(registry: Registry, scope) -> dict[str, str]:
    return {c.key: c.state for c in registry.get(scope).cards}


def test_a_scope_never_started_reads_as_eight_waiting_cards():
    found = Registry(Fake()).get((90, None))
    assert (found.days, found.segment) == (90, None)
    assert [c.key for c in found.cards] == KEYS
    assert [c.title for c in found.cards][0] == "潛力未發揮的產品組合分析"
    assert {c.state for c in found.cards} == {"waiting"}
    assert all(c.answer is None and c.answered_at is None for c in found.cards)


def test_start_runs_each_card_once():
    fake = Fake()

    async def go():
        registry = Registry(fake)
        first = registry.start((90, None))
        again = registry.start((90, None))
        assert first == again
        await settle(registry)
        # A scope already answered is left as it is.
        registry.start((90, None))
        await settle(registry)
        return registry

    registry = asyncio.run(go())
    assert sorted(key for key, _, _ in fake.calls) == sorted(KEYS)
    assert set(states(registry, (90, None)).values()) == {"answered"}


def test_concurrent_starts_share_one_run():
    fake = Fake()

    async def go():
        registry = Registry(fake)

        async def start():
            return registry.start((30, "Champions"))

        await asyncio.gather(start(), start())
        await settle(registry)

    asyncio.run(go())
    assert len(fake.calls) == 8
    assert {(days, segment) for _, days, segment in fake.calls} == {(30, "Champions")}


def test_an_old_scope_finishes_when_a_new_one_starts():
    held, free = Fake(), Fake()

    async def run(card, days, segment):
        return await (held if days == 90 else free)(card, days, segment)

    async def go():
        registry = Registry(run, concurrency=16)
        held.gate = asyncio.Event()
        registry.start((90, None))
        await until(lambda: held.running == 8)
        registry.start((30, None))
        await until(lambda: set(states(registry, (30, None)).values()) == {"answered"})
        assert set(states(registry, (90, None)).values()) == {"answering"}
        held.gate.set()
        await settle(registry)
        return registry

    registry = asyncio.run(go())
    assert set(states(registry, (90, None)).values()) == {"answered"}


def test_one_failure_leaves_the_others_answered(caplog: pytest.LogCaptureFixture):
    async def go():
        registry = Registry(Fake(fail=("best_pairs",)))
        registry.start((None, None))
        await settle(registry)
        return registry

    with caplog.at_level(logging.ERROR):
        registry = asyncio.run(go())
    cards = {c.key: c for c in registry.get((None, None)).cards}
    assert cards["best_pairs"].state == "failed"
    assert cards["best_pairs"].error == "Couldn't answer. Try again."
    assert cards["best_pairs"].answer is None
    assert [k for k, c in cards.items() if c.state == "answered"] == [
        k for k in KEYS if k != "best_pairs"
    ]
    assert "best_pairs" in caplog.text


def test_a_failed_network_read_fails_each_card_alone(monkeypatch: pytest.MonkeyPatch):
    def load_network(days, segment):
        raise OSError("no database")

    monkeypatch.setattr(depict, "load_network", load_network)

    async def go():
        registry = Registry(Fake())
        registry.start((None, None))
        await settle(registry)
        return registry

    assert set(states(asyncio.run(go()), (None, None)).values()) == {"failed"}


def test_no_data_skips_the_model(networks: dict):
    networks["Lost"] = NO_BRIDGE
    fake = Fake()

    async def go():
        registry = Registry(fake)
        registry.start((None, "Lost"))
        await settle(registry)
        return registry

    cards = {c.key: c for c in asyncio.run(go()).get((None, "Lost")).cards}
    assert cards["bridge_removal"].state == "no_data"
    assert cards["bridge_removal"].reason == NO_BRIDGES
    # Only the cards with something to answer called the model.
    runnable = [k for k in KEYS if precheck(k, NO_BRIDGE) is None]
    assert "bridge_removal" not in runnable
    assert sorted(key for key, _, _ in fake.calls) == sorted(runnable)


def test_refresh_reruns_only_that_card():
    fake = Fake(fail=("best_pairs",))

    async def go():
        registry = Registry(fake)
        registry.start((None, None))
        await settle(registry)
        fake.fail.clear()
        fake.gate = asyncio.Event()
        card = registry.refresh((None, None), "best_pairs")
        assert card.state == "answering"
        await until(lambda: fake.running == 1)
        with pytest.raises(Busy) as busy:
            registry.refresh((None, None), "best_pairs")
        assert busy.value.card.state == "answering"
        fake.gate.set()
        await settle(registry)
        return registry

    registry = asyncio.run(go())
    assert len(fake.calls) == 9
    assert fake.calls[-1][0] == "best_pairs"
    assert set(states(registry, (None, None)).values()) == {"answered"}


def test_refresh_keeps_the_old_answer_while_it_runs():
    fake = Fake()

    async def go():
        registry = Registry(fake)
        registry.start((None, None))
        await settle(registry)
        before = next(c for c in registry.get((None, None)).cards if c.key == "worst_pairs")
        fake.gate = asyncio.Event()
        registry.refresh((None, None), "worst_pairs")
        await until(lambda: fake.running == 1)
        during = next(c for c in registry.get((None, None)).cards if c.key == "worst_pairs")
        assert during.state == "answering"
        assert (during.answer, during.answered_at) == (before.answer, before.answered_at)
        fake.gate.set()
        await settle(registry)
        after = next(c for c in registry.get((None, None)).cards if c.key == "worst_pairs")
        assert after.state == "answered"
        assert after.answer.text == "worst_pairs #9"

    asyncio.run(go())


def test_a_failed_refresh_clears_the_old_answer():
    fake = Fake()

    async def go():
        registry = Registry(fake)
        registry.start((None, None))
        await settle(registry)
        fake.fail.add("worst_pairs")
        registry.refresh((None, None), "worst_pairs")
        await settle(registry)
        return next(c for c in registry.get((None, None)).cards if c.key == "worst_pairs")

    card = asyncio.run(go())
    assert (card.state, card.answer, card.answered_at) == ("failed", None, None)


def test_refresh_is_refused_while_busy_or_unknown():
    async def go():
        registry = Registry(Fake())
        with pytest.raises(KeyError):
            registry.refresh((None, None), "nope")
        # Never started: every card is waiting.
        with pytest.raises(Busy):
            registry.refresh((None, None), "best_pairs")

    asyncio.run(go())


def test_the_concurrency_cap_is_respected():
    fake = Fake()

    async def go():
        registry = Registry(fake, concurrency=2)
        fake.gate = asyncio.Event()
        registry.start((None, None))
        await until(lambda: fake.running == 2)
        for _ in range(20):
            await asyncio.sleep(0)
        counts = list(states(registry, (None, None)).values())
        assert (counts.count("answering"), counts.count("waiting")) == (2, 6)
        fake.gate.set()
        await settle(registry)
        return registry

    registry = asyncio.run(go())
    assert fake.most == 2
    assert set(states(registry, (None, None)).values()) == {"answered"}


# The fixed plan of one card.


def reply() -> Reply:
    return Reply(
        text="重點\n\n1. 吐司與鮮乳的提升度為 1.8。",
        views=[Scope(days=None, segment=None)],
        items=["吐司", "鮮乳"],
        pairs=[],
        figures=[Figure(name="lift", value=1.8, source="L1")],
        options=[],
    )


@pytest.fixture
def plan(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Fakes the analyst and the strategist, and records what each was given."""
    given: dict = {"passed": True}

    async def analyse(question, days, segment, handoff=False, ignored=(), history=()):
        given["analyst"] = {"handoff": handoff, "ignored": tuple(ignored), "scope": (days, segment)}
        ledger = [{"id": "L1", "tool": "top_pairs", "args": {}, "result": []}]
        review = Review(passed=given["passed"], caught=[], notes=[] if given["passed"] else ["x"])
        return reply(), Run(segments=[], ledger=ledger), review

    async def draft(question, reply, run, history=()):
        given["strategist"] = question
        campaign = Campaign(
            name="早餐組合",
            basis="proven",
            items=["吐司", "鮮乳"],
            discount_percent=10,
            audience=None,
            reason="常一起買",
        )
        return Strategy(text="推薦", campaigns=[campaign], figures=[]), ["caught"], []

    monkeypatch.setattr(depict, "analyse", analyse)
    monkeypatch.setattr(depict.strategist, "draft", draft)
    return given


def card(key: str):
    return next(c for c in CARDS if c.key == key)


def test_a_strategy_card_drafts_campaigns_without_slogans(plan: dict):
    found = asyncio.run(answer_card(card("cross_community"), 90, "Champions"))
    assert plan["analyst"] == {"handoff": True, "ignored": (), "scope": (90, "Champions")}
    assert plan["strategist"] == card("cross_community").prompt
    assert found.plan.model_dump() == {"route": "depict", "strategy": True, "chart": False}
    assert [c.slogans for c in found.strategy.campaigns] == [[]]
    assert found.review.caught == ["caught"]
    assert found.ledger[0]["id"] == "L1"
    assert found.chart is None


def test_a_card_of_fact_asks_no_strategist(plan: dict):
    found = asyncio.run(answer_card(card("best_pairs"), None, None))
    assert plan["analyst"]["handoff"] is False
    assert "strategist" not in plan
    assert found.strategy is None
    assert found.plan.model_dump() == {"route": "depict", "strategy": False, "chart": False}


def test_a_strategy_card_skips_the_strategist_when_review_fails(plan: dict):
    plan["passed"] = False
    found = asyncio.run(answer_card(card("in_community_combos"), None, None))
    assert "strategist" not in plan
    assert found.strategy is None
    assert found.review.passed is False


def test_every_prompt_asks_for_the_takeaway_first():
    assert all(depict.FORMAT in c.prompt for c in CARDS)
