"""Writes the campaigns the store team saves. The only module that writes to the database.

data.py reads the invoices over a read-only connection, and stays that way: the network, the
agent's tools and the graph cannot change the data they describe. Saving a campaign needs a
connection that can write, so it lives here, apart, where every write is in one place.
"""

import os
from datetime import date
from functools import lru_cache
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.campaigns import (
    ACTIONS,
    CampaignAction,
    CampaignDraft,
    CampaignStatus,
    Pilot,
    ProductRef,
    Proposal,
    SavedCampaign,
    action_problem,
    status_of,
)
from app.infra import data

PILOT_FIELDS = list(Pilot.model_fields)


class Changed(Exception):
    """The campaign is no longer in the status the change was asked for: someone else acted on it
    first, or the date moved it on. Nothing was written; `campaign` is how it stands now."""

    def __init__(self, campaign: SavedCampaign):
        super().__init__(f"Campaign {campaign.id} is {campaign.status}")
        self.campaign = campaign


class Refused(Exception):
    """The action is allowed from the campaign's status, but a rule refuses it. Nothing was
    written; `message` says why."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _writable() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def _run(conn: psycopg.Connection, name: str, params: dict) -> list[dict]:
    return conn.execute((data.SQL / f"{name}.sql").read_text(), params).fetchall()


def campaign_params(draft: CampaignDraft, campaign_id: UUID) -> dict:
    """The insert parameters for a campaign: its products split by kind, each in input order."""
    proposal = draft.source_proposal
    return {
        "id": campaign_id,
        "client_token": draft.client_token,
        "source_proposal": Jsonb(proposal.model_dump()) if proposal is not None else None,
        "title": draft.title,
        "strategy": draft.strategy,
        "slogan": draft.slogan,
        "item_types": [p.name for p in draft.products if p.kind == "type"],
        "products": [p.name for p in draft.products if p.kind == "product"],
        "discount_percent": draft.discount_percent,
        "starts_on": draft.starts_on,
        "ends_on": draft.ends_on,
        "segment": draft.segment,
        "counties": draft.counties,
    }


def pilot_params(pilot: Pilot | None, campaign_id: UUID) -> dict | None:
    """The insert parameters for a pilot, or None when the campaign has none."""
    if pilot is None:
        return None
    return {"campaign_id": campaign_id, **pilot.model_dump()}


def saved_from_rows(campaign: dict, pilot: dict | None, today: date) -> SavedCampaign:
    """A stored campaign from its row and its pilot's row, with the status it shows today. The
    rows keep types and products in two arrays, so the list comes back as the types, then the
    products."""
    proposal = campaign["source_proposal"]  # psycopg reads JSONB as a dict
    stored_pilot = Pilot(**{f: pilot[f] for f in PILOT_FIELDS}) if pilot is not None else None
    return SavedCampaign(
        id=campaign["id"],
        status=status_of(
            stored=campaign["status"],
            starts_on=campaign["starts_on"],
            ends_on=campaign["ends_on"],
            pilot=stored_pilot,
            approved_at=campaign["approved_at"],
            ended_at=campaign["ended_at"],
            cancelled_at=campaign["cancelled_at"],
            today=today,
        ),
        created_at=campaign["created_at"],
        launched_at=campaign["launched_at"],
        approved_at=campaign["approved_at"],
        ended_at=campaign["ended_at"],
        cancelled_at=campaign["cancelled_at"],
        source_proposal=Proposal.model_validate(proposal) if proposal is not None else None,
        title=campaign["title"],
        strategy=campaign["strategy"],
        slogan=campaign["slogan"],
        products=[ProductRef(kind="type", name=n) for n in campaign["item_types"]]
        + [ProductRef(kind="product", name=n) for n in campaign["products"]],
        discount_percent=campaign["discount_percent"],
        starts_on=campaign["starts_on"],
        ends_on=campaign["ends_on"],
        segment=campaign["segment"],
        counties=campaign["counties"],
        pilot=stored_pilot,
    )


def saved_from_joined(row: dict, today: date) -> SavedCampaign:
    """A stored campaign from a row that joins its pilot (campaign_by_token.sql and the like),
    whose pilot columns are pilot_*."""
    pilot = {f: row[f"pilot_{f}"] for f in PILOT_FIELDS}
    return saved_from_rows(row, pilot if row["pilot_campaign_id"] is not None else None, today)


def campaign_by_token(client_token: UUID, today: date) -> SavedCampaign | None:
    """The campaign saved with this client_token, or None. Read-only.

    A retry is answered from here before any rule runs: a campaign that started today and was
    saved, but whose response was lost, would fail "Must be today or later." after midnight.
    """
    rows = data.query("campaign_by_token", {"client_token": client_token})
    return saved_from_joined(rows[0], today) if rows else None


def save_campaign(draft: CampaignDraft, today: date) -> tuple[SavedCampaign, bool]:
    """Stores a campaign and its pilot, once per client_token: the stored campaign, and whether
    this call created it. A repeated token returns what is stored, unchanged."""
    campaign_id = uuid4()
    with _writable() as conn, conn.transaction():
        # One transaction, so a campaign is never stored without the pilot it was saved with.
        rows = _run(conn, "save_campaign", campaign_params(draft, campaign_id))
        if not rows:
            # Another request with this token committed first (a double click racing itself).
            row = _run(conn, "campaign_by_token", {"client_token": draft.client_token})[0]
            return saved_from_joined(row, today), False
        params = pilot_params(draft.pilot, campaign_id)
        pilot = _run(conn, "save_pilot", params)[0] if params is not None else None
        return saved_from_rows(rows[0], pilot, today), True


def list_campaigns(today: date) -> list[SavedCampaign]:
    """Every campaign, newest first, each with the status it shows today. Read-only."""
    return [saved_from_joined(row, today) for row in data.query("list_campaigns")]


def _locked(conn: psycopg.Connection, campaign_id: UUID, today: date) -> SavedCampaign | None:
    """The campaign as it stands, locked until the transaction ends, or None. Every change is
    decided on what this returns, so two changes to one campaign can't both act on a stale view."""
    rows = _run(conn, "campaign_for_update", {"id": campaign_id})
    return saved_from_joined(rows[0], today) if rows else None


def update_draft(campaign_id: UUID, draft: CampaignDraft, today: date) -> SavedCampaign | None:
    """Replaces a draft's fields and pilot (added, changed or removed) in one transaction: the
    stored campaign, or None when there is none. Raises Changed once it has been launched: what
    runs must be what was launched."""
    with _writable() as conn, conn.transaction():
        current = _locked(conn, campaign_id, today)
        if current is None:
            return None
        if current.status != "draft":
            raise Changed(current)
        row = _run(conn, "update_campaign", campaign_params(draft, campaign_id))[0]
        params = pilot_params(draft.pilot, campaign_id)
        if params is None:
            _run(conn, "delete_pilot", {"campaign_id": campaign_id})
            pilot = None
        else:
            pilot = _run(conn, "upsert_pilot", params)[0]
        return saved_from_rows(row, pilot, today)


def delete_draft(campaign_id: UUID, today: date) -> bool:
    """Deletes a draft and its pilot: False when there is none. Raises Changed once it has been
    launched: a launched campaign is history and stays."""
    with _writable() as conn, conn.transaction():
        current = _locked(conn, campaign_id, today)
        if current is None:
            return False
        if current.status != "draft":
            raise Changed(current)
        _run(conn, "delete_campaign", {"id": campaign_id})
        return True


def apply_action(
    campaign_id: UUID, action: CampaignAction, expected: CampaignStatus, today: date
) -> SavedCampaign | None:
    """Takes an action on a campaign the user saw in the `expected` status: the campaign after
    it, or None when there is none.

    The status is worked out on the locked row, so of two people acting at once the first wins
    and the second gets Changed with how it stands now (D7). Raises Refused, writing nothing,
    when the action is allowed but a rule refuses it.
    """
    with _writable() as conn, conn.transaction():
        current = _locked(conn, campaign_id, today)
        if current is None:
            return None
        if current.status != expected or current.status not in ACTIONS[action]:
            raise Changed(current)
        problem = action_problem(action, current.status, current.ends_on, today)
        if problem is not None:
            raise Refused(problem)
        row = _run(conn, "campaign_action", {"id": campaign_id, "action": action})[0]
        return saved_from_rows(row, pilot_params(current.pilot, campaign_id), today)


@lru_cache
def load_segments() -> list[str]:
    """Every customer segment, read once. The same query the network's segment list comes from,
    without building the whole network for it."""
    return [row["segment"] for row in data.query("segments")]


@lru_cache
def load_counties() -> list[str]:
    """Every county in the invoices, sorted, read once: what a campaign may be limited to."""
    return [row["county"] for row in data.query("counties")]
