"""The writer's slogans: what may go out, and what the answer carries when it fails. No model."""

import asyncio
from types import SimpleNamespace

import pytest

from app.roles import writer
from app.roles.strategist import Campaign, Strategy
from app.roles.writer import Copy, Lines, Slogan, slogan_problems

CAMPAIGN = Campaign(
    name="早餐組合",
    basis="proven",
    items=["鮮乳", "吐司"],
    discount_percent=20,
    audience=None,
    reason="常一起買",
)
STRATEGY = Strategy(text="兩個選項", campaigns=[CAMPAIGN], figures=[])


def plain(text: str) -> Slogan:
    return Slogan(text=text, pun=None)


@pytest.mark.parametrize(
    "text", ["早餐一次備齊", "鮮乳配吐司，現省 20%", "早餐組合 8 折", "立享八折", "全組 80 折"]
)
def test_a_slogan_may_carry_the_discount_and_no_other_number(text):
    assert slogan_problems(plain(text), CAMPAIGN) == []


# 20% off is 8折: 20折 and 二十折 misstate the offer.
@pytest.mark.parametrize(
    "text", ["買 2 送 1", "現省 30%", "只要 99 元", "輕鬆 20 折", "輕鬆二十折", "七折", "現省 80%"]
)
def test_a_slogan_may_not_promise_another_number(text):
    assert slogan_problems(plain(text), CAMPAIGN)


def test_a_slogan_may_not_name_a_type_set_aside():
    assert slogan_problems(plain("配啤酒更對味"), CAMPAIGN, ignored=["啤酒"])
    assert slogan_problems(plain("配啤酒更對味"), CAMPAIGN) == []


def test_a_pun_is_played_in_its_slogan():
    assert slogan_problems(Slogan(text="吐司你的早晨", pun="吐司 ≈ 偷吃"), CAMPAIGN) == []
    # The word heard is there, not the product's: the swap was never made.
    assert slogan_problems(Slogan(text="不要先入為主", pun="鮮乳 ≈ 先入"), CAMPAIGN)
    assert slogan_problems(Slogan(text="吐司你的早晨", pun="a pun on toast"), CAMPAIGN)


def test_write_keeps_the_slogans_that_pass(monkeypatch):
    async def run(agent, brief):
        slogans = [
            Slogan(text="吐司你的早晨", pun="吐司 ≈ 偷吃"),
            Slogan(text="買 2 送 1", pun=None),
            Slogan(text="現省 20%", pun=None),
        ]
        lines = Lines(campaign="早餐組合", sounds=["吐司：偷吃"], slogans=slogans)
        return SimpleNamespace(final_output=Copy(campaigns=[lines]))

    monkeypatch.setattr(writer.Runner, "run", run)
    pitched = asyncio.run(writer.write("幫我想個活動", STRATEGY))
    assert [s.text for s in pitched.campaigns[0].slogans] == ["吐司你的早晨", "現省 20%"]
    assert pitched.campaigns[0].slogans[0].pun == "吐司 ≈ 偷吃"
    assert "sounds" not in pitched.model_dump()["campaigns"][0]
    assert pitched.campaigns[0].items == CAMPAIGN.items


def test_a_writer_that_fails_leaves_the_campaigns_without_slogans(monkeypatch):
    async def run(agent, brief):
        raise RuntimeError("no such model")

    monkeypatch.setattr(writer.Runner, "run", run)
    pitched = asyncio.run(writer.write("幫我想個活動", STRATEGY))
    assert pitched.text == STRATEGY.text
    assert pitched.campaigns[0].slogans == []
