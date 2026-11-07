"""v3's run around its roles. No model: the router is faked."""

import asyncio

import pytest

from app.roles import router, writer
from app.roles.analyst import Figure, Reply, Review, Scope
from app.roles.conversation import Turn
from app.roles.strategist import Strategy
from app.tools import Run
from app.versions import v3


def test_a_refusal_claims_no_review(monkeypatch: pytest.MonkeyPatch):
    async def plan(question, history=()):
        reply = "我只能回答這家店的銷售問題。"
        return router.Plan(route="refuse", strategy=False, chart=False, reply=reply, options=[])

    monkeypatch.setattr(v3.router, "plan", plan)
    answer = asyncio.run(v3.ask("今天天氣如何？", days=None, segment=None))
    # Nothing was looked up, so nothing was checked: the app must not say it was.
    assert answer.review is None
    assert answer.ledger == []


def test_a_follow_up_reaches_every_role_that_reads_it(monkeypatch: pytest.MonkeyPatch):
    """A follow-up such as "a smaller discount" means nothing alone: the router, the analyst and
    the strategist each get the conversation it follows."""
    earlier = [Turn(question="幫早餐類商品設計活動", answer="吐司 + 鮮乳，打 8 折。")]
    given = {}

    async def plan(question, history=()):
        given["router"] = list(history)
        return router.Plan(route="answer", strategy=True, chart=False, reply="", options=[])

    async def analyse(question, days, segment, handoff=False, ignored=(), history=()):
        given["analyst"] = list(history)
        figure = Figure(name="lift", value=2.1, source="L1")
        reply = Reply(
            text="吐司與鮮乳的提升度為 2.1。",
            views=[Scope(days=None, segment=None)],
            items=["吐司", "鮮乳"],
            pairs=[],
            figures=[figure],
            options=[],
        )
        return reply, Run(segments=[]), Review(passed=True, caught=[], notes=[])

    async def draft(question, reply, run, history=()):
        given["strategist"] = list(history)
        return Strategy(text="", campaigns=[], figures=[]), [], []

    async def write(question, strategy, ignored=()):
        return writer.pitched(strategy)

    monkeypatch.setattr(v3.router, "plan", plan)
    monkeypatch.setattr(v3, "analyse", analyse)
    monkeypatch.setattr(v3.strategist, "draft", draft)
    monkeypatch.setattr(v3.writer, "write", write)
    asyncio.run(v3.ask("折扣小一點", days=None, segment=None, history=earlier))
    assert given == {"router": earlier, "analyst": earlier, "strategist": earlier}
