"""Writes the campaigns the store team saves. The only module that writes to the database.

data.py reads the invoices over a read-only connection, and stays that way: the network, the
agent's tools and the graph cannot change the data they describe. Saving a campaign needs a
connection that can write, so it lives here, apart, where every write is in one place.
"""

import os
from functools import lru_cache
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.campaigns import CampaignDraft, Pilot, ProductRef, Proposal, SavedCampaign
from app.infra import data

PILOT_FIELDS = list(Pilot.model_fields)


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


def saved_from_rows(campaign: dict, pilot: dict | None) -> SavedCampaign:
    """A stored campaign from its row and its pilot's row. The rows keep types and products in
    two arrays, so the list comes back as the types, then the products."""
    proposal = campaign["source_proposal"]  # psycopg reads JSONB as a dict
    return SavedCampaign(
        id=campaign["id"],
        status=campaign["status"],
        created_at=campaign["created_at"],
        source_proposal=Proposal.model_validate(proposal) if proposal is not None else None,
        title=campaign["title"],
        strategy=campaign["strategy"],
        products=[ProductRef(kind="type", name=n) for n in campaign["item_types"]]
        + [ProductRef(kind="product", name=n) for n in campaign["products"]],
        discount_percent=campaign["discount_percent"],
        starts_on=campaign["starts_on"],
        ends_on=campaign["ends_on"],
        segment=campaign["segment"],
        counties=campaign["counties"],
        pilot=Pilot(**{f: pilot[f] for f in PILOT_FIELDS}) if pilot is not None else None,
    )


def save_campaign(draft: CampaignDraft) -> tuple[SavedCampaign, bool]:
    """Stores a campaign and its pilot, once per client_token: the stored campaign, and whether
    this call created it. A repeated token returns what is stored, unchanged."""
    campaign_id = uuid4()
    with _writable() as conn, conn.transaction():
        # One transaction, so a campaign is never stored without the pilot it was saved with.
        rows = _run(conn, "save_campaign", campaign_params(draft, campaign_id))
        if not rows:
            row = _run(conn, "campaign_by_token", {"client_token": draft.client_token})[0]
            pilot = {f: row[f"pilot_{f}"] for f in PILOT_FIELDS}
            has_pilot = row["pilot_campaign_id"] is not None
            return saved_from_rows(row, pilot if has_pilot else None), False
        params = pilot_params(draft.pilot, campaign_id)
        pilot = _run(conn, "save_pilot", params)[0] if params is not None else None
        return saved_from_rows(rows[0], pilot), True


@lru_cache
def load_counties() -> list[str]:
    """Every county in the invoices, sorted, read once: what a campaign may be limited to."""
    return [row["county"] for row in data.query("counties")]
