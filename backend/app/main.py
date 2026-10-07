"""The API: the network for the graph, and the agent's answers for the chat."""

from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from app import agent, data

app = FastAPI(title="Constella AI")


class Question(BaseModel):
    question: str
    # The graph's filters, so the answer is about what the user is looking at. Leave one out for
    # no filter: 0 days or an empty segment would filter the data while reading as "all of it".
    days: int | None = Field(None, gt=0)
    segment: str | None = Field(None, min_length=1)


@app.get("/api/network")
def network(
    days: Annotated[int | None, Query(gt=0)] = None,
    segment: Annotated[str | None, Query(min_length=1)] = None,
) -> dict:
    return data.load_network(days, segment)


@app.post("/api/ask")
async def ask(body: Question) -> agent.Answer:
    return await agent.ask(body.question, body.days, body.segment)
