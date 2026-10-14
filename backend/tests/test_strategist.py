"""The checks on the campaigns the strategist drafts: each must be runnable as written, and the
options must differ. No model."""

import pytest

from app.roles.strategist import Campaign, Strategy, campaign_problems, strategy_problems

NETWORK = {
    "items": [{"name": n} for n in ["鮮乳", "吐司", "優格", "啤酒", "雞蛋"]],
    "pairs": [{"a": "吐司", "b": "鮮乳"}, {"a": "優格", "b": "鮮乳"}],
    "segments": ["忠誠客戶", "新客戶"],
}
# The run's tools returned one candidate: 吐司 + 優格 could sell together.
LEDGER = [
    {
        "id": "L1",
        "tool": "potential_pairs",
        "args": {},
        "result": [{"a": "優格", "b": "吐司", "shared_partners": ["鮮乳", "雞蛋"]}],
    }
]


def campaign(**changes) -> Campaign:
    proven = {
        "name": "早餐組合",
        "basis": "proven",
        "items": ["鮮乳", "吐司"],
        "discount_percent": 10,
        "audience": None,
        "reason": "常一起買",
    }
    return Campaign(**{**proven, **changes})


def problems(**changes) -> list[str]:
    return campaign_problems(campaign(**changes), NETWORK, LEDGER)


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"items": ["鮮乳", "吐司", "優格"]},
        {"audience": "忠誠客戶"},
        {"discount_percent": 30},
        # A bet on growth: a candidate the tools returned, though not a pair on the graph.
        {"basis": "potential", "items": ["吐司", "優格"]},
    ],
)
def test_a_campaign_that_can_run_passes(changes: dict):
    assert problems(**changes) == []


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"items": ["鮮乳"]}, "two or three different product types"),
        ({"items": ["鮮乳", "吐司", "優格", "啤酒"]}, "two or three different product types"),
        ({"items": ["鮮乳", "鮮乳"]}, "two or three different product types"),
        ({"items": ["鮮乳", "貓砂"]}, "貓砂 is not a product type on the graph"),
        ({"items": ["鮮乳", "吐司", "啤酒"]}, "啤酒 is not a pair on the graph with another"),
        ({"discount_percent": 60}, "`discount_percent` must be from 5 to 30"),
        ({"discount_percent": 0}, "`discount_percent` must be from 5 to 30"),
        ({"audience": "白金會員"}, "白金會員 is not a segment"),
        # A bet the data never suggested.
        ({"basis": "potential", "items": ["啤酒", "雞蛋"]}, "not a candidate potential_pairs"),
    ],
)
def test_a_campaign_that_cannot_run_is_refused(changes: dict, problem: str):
    assert any(problem in found for found in problems(**changes))


def options(*campaigns: Campaign) -> list[str]:
    strategy = Strategy(text="三個選項", campaigns=list(campaigns), figures=[])
    return strategy_problems(strategy, NETWORK, LEDGER)


def test_two_options_that_differ_pass():
    assert options(campaign(), campaign(name="優格組合", items=["鮮乳", "優格"])) == []


def test_one_option_is_not_a_choice():
    assert "Give two or three campaigns." in options(campaign())


def test_the_same_bundle_twice_is_not_a_choice():
    found = options(campaign(), campaign(name="換個名字", items=["吐司", "鮮乳"]))
    assert any("bundle the same product types" in problem for problem in found)


def test_a_campaign_on_a_type_the_user_set_aside_is_refused():
    assert campaign_problems(campaign(), NETWORK, LEDGER, ["啤酒"]) == []
    problems = campaign_problems(campaign(), NETWORK, LEDGER, ["吐司"])
    assert len(problems) == 1
    assert "set 吐司 aside" in problems[0]
