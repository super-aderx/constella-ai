"""Campaigns the store team saves, and the rules a campaign must keep before it is stored.

`draft_problems` is the authoritative check: the app's wizard mirrors these rules so the user
sees a problem as they type, but only this one decides what is stored. It is code, not a model,
and it reports every rule broken at once so the wizard can mark every field in one go.

`source_proposal` is a copy of the AI proposal the campaign came from, as the user saw it. It
records what the AI said, not what will run, so no rule checks it.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# The strategist's campaign is the AI's proposal: name, basis, items, discount_percent,
# audience and reason.
from app.roles.strategist import Campaign as Proposal

Problem = tuple[tuple[str | int, ...], str]


class ProductRef(BaseModel):
    kind: Literal["type", "product"]
    name: str


class Pilot(BaseModel):
    audience_percent: int = Field(ge=1, le=99, strict=True)
    starts_on: date
    ends_on: date
    discount_percent: int = Field(ge=1, le=100, strict=True)
    auto_start: bool


class CampaignDraft(BaseModel):
    # Made once per wizard opening, so a double click or a retry saves the campaign once.
    client_token: UUID
    source_proposal: Proposal | None = None
    title: str = Field(max_length=200)
    strategy: str = Field(max_length=4000)
    products: list[ProductRef]
    discount_percent: int = Field(ge=1, le=100, strict=True)
    starts_on: date
    ends_on: date
    segment: str | None = None  # None: all customers
    counties: list[str] = []  # empty: every county
    pilot: Pilot | None = None


class SavedCampaign(BaseModel):
    """A stored campaign, as POST /api/campaigns returns it."""

    id: UUID
    status: Literal["scheduled"]
    created_at: datetime
    source_proposal: Proposal | None
    title: str
    strategy: str
    products: list[ProductRef]  # types first, then products, each in stored order
    discount_percent: int
    starts_on: date
    ends_on: date
    segment: str | None
    counties: list[str]
    pilot: Pilot | None


def repeats(names: list) -> list[int]:
    """The positions of the names that are equal to an earlier one."""
    seen = set()
    found = []
    for i, name in enumerate(names):
        if name in seen:
            found.append(i)
        seen.add(name)
    return found


def draft_problems(
    draft: CampaignDraft,
    catalog: dict[str, list[str]],
    segments: list[str],
    counties: list[str],
    today: date,
) -> list[Problem]:
    """Every rule the draft breaks, in rule order, as (field location, message); empty when it
    can be stored. Pure: the catalog, segments, counties and today are passed in."""
    problems: list[Problem] = []
    if not draft.title.strip():
        problems.append((("title",), "Required."))
    if not draft.strategy.strip():
        problems.append((("strategy",), "Required."))

    products = draft.products
    if not products:
        problems.append((("products",), "Add at least one product."))
    # A type and a product are looked up in their own lists: the same name may be both.
    known = {"type": set(catalog), "product": {p for names in catalog.values() for p in names}}
    for i, product in enumerate(products):
        if product.name not in known[product.kind]:
            problems.append((("products", i), f"{product.name} is not in the catalog."))
    for i in repeats([(p.kind, p.name) for p in products]):
        problems.append((("products", i), "Listed twice."))

    if draft.segment is not None and draft.segment not in segments:
        problems.append((("segment",), f"{draft.segment} is not a segment."))
    for i, county in enumerate(draft.counties):
        if county not in counties:
            problems.append((("counties", i), f"{county} is not a county."))
    for i in repeats(draft.counties):
        problems.append((("counties", i), "Listed twice."))

    if draft.starts_on < today:
        problems.append((("starts_on",), "Must be today or later."))
    if draft.ends_on < draft.starts_on:
        problems.append((("ends_on",), "Must be on or after the start date."))

    pilot = draft.pilot
    if pilot is not None:
        if pilot.starts_on < today:
            problems.append((("pilot", "starts_on"), "Must be today or later."))
        if pilot.ends_on < pilot.starts_on:
            problems.append((("pilot", "ends_on"), "Must be on or after the start date."))
        # The pilot's result decides whether the campaign runs, so it must be over first.
        if pilot.ends_on >= draft.starts_on:
            problems.append((("pilot", "ends_on"), "Pilot must end before the campaign starts."))
    return problems
