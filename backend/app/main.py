"""The API: the network for the graph, and the agent's answers for the chat."""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.infra import data, progress
from app.versions import v1, v2, v3

app = FastAPI(title="Constella AI")


class Question(BaseModel):
    question: str
    # The graph's filters, so the answer is about what the user is looking at. Leave one out for
    # no filter: 0 days or an empty segment would filter the data while reading as "all of it".
    days: int | None = Field(None, gt=0)
    segment: str | None = Field(None, min_length=1)
    # Product types the user has set aside: the graph still shows them and facts about them are
    # still answered, but no campaign is built on one.
    ignored: list[str] = Field(default_factory=list)


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
    return await chosen().ask(body.question, body.days, body.segment, body.ignored)


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
            answer = await chosen().ask(body.question, body.days, body.segment, body.ignored)
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
