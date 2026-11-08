"""The Brief: 8 standard questions about the network, answered on the server for whatever scope
the graph shows, and shared by everyone who looks at that scope until the server restarts.

It is called `depict` in code because `brief` already means v1's network summary.

Each card runs a fixed plan, with no router and no writer: the analyst (reviewed), and for the
two cards that recommend combinations, the strategist (reviewed) too. The 8 runs are the same
every time, so routing them would only add cost and chance. The answer has v3's shape, so the app
shows, highlights and continues it the way it does a chat answer.

The registry keeps every scope's cards in memory, per process: one worker only. A scope's cards
run as background tasks, so a scope the user has left still finishes and is there when someone
comes back to it. A pre-check in code says "not enough data" before any model is called.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from app.infra.data import load_network
from app.roles import strategist, writer
from app.roles.analyst import Review, analyse
from app.tools.lookups import betweenness
from app.tools.potential import shared_partners
from app.versions import v3

DEPICT_CONCURRENCY = 4  # card runs calling the model at once: a new scope is 8 runs
FAILED = "Couldn't answer. Try again."

CardKey = Literal[
    "unrealized_combos",
    "best_pairs",
    "worst_pairs",
    "bestseller_causes",
    "community_key_items",
    "cross_community",
    "in_community_combos",
    "bridge_removal",
]
CardState = Literal["waiting", "answering", "answered", "no_data", "failed"]
Scope = tuple[int | None, str | None]


class Card(BaseModel):
    """One of the Brief's questions: what it asks the analyst, and whether the strategist turns
    its findings into campaigns."""

    key: CardKey
    title: str
    prompt: str
    strategy: bool


# The app shows the first paragraph as the card's takeaway (D5), so every prompt asks for it.
FORMAT = "先用最多 3 行寫出重點結論，空一行，再用編號清單列出細節排名。每個數字都要來自工具。"

CARDS = [
    Card(
        key="unrealized_combos",
        title="潛力未發揮的產品組合分析",
        prompt="這個範圍內有哪些產品組合潛力還沒發揮？用 potential_pairs（shared_partners）"
        "找出還沒常被一起買、但有共同搭配對象的組合，附上證據，並說明它們是值得測試的候選，"
        "不是預測。",
        strategy=False,
    ),
    Card(
        key="best_pairs",
        title="最佳共同購買組合排名",
        prompt="這個範圍內最常被一起購買的產品組合排名：用 top_pairs 依提升度由強到弱排出前幾名，"
        "並附上共同購買的籃數。",
        strategy=False,
    ),
    Card(
        key="worst_pairs",
        title="最差共同購買組合排名",
        prompt="這個範圍內一起購買最弱的產品組合排名：用 top_pairs 依提升度由弱到強"
        "（order weakest）排出前幾名，並附上共同購買的籃數。",
        strategy=False,
    ),
    Card(
        key="bestseller_causes",
        title="暢銷產品組合之成因分析",
        prompt="這個範圍內最暢銷的產品類型為什麼賣得好？先用 top_items 依營收找出暢銷類型，"
        "再看它們最常和哪些類型一起被買（item_neighbors），以及是否是連接其他類型的橋樑"
        "（central_items）。",
        strategy=False,
    ),
    Card(
        key="community_key_items",
        title="社群內重要產品分析",
        prompt="這個範圍內每個社群（communities）裡最重要的產品類型是哪些？依營收、訂單數"
        "和連接其他類型的程度（central_items）說明。",
        strategy=False,
    ),
    Card(
        key="cross_community",
        title="跨社群產品推薦",
        prompt="這個範圍內有哪些跨社群的產品組合值得推薦？先用 communities 找出社群，"
        "再找出分屬兩個不同社群、但被一起購買高於機率的產品類型組合，作為跨社群推薦的依據。",
        strategy=True,
    ),
    Card(
        key="in_community_combos",
        title="社群內產品組合推薦",
        prompt="這個範圍內各社群裡有哪些產品組合值得推薦？先用 communities 找出社群，"
        "再用 top_pairs 或 top_bundles 找出同一社群內最常一起購買的組合，作為推薦的依據。",
        strategy=True,
    ),
    Card(
        key="bridge_removal",
        title="關鍵節點去留差異比較",
        prompt="這個範圍內的關鍵橋樑產品類型如果不存在，網路會有什麼不同？先用 central_items "
        "找出最多 3 個橋樑類型，再對每一個用 without_item 比較有它和沒有它的網路："
        "失去的組合、網路分成幾塊、被切開的部分，以及只靠它連接的社群。",
        strategy=False,
    ),
]
for _card in CARDS:
    _card.prompt += f"\n\n{FORMAT}"
BY_KEY = {c.key: c for c in CARDS}


class DepictCard(BaseModel):
    """One card as the app shows it. `answer` is kept while a refresh runs."""

    key: CardKey
    title: str
    state: CardState
    answer: v3.Answer | None = None
    reason: str | None = None  # why there is not enough data, when "no_data"
    error: str | None = None  # when "failed"
    answered_at: datetime | None = None


class Depict(BaseModel):
    """A scope's 8 cards, in the order of the questions."""

    days: int | None
    segment: str | None
    cards: list[DepictCard]


def precheck(key: CardKey, network: dict) -> str | None:
    """Why a card has nothing to answer in this scope, or None. Code, so a scope that is too
    small costs no model call and says plainly why it is empty."""
    if key in ("best_pairs", "worst_pairs", "bestseller_causes") and not network["pairs"]:
        return "No pairs bought together in this scope."
    if key == "unrealized_combos" and not shared_partners(network):
        return "No combos with unused potential in this scope."
    if key in ("community_key_items", "in_community_combos") and not network["communities"]:
        return "No groups of product types in this scope."
    if key == "cross_community" and len(network["communities"]) < 2:
        return "Only one group of product types in this scope."
    if key == "bridge_removal" and not any(v > 0 for v in betweenness(network)[0].values()):
        return "No bridge product types in this scope."
    return None


async def answer_card(card: Card, days: int | None, segment: str | None) -> v3.Answer:
    """One card's fixed plan: v3's chain without the router, the writer's model or a chart.

    It runs for everyone who looks at the scope, so with no one's set-aside types (D3); the app
    flags a recommendation that uses one of the viewer's. Campaigns go out without slogans.
    """
    reply, run, verdict = await analyse(
        card.prompt, days, segment, handoff=card.strategy, ignored=()
    )
    strategy = None
    # Campaigns only on findings that passed review and state something to build on, as in v3.
    if card.strategy and verdict.passed and reply.figures:
        drafted, caught, notes = await strategist.draft(card.prompt, reply, run)
        verdict = Review(
            passed=not notes, caught=verdict.caught + caught, notes=verdict.notes + notes
        )
        strategy = writer.pitched(drafted)
    return v3.Answer(
        **reply.model_dump(),
        ledger=run.ledger,
        review=verdict,
        chart=None,
        plan=v3.Route(route="depict", strategy=card.strategy, chart=False),
        strategy=strategy,
    )


class Busy(Exception):
    """A refresh of a card that is still waiting or being answered."""

    def __init__(self, card: DepictCard):
        super().__init__(f"The card {card.key} is {card.state}.")
        self.card = card


def waiting(card: Card) -> DepictCard:
    return DepictCard(key=card.key, title=card.title, state="waiting")


class Registry:
    """Every scope's cards, and the background runs that answer them.

    `run` answers one card; tests pass a fake. Methods that start runs must be called on the
    event loop. Starting and refreshing never await between checking a card and claiming it, so
    two requests at once can't both start the same run.
    """

    def __init__(self, run=answer_card, concurrency: int = DEPICT_CONCURRENCY):
        self.run = run
        self._limit = asyncio.Semaphore(concurrency)
        self._scopes: dict[Scope, dict[str, DepictCard]] = {}
        # One read of each scope's network, shared by its cards (see _network).
        self._networks: dict[Scope, asyncio.Task] = {}
        # The loop keeps only weak references to tasks: these keep the runs alive.
        self._tasks: set[asyncio.Task] = set()

    def get(self, scope: Scope) -> Depict:
        """The scope's cards. A scope never started reads as 8 waiting cards."""
        cards = self._scopes.get(scope, {})
        days, segment = scope
        found = [cards.get(c.key) or waiting(c) for c in CARDS]
        return Depict(days=days, segment=segment, cards=found)

    def start(self, scope: Scope) -> Depict:
        """Starts every card of a scope once. A scope already started, answered or not, is left
        as it is: a failed card is retried by refreshing it."""
        if scope not in self._scopes:
            self._scopes[scope] = {c.key: waiting(c) for c in CARDS}
            for card in CARDS:
                self._spawn(scope, card)
        return self.get(scope)

    def refresh(self, scope: Scope, key: str) -> DepictCard:
        """Runs one card again. It shows as answering and keeps its answer until the new one
        lands. Raises KeyError for an unknown card and Busy while it is waiting or answering."""
        card = BY_KEY[key]
        current = self._scopes.get(scope, {}).get(key) or waiting(card)
        if current.state in ("waiting", "answering"):
            raise Busy(current)
        self._set(scope, key, state="answering", reason=None, error=None)
        self._spawn(scope, card)
        return self._scopes[scope][key]

    def _spawn(self, scope: Scope, card: Card) -> None:
        task = asyncio.create_task(self._answer(scope, card))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _network(self, scope: Scope) -> asyncio.Task:
        """The scope's network, read once for all its cards. load_network's cache does not stop
        threads that miss it at the same moment from each reading the database, so the 8 cards
        of a new scope wait on one read. A read that failed is tried again by the next card that
        needs it, such as a refresh."""
        read = self._networks.get(scope)
        if read is None or (read.done() and (read.cancelled() or read.exception())):
            read = asyncio.create_task(asyncio.to_thread(load_network, *scope))
            self._networks[scope] = read
        return read

    def _set(self, scope: Scope, key: str, **update) -> None:
        # A fresh card each time: one already handed out never changes under its reader.
        self._scopes[scope][key] = self._scopes[scope][key].model_copy(update=update)

    async def _answer(self, scope: Scope, card: Card) -> None:
        try:
            network = await self._network(scope)
            if reason := precheck(card.key, network):
                self._set(scope, card.key, state="no_data", reason=reason, answer=None)
                self._set(scope, card.key, answered_at=None)
                return
            async with self._limit:
                self._set(scope, card.key, state="answering")
                answer = await self.run(card, *scope)
            now = datetime.now(UTC)
            self._set(scope, card.key, state="answered", answer=answer, answered_at=now)
        except Exception:
            # One card's failure is that card's: the others carry on.
            logging.exception("The depict card %s failed for %s", card.key, scope)
            self._set(scope, card.key, state="failed", error=FAILED, answer=None)
            self._set(scope, card.key, answered_at=None)


registry = Registry()
