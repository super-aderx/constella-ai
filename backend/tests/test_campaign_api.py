"""The campaign endpoints: options, product search and saving, checked without a database or a
model."""

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
SOON = date.today() + timedelta(days=30)


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
    }
    return {**clean, **changes}


def saved_for(draft: CampaignDraft) -> SavedCampaign:
    return SavedCampaign(
        id=UUID("6f1e2d3c-4b5a-4968-8776-655443322110"),
        status="scheduled",
        created_at=datetime(2026, 11, 7, 9, 30, tzinfo=UTC),
        **draft.model_dump(exclude={"client_token"}),
    )


@pytest.fixture
def saves(monkeypatch: pytest.MonkeyPatch) -> list:
    """Stands in for the database, and records every call to the store."""
    calls = []
    monkeypatch.setattr(data, "load_catalog", lambda: CATALOG)

    def load_network(*args):
        raise AssertionError("the whole network was built for its segment names")

    monkeypatch.setattr(data, "load_network", load_network)
    monkeypatch.setattr(store, "load_segments", lambda: SEGMENTS)
    monkeypatch.setattr(store, "campaign_by_token", lambda token: None)

    def load_counties():
        calls.append("load_counties")
        return COUNTIES

    def save_campaign(draft):
        calls.append(draft)
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
    assert response.json()["source_proposal"] == {
        k: v for k, v in body()["source_proposal"].items() if k != "slogans"
    }
    assert saves[-1] == sent


def test_a_repeated_token_returns_the_saved_campaign(saves: list, monkeypatch):
    first = CampaignDraft.model_validate(body())
    monkeypatch.setattr(store, "save_campaign", lambda draft: (saved_for(first), False))
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

    def campaign_by_token(token):
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


@pytest.mark.parametrize(
    "failing", ["campaign_by_token", "load_segments", "load_counties", "save_campaign"]
)
def test_a_database_failure_is_a_500(failing: str, saves: list, monkeypatch, caplog):
    def fail(*args):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(store, failing, fail)
    with caplog.at_level(logging.ERROR):
        response = client.post("/api/campaigns", json=body())
    assert response.status_code == 500
    assert response.json() == {"detail": "Could not save the campaign."}
    assert any(r.exc_info and r.exc_info[0] is psycopg.OperationalError for r in caplog.records)
