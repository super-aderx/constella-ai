"""The API's filters and its stream, checked without a database or a model."""

import json

import pytest
from fastapi.testclient import TestClient

from app.infra import data, progress
from app.main import MAX_TURNS, app
from app.versions import v1 as agent
from app.versions import v2 as agent_v2
from app.versions import v3 as agent_v3

client = TestClient(app)


@pytest.fixture(autouse=True)
def seen(monkeypatch: pytest.MonkeyPatch) -> list:
    """Stands in for the database and the agent, and records the filters they were given."""
    calls = []

    def load_network(days=None, segment=None):
        calls.append((days, segment))
        return {"items": [], "pairs": [], "communities": [], "segments": []}

    async def ask(question, days, segment, ignored=(), history=()):
        calls.append((days, segment, *ignored))
        return agent.Answer(text="ok", items=[], pairs=[])

    monkeypatch.setattr(data, "load_network", load_network)
    monkeypatch.setattr(agent, "ask", ask)
    monkeypatch.setattr(agent_v2, "ask", ask)
    monkeypatch.setattr(agent_v3, "ask", ask)
    return calls


@pytest.mark.parametrize("params", [{"days": 0}, {"days": -5}, {"segment": ""}])
def test_network_rejects_a_filter_that_would_read_as_none(params: dict, seen: list):
    assert client.get("/api/network", params=params).status_code == 422
    assert seen == []


@pytest.mark.parametrize("filters", [{"days": 0}, {"days": -5}, {"segment": ""}])
def test_ask_rejects_a_filter_that_would_read_as_none(filters: dict, seen: list):
    assert client.post("/api/ask", json={"question": "x", **filters}).status_code == 422
    assert seen == []


def test_network_passes_its_filters_on(seen: list):
    assert (
        client.get("/api/network", params={"days": 90, "segment": "Champions"}).status_code == 200
    )
    assert client.get("/api/network").status_code == 200
    assert seen == [(90, "Champions"), (None, None)]


def test_ask_passes_its_filters_on(seen: list):
    body = {"question": "x", "days": 90, "segment": "Champions"}
    assert client.post("/api/ask", json=body).json() == {"text": "ok", "items": [], "pairs": []}
    assert client.post("/api/ask", json={"question": "x"}).status_code == 200
    assert seen == [(90, "Champions"), (None, None)]


def lines(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines()]


def test_the_stream_sends_each_step_then_the_answer(monkeypatch: pytest.MonkeyPatch):
    async def ask(question, days, segment, ignored=(), history=()):
        progress.step("router")
        progress.step("tool", id="L1", tool="top_items", args={"limit": 5})
        return agent.Answer(text="ok", items=[], pairs=[])

    monkeypatch.setattr(agent_v3, "ask", ask)
    response = client.post("/api/ask/stream", json={"question": "x"})
    assert lines(response) == [
        {"step": "router"},
        {"step": "tool", "id": "L1", "tool": "top_items", "args": {"limit": 5}},
        {"answer": {"text": "ok", "items": [], "pairs": []}},
    ]


def test_the_stream_ends_with_an_error_when_the_agent_fails(monkeypatch: pytest.MonkeyPatch):
    async def ask(question, days, segment, ignored=(), history=()):
        progress.step("router")
        raise RuntimeError("no model")

    monkeypatch.setattr(agent_v3, "ask", ask)
    response = client.post("/api/ask/stream", json={"question": "x"})
    assert [list(line) for line in lines(response)] == [["step"], ["error"]]


def test_the_stream_rejects_a_filter_that_would_read_as_none(seen: list):
    assert client.post("/api/ask/stream", json={"question": "x", "days": 0}).status_code == 422
    assert seen == []


@pytest.mark.parametrize("path", ["/api/ask", "/api/ask/stream"])
def test_ask_passes_on_the_types_set_aside(path: str, seen: list):
    assert client.post(path, json={"question": "x", "ignored": ["啤酒"]}).status_code == 200
    assert seen == [(None, None, "啤酒")]


@pytest.mark.parametrize("path", ["/api/ask", "/api/ask/stream"])
def test_ask_passes_on_the_conversation_so_far(path: str, monkeypatch: pytest.MonkeyPatch):
    given = []

    async def ask(question, days, segment, ignored=(), history=()):
        given.append(history)
        return agent.Answer(text="ok", items=[], pairs=[])

    monkeypatch.setattr(agent_v3, "ask", ask)
    earlier = [{"question": "忠誠客戶買吐司時還買什麼？", "answer": "最常一起買的是鮮乳。"}]
    body = {"question": "那新客戶呢？", "history": earlier}
    assert client.post(path, json=body).status_code == 200
    assert client.post(path, json={"question": "x"}).status_code == 200
    assert [[turn.model_dump() for turn in history] for history in given] == [earlier, []]


def test_ask_rejects_a_conversation_past_the_cap(seen: list):
    history = [{"question": "q", "answer": "a"}] * (MAX_TURNS + 1)
    assert client.post("/api/ask", json={"question": "x", "history": history}).status_code == 422
    assert seen == []
