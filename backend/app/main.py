"""The API: the network for the graph, and the agent's answers for the chat."""

from fastapi import FastAPI
from pydantic import BaseModel

from app import agent, data

app = FastAPI(title="Constella AI")


class Question(BaseModel):
    question: str
    # The graph's filters, so the answer is about what the user is looking at.
    days: int | None = None
    segment: str | None = None


@app.get("/api/network")
def network(days: int | None = None, segment: str | None = None) -> dict:
    return data.load_network(days, segment)


@app.post("/api/ask")
async def ask(body: Question) -> agent.Answer:
    return await agent.ask(body.question, body.days, body.segment)
