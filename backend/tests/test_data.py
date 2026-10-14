"""build_network, checked without a database."""

import pytest

from app.infra import data
from app.infra.data import build_network

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


@pytest.mark.parametrize(
    ("baskets", "expected"),
    [
        (11431, 30),  # all the data: the threshold as written
        (5549, 15),  # about half the baskets, half the threshold
        (389, 5),  # 1 by share, held at the floor
        (0, 5),
    ],
)
def test_the_threshold_keeps_its_share_of_the_baskets(baskets: int, expected: int):
    assert data.min_co_orders(baskets, all_baskets=11431) == expected


def test_the_threshold_with_no_data_is_the_floor():
    assert data.min_co_orders(0, all_baskets=0) == 5


def test_items_are_those_in_a_pair_and_the_revenue_leaders(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(data, "MAX_REVENUE_ITEMS", 1)
    rows = [
        {"name": "A", "orders": 900, "revenue": 100.0},
        {"name": "B", "orders": 800, "revenue": 90.0},
        {"name": "C", "orders": 700, "revenue": 80.0},  # no pair, not a leader: left out
        {"name": "D", "orders": 3, "revenue": 5000.0},  # no pair, the revenue leader
    ]
    kept = data.select_items(rows, [pair("A", "B", 40)])
    assert [i["name"] for i in kept] == ["A", "B", "D"]


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
