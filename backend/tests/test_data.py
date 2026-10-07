"""build_network, checked without a database."""

import pytest

from app import data
from app.data import build_network

ITEMS = [
    {"name": name, "orders": orders, "revenue": revenue}
    for name, orders, revenue in [
        ("A", 900, 9000.0),
        ("B", 900, 8000.0),
        ("C", 20, 300.0),
        ("D", 20, 200.0),
        ("E", 3, 50000.0),  # few orders, no pair, the most revenue
    ]
]
# A + B: two best sellers in 800 of 1,000 baskets, still a little less than chance predicts.
PAIRS = [{"a": "A", "b": "B", "co_orders": 800}, {"a": "C", "b": "D", "co_orders": 10}]


def items(*names: str, orders: int = 100) -> list[dict]:
    return [{"name": name, "orders": orders, "revenue": 0.0} for name in names]


def pair(a: str, b: str, co_orders: int) -> dict:
    return {"a": a, "b": b, "co_orders": co_orders}


def test_lift_is_co_orders_over_what_chance_predicts():
    network = build_network(ITEMS, PAIRS, baskets=1000)
    lift = {(p["a"], p["b"]): p["lift"] for p in network["pairs"]}
    # 800 * 1000 / (900 * 900) and 10 * 1000 / (20 * 20)
    assert lift == {("A", "B"): 0.988, ("C", "D"): 25.0}


def test_keeps_the_most_frequent_pair_below_chance():
    network = build_network(ITEMS, PAIRS, baskets=1000)
    top = max(network["pairs"], key=lambda p: p["coOrders"])
    assert (top["a"], top["b"], top["coOrders"]) == ("A", "B", 800)
    assert top["lift"] < 1


def test_keeps_every_item_and_groups_only_pairs_above_chance():
    network = build_network(ITEMS, PAIRS, baskets=1000)
    community = {i["name"]: i["community"] for i in network["items"]}
    assert community == {"A": None, "B": None, "C": 0, "D": 0, "E": None}
    assert network["communities"] == ["C & D"]
    assert max(network["items"], key=lambda i: i["revenue"])["name"] == "E"


def test_pairs_come_strongest_first():
    pairs = [pair("A", "B", 20), pair("A", "C", 60), pair("B", "C", 40)]
    network = build_network(items("A", "B", "C"), pairs, baskets=1000)
    assert [p["lift"] for p in network["pairs"]] == [6.0, 4.0, 2.0]


def test_the_cap_keeps_the_leaders_of_both_rankings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(data, "MAX_PAIRS", 1)
    rows = [
        {"name": "A", "orders": 900, "revenue": 0.0},
        {"name": "B", "orders": 900, "revenue": 0.0},
        *items("C", "D", "E", "F", orders=20),
    ]
    # The most frequent, the highest lift, and one that leads neither ranking.
    pairs = [pair("A", "B", 800), pair("C", "D", 10), pair("E", "F", 5)]
    network = build_network(rows, pairs, baskets=1000)
    assert [(p["a"], p["b"]) for p in network["pairs"]] == [("C", "D"), ("A", "B")]


def test_a_pair_at_chance_is_not_grouped():
    network = build_network(items("A", "B"), [pair("A", "B", 10)], baskets=1000)
    assert network["pairs"][0]["lift"] == 1.0
    assert network["communities"] == []


def test_communities_are_largest_first_and_named_after_their_best_sellers():
    rows = [
        {"name": name, "orders": orders, "revenue": 0.0}
        for name, orders in [("A", 100), ("B", 300), ("C", 200), ("X", 50), ("Y", 60)]
    ]
    pairs = [pair("A", "B", 90), pair("B", "C", 90), pair("A", "C", 90), pair("X", "Y", 40)]
    network = build_network(rows, pairs, baskets=1000)
    assert network["communities"] == ["B & C", "Y & X"]
    assert {i["name"]: i["community"] for i in network["items"]} == {
        "A": 0,
        "B": 0,
        "C": 0,
        "X": 1,
        "Y": 1,
    }


def test_a_bridge_sits_between_two_others():
    # A - B - C: only B is on a shortest path between two others.
    pairs = [pair("A", "B", 50), pair("B", "C", 50)]
    network = build_network(items("A", "B", "C"), pairs, baskets=1000)
    assert {i["name"] for i in network["items"] if i["bridge"]} == {"B"}


def test_the_same_input_gives_the_same_network():
    assert build_network(ITEMS, PAIRS, baskets=1000) == build_network(ITEMS, PAIRS, baskets=1000)
