"""Campaigns the store team saves, and the rules a campaign must keep before it is stored.

`draft_problems` is the authoritative check: the app's wizard mirrors these rules so the user
sees a problem as they type, but only this one decides what is stored. It is code, not a model,
and it reports every rule broken at once so the wizard can mark every field in one go.

`source_proposal` is a copy of the AI proposal the campaign came from, as the user saw it. It
records what the AI said, not what will run, so no rule checks it.

A campaign's status moves with the date: a launched campaign becomes Piloting on its pilot's first
day without anyone touching it. So the table stores only facts that don't move (draft or launched,
and when it was launched, approved, ended or cancelled), and `status_of` works out the status from
them and today's date every time a campaign is read. No job has to run at midnight to keep a
stored status true.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

# The strategist's campaign is the AI's proposal: name, basis, items, discount_percent,
# audience and reason.
from app.roles.strategist import Campaign as Proposal

Problem = tuple[tuple[str | int, ...], str]

CampaignStatus = Literal[
    "draft", "scheduled", "piloting", "awaiting_approval", "running", "ended", "cancelled"
]
CampaignAction = Literal["launch", "approve", "end", "cancel"]
Stored = Literal["draft", "launched"]  # the only statuses the table keeps

STATUS_LABELS: dict[CampaignStatus, str] = {
    "draft": "Draft",
    "scheduled": "Scheduled",
    "piloting": "Piloting",
    "awaiting_approval": "Awaiting approval",
    "running": "Running",
    "ended": "Ended",
    "cancelled": "Cancelled",
}

# The statuses each action may be taken from. Ended and cancelled are final: nothing leaves them.
ACTIONS: dict[CampaignAction, set[CampaignStatus]] = {
    "launch": {"draft"},
    "approve": {"awaiting_approval"},
    "end": {"piloting", "running"},
    "cancel": {"scheduled", "piloting", "awaiting_approval", "running"},
}

SLOGAN_MAX = 100

# The store's own calendar: "today" for a campaign is the store's day, wherever the server runs.
STORE_ZONE = ZoneInfo("Asia/Taipei")


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
    slogan: str | None = None  # None: no slogan

    @field_validator("slogan")
    @classmethod
    def _no_blank_slogan(cls, slogan: str | None) -> str | None:
        # A blank slogan is no slogan, so it is stored as NULL rather than as spaces.
        slogan = slogan.strip() if slogan is not None else None
        return slogan or None


class SavedCampaign(BaseModel):
    """A stored campaign, as the campaign endpoints return it. `status` is worked out from the
    stored facts and today's date when it is read, never read from the table."""

    id: UUID
    status: CampaignStatus
    created_at: datetime
    launched_at: datetime | None
    approved_at: datetime | None
    ended_at: datetime | None
    cancelled_at: datetime | None
    source_proposal: Proposal | None
    title: str
    strategy: str
    slogan: str | None
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
    if draft.slogan is not None and len(draft.slogan) > SLOGAN_MAX:
        problems.append((("slogan",), f"At most {SLOGAN_MAX} characters."))

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


def store_today() -> date:
    """Today in the store's own time zone: what every date rule and status is measured against."""
    return datetime.now(STORE_ZONE).date()


def status_of(
    *,
    stored: Stored,
    starts_on: date,
    ends_on: date,
    pilot: Pilot | None,
    approved_at: datetime | None,
    ended_at: datetime | None,
    cancelled_at: datetime | None,
    today: date,
) -> CampaignStatus:
    """The status a campaign shows today. Pure: the stored facts and today are passed in.

    A pilot always ends before its campaign starts (draft_problems), so the pilot's branches and
    the campaign's never overlap. A pilot on hold that is never approved waits until the
    campaign's end date passes, and then the campaign is over like any other.
    """
    if stored == "draft":
        return "draft"
    if cancelled_at is not None:
        return "cancelled"
    if ended_at is not None or today > ends_on:
        return "ended"
    if pilot is not None:
        if today < pilot.starts_on:
            return "scheduled"
        if today <= pilot.ends_on:
            return "piloting"
        if not pilot.auto_start and approved_at is None:
            return "awaiting_approval"
    if today < starts_on:
        return "scheduled"
    return "running"


def action_problem(
    action: CampaignAction, status: CampaignStatus, ends_on: date, today: date
) -> str | None:
    """Why an action that its status allows is still refused, or None. Whether the status allows
    it at all is ACTIONS' job: that is a conflict with what the user saw, not a broken rule."""
    if action == "launch" and ends_on < today:
        # It would go straight to Ended: nothing would ever run.
        return "The end date has passed."
    return None
