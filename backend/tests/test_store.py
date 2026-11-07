"""How a campaign maps to rows and back, checked without a database or a model."""

from datetime import UTC, datetime
from uuid import UUID

from psycopg.types.json import Jsonb

from app.campaigns import CampaignDraft
from app.infra.store import campaign_params, pilot_params, saved_from_joined, saved_from_rows

CAMPAIGN_ID = UUID("6f1e2d3c-4b5a-4968-8776-655443322110")
CREATED_AT = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)
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
    }
    return CampaignDraft.model_validate({**clean, **changes})


def stored(params: dict) -> dict:
    """The row the database would return for these insert params."""
    proposal = params["source_proposal"]
    return {
        **params,
        "source_proposal": proposal.obj if proposal is not None else None,
        "status": "scheduled",
        "created_at": CREATED_AT,
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
    assert isinstance(params["source_proposal"], Jsonb)
    assert params["source_proposal"].obj == PROPOSAL

    pilot = pilot_params(d.pilot, CAMPAIGN_ID)
    assert pilot == {"campaign_id": CAMPAIGN_ID, **d.pilot.model_dump()}

    saved = saved_from_rows(stored(params), pilot)
    assert saved.id == CAMPAIGN_ID
    assert saved.status == "scheduled"
    assert saved.created_at == CREATED_AT
    assert saved.products == d.products
    assert saved.pilot == d.pilot
    assert saved.source_proposal == d.source_proposal
    assert saved.model_dump(exclude={"id", "status", "created_at"}) == d.model_dump(
        exclude={"client_token"}
    )


def test_types_come_back_first_whatever_the_input_order():
    d = draft(
        products=[{"kind": "product", "name": "blue tea cup"}, {"kind": "type", "name": "teapot"}]
    )
    saved = saved_from_rows(stored(campaign_params(d, CAMPAIGN_ID)), None)
    assert [p.name for p in saved.products] == ["teapot", "blue tea cup"]


def test_no_pilot_and_no_proposal_map_to_none():
    d = draft(pilot=None, source_proposal=None)
    params = campaign_params(d, CAMPAIGN_ID)
    assert params["source_proposal"] is None
    assert pilot_params(d.pilot, CAMPAIGN_ID) is None

    saved = saved_from_rows(stored(params), None)
    assert saved.pilot is None
    assert saved.source_proposal is None


def joined(params: dict, pilot: dict | None) -> dict:
    """The row campaign_by_token.sql returns: the campaign, and its pilot's columns as pilot_*."""
    fields = ["campaign_id", "audience_percent", "starts_on", "ends_on", "discount_percent"]
    pilot_columns = {f"pilot_{f}": (pilot or {}).get(f) for f in [*fields, "auto_start"]}
    return {**stored(params), **pilot_columns}


def test_a_campaign_read_back_by_token_keeps_its_pilot():
    d = draft()
    row = joined(campaign_params(d, CAMPAIGN_ID), pilot_params(d.pilot, CAMPAIGN_ID))
    saved = saved_from_joined(row)
    assert saved.pilot == d.pilot
    assert saved.products == d.products


def test_a_campaign_read_back_by_token_without_a_pilot_has_none():
    d = draft(pilot=None)
    assert saved_from_joined(joined(campaign_params(d, CAMPAIGN_ID), None)).pilot is None
