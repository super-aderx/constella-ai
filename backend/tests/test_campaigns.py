"""The campaign rules, on a sound draft and on drafts with a planted fault, checked without a
database or a model."""

from datetime import UTC, date, datetime

import pytest

from app.campaigns import (
    ACTIONS,
    CampaignDraft,
    Pilot,
    action_problem,
    draft_problems,
    status_of,
    store_today,
)

CATALOG = {"teapot": ["blue teapot"], "cups": ["tea cup", "blue tea cup"]}
SEGMENTS = ["Champions", "Loyal"]
COUNTIES = ["台北市", "新北市"]
TODAY = date(2026, 11, 7)


def draft(**changes) -> CampaignDraft:
    """A sound draft, with some of it changed."""
    clean = {
        "client_token": "0b7e3c1a-5d2f-4e8b-9a6c-1f2e3d4c5b6a",
        "source_proposal": {
            "name": "Tea time bundle",
            "basis": "proven",
            "items": ["teapot", "cups"],
            "discount_percent": 15,
            "audience": None,
            "reason": "Teapots and cups sell together.",
        },
        "title": "Tea time bundle",
        "strategy": "Teapots and cups sell together.",
        "products": [{"kind": "type", "name": "teapot"}, {"kind": "product", "name": "tea cup"}],
        "discount_percent": 15,
        "starts_on": "2026-12-10",
        "ends_on": "2026-12-24",
        "segment": "Champions",
        "counties": ["台北市"],
        "pilot": {
            "audience_percent": 10,
            "starts_on": "2026-12-01",
            "ends_on": "2026-12-07",
            "discount_percent": 10,
            "auto_start": False,
        },
    }
    return CampaignDraft.model_validate({**clean, **changes})


def pilot(**changes) -> dict:
    return {**draft().pilot.model_dump(mode="json"), **changes}


def problems(d: CampaignDraft) -> list:
    return draft_problems(d, CATALOG, SEGMENTS, COUNTIES, TODAY)


def test_a_valid_draft_has_no_problems():
    assert problems(draft()) == []


def test_a_draft_with_no_pilot_segment_or_counties_has_no_problems():
    assert problems(draft(pilot=None, segment=None, counties=[], source_proposal=None)) == []


def test_every_problem_is_reported_in_rule_order():
    found = problems(
        draft(
            title="  ",
            products=[{"kind": "type", "name": "teapot"}, {"kind": "type", "name": "teapot"}],
            pilot=pilot(ends_on="2026-12-10"),
        )
    )
    assert found == [
        (("title",), "Required."),
        (("products", 1), "Listed twice."),
        (("pilot", "ends_on"), "Pilot must end before the campaign starts."),
    ]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"title": " \n"}, (("title",), "Required.")),
        ({"strategy": ""}, (("strategy",), "Required.")),
        ({"slogan": "x" * 101}, (("slogan",), "At most 100 characters.")),
        ({"products": []}, (("products",), "Add at least one product.")),
        (
            {"products": [{"kind": "type", "name": "teapot"}, {"kind": "type", "name": "mugs"}]},
            (("products", 1), "mugs is not in the catalog."),
        ),
        (
            # A product's name is not a type, even when it is in the catalog as a product.
            {"products": [{"kind": "type", "name": "tea cup"}]},
            (("products", 0), "tea cup is not in the catalog."),
        ),
        (
            {
                "products": [
                    {"kind": "product", "name": "tea cup"},
                    {"kind": "type", "name": "cups"},
                    {"kind": "product", "name": "tea cup"},
                ]
            },
            (("products", 2), "Listed twice."),
        ),
        ({"segment": "Lost"}, (("segment",), "Lost is not a segment.")),
        ({"counties": ["台北市", "火星"]}, (("counties", 1), "火星 is not a county.")),
        ({"counties": ["台北市", "台北市"]}, (("counties", 1), "Listed twice.")),
        (
            {"starts_on": "2026-11-06", "pilot": None},
            (("starts_on",), "Must be today or later."),
        ),
        ({"ends_on": "2026-12-09"}, (("ends_on",), "Must be on or after the start date.")),
        (
            {"pilot": pilot(starts_on="2026-11-06")},
            (("pilot", "starts_on"), "Must be today or later."),
        ),
        (
            {"pilot": pilot(ends_on="2026-11-30")},
            (("pilot", "ends_on"), "Must be on or after the start date."),
        ),
        (
            {"pilot": pilot(ends_on="2026-12-12")},
            (("pilot", "ends_on"), "Pilot must end before the campaign starts."),
        ),
    ],
    ids=[
        "1-title",
        "2-strategy",
        "2-slogan-too-long",
        "3-no-products",
        "4-unknown-type",
        "4-product-as-type",
        "5-listed-twice",
        "6-segment",
        "7-county",
        "8-county-twice",
        "9-starts-in-the-past",
        "10-ends-before-start",
        "11-pilot-starts-in-the-past",
        "12-pilot-ends-before-start",
        "13-pilot-overlaps",
    ],
)
def test_each_rule(changes: dict, expected: tuple):
    assert problems(draft(**changes)) == [expected]


def test_today_is_a_valid_start():
    assert problems(draft(starts_on="2026-11-07", ends_on="2026-11-07", pilot=None)) == []


def test_the_proposal_is_not_checked():
    # It records what the AI proposed, not what will run: a type off the catalog is fine there.
    proposal = {**draft().source_proposal.model_dump(), "items": ["nothing we sell"]}
    assert problems(draft(source_proposal=proposal)) == []


@pytest.mark.parametrize(
    ("given", "expected"),
    [("  Tea for two  ", "Tea for two"), ("   ", None), ("", None), (None, None)],
)
def test_slogan_is_stripped_and_empty_is_none(given, expected):
    assert draft(slogan=given).slogan == expected


def test_a_slogan_of_100_characters_is_fine():
    assert problems(draft(slogan="x" * 100)) == []


# A campaign from 2026-12-10 to 2026-12-24, with a pilot from 2026-12-01 to 2026-12-07.
STARTS_ON, ENDS_ON = date(2026, 12, 10), date(2026, 12, 24)
HOLD = Pilot(
    audience_percent=10,
    starts_on=date(2026, 12, 1),
    ends_on=date(2026, 12, 7),
    discount_percent=10,
    auto_start=False,
)
AUTO = HOLD.model_copy(update={"auto_start": True})
AT = datetime(2026, 12, 2, 9, 0, tzinfo=UTC)


def status(today: str, *, stored="launched", pilot=HOLD, approved=None, ended=None, cancelled=None):
    return status_of(
        stored=stored,
        starts_on=STARTS_ON,
        ends_on=ENDS_ON,
        pilot=pilot,
        approved_at=approved,
        ended_at=ended,
        cancelled_at=cancelled,
        today=date.fromisoformat(today),
    )


@pytest.mark.parametrize(
    ("today", "facts", "expected"),
    [
        ("2026-11-08", {"stored": "draft"}, "draft"),
        ("2027-01-01", {"stored": "draft"}, "draft"),
        ("2026-12-03", {"cancelled": AT}, "cancelled"),
        ("2026-12-03", {"cancelled": AT, "ended": AT}, "cancelled"),
        ("2026-12-03", {"ended": AT}, "ended"),
        ("2026-12-25", {"pilot": None}, "ended"),
        ("2026-12-25", {}, "ended"),
        ("2026-11-30", {}, "scheduled"),
        ("2026-12-01", {}, "piloting"),
        ("2026-12-07", {}, "piloting"),
        ("2026-12-08", {}, "awaiting_approval"),
        ("2026-12-24", {}, "awaiting_approval"),
        ("2026-12-08", {"approved": AT}, "scheduled"),
        ("2026-12-10", {"approved": AT}, "running"),
        ("2026-12-08", {"pilot": AUTO}, "scheduled"),
        ("2026-12-12", {"pilot": AUTO}, "running"),
        ("2026-12-09", {"pilot": None}, "scheduled"),
        ("2026-12-10", {"pilot": None}, "running"),
        ("2026-12-24", {"pilot": None}, "running"),
    ],
    ids=[
        "draft",
        "draft-with-past-dates",
        "cancelled",
        "cancelled-wins-over-ended",
        "ended-early",
        "no-pilot-past-end",
        "hold-never-approved-past-end",
        "pilot-not-started",
        "pilot-first-day",
        "pilot-last-day",
        "hold-awaiting-approval",
        "hold-awaiting-on-last-campaign-day",
        "hold-approved-before-start",
        "hold-approved-running",
        "auto-start-before-start",
        "auto-start-running",
        "no-pilot-before-start",
        "no-pilot-first-day",
        "no-pilot-last-day",
    ],
)
def test_status_of(today: str, facts: dict, expected: str):
    assert status(today, **facts) == expected


def test_actions_follow_the_status_table():
    assert {
        "launch": {"draft"},
        "approve": {"awaiting_approval"},
        "end": {"piloting", "running"},
        "cancel": {"scheduled", "piloting", "awaiting_approval", "running"},
    } == ACTIONS
    allowed = set().union(*ACTIONS.values())
    assert "ended" not in allowed
    assert "cancelled" not in allowed


@pytest.mark.parametrize(
    ("action", "ends_on", "expected"),
    [
        ("launch", "2026-11-07", "The end date has passed."),
        ("launch", "2026-11-08", None),
        ("launch", "2026-12-24", None),
        ("cancel", "2026-11-07", None),
    ],
)
def test_action_problem(action: str, ends_on: str, expected):
    today = date(2026, 11, 8)
    assert action_problem(action, "draft", date.fromisoformat(ends_on), today) == expected


def test_store_today_is_a_date():
    assert isinstance(store_today(), date)
