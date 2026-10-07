"""The API's filters, checked without a database or a model."""

import pytest
from fastapi.testclient import TestClient

from app import agent, data
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def seen(monkeypatch: pytest.MonkeyPatch) -> list:
    """Stands in for the database and the agent, and records the filters they were given."""
    calls = []

    def load_network(days=None, segment=None):
        calls.append((days, segment))
        return {"items": [], "pairs": [], "communities": [], "segments": []}

    async def ask(question, days, segment):
        calls.append((days, segment))
        return agent.Answer(text="ok", items=[], pairs=[])

    monkeypatch.setattr(data, "load_network", load_network)
    monkeypatch.setattr(agent, "ask", ask)
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
