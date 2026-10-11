"""Reads the invoice table and builds the network of product types: items, pairs, communities.

An item is a product type (the item_tag column), not a single product. The queries are in app/sql.
They assume a table `invoice` with one row per invoice line and the columns inv_num, item_tag,
item_name, amount, segment (the customer's RFM segment) and datetime.
"""

import os
from functools import lru_cache
from pathlib import Path

import networkx as nx
import psycopg
from psycopg.rows import dict_row

SQL = Path(__file__).parent / "sql"

MIN_CO_ORDERS = 60  # out of all the data: a pair seen in fewer baskets is an outlier
MIN_CO_ORDERS_FLOOR = 5  # and never fewer than this, however little data a filter leaves
MAX_REVENUE_ITEMS = 10  # revenue leaders kept even with no pair: few orders, high revenue
MAX_PRODUCTS = 5  # products listed under each product type
MAX_BRIDGES = 5


@lru_cache
def load_network(days: int | None = None, segment: str | None = None) -> dict:
    """The network for one filter: the last `days` days of the data and one customer segment.

    None means no filter. Each filter is read once and kept: the data does not change while
    the demo runs.
    """
    scope = {"days": days, "segment": segment}
    read_only = "-c default_transaction_read_only=on"
    with psycopg.connect(
        os.environ["DATABASE_URL"], row_factory=dict_row, options=read_only
    ) as conn:

        def query(name: str, params: dict | None = None) -> list[dict]:
            return conn.execute((SQL / f"{name}.sql").read_text(), params).fetchall()

        segments = [row["segment"] for row in query("segments")]
        all_baskets = query("baskets", {"days": None, "segment": None})[0]["baskets"]
        baskets = query("baskets", scope)[0]["baskets"]
        threshold = min_co_orders(baskets, all_baskets)
        items = query("items", scope)
        names = [i["name"] for i in items]
        pairs = query("pairs", {**scope, "names": names, "min_co_orders": threshold})
        items = select_items(items, pairs)
        names = [i["name"] for i in items]
        products = query("products", {**scope, "names": names, "max_products": MAX_PRODUCTS})
    # Each product type carries its best-selling products, for the graph's detail card.
    for item in items:
        item["products"] = [
            {"name": p["name"], "orders": p["orders"], "revenue": p["revenue"]}
            for p in products
            if p["tag"] == item["name"]
        ]
    network = build_network(items, pairs, baskets)
    return {**network, "minCoOrders": threshold, "segments": segments}


def min_co_orders(baskets: int, all_baskets: int) -> int:
    """The baskets a pair must share to count, for a filter that leaves `baskets` baskets.

    MIN_CO_ORDERS is for all the data. A filter keeps the same share of its own baskets, so a
    small period or segment is not left with no pairs at all.
    """
    if not all_baskets:
        return MIN_CO_ORDERS_FLOOR
    return max(MIN_CO_ORDERS_FLOOR, round(MIN_CO_ORDERS * baskets / all_baskets))


def select_items(items: list[dict], pairs: list[dict]) -> list[dict]:
    """The product types of the network: those in a pair, and the revenue leaders."""
    kept = {name for p in pairs for name in (p["a"], p["b"])}
    leaders = sorted(items, key=lambda i: (-i["revenue"], i["name"]))[:MAX_REVENUE_ITEMS]
    kept |= {i["name"] for i in leaders}
    return [i for i in items if i["name"] in kept]


def build_network(items: list[dict], pairs: list[dict], baskets: int) -> dict:
    """Adds lift, communities and bridges. Pure, so it can be checked without a database."""
    orders = {i["name"]: i["orders"] for i in items}
    pairs = [
        {
            "a": p["a"],
            "b": p["b"],
            "coOrders": p["co_orders"],
            "lift": round(p["co_orders"] * baskets / (orders[p["a"]] * orders[p["b"]]), 3),
        }
        for p in pairs
    ]
    # Every pair stays, whatever its lift, strongest first: a pair of best sellers can be the one
    # bought together most often with a lift below 1.
    pairs = sorted(pairs, key=lambda p: (-p["lift"], p["a"], p["b"]))

    # Communities and bridges come from the pairs above chance only: sharing baskets less often
    # than chance predicts is no reason to group two types.
    graph = nx.Graph()
    graph.add_weighted_edges_from((p["a"], p["b"], p["lift"]) for p in pairs if p["lift"] > 1)
    # Louvain with a fixed seed, largest community first.
    groups = sorted(
        nx.community.louvain_communities(graph, seed=42), key=lambda g: (-len(g), min(g))
    )
    community = {name: c for c, group in enumerate(groups) for name in group}
    # Bridges: the types that most often sit on the shortest path between two others.
    between = nx.betweenness_centrality(graph)
    bridges = {
        n for n in sorted(between, key=lambda n: -between[n])[:MAX_BRIDGES] if between[n] > 0
    }

    return {
        # A product type with no pair above chance is in no community.
        "items": [
            {**i, "community": community.get(i["name"]), "bridge": i["name"] in bridges}
            for i in items
        ],
        "pairs": pairs,
        # A community is named after its two best sellers. Ties go by name, so the label is stable.
        "communities": [
            " & ".join(sorted(g, key=lambda name: (-orders[name], name))[:2]) for g in groups
        ],
    }
