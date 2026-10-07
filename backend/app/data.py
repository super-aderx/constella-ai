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

MAX_ITEMS = 30  # best-selling types kept, so the graph and the brief stay readable
MAX_REVENUE_ITEMS = 10  # revenue leaders kept as well: few orders can still mean high revenue
MIN_CO_ORDERS = 5  # pairs seen in fewer baskets are noise
MAX_PAIRS = 150  # kept from each ranking: by lift, and by baskets with both
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
        baskets = query("baskets", scope)[0]["baskets"]
        limits = {"max_items": MAX_ITEMS, "max_revenue_items": MAX_REVENUE_ITEMS}
        items = query("items", {**scope, **limits})
        names = [i["name"] for i in items]
        pairs = query("pairs", {**scope, "names": names, "min_co_orders": MIN_CO_ORDERS})
        products = query("products", {**scope, "names": names, "max_products": MAX_PRODUCTS})
    # Each product type carries its best-selling products, for the graph's detail card.
    for item in items:
        item["products"] = [
            {"name": p["name"], "orders": p["orders"], "revenue": p["revenue"]}
            for p in products
            if p["tag"] == item["name"]
        ]
    return {**build_network(items, pairs, baskets), "segments": segments}


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
    # Two rankings, so neither question about pairs is answered from a cut list: the pairs bought
    # together more often than chance predicts, and the pairs bought together most often. A pair
    # of best sellers can lead the second with a lift below 1.
    by_lift = sorted(
        (p for p in pairs if p["lift"] > 1), key=lambda p: (-p["lift"], p["a"], p["b"])
    )
    by_co_orders = sorted(pairs, key=lambda p: (-p["coOrders"], p["a"], p["b"]))
    kept = {(p["a"], p["b"]) for p in by_lift[:MAX_PAIRS] + by_co_orders[:MAX_PAIRS]}
    # Strongest first.
    pairs = sorted(
        (p for p in pairs if (p["a"], p["b"]) in kept), key=lambda p: (-p["lift"], p["a"], p["b"])
    )

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
