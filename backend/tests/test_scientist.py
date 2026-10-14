"""The checks on a chart the scientist asks for: it must be drawable from the ledger. No model."""

import pytest

from app.roles.scientist import Chart, chart_problems

LEDGER = [
    {
        "id": "L1",
        "tool": "top_pairs",
        "args": {},
        "result": [{"a": "吐司", "b": "鮮乳", "lift": 2.1}],
    },
    {
        "id": "L2",
        "tool": "top_items",
        "args": {},
        "result": [{"name": n, "revenue": r} for n, r in [("衛生紙", 9), ("鮮乳", 7), ("咖啡", 5)]],
    },
    {
        "id": "L3",
        "tool": "top_pairs",
        "args": {},
        "result": [{"a": "吐司", "b": x, "lift": 2.0, "coOrders": 9} for x in "甲乙丙丁戊己庚"],
    },
    {"id": "L4", "tool": "pair_stats", "args": {}, "result": {"error": "not a pair"}},
]


def problems(**spec) -> list[str]:
    chart = {"type": "bar", "title": "t", "source": "L2", "label": "name", "value": "revenue"}
    return chart_problems(Chart(**{**chart, **spec}), LEDGER)


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {"type": "pie"},
        {"source": "L3", "label": "pair", "value": "lift"},
        {"type": "heatmap", "source": "L3", "label": "pair", "value": "coOrders"},
    ],
)
def test_a_chart_the_ledger_can_draw_passes(spec: dict):
    assert problems(**spec) == []


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        ({"source": "L9"}, "L9 is not in the ledger"),
        ({"source": "L1", "label": "pair", "value": "lift"}, "not a list of at least 3 rows"),
        ({"source": "L4"}, "not a list of at least 3 rows"),
        ({"value": "name"}, "`name` is not a number"),
        ({"value": "lift"}, "`lift` is not a number"),
        ({"label": "item"}, "`item` is not a field"),
        ({"label": "pair"}, "`pair` labels need rows with `a` and `b`"),
        ({"type": "heatmap"}, "a heat map needs rows with `a` and `b`"),
        ({"type": "pie", "source": "L3", "label": "pair", "value": "lift"}, "a pie takes 3 to 6"),
    ],
)
def test_a_chart_the_ledger_cannot_draw_is_refused(spec: dict, problem: str):
    assert any(problem in found for found in problems(**spec))
