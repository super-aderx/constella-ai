"""The lookups the analyst calls, checked on small networks made by hand. No database or model:
tools are invoked the way the Agents SDK invokes them, with load_network stood in for."""

import asyncio
import json

import pytest
from agents.tool_context import ToolContext

from app.tools import TOOLS, Run, lookups
from app.tools.lookups import removal


def pair(a: str, b: str, lift: float, co_orders: int = 50) -> dict:
    return {"a": a, "b": b, "lift": lift, "coOrders": co_orders}


def item(name: str, community: int | None) -> dict:
    return {"name": name, "orders": 100, "revenue": 0.0, "community": community, "bridge": False}


# Two groups that only 鮮乳 links: 吐司, 果醬 and 奶油 on one side, 優格 and 穀片 on the other.
# 啤酒 is on the graph, but only in a pair below chance.
BRIDGED = {
    "items": [
        item("鮮乳", 0),
        item("吐司", 0),
        item("果醬", 0),
        item("奶油", 0),
        item("優格", 1),
        item("穀片", 1),
        item("啤酒", None),
    ],
    "pairs": [
        pair("吐司", "果醬", 3.0),
        pair("吐司", "奶油", 2.5),
        pair("果醬", "奶油", 2.0),
        pair("優格", "穀片", 2.2),
        pair("鮮乳", "吐司", 1.8, 120),
        pair("鮮乳", "優格", 1.4, 90),
        pair("鮮乳", "啤酒", 0.8, 200),
    ],
    "communities": ["吐司 & 果醬", "優格 & 穀片"],
}


def test_removing_a_bridge_splits_the_graph():
    found = removal(BRIDGED, "鮮乳")
    assert found["item"] == "鮮乳"
    # Only its pairs above chance: the graph the bridges are measured on.
    assert found["pairs_lost"] == [
        {"a": "鮮乳", "b": "吐司", "lift": 1.8, "coOrders": 120},
        {"a": "鮮乳", "b": "優格", "lift": 1.4, "coOrders": 90},
    ]
    assert (found["parts_before"], found["parts_after"]) == (1, 2)
    assert found["cut_off"] == [["優格", "穀片"]]
    assert found["groups_linked_only_through_it"] == [sorted(BRIDGED["communities"])]


def test_removing_a_type_in_no_pair_above_chance_changes_nothing():
    found = removal(BRIDGED, "啤酒")
    assert found["pairs_lost"] == []
    assert found["parts_before"] == found["parts_after"] == 1
    assert found["cut_off"] == []
    assert found["groups_linked_only_through_it"] == []


def test_removing_a_type_inside_a_group_cuts_nothing_off():
    found = removal(BRIDGED, "果醬")
    assert (found["parts_before"], found["parts_after"]) == (1, 1)
    assert found["cut_off"] == []
    assert found["groups_linked_only_through_it"] == []


def invoke(tool, run: Run, **args) -> dict:
    """Calls a tool as the Agents SDK does, and returns the ledger entry it wrote."""
    payload = json.dumps(args, ensure_ascii=False)
    ctx = ToolContext(run, tool_name=tool.name, tool_call_id="t1", tool_arguments=payload)
    asyncio.run(tool.on_invoke_tool(ctx, payload))
    return run.ledger[-1]


@pytest.fixture
def scope(monkeypatch: pytest.MonkeyPatch) -> Run:
    monkeypatch.setattr(lookups, "load_network", lambda days, segment: BRIDGED)
    return Run(segments=["Champions"])


def test_without_item_records_what_the_removal_takes_away(scope: Run):
    entry = invoke(lookups.without_item, scope, item="鮮乳", days=90, segment=None)
    assert entry["tool"] == "without_item"
    assert entry["args"] == {"item": "鮮乳", "days": 90, "segment": None}
    assert entry["result"] == removal(BRIDGED, "鮮乳")


def test_without_item_refuses_a_type_not_on_the_graph(scope: Run):
    entry = invoke(lookups.without_item, scope, item="咖啡", days=None, segment=None)
    assert entry["result"] == {"error": "咖啡 is not a product type on the graph."}


def test_without_item_refuses_an_unknown_segment(scope: Run):
    entry = invoke(lookups.without_item, scope, item="鮮乳", days=None, segment="Champion")
    assert entry["result"]["error"].startswith("There is no segment Champion.")


@pytest.mark.parametrize(
    ("order", "lifts"),
    [("weakest", [0.8, 1.4, 1.8, 2.0]), ("strongest", [3.0, 2.5, 2.2, 2.0])],
)
def test_top_pairs_ranks_either_way(scope: Run, order: str, lifts: list[float]):
    args = {"by": "lift", "order": order, "min_co_orders": 1, "limit": 4}
    entry = invoke(lookups.top_pairs, scope, **args, days=None, segment=None)
    assert [p["lift"] for p in entry["result"]] == lifts
    assert entry["args"]["order"] == order


def test_the_new_tool_is_offered():
    assert lookups.without_item in TOOLS
