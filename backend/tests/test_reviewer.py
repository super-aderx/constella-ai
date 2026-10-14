"""The reviewer's code checks, on answers with a planted fault and on clean ones. No model."""

import pytest

from app.roles.reviewer import review

NETWORK = {
    "items": [{"name": "鮮乳"}, {"name": "吐司"}, {"name": "咖啡"}],
    "pairs": [{"a": "吐司", "b": "鮮乳"}, {"a": "咖啡", "b": "鮮乳"}],
}
LEDGER = [
    {
        "id": "L1",
        "tool": "top_pairs",
        "args": {"by": "lift", "min_co_orders": 1, "limit": 1, "days": 30, "segment": None},
        "result": [{"a": "吐司", "b": "鮮乳", "coOrders": 186, "lift": 2.104}],
    },
    {
        "id": "L2",
        "tool": "item_products",
        "args": {"item": "鮮乳", "days": 30, "segment": None},
        "result": [{"name": "瑞穗鮮乳 930ml", "orders": 203, "revenue": 18676.0}],
    },
]
QUESTION = "最近 30 天，哪一組產品類別的提升度最高？"


def reply(**changes) -> dict:
    """A sound reply, with some of it changed."""
    clean = {
        "text": "提升度最高的是吐司與鮮乳，提升度為 2.10，共同出現在 186 個購物籃。",
        "views": [{"days": 30, "segment": None}],
        "items": ["吐司", "鮮乳"],
        "pairs": [{"a": "鮮乳", "b": "吐司"}],
        "figures": [
            {"name": "lift", "value": 2.1, "source": "L1"},
            {"name": "co_orders", "value": 186, "source": "L1"},
        ],
    }
    return {**clean, **changes}


def notes(**changes) -> list[str]:
    return review(reply(**changes), LEDGER, [NETWORK], QUESTION)


def test_a_sound_reply_passes():
    assert notes() == []


def test_a_rounded_figure_passes():
    assert notes(figures=[{"name": "lift", "value": 2.104, "source": "L1"}]) == []


def test_numbers_from_the_question_and_from_a_product_name_pass():
    text = "最近 30 天，鮮乳中最暢銷的是瑞穗鮮乳 930ml，共 203 筆訂單。"
    figures = [{"name": "orders", "value": 203, "source": "L2"}]
    assert notes(text=text, figures=figures, items=["鮮乳"], pairs=[]) == []


def test_a_reply_with_no_figures_passes():
    assert notes(text="資料中沒有寵物食品這個產品類別。", items=[], pairs=[], figures=[]) == []


@pytest.mark.parametrize(
    ("changes", "caught"),
    [
        # The planted faults: a wrong figure, a figure cited to the wrong call or to none, a
        # number in the text no tool returned, an item and a pair that are not on the graph.
        ({"figures": [{"name": "lift", "value": 3.1, "source": "L1"}]}, "lift = 3.1 is not in L1"),
        ({"figures": [{"name": "co_orders", "value": 186, "source": "L2"}]}, "is not in L2"),
        ({"figures": [{"name": "lift", "value": 2.1, "source": "L9"}]}, "cites L9"),
        ({"text": "提升度為 2.10，約佔所有購物籃的 12.4%。"}, "12.4 in your text"),
        ({"items": ["吐司", "鮮乳", "寵物食品"]}, "寵物食品 is not a product type on the graph"),
        ({"pairs": [{"a": "吐司", "b": "咖啡"}]}, "吐司 + 咖啡 is not a pair on the graph"),
        # A view the tools were never asked about: the figures cannot be about it.
        ({"views": [{"days": None, "segment": "忠誠客戶"}]}, "no tool was called for that scope"),
    ],
)
def test_a_planted_fault_is_caught(changes: dict, caught: str):
    found = notes(**changes)
    assert len(found) == 1 and caught in found[0]
