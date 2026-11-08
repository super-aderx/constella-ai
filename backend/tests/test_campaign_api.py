"""The campaign endpoints: options, product search, saving, listing, editing, deleting and
actions, checked without a database or a model."""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import campaigns
from app.campaigns import CampaignDraft, SavedCampaign
from app.infra import data, store
from app.main import app

client = TestClient(app)

CATALOG = {"teapot": ["blue teapot"], "cups": ["tea cup"]}
SEGMENTS = ["Champions", "Loyal"]
COUNTIES = ["台北市", "新北市"]
TODAY = date.today()
SOON = TODAY + timedelta(days=30)
CAMPAIGN_ID = "6f1e2d3c-4b5a-4968-8776-655443322110"


def body(**changes) -> dict:
    """A sound draft as the app sends it, with some of it changed."""
    clean = {
        "client_token": "0b7e3c1a-5d2f-4e8b-9a6c-1f2e3d4c5b6a",
        "source_proposal": {
            "name": "Tea time bundle",
            "basis": "proven",
            "items": ["teapot", "cups"],
            "discount_percent": 15,
            "audience": None,
            "reason": "Teapots and cups sell together.",
            # A writer.Pitch carries its slogans too: they are not part of the proposal.
            "slogans": ["Tea for two"],
        },
        "title": "Tea time bundle",
        "strategy": "Teapots and cups sell together.",
        "products": [{"kind": "type", "name": "teapot"}, {"kind": "product", "name": "tea cup"}],
        "discount_percent": 15,
        "starts_on": SOON.isoformat(),
        "ends_on": (SOON + timedelta(days=14)).isoformat(),
        "segment": None,
        "counties": ["台北市"],
        "pilot": {
            "audience_percent": 10,
            "starts_on": (SOON - timedelta(days=9)).isoformat(),
            "ends_on": (SOON - timedelta(days=3)).isoformat(),
            "discount_percent": 10,
            "auto_start": False,
        },
        "slogan": "Tea for two",
    }
    return {**clean, **changes}


def saved_for(draft: CampaignDraft, status: str = "draft", **facts) -> SavedCampaign:
    lifecycle = {"launched_at": None, "approved_at": None, "ended_at": None, "cancelled_at": None}
    return SavedCampaign(
        id=UUID(CAMPAIGN_ID),
        status=status,
        created_at=datetime(2026, 11, 7, 9, 30, tzinfo=UTC),
        **{**lifecycle, **facts},
        **draft.model_dump(exclude={"client_token"}),
    )


LAUNCHED_AT = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)


@pytest.fixture
def saves(monkeypatch: pytest.MonkeyPatch) -> list:
    """Stands in for the database, and records every call to the store."""
    calls = []
    monkeypatch.setattr(data, "load_catalog", lambda: CATALOG)
    monkeypatch.setattr(campaigns, "store_today", lambda: TODAY)

    def load_network(*args):
        raise AssertionError("the whole network was built for its segment names")

    monkeypatch.setattr(data, "load_network", load_network)
    monkeypatch.setattr(store, "load_segments", lambda: SEGMENTS)
    monkeypatch.setattr(store, "campaign_by_token", lambda token, today: None)

    def load_counties():
        calls.append("load_counties")
        return COUNTIES

    def save_campaign(draft, today):
        calls.append(draft)
        calls.append(("today", today))
        return saved_for(draft), True

    monkeypatch.setattr(store, "load_counties", load_counties)
    monkeypatch.setattr(store, "save_campaign", save_campaign)
    return calls


def test_options_list_segments_and_counties(saves: list):
    response = client.get("/api/campaign-options")
    assert response.status_code == 200
    assert response.json() == {"segments": SEGMENTS, "counties": COUNTIES}


def test_search_finds_a_type(saves: list):
    response = client.get("/api/products/search", params={"q": "teapto"})
    assert response.status_code == 200
    assert response.json()[0] == {"kind": "type", "name": "teapot", "type": "teapot"}


def test_search_with_no_query_finds_nothing(saves: list):
    assert client.get("/api/products/search").json() == []


@pytest.mark.parametrize("limit", [0, 51])
def test_search_limit_is_checked(limit: int, saves: list):
    response = client.get("/api/products/search", params={"q": "tea", "limit": limit})
    assert response.status_code == 422


def test_a_new_campaign_is_created(saves: list):
    response = client.post("/api/campaigns", json=body())
    assert response.status_code == 201
    sent = CampaignDraft.model_validate(body())
    assert response.json() == saved_for(sent).model_dump(mode="json")
    assert response.json()["status"] == "draft"
    assert response.json()["slogan"] == "Tea for two"
    assert response.json()["source_proposal"] == {
        k: v for k, v in body()["source_proposal"].items() if k != "slogans"
    }
    assert saves[-2:] == [sent, ("today", TODAY)]


def test_a_repeated_token_returns_the_saved_campaign(saves: list, monkeypatch):
    first = CampaignDraft.model_validate(body())
    monkeypatch.setattr(store, "save_campaign", lambda draft, today: (saved_for(first), False))
    response = client.post("/api/campaigns", json=body(title="Changed since"))
    assert response.status_code == 200
    assert response.json() == saved_for(first).model_dump(mode="json")


def test_a_retry_after_the_start_date_returns_the_saved_campaign(saves: list, monkeypatch):
    # Saved yesterday to start yesterday, and the response was lost: the identical retry must get
    # the stored campaign back, not a "Must be today or later." the rules would now give.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    sent = body(starts_on=yesterday, ends_on=yesterday, pilot=None)
    stored = saved_for(CampaignDraft.model_validate(sent))
    tokens = []

    def campaign_by_token(token, today):
        tokens.append(str(token))
        return stored

    monkeypatch.setattr(store, "campaign_by_token", campaign_by_token)
    response = client.post("/api/campaigns", json=sent)
    assert response.status_code == 200
    assert response.json() == stored.model_dump(mode="json")
    assert tokens == [sent["client_token"]]
    assert saves == []


@pytest.mark.parametrize(
    "changes",
    [
        {"discount_percent": 12.5},
        {"discount_percent": 0},
        {"discount_percent": 101},
        {"discount_percent": "15"},
        {"pilot": {**body()["pilot"], "audience_percent": 100}},
        {"source_proposal": {**body()["source_proposal"], "basis": "maybe"}},
        {"client_token": "not-a-uuid"},
        {"starts_on": "next week"},
    ],
    ids=[
        "discount-12.5",
        "discount-0",
        "discount-101",
        "discount-string",
        "pilot-100",
        "basis-maybe",
        "bad-uuid",
        "bad-date",
    ],
)
def test_a_body_out_of_range_is_rejected_before_the_store(changes: dict, saves: list):
    response = client.post("/api/campaigns", json=body(**changes))
    assert response.status_code == 422
    assert saves == []


def test_rule_problems_come_back_as_field_errors(saves: list, monkeypatch):
    found = [(("title",), "Required."), (("pilot", "ends_on"), "Pilot must end before...")]
    monkeypatch.setattr(campaigns, "draft_problems", lambda *args: found)
    response = client.post("/api/campaigns", json=body())
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {"loc": ["body", "title"], "msg": "Required.", "type": "campaign_rule"},
            {
                "loc": ["body", "pilot", "ends_on"],
                "msg": "Pilot must end before...",
                "type": "campaign_rule",
            },
        ]
    }
    assert not any(isinstance(call, CampaignDraft) for call in saves)


def test_a_broken_rule_is_reported_by_the_real_check(saves: list):
    pilot = {**body()["pilot"], "ends_on": SOON.isoformat()}
    response = client.post("/api/campaigns", json=body(title="  ", pilot=pilot))
    assert response.status_code == 422
    assert response.json()["detail"] == [
        {"loc": ["body", "title"], "msg": "Required.", "type": "campaign_rule"},
        {
            "loc": ["body", "pilot", "ends_on"],
            "msg": "Pilot must end before the campaign starts.",
            "type": "campaign_rule",
        },
    ]


def fail(*args):
    raise psycopg.OperationalError("connection refused")


@pytest.mark.parametrize(
    "failing", ["campaign_by_token", "load_segments", "load_counties", "save_campaign"]
)
def test_a_database_failure_is_a_500(failing: str, saves: list, monkeypatch, caplog):
    monkeypatch.setattr(store, failing, fail)
    with caplog.at_level(logging.ERROR):
        response = client.post("/api/campaigns", json=body())
    assert response.status_code == 500
    assert response.json() == {"detail": "Could not save the campaign."}
    assert any(r.exc_info and r.exc_info[0] is psycopg.OperationalError for r in caplog.records)


ACTION_URL = f"/api/campaigns/{CAMPAIGN_ID}/actions"


@pytest.mark.parametrize(
    ("failing", "method", "url", "sent", "detail"),
    [
        ("list_campaigns", "GET", "/api/campaigns", None, "Could not read the campaigns."),
        (
            "update_draft",
            "PUT",
            f"/api/campaigns/{CAMPAIGN_ID}",
            body(),
            "Could not save the campaign.",
        ),
        (
            "delete_draft",
            "DELETE",
            f"/api/campaigns/{CAMPAIGN_ID}",
            None,
            "Could not delete the campaign.",
        ),
        (
            "apply_action",
            "POST",
            ACTION_URL,
            {"action": "launch", "expected": "draft"},
            "Could not change the campaign.",
        ),
    ],
    ids=["list", "put", "delete", "action"],
)
def test_a_database_failure_on_the_other_endpoints_is_a_500(
    failing, method, url, sent, detail, saves: list, monkeypatch, caplog
):
    monkeypatch.setattr(store, failing, fail)
    with caplog.at_level(logging.ERROR):
        response = client.request(method, url, json=sent)
    assert response.status_code == 500
    assert response.json() == {"detail": detail}
    assert any(r.exc_info and r.exc_info[0] is psycopg.OperationalError for r in caplog.records)


def test_campaigns_are_listed_newest_first(saves: list, monkeypatch):
    newer = saved_for(CampaignDraft.model_validate(body(title="Newer")))
    older = saved_for(
        CampaignDraft.model_validate(body(title="Older")), "scheduled", launched_at=LAUNCHED_AT
    )
    asked = []

    def list_campaigns(today):
        asked.append(today)
        return [newer, older]

    monkeypatch.setattr(store, "list_campaigns", list_campaigns)
    response = client.get("/api/campaigns")
    assert response.status_code == 200
    assert response.json() == [newer.model_dump(mode="json"), older.model_dump(mode="json")]
    assert asked == [TODAY]


def test_a_draft_is_updated(saves: list, monkeypatch):
    sent = body(discount_percent=20, slogan="  New slogan ", pilot=None)
    edited = CampaignDraft.model_validate(sent)
    got = []

    def update_draft(campaign_id, draft, today):
        got.append((str(campaign_id), draft, today))
        return saved_for(draft)

    monkeypatch.setattr(store, "update_draft", update_draft)
    response = client.put(f"/api/campaigns/{CAMPAIGN_ID}", json=sent)
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["discount_percent"] == 20
    assert response.json()["slogan"] == "New slogan"
    assert response.json()["pilot"] is None
    assert got == [(CAMPAIGN_ID, edited, TODAY)]


def changed(campaign: SavedCampaign):
    def raise_changed(*args):
        raise store.Changed(campaign)

    return raise_changed


@pytest.mark.parametrize(
    ("method", "replaced", "sent"),
    [("PUT", "update_draft", body()), ("DELETE", "delete_draft", None)],
    ids=["put", "delete"],
)
def test_a_launched_campaign_cannot_be_edited_or_deleted(
    method, replaced, sent, saves: list, monkeypatch
):
    current = saved_for(CampaignDraft.model_validate(body()), "scheduled", launched_at=LAUNCHED_AT)
    monkeypatch.setattr(store, replaced, changed(current))
    response = client.request(method, f"/api/campaigns/{CAMPAIGN_ID}", json=sent)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "This campaign changed. Status is now Scheduled.",
        "campaign": current.model_dump(mode="json"),
    }


def test_a_draft_is_deleted(saves: list, monkeypatch):
    got = []

    def delete_draft(campaign_id, today):
        got.append((str(campaign_id), today))
        return True

    monkeypatch.setattr(store, "delete_draft", delete_draft)
    response = client.delete(f"/api/campaigns/{CAMPAIGN_ID}")
    assert response.status_code == 204
    assert response.content == b""
    assert got == [(CAMPAIGN_ID, TODAY)]


@pytest.mark.parametrize(
    ("method", "url", "sent"),
    [
        ("PUT", f"/api/campaigns/{CAMPAIGN_ID}", body()),
        ("DELETE", f"/api/campaigns/{CAMPAIGN_ID}", None),
        ("POST", ACTION_URL, {"action": "approve", "expected": "awaiting_approval"}),
    ],
    ids=["put", "delete", "action"],
)
def test_an_unknown_campaign_is_a_404(method, url, sent, saves: list, monkeypatch):
    monkeypatch.setattr(store, "update_draft", lambda *args: None)
    monkeypatch.setattr(store, "delete_draft", lambda *args: False)
    monkeypatch.setattr(store, "apply_action", lambda *args: None)
    response = client.request(method, url, json=sent)
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found."}


def test_an_edit_that_breaks_a_rule_is_rejected(saves: list, monkeypatch):
    monkeypatch.setattr(store, "update_draft", lambda *args: pytest.fail("the store was called"))
    response = client.put(f"/api/campaigns/{CAMPAIGN_ID}", json=body(slogan="x" * 101))
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {"loc": ["body", "slogan"], "msg": "At most 100 characters.", "type": "campaign_rule"}
        ]
    }


@pytest.mark.parametrize(
    ("action", "expected", "status", "facts"),
    [
        ("launch", "draft", "scheduled", {"launched_at": LAUNCHED_AT}),
        ("launch", "draft", "running", {"launched_at": LAUNCHED_AT}),
        ("approve", "awaiting_approval", "running", {"approved_at": LAUNCHED_AT}),
        ("end", "running", "ended", {"ended_at": LAUNCHED_AT}),
        ("cancel", "scheduled", "cancelled", {"cancelled_at": LAUNCHED_AT}),
    ],
    ids=["launch-scheduled", "launch-running", "approve", "end", "cancel"],
)
def test_an_action_returns_the_campaign(action, expected, status, facts, saves, monkeypatch):
    after = saved_for(CampaignDraft.model_validate(body()), status, **facts)
    got = []

    def apply_action(campaign_id, *args):
        got.append((str(campaign_id), *args))
        return after

    monkeypatch.setattr(store, "apply_action", apply_action)
    response = client.post(ACTION_URL, json={"action": action, "expected": expected})
    assert response.status_code == 200
    assert response.json() == after.model_dump(mode="json")
    assert got == [(CAMPAIGN_ID, action, expected, TODAY)]


def test_a_launch_past_its_end_date_is_refused(saves: list, monkeypatch):
    def refuse(*args):
        raise store.Refused("The end date has passed.")

    monkeypatch.setattr(store, "apply_action", refuse)
    response = client.post(ACTION_URL, json={"action": "launch", "expected": "draft"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {"loc": ["body", "action"], "msg": "The end date has passed.", "type": "campaign_rule"}
        ]
    }


@pytest.mark.parametrize(
    ("action", "expected", "status", "label"),
    [
        ("approve", "awaiting_approval", "cancelled", "Cancelled"),
        ("end", "scheduled", "scheduled", "Scheduled"),
        ("approve", "awaiting_approval", "awaiting_approval", "Awaiting approval"),
    ],
    ids=["stale-expected", "not-allowed", "label-with-space"],
)
def test_a_stale_or_disallowed_action_is_a_409(action, expected, status, label, saves, monkeypatch):
    current = saved_for(CampaignDraft.model_validate(body()), status, launched_at=LAUNCHED_AT)
    monkeypatch.setattr(store, "apply_action", changed(current))
    response = client.post(ACTION_URL, json={"action": action, "expected": expected})
    assert response.status_code == 409
    assert response.json() == {
        "detail": f"This campaign changed. Status is now {label}.",
        "campaign": current.model_dump(mode="json"),
    }


@pytest.mark.parametrize(
    "sent",
    [
        {"action": "pause", "expected": "running"},
        {"action": "end", "expected": "paused"},
        {"action": "end"},
    ],
    ids=["unknown-action", "unknown-status", "no-expected"],
)
def test_a_bad_action_body_is_rejected(sent: dict, saves: list, monkeypatch):
    monkeypatch.setattr(store, "apply_action", lambda *args: pytest.fail("the store was called"))
    response = client.post(ACTION_URL, json=sent)
    assert response.status_code == 422
