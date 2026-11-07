"""The API: the network for the graph, the agent's answers for the chat, and the campaigns the
store team saves from them."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

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


@app.post("/api/campaigns", response_model=campaigns.SavedCampaign)
def save_campaign(draft: campaigns.CampaignDraft, response: Response):
    """Checks a campaign against every rule and stores it: 201 when this call stored it, 200
    with the stored one when its client_token was saved before. A broken rule is a 422 in
    FastAPI's own shape, so the app marks its fields the same way as a malformed body.

    A saved token is answered before the rules run, so a retry gets the stored campaign even
    when a rule would now fail it, such as a start date that was today when it was saved.
    """
    try:
        stored = store.campaign_by_token(draft.client_token)
        if stored is not None:
            return stored
        catalog = data.load_catalog()
        segments = store.load_segments()
        counties = store.load_counties()
    except Exception:
        logging.exception("Could not read what a campaign is checked against")
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    problems = campaigns.draft_problems(draft, catalog, segments, counties, date.today())
    if problems:
        detail = [
            {"loc": ["body", *loc], "msg": msg, "type": "campaign_rule"} for loc, msg in problems
        ]
        return JSONResponse(status_code=422, content={"detail": detail})
    try:
        saved, created = store.save_campaign(draft)
    except Exception:
        logging.exception("Could not save the campaign %s", draft.client_token)
        return JSONResponse(status_code=500, content=SAVE_FAILED)
    if created:
        response.status_code = 201
    return saved
