"""The agent's side, checked without a database or a model: the brief, and where it is loaded."""

import asyncio
import threading
from types import SimpleNamespace

import pytest

from app.infra.data import build_network
from app.versions import v1 as agent

ITEMS = [
    {"name": name, "orders": orders, "revenue": revenue}
    for name, orders, revenue in [
        ("Bread", 900, 9000.0),
        ("Milk", 900, 8000.0),
        ("Beer", 20, 300.0),
        ("Crisps", 20, 200.0),
        ("Whisky", 3, 50000.0),
    ]
]
PAIRS = [
    {"a": "Bread", "b": "Milk", "co_orders": 800},
    {"a": "Beer", "b": "Crisps", "co_orders": 10},
]
NETWORK = {**build_network(ITEMS, PAIRS, baskets=1000), "minCoOrders": 5}


def test_brief_lists_every_item_and_pair_with_its_figures():
    lines = agent.brief(NETWORK, days=None, segment=None).splitlines()
    assert "Whisky | 3 | $50,000" in lines  # the revenue leader, with no pair
    assert "Bread + Milk | 800 | 0.99x" in lines  # the most frequent pair, below chance
    assert "Beer + Crisps | 10 | 25.00x" in lines


def test_brief_says_how_many_baskets_a_pair_needs():
    assert "## Pairs: every pair found in at least 5 baskets" in agent.brief(NETWORK, None, None)


def test_brief_groups_only_the_types_in_a_community():
    lines = agent.brief(NETWORK, days=None, segment=None).splitlines()
    assert lines[lines.index("## Groups (product types often bought together)") + 1 :] == [
        "Beer & Crisps: Beer, Crisps"
    ]


@pytest.mark.parametrize(
    ("days", "segment", "period", "customers"),
    [
        (None, None, "Period: all of the data", "Customers: all segments"),
        (
            90,
            "Champions",
            "Period: the last 90 days of the data",
            "Customers: the Champions segment only",
        ),
    ],
)
def test_brief_names_its_scope(days, segment, period, customers):
    lines = agent.brief(NETWORK, days, segment).splitlines()
    assert lines[1:3] == [period, customers]


def test_ask_loads_the_network_off_the_event_loop(monkeypatch: pytest.MonkeyPatch):
    loaded_on = []

    def load_network(days, segment):
        loaded_on.append(threading.current_thread())
        return NETWORK

    async def run(_agent, _question):
        return SimpleNamespace(final_output=agent.Answer(text="ok", items=[], pairs=[]))

    monkeypatch.setattr(agent, "load_network", load_network)
    monkeypatch.setattr(agent.Runner, "run", run)

    answer = asyncio.run(agent.ask("Which pair has the highest lift?", days=None, segment=None))

    assert answer.text == "ok"
    assert loaded_on and loaded_on[0] is not threading.current_thread()
