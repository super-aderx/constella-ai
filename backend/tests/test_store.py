"""How a campaign maps to rows and back, checked without a database or a model."""

from contextlib import nullcontext
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from psycopg.types.json import Jsonb

from app.campaigns import CampaignDraft
from app.infra import store
from app.infra.store import campaign_params, pilot_params, saved_from_joined, saved_from_rows

CAMPAIGN_ID = UUID("6f1e2d3c-4b5a-4968-8776-655443322110")
CREATED_AT = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)
LAUNCHED_AT = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)
# Before the pilot (2026-12-01 to 2026-12-07) and the campaign (2026-12-10 to 2026-12-24).
TODAY = date(2026, 11, 8)
PROPOSAL = {
    "name": "Tea time bundle",
    "basis": "proven",
    "items": ["teapot", "cups"],
    "discount_percent": 15,
    "audience": None,
    "reason": "Teapots and cups sell together.",
}


def draft(**changes) -> CampaignDraft:
    clean = {
        "client_token": "0b7e3c1a-5d2f-4e8b-9a6c-1f2e3d4c5b6a",
        "source_proposal": PROPOSAL,
        "title": "Tea time bundle",
        "strategy": "Teapots and cups sell together.",
        "products": [
            {"kind": "type", "name": "teapot"},
            {"kind": "type", "name": "cups"},
            {"kind": "product", "name": "blue tea cup"},
        ],
        "discount_percent": 15,
        "starts_on": "2026-12-10",
        "ends_on": "2026-12-24",
        "segment": None,
        "counties": ["台北市"],
        "pilot": {
            "audience_percent": 10,
            "starts_on": "2026-12-01",
            "ends_on": "2026-12-07",
            "discount_percent": 10,
            "auto_start": False,
        },
        "slogan": "Tea for two",
    }
    return CampaignDraft.model_validate({**clean, **changes})


def stored(params: dict, **facts) -> dict:
    """The row the database would return for these insert params, with some lifecycle facts."""
    proposal = params["source_proposal"]
    return {
        **params,
        "source_proposal": proposal.obj if proposal is not None else None,
        "status": "draft",
        "created_at": CREATED_AT,
        "launched_at": None,
        "approved_at": None,
        "ended_at": None,
        "cancelled_at": None,
        **facts,
    }


def test_a_campaign_maps_to_rows_and_back():
    d = draft()
    params = campaign_params(d, CAMPAIGN_ID)
    assert params["id"] == CAMPAIGN_ID
    assert params["client_token"] == d.client_token
    assert params["item_types"] == ["teapot", "cups"]
    assert params["products"] == ["blue tea cup"]
    assert params["counties"] == ["台北市"]
    assert params["segment"] is None
    assert params["slogan"] == "Tea for two"
    assert isinstance(params["source_proposal"], Jsonb)
    assert params["source_proposal"].obj == PROPOSAL

    pilot = pilot_params(d.pilot, CAMPAIGN_ID)
    assert pilot == {"campaign_id": CAMPAIGN_ID, **d.pilot.model_dump()}

    saved = saved_from_rows(stored(params), pilot, TODAY)
    assert saved.id == CAMPAIGN_ID
    assert saved.status == "draft"
    assert saved.created_at == CREATED_AT
    assert saved.slogan == "Tea for two"
    assert saved.products == d.products
    assert saved.pilot == d.pilot
    assert saved.source_proposal == d.source_proposal
    lifecycle = {"launched_at", "approved_at", "ended_at", "cancelled_at"}
    assert all(getattr(saved, f) is None for f in lifecycle)
    assert saved.model_dump(exclude={"id", "status", "created_at", *lifecycle}) == d.model_dump(
        exclude={"client_token"}
    )


@pytest.mark.parametrize(
    ("facts", "today", "expected"),
    [
        ({}, date(2026, 12, 25), "draft"),
        ({"status": "launched", "launched_at": LAUNCHED_AT}, TODAY, "scheduled"),
        ({"status": "launched", "launched_at": LAUNCHED_AT}, date(2026, 12, 3), "piloting"),
        ({"status": "launched", "cancelled_at": LAUNCHED_AT}, TODAY, "cancelled"),
    ],
)
def test_status_is_worked_out_from_the_facts_not_read(facts: dict, today: date, expected: str):
    d = draft()
    row = stored(campaign_params(d, CAMPAIGN_ID), **facts)
    saved = saved_from_rows(row, pilot_params(d.pilot, CAMPAIGN_ID), today)
    assert saved.status == expected
    for f in ("launched_at", "cancelled_at"):
        assert getattr(saved, f) == facts.get(f)


def test_types_come_back_first_whatever_the_input_order():
    d = draft(
        products=[{"kind": "product", "name": "blue tea cup"}, {"kind": "type", "name": "teapot"}]
    )
    saved = saved_from_rows(stored(campaign_params(d, CAMPAIGN_ID)), None, TODAY)
    assert [p.name for p in saved.products] == ["teapot", "blue tea cup"]


def test_no_pilot_and_no_proposal_map_to_none():
    d = draft(pilot=None, source_proposal=None)
    params = campaign_params(d, CAMPAIGN_ID)
    assert params["source_proposal"] is None
    assert pilot_params(d.pilot, CAMPAIGN_ID) is None

    saved = saved_from_rows(stored(params), None, TODAY)
    assert saved.pilot is None
    assert saved.source_proposal is None


def joined(params: dict, pilot: dict | None, **facts) -> dict:
    """The row campaign_by_token.sql returns: the campaign, and its pilot's columns as pilot_*."""
    fields = ["campaign_id", "audience_percent", "starts_on", "ends_on", "discount_percent"]
    pilot_columns = {f"pilot_{f}": (pilot or {}).get(f) for f in [*fields, "auto_start"]}
    return {**stored(params, **facts), **pilot_columns}


def test_a_campaign_read_back_by_token_keeps_its_pilot():
    d = draft()
    row = joined(campaign_params(d, CAMPAIGN_ID), pilot_params(d.pilot, CAMPAIGN_ID))
    saved = saved_from_joined(row, TODAY)
    assert saved.pilot == d.pilot
    assert saved.products == d.products


def test_a_campaign_read_back_by_token_without_a_pilot_has_none():
    d = draft(pilot=None)
    assert saved_from_joined(joined(campaign_params(d, CAMPAIGN_ID), None), TODAY).pilot is None


class FakeDatabase:
    """Stands in for the writable connection: each named statement returns its canned rows, and
    every statement run is recorded in order."""

    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows
        self.ran: list[tuple[str, dict]] = []

    def transaction(self):
        return nullcontext()

    def run(self, conn, name: str, params: dict) -> list[dict]:
        self.ran.append((name, params))
        return self.rows.get(name, [])

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.ran]


def database(monkeypatch: pytest.MonkeyPatch, rows: dict[str, list[dict]]) -> FakeDatabase:
    db = FakeDatabase(rows)
    monkeypatch.setattr(store, "_writable", lambda: nullcontext(db))
    monkeypatch.setattr(store, "_run", db.run)
    return db


def locked(d: CampaignDraft, **facts) -> list[dict]:
    """What campaign_for_update.sql returns for this draft, stored with these facts."""
    return [joined(campaign_params(d, CAMPAIGN_ID), pilot_params(d.pilot, CAMPAIGN_ID), **facts)]


LAUNCHED = {"status": "launched", "launched_at": LAUNCHED_AT}


def test_update_draft_replaces_the_campaign_and_its_pilot(monkeypatch):
    before = draft()
    after = draft(
        discount_percent=20,
        slogan="New",
        pilot={**before.pilot.model_dump(), "discount_percent": 5},
    )
    row = stored(campaign_params(after, CAMPAIGN_ID))
    pilot = pilot_params(after.pilot, CAMPAIGN_ID)
    db = database(
        monkeypatch,
        {"campaign_for_update": locked(before), "update_campaign": [row], "upsert_pilot": [pilot]},
    )
    saved = store.update_draft(CAMPAIGN_ID, after, TODAY)
    assert db.names == ["campaign_for_update", "update_campaign", "upsert_pilot"]
    assert db.ran[0][1] == {"id": CAMPAIGN_ID}
    assert db.ran[1][1]["discount_percent"] == 20
    assert db.ran[1][1]["slogan"] == "New"
    assert saved.status == "draft"
    assert saved.discount_percent == 20
    assert saved.pilot == after.pilot


def test_update_draft_adds_a_pilot(monkeypatch):
    after = draft()
    db = database(
        monkeypatch,
        {
            "campaign_for_update": locked(draft(pilot=None)),
            "update_campaign": [stored(campaign_params(after, CAMPAIGN_ID))],
            "upsert_pilot": [pilot_params(after.pilot, CAMPAIGN_ID)],
        },
    )
    assert store.update_draft(CAMPAIGN_ID, after, TODAY).pilot == after.pilot
    assert db.names[-1] == "upsert_pilot"


def test_update_draft_removes_the_pilot(monkeypatch):
    after = draft(pilot=None)
    db = database(
        monkeypatch,
        {
            "campaign_for_update": locked(draft()),
            "update_campaign": [stored(campaign_params(after, CAMPAIGN_ID))],
            "delete_pilot": [{"campaign_id": CAMPAIGN_ID}],
        },
    )
    assert store.update_draft(CAMPAIGN_ID, after, TODAY).pilot is None
    assert db.names == ["campaign_for_update", "update_campaign", "delete_pilot"]
    assert db.ran[-1][1] == {"campaign_id": CAMPAIGN_ID}


def test_update_draft_without_a_pilot_before_or_after_deletes_none(monkeypatch):
    after = draft(pilot=None)
    db = database(
        monkeypatch,
        {
            "campaign_for_update": locked(draft(pilot=None)),
            "update_campaign": [stored(campaign_params(after, CAMPAIGN_ID))],
        },
    )
    assert store.update_draft(CAMPAIGN_ID, after, TODAY).pilot is None
    assert db.names == ["campaign_for_update", "update_campaign"]


def test_update_or_delete_of_a_missing_campaign_writes_nothing(monkeypatch):
    db = database(monkeypatch, {})
    assert store.update_draft(CAMPAIGN_ID, draft(), TODAY) is None
    assert store.delete_draft(CAMPAIGN_ID, TODAY) is False
    assert store.apply_action(CAMPAIGN_ID, "launch", "draft", TODAY) is None
    assert db.names == ["campaign_for_update"] * 3


def test_a_launched_campaign_is_not_updated_or_deleted(monkeypatch):
    db = database(monkeypatch, {"campaign_for_update": locked(draft(), **LAUNCHED)})
    with pytest.raises(store.Changed) as raised:
        store.update_draft(CAMPAIGN_ID, draft(), TODAY)
    assert raised.value.campaign.status == "scheduled"
    with pytest.raises(store.Changed):
        store.delete_draft(CAMPAIGN_ID, TODAY)
    assert db.names == ["campaign_for_update"] * 2


def test_delete_draft_deletes_it(monkeypatch):
    db = database(
        monkeypatch,
        {"campaign_for_update": locked(draft()), "delete_campaign": [{"id": CAMPAIGN_ID}]},
    )
    assert store.delete_draft(CAMPAIGN_ID, TODAY) is True
    assert db.names == ["campaign_for_update", "delete_campaign"]
    assert db.ran[-1][1] == {"id": CAMPAIGN_ID}


def test_launch_writes_the_action_and_returns_the_status_its_dates_call_for(monkeypatch):
    d = draft()
    db = database(
        monkeypatch,
        {
            "campaign_for_update": locked(d),
            "campaign_action": [stored(campaign_params(d, CAMPAIGN_ID), **LAUNCHED)],
        },
    )
    saved = store.apply_action(CAMPAIGN_ID, "launch", "draft", TODAY)
    assert db.names == ["campaign_for_update", "campaign_action"]
    assert db.ran[-1][1] == {"id": CAMPAIGN_ID, "action": "launch"}
    assert saved.status == "scheduled"
    assert saved.launched_at == LAUNCHED_AT
    assert saved.pilot == d.pilot


@pytest.mark.parametrize(
    ("action", "expected", "facts", "today", "after", "status"),
    [
        ("approve", "awaiting_approval", {}, date(2026, 12, 12), "approved_at", "running"),
        ("end", "running", {"approved_at": LAUNCHED_AT}, date(2026, 12, 12), "ended_at", "ended"),
        ("cancel", "scheduled", {}, TODAY, "cancelled_at", "cancelled"),
    ],
)
def test_each_action_stamps_its_fact(monkeypatch, action, expected, facts, today, after, status):
    d = draft()
    params = campaign_params(d, CAMPAIGN_ID)
    db = database(
        monkeypatch,
        {
            "campaign_for_update": locked(d, **LAUNCHED, **facts),
            "campaign_action": [stored(params, **LAUNCHED, **facts, **{after: LAUNCHED_AT})],
        },
    )
    saved = store.apply_action(CAMPAIGN_ID, action, expected, today)
    assert db.ran[-1] == ("campaign_action", {"id": CAMPAIGN_ID, "action": action})
    assert saved.status == status


@pytest.mark.parametrize(
    ("action", "expected"),
    [("approve", "awaiting_approval"), ("end", "scheduled"), ("launch", "scheduled")],
    ids=["stale-expected", "not-allowed", "launch-launched"],
)
def test_a_stale_or_disallowed_action_raises_changed_and_writes_nothing(
    monkeypatch, action, expected
):
    # Scheduled today: the pilot hasn't started.
    db = database(monkeypatch, {"campaign_for_update": locked(draft(), **LAUNCHED)})
    with pytest.raises(store.Changed) as raised:
        store.apply_action(CAMPAIGN_ID, action, expected, TODAY)
    assert raised.value.campaign.status == "scheduled"
    assert db.names == ["campaign_for_update"]


def test_a_launch_past_its_end_date_is_refused_and_writes_nothing(monkeypatch):
    db = database(monkeypatch, {"campaign_for_update": locked(draft())})
    with pytest.raises(store.Refused) as raised:
        store.apply_action(CAMPAIGN_ID, "launch", "draft", date(2026, 12, 25))
    assert raised.value.message == "The end date has passed."
    assert db.names == ["campaign_for_update"]


def test_campaigns_are_listed_in_the_order_read(monkeypatch):
    first, second = draft(title="Newer"), draft(title="Older", pilot=None)
    rows = [
        joined(campaign_params(first, CAMPAIGN_ID), pilot_params(first.pilot, CAMPAIGN_ID)),
        joined(campaign_params(second, UUID(int=1)), None, **LAUNCHED),
    ]
    asked = []

    def query(name, params=None):
        asked.append(name)
        return rows

    monkeypatch.setattr(store.data, "query", query)
    listed = store.list_campaigns(TODAY)
    assert asked == ["list_campaigns"]
    assert [c.title for c in listed] == ["Newer", "Older"]
    assert [c.status for c in listed] == ["draft", "scheduled"]
