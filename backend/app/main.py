"""The API: the network for the graph, the agent's answers for the chat, and the campaigns the
store team saves from them."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import campaigns, products
from app.infra import data, progress, store
from app.roles.conversation import Turn
from app.versions import v1, v2, v3

app = FastAPI(title="Constella AI")

MAX_TURNS = 10  # earlier turns a question may carry


class Question(BaseModel):
    question: str
    # The graph's filters, so the answer is about what the user is looking at. Leave one out for
    # no filter: 0 days or an empty segment would filter the data while reading as "all of it".
    days: int | None = Field(None, gt=0)
    segment: str | None = Field(None, min_length=1)
    # Product types the user has set aside: the graph still shows them and facts about them are
    # still answered, but no campaign is built on one.
    ignored: list[str] = Field(default_factory=list)
    # The conversation before the question, oldest first, so a follow-up can be read. The app
    # sends its last few turns; the cap keeps a run's input, and its cost, bounded.
    history: list[Turn] = Field(default_factory=list, max_length=MAX_TURNS)


@app.get("/api/network")
def network(
    days: Annotated[int | None, Query(gt=0)] = None,
    segment: Annotated[str | None, Query(min_length=1)] = None,
) -> dict:
    return data.load_network(days, segment)


def chosen():
    """The agent AGENT_VERSION picks: 1 is prompt only, 2 is one agent with tools, and the
    default, 3, is the roles (router, analyst, strategist, writer, scientist, reviewer)."""
    versions = {"1": v1, "2": v2}
    return versions.get(os.environ.get("AGENT_VERSION", "3"), v3)


@app.post("/api/ask")
async def ask(body: Question) -> v3.Answer | v2.Answer | v1.Answer:
    return await chosen().ask(body.question, body.days, body.segment, body.ignored, body.history)


@app.post("/api/ask/stream")
async def ask_stream(body: Question) -> StreamingResponse:
    """The same answer as /api/ask, sent as lines of JSON so the app can show the run as it
    goes: a {"step": ...} line as each step starts, then one {"answer": ...} or {"error": ...}.
    """
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[dict] = asyncio.Queue()

    def send(event: dict) -> None:
        # Tools run in worker threads, so a step can be reported from one.
        loop.call_soon_threadsafe(events.put_nowait, event)

    async def run() -> None:
        progress.listen(send)
        try:
            answer = await chosen().ask(
                body.question, body.days, body.segment, body.ignored, body.history
            )
            send({"answer": answer.model_dump()})
        except Exception:
            # The stream has already answered 200, so a failure is a line of its own.
            logging.exception("The agent failed on %r", body.question)
            send({"error": "The agent could not answer. Try again."})

    async def lines() -> AsyncIterator[str]:
        task = asyncio.create_task(run())
        try:
            while True:
                event = await events.get()
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if "step" not in event:
                    break
        finally:
            task.cancel()  # the reader left: stop paying for a run nobody will see

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@app.get("/api/campaign-options")
def campaign_options() -> dict:
    """What the campaign wizard's segment and county fields offer."""
    return {"segments": store.load_segments(), "counties": store.load_counties()}


@app.get("/api/products/search")
def product_search(
    q: str = "", limit: Annotated[int, Query(ge=1, le=50)] = 20
) -> list[products.ProductHit]:
    return products.search_products(q, limit)


SAVE_FAILED = {"detail": "Could not save the campaign."}
NOT_FOUND = {"detail": "Campaign not found."}


def problems_of(draft: campaigns.CampaignDraft, today: date) -> list[campaigns.Problem]:
    """Every rule the draft breaks, checked against the catalog, segments and counties as they
    are. Raises when those can't be read."""
    catalog = data.load_catalog()
    return campaigns.draft_problems(
        draft, catalog, store.load_segments(), store.load_counties(), today
    )


def rule_errors(problems: list[campaigns.Problem]) -> JSONResponse:
    """Broken campaign rules as a 422 in FastAPI's own shape, so the app marks its fields the same
    way as for a malformed body."""
    detail = [{"loc": ["body", *loc], "msg": msg, "type": "campaign_rule"} for loc, msg in problems]
    return JSONResponse(status_code=422, content={"detail": detail})


def changed(error: store.Changed) -> JSONResponse:
    """A 409 carrying the campaign as it stands, so the app can show it without asking again."""
    campaign = error.campaign
    label = campaigns.STATUS_LABELS[campaign.status]
    return JSONResponse(
        status_code=409,
        content={
            "detail": f"This campaign changed. Status is now {label}.",
            "campaign": campaign.model_dump(mode="json"),
        },
    )


@app.post("/api/campaigns", response_model=campaigns.SavedCampaign)
def save_campaign(draft: campaigns.CampaignDraft, response: Response):
    """Checks a campaign against every rule and stores it: 201 when this call stored it, 200
    with the stored one when its client_token was saved before. A broken rule is a 422 in
    FastAPI's own shape, so the app marks its fields the same way as a malformed body.

    A saved token is answered before the rules run, so a retry gets the stored campaign even
    when a rule would now fail it, such as a start date that was today when it was saved.
    """
    today = campaigns.store_today()
    try:
        stored = store.campaign_by_token(draft.client_token, today)
        if stored is not None:
            return stored
        problems = problems_of(draft, today)
    except Exception:
        logging.exception("Could not read what a campaign is checked against")
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    if problems:
        return rule_errors(problems)
    try:
        saved, created = store.save_campaign(draft, today)
    except Exception:
        logging.exception("Could not save the campaign %s", draft.client_token)
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    if created:
        response.status_code = 201
    return saved


@app.get("/api/campaigns", response_model=list[campaigns.SavedCampaign])
def list_campaigns():
    """Every campaign, newest first, each with the status it shows today."""
    try:
        return store.list_campaigns(campaigns.store_today())
    except Exception:
        logging.exception("Could not read the campaigns")
        return JSONResponse(status_code=500, content={"detail": "Could not read the campaigns."})


@app.put("/api/campaigns/{campaign_id}", response_model=campaigns.SavedCampaign)
def update_campaign(campaign_id: UUID, draft: campaigns.CampaignDraft):
    """Replaces a draft with the wizard's edit (its client_token is ignored): 404 when there is
    none, 409 once it has been launched. The rules are checked first, as for a new campaign."""
    today = campaigns.store_today()
    try:
        problems = problems_of(draft, today)
    except Exception:
        logging.exception("Could not read what a campaign is checked against")
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    if problems:
        return rule_errors(problems)
    try:
        saved = store.update_draft(campaign_id, draft, today)
    except store.Changed as error:
        return changed(error)
    except Exception:
        logging.exception("Could not save the campaign %s", campaign_id)
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    if saved is None:
        return JSONResponse(status_code=404, content=NOT_FOUND)
    return saved


@app.delete("/api/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: UUID):
    """Deletes a draft: 404 when there is none, 409 once it has been launched."""
    try:
        deleted = store.delete_draft(campaign_id, campaigns.store_today())
    except store.Changed as error:
        return changed(error)
    except Exception:
        logging.exception("Could not delete the campaign %s", campaign_id)
        return JSONResponse(status_code=500, content={"detail": "Could not delete the campaign."})
    if not deleted:
        return JSONResponse(status_code=404, content=NOT_FOUND)
    return Response(status_code=204)


class ActionRequest(BaseModel):
    action: campaigns.CampaignAction
    # The status the user saw when they chose the action. If it has moved on since, they chose
    # on a stale view, and the action is refused rather than applied to something else (D7).
    expected: campaigns.CampaignStatus


@app.post("/api/campaigns/{campaign_id}/actions", response_model=campaigns.SavedCampaign)
def campaign_action(campaign_id: UUID, body: ActionRequest):
    """Launches, approves, ends or cancels a campaign: 404 when there is none, 409 with the
    campaign as it stands when it is no longer in the expected status or the action isn't allowed
    from it, and 422 when a rule refuses it (a launch past its end date)."""
    try:
        saved = store.apply_action(campaign_id, body.action, body.expected, campaigns.store_today())
    except store.Changed as error:
        return changed(error)
    except store.Refused as refused:
        return rule_errors([(("action",), refused.message)])
    except Exception:
        logging.exception("Could not %s the campaign %s", body.action, campaign_id)
        return JSONResponse(status_code=500, content={"detail": "Could not change the campaign."})
    if saved is None:
        return JSONResponse(status_code=404, content=NOT_FOUND)
    return saved
