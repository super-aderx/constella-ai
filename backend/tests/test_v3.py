"""v3's run around its roles. No model: the router is faked."""

import asyncio

import pytest

from app.roles import router
from app.versions import v3


def test_a_refusal_claims_no_review(monkeypatch: pytest.MonkeyPatch):
    async def plan(question):
        reply = "我只能回答這家店的銷售問題。"
        return router.Plan(route="refuse", strategy=False, chart=False, reply=reply, options=[])

    monkeypatch.setattr(v3.router, "plan", plan)
    answer = asyncio.run(v3.ask("今天天氣如何？", days=None, segment=None))
    # Nothing was looked up, so nothing was checked: the app must not say it was.
    assert answer.review is None
    assert answer.ledger == []
