"""The agents' tools: fixed lookups over the networks the graph can draw. The agent picks a
tool and its arguments; it never writes SQL, and every figure it states comes from one of these.

Every tool takes a scope, a period and a customer segment, and reads the network the graph draws
for it (data.load_network): the same data, the same cut-off for rare pairs. What the agent says
about a scope and what the graph shows for it cannot disagree.

Each call is written to the run's ledger (L1, L2 …), so a figure in an answer can be traced to
the call it came from.
"""

from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
from agents import RunContextWrapper, function_tool

from app.infra import progress
from app.infra.data import load_bundles, load_catalog, load_network
from app.tools.potential import segment_gaps, shared_partners
from app.tools.search import best, closest

SMALL = 300  # baskets: below this, a scope's pairs and lifts are too noisy to lean on


@dataclass
class Run:
    """One question's run: the segments that exist, the product types the user has set aside
    (no campaign may be built on them), and every tool call made so far."""

    segments: list[str]
    ignored: list[str] = field(default_factory=list)
    ledger: list[dict] = field(default_factory=list)


Ctx = RunContextWrapper[Run]


def record(ctx: Ctx, tool: str, args: dict, result) -> dict:
    """Writes a call to the ledger and returns its result with the entry's id."""
    ledger = ctx.context.ledger
    entry = {"id": f"L{len(ledger) + 1}", "tool": tool, "args": args, "result": result}
    ledger.append(entry)
    progress.step("tool", id=entry["id"], tool=tool, args=args)
    return {"ledger_id": entry["id"], "result": result}


def unknown(ctx: Ctx, *segments: str | None) -> dict | None:
    """An error for the first segment that does not exist, with the segments it could be a
    loose spelling of: the tools take a segment spelt exactly, and the agent calls again."""
    known = ctx.context.segments
    absent = [s for s in segments if s and s not in known]
    if not absent:
        return None
    error = f"There is no segment {absent[0]}."
    if near := closest(absent[0], known, 3):
        error += (
            f" Closest: {near}. If one is plainly what the user means, call again with it spelt"
            " exactly, and say in your answer which segment you took them to mean."
        )
    return {"error": f"{error} Segments: {known}"}


def missing(network: dict, *names: str) -> dict | None:
    """An error for the first name that is not a product type on the graph."""
    known = {i["name"] for i in network["items"]}
    absent = [name for name in names if name not in known]
    return {"error": f"{absent[0]} is not a product type on the graph."} if absent else None


def betweenness(network: dict) -> tuple[dict[str, float], nx.Graph]:
    """How often each type sits between two others, on the pairs above chance: the same graph
    data.build_network marks its bridges on."""
    graph = nx.Graph((p["a"], p["b"]) for p in network["pairs"] if p["lift"] > 1)
    return nx.betweenness_centrality(graph), graph


def groups(network: dict) -> list[dict]:
    """The graph's groups, each with its members, best seller first, and their revenue added up."""
    found = []
    for index, label in enumerate(network["communities"]):
        members = [i for i in network["items"] if i["community"] == index]
        members.sort(key=lambda i: (-i["orders"], i["name"]))
        revenue = round(sum(i["revenue"] for i in members))
        found.append({"group": label, "members": [i["name"] for i in members], "revenue": revenue})
    return found


@function_tool
def find_item(ctx: Ctx, text: str, days: int | None, segment: str | None) -> dict:
    """Finds the product types a loose name could mean. It takes a shortened or misspelt name,
    or the name of a product, and returns the product types that fit and the products that fit
    with the type each belongs to. Each says whether it is on the graph for this scope: a type
    can be in the data and still be too rare for the graph.

    Use it whenever the user's words are not exactly a product type you have seen from a tool.
    When nothing is spelt alike, it lists every type on the graph instead: if one is plainly what
    the user means by another word, take that one.

    Args:
        text: What the user called it, e.g. "milk" or a product's name.
    """
    args = {"text": text, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "find_item", args, error)
    catalog = load_catalog()
    on_graph = {i["name"] for i in load_network(days, segment)["items"]}
    types = [{"type": t, "on_graph": t in on_graph} for t in best(text, list(catalog), 5)]
    owner = {product: tag for tag, products in catalog.items() for product in products}
    products = [
        {"product": p, "type": owner[p], "type_on_graph": owner[p] in on_graph}
        for p in best(text, list(owner), 8)
    ]
    found = {"types": types, "products": products}
    if not types and not products:
        # Nothing is spelt alike. The user may mean a type by another word, which only its
        # reader can tell: here is every type on the graph to choose from.
        found["nothing_alike_types_on_graph"] = sorted(on_graph)
    return record(ctx, "find_item", args, found)


@function_tool
def top_items(
    ctx: Ctx, by: Literal["revenue", "orders"], limit: int, days: int | None, segment: str | None
) -> dict:
    """Ranks the product types on the graph by revenue or by orders (the baskets they are in).

    Args:
        by: What to rank by.
        limit: How many to return.
    """
    args = {"by": by, "limit": limit, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "top_items", args, error)
    ranked = sorted(load_network(days, segment)["items"], key=lambda i: (-i[by], i["name"]))
    rows = [{"name": i["name"], "orders": i["orders"], "revenue": i["revenue"]} for i in ranked]
    return record(ctx, "top_items", args, rows[:limit])


@function_tool
def top_pairs(
    ctx: Ctx,
    by: Literal["co_orders", "lift"],
    min_co_orders: int,
    limit: int,
    days: int | None,
    segment: str | None,
) -> dict:
    """Ranks the pairs on the graph by how often they share a basket (co_orders) or by lift.

    Args:
        by: What to rank by.
        min_co_orders: Leave out pairs sharing fewer baskets than this. The graph already leaves
            out its rarest pairs; 1 keeps every pair it shows.
        limit: How many to return.
    """
    args = {"by": by, "min_co_orders": min_co_orders, "limit": limit}
    args |= {"days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "top_pairs", args, error)
    key = "coOrders" if by == "co_orders" else "lift"
    pairs = [p for p in load_network(days, segment)["pairs"] if p["coOrders"] >= min_co_orders]
    ranked = sorted(pairs, key=lambda p: (-p[key], p["a"], p["b"]))[:limit]
    return record(ctx, "top_pairs", args, ranked)


@function_tool
def item_neighbors(
    ctx: Ctx,
    item: str,
    by: Literal["co_orders", "lift"],
    limit: int,
    days: int | None,
    segment: str | None,
) -> dict:
    """The product types linked to one product type on the graph, strongest first.

    Args:
        item: The product type, spelled as on the graph.
        by: Rank its partners by shared baskets (co_orders) or by lift.
        limit: How many to return.
    """
    args = {"item": item, "by": by, "limit": limit, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "item_neighbors", args, error)
    network = load_network(days, segment)
    if error := missing(network, item):
        return record(ctx, "item_neighbors", args, error)
    key = "coOrders" if by == "co_orders" else "lift"
    partners = [
        {"item": p["b"] if p["a"] == item else p["a"], "coOrders": p["coOrders"], "lift": p["lift"]}
        for p in network["pairs"]
        if item in (p["a"], p["b"])
    ]
    ranked = sorted(partners, key=lambda p: (-p[key], p["item"]))[:limit]
    return record(ctx, "item_neighbors", args, ranked)


@function_tool
def pair_stats(ctx: Ctx, a: str, b: str, days: int | None, segment: str | None) -> dict:
    """How often two product types share a basket, and their lift. Lift above 1 means more often
    than chance predicts; below 1, less often, however many baskets hold both.

    Args:
        a: One product type, spelled as on the graph.
        b: The other.
    """
    args = {"a": a, "b": b, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "pair_stats", args, error)
    network = load_network(days, segment)
    if error := missing(network, a, b):
        return record(ctx, "pair_stats", args, error)
    found = [p for p in network["pairs"] if {p["a"], p["b"]} == {a, b}]
    if not found:
        floor = network["minCoOrders"]
        error = f"{a} + {b} is not a pair on the graph: they share fewer than {floor} baskets."
        return record(ctx, "pair_stats", args, {"error": error})
    return record(ctx, "pair_stats", args, found[0])


@function_tool
def central_items(ctx: Ctx, limit: int, days: int | None, segment: str | None) -> dict:
    """The product types that connect the most others on the graph: those that most often sit on
    the shortest path between two types (betweenness), over the pairs bought together more than
    chance predicts. These are the graph's bridges. The best seller is not necessarily one.

    Args:
        limit: How many to return.
    """
    args = {"by": "betweenness", "limit": limit, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "central_items", args, error)
    between, graph = betweenness(load_network(days, segment))
    ranked = sorted(between, key=lambda name: (-between[name], name))[:limit]
    rows = [
        {"item": name, "betweenness": round(between[name], 3), "links": graph.degree[name]}
        for name in ranked
    ]
    return record(ctx, "central_items", args, rows)


@function_tool
def communities(ctx: Ctx, days: int | None, segment: str | None) -> dict:
    """The groups the graph colours: product types that are bought together. Each comes with its
    members, best seller first, and the revenue of its members added up. A product type with no
    pair above chance is in no group.
    """
    args = {"days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "communities", args, error)
    return record(ctx, "communities", args, groups(load_network(days, segment)))


@function_tool
def item_products(ctx: Ctx, item: str, days: int | None, segment: str | None) -> dict:
    """The best-selling products inside one product type, by orders: what the graph's detail card
    lists for it. Use it when the question is about single products.

    Args:
        item: The product type, spelled as on the graph.
    """
    args = {"item": item, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "item_products", args, error)
    network = load_network(days, segment)
    if error := missing(network, item):
        return record(ctx, "item_products", args, error)
    products = next(i["products"] for i in network["items"] if i["name"] == item)
    return record(ctx, "item_products", args, products)


@function_tool
def top_bundles(
    ctx: Ctx,
    by: Literal["co_orders", "lift"],
    item: str | None,
    limit: int,
    days: int | None,
    segment: str | None,
) -> dict:
    """Ranks sets of three product types bought in the same basket: for a bundle or a
    recommendation of more than two. Each set is three types where every two are a pair on the
    graph. Ranked by the baskets holding all three (co_orders) or by lift, how many times more
    often the three share a basket than chance predicts. Sets of three are the largest there are.

    Args:
        by: What to rank by.
        item: Only sets that include this product type, spelled as on the graph. Null for any.
        limit: How many to return.
    """
    args = {"by": by, "item": item, "limit": limit, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "top_bundles", args, error)
    if item and (error := missing(load_network(days, segment), item)):
        return record(ctx, "top_bundles", args, error)
    key = "coOrders" if by == "co_orders" else "lift"
    bundles = [b for b in load_bundles(days, segment) if not item or item in b["items"]]
    ranked = sorted(bundles, key=lambda b: (-b[key], b["items"]))[:limit]
    return record(ctx, "top_bundles", args, ranked)


@function_tool
def potential_pairs(
    ctx: Ctx,
    method: Literal["shared_partners", "segment_gap"],
    item: str | None,
    limit: int,
    days: int | None,
    segment: str | None,
) -> dict:
    """Finds pairs of product types that do not sell together much yet but have a reason in the
    data to: leads for growth, for a new bundle or a cross-sell. Each comes with its evidence.
    They are candidates to test, never forecasts: say so.

    Args:
        method: "shared_partners" finds two types that are each bought with the same other
            types but not with each other. "segment_gap" finds pairs one customer segment buys
            together far more than customers overall; it compares every segment for the period
            and ignores `segment`.
        item: Only candidates that include this product type, spelled as on the graph. Null for
            any.
        limit: How many to return.
    """
    args = {"method": method, "item": item, "limit": limit, "days": days, "segment": segment}
    if error := unknown(ctx, segment):
        return record(ctx, "potential_pairs", args, error)
    if item and (error := missing(load_network(days, None), item)):
        return record(ctx, "potential_pairs", args, error)
    if method == "shared_partners":
        found = shared_partners(load_network(days, segment))
    else:
        each = {s: load_network(days, s) for s in ctx.context.segments}
        found = segment_gaps(load_network(days, None), each)
    kept = [c for c in found if not item or item in (c["a"], c["b"])]
    return record(ctx, "potential_pairs", args, kept[:limit])


@function_tool
def compare(
    ctx: Ctx,
    days_a: int | None,
    segment_a: str | None,
    days_b: int | None,
    segment_b: str | None,
) -> dict:
    """Compares the graph under two scopes, A and B: two customer segments, or two periods. It
    returns what differs: the product types whose share of baskets moves most, the pairs on one
    graph only, the pairs whose lift changes most, and each side's bridges and groups.

    A small scope has a lower cut-off for pairs, so a pair can be on one graph only because of
    size. Each side says how many baskets it has and whether that is small; lean on shares and
    lift, not on raw counts, and say so when a side is small.

    Args:
        days_a: A's period: only the last this many days of the data. Null for all of it.
        segment_a: A's customer segment. Null for all customers.
        days_b: B's period.
        segment_b: B's customer segment.
    """
    a, b = {"days": days_a, "segment": segment_a}, {"days": days_b, "segment": segment_b}
    args = {"a": a, "b": b}
    if error := unknown(ctx, segment_a, segment_b):
        return record(ctx, "compare", args, error)
    one, two = load_network(**a), load_network(**b)

    def side(network: dict) -> dict:
        between, _ = betweenness(network)
        bridges = sorted(between, key=lambda name: (-between[name], name))[:3]
        return {
            "baskets": network["baskets"],
            "small": network["baskets"] < SMALL,
            "min_co_orders": network["minCoOrders"],
            "bridges": [name for name in bridges if between[name] > 0],
            "groups": [g["members"] for g in groups(network)],
        }

    # A type's share: the part of the scope's baskets it is in.
    def shares(network: dict) -> dict[str, float]:
        return {i["name"]: i["orders"] / network["baskets"] for i in network["items"]}

    share_a, share_b = shares(one), shares(two)
    items = [
        {"item": n, "share_a": round(share_a.get(n, 0), 3), "share_b": round(share_b.get(n, 0), 3)}
        for n in share_a.keys() | share_b.keys()
    ]
    items.sort(key=lambda i: (-abs(i["share_a"] - i["share_b"]), i["item"]))

    lift_a = {(p["a"], p["b"]): p["lift"] for p in one["pairs"]}
    lift_b = {(p["a"], p["b"]): p["lift"] for p in two["pairs"]}
    changed = [
        {"a": p[0], "b": p[1], "lift_a": lift_a[p], "lift_b": lift_b[p]}
        for p in lift_a.keys() & lift_b.keys()
    ]
    changed.sort(key=lambda p: (-abs(p["lift_a"] - p["lift_b"]), p["a"], p["b"]))

    def only(mine: dict, theirs: dict) -> list[dict]:
        pairs = [{"a": p[0], "b": p[1], "lift": mine[p]} for p in mine.keys() - theirs.keys()]
        return sorted(pairs, key=lambda p: (-p["lift"], p["a"], p["b"]))[:5]

    result = {
        "a": side(one),
        "b": side(two),
        "items_share_of_baskets": items[:6],
        "pairs_only_on_a": only(lift_a, lift_b),
        "pairs_only_on_b": only(lift_b, lift_a),
        "pairs_lift_changed": changed[:5],
    }
    return record(ctx, "compare", args, result)


TOOLS = [
    find_item,
    top_items,
    top_pairs,
    item_neighbors,
    pair_stats,
    central_items,
    communities,
    item_products,
    top_bundles,
    potential_pairs,
    compare,
]
