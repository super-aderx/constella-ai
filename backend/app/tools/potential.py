"""Potential combinations: pairs of product types that do not sell together much yet, with a
reason in the data to think they could.

Two signals, both read off the graph's networks and neither a forecast:
- shared partners: two types that are each bought with the same other types, but not with each
  other. Shoppers who put either in a basket want the same things around it.
- segment gap: a pair that one customer segment buys together far more than customers overall.
  What works for one segment may be worth offering to the others.

Each candidate comes with the evidence it rests on, so it can be shown and tested, not trusted.
"""

from math import log

import networkx as nx

MIN_SHARED = 2  # partners two types must share before the pair counts as a lead
GAP = 1.5  # times: how far a segment's lift must stand above everyone's


def shared_partners(network: dict) -> list[dict]:
    """Pairs of types with no link above chance between them that share partners, most first.

    The score is Adamic-Adar: a shared partner counts for more when it has few partners itself,
    since a type bought with everything says little.
    """
    current = {frozenset((p["a"], p["b"])): p for p in network["pairs"]}
    graph = nx.Graph((p["a"], p["b"]) for p in network["pairs"] if p["lift"] > 1)
    found = []
    for a, b in nx.non_edges(graph):
        a, b = sorted((a, b))
        shared = sorted(nx.common_neighbors(graph, a, b))
        if len(shared) < MIN_SHARED:
            continue
        pair = current.get(frozenset((a, b)))
        found.append(
            {
                "a": a,
                "b": b,
                "shared_partners": shared,
                "score": round(sum(1 / log(graph.degree[w]) for w in shared), 2),
                # Where the pair stands today: on the graph below chance, or too rare for it.
                "coOrders_now": pair["coOrders"] if pair else None,
                "lift_now": pair["lift"] if pair else None,
            }
        )
    return sorted(found, key=lambda c: (-len(c["shared_partners"]), -c["score"], c["a"], c["b"]))


def segment_gaps(everyone: dict, segments: dict[str, dict]) -> list[dict]:
    """Pairs a segment buys together well above chance and well above customers overall.

    `everyone` is the network for all customers and `segments` each segment's, for one period.
    """
    overall = {frozenset((p["a"], p["b"])): p["lift"] for p in everyone["pairs"]}
    found = []
    for segment, network in segments.items():
        for p in network["pairs"]:
            lift_all = overall.get(frozenset((p["a"], p["b"])))
            if p["lift"] > 1 and (lift_all is None or p["lift"] >= GAP * lift_all):
                found.append(
                    {
                        "a": p["a"],
                        "b": p["b"],
                        "segment": segment,
                        "lift_in_segment": p["lift"],
                        "coOrders_in_segment": p["coOrders"],
                        # None: among all customers the pair is too rare for the graph.
                        "lift_all_customers": lift_all,
                    }
                )
    # The widest gap first; a pair missing overall ranks by its lift in the segment alone.
    return sorted(
        found,
        key=lambda c: (-c["lift_in_segment"] / (c["lift_all_customers"] or 1), c["a"], c["b"]),
    )
