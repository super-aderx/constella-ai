"""The two signals for a potential combination, on small networks made to show each. No model."""

from app.tools.potential import segment_gaps, shared_partners


def pair(a: str, b: str, lift: float, co_orders: int = 50) -> dict:
    return {"a": a, "b": b, "lift": lift, "coOrders": co_orders}


def test_two_types_with_the_same_partners_are_a_candidate():
    # 吐司 and 優格 are each bought with 鮮乳 and 雞蛋, but not with each other.
    pairs = [pair("吐司", "鮮乳", 2), pair("優格", "鮮乳", 2), pair("吐司", "雞蛋", 2)]
    pairs += [pair("優格", "雞蛋", 2), pair("啤酒", "洋芋片", 3)]
    found = shared_partners({"pairs": pairs})
    assert [(c["a"], c["b"]) for c in found][0] == ("優格", "吐司")
    assert found[0]["shared_partners"] == ["雞蛋", "鮮乳"]
    assert found[0]["lift_now"] is None


def test_a_pair_already_above_chance_is_not_a_candidate():
    pairs = [pair("吐司", "鮮乳", 2), pair("優格", "鮮乳", 2), pair("吐司", "雞蛋", 2)]
    pairs += [pair("優格", "雞蛋", 2), pair("優格", "吐司", 1.5)]
    assert ("優格", "吐司") not in [(c["a"], c["b"]) for c in shared_partners({"pairs": pairs})]


def test_a_pair_on_the_graph_below_chance_shows_where_it_stands():
    pairs = [pair("吐司", "鮮乳", 2), pair("優格", "鮮乳", 2), pair("吐司", "雞蛋", 2)]
    pairs += [pair("優格", "雞蛋", 2), pair("優格", "吐司", 0.6, 70)]
    candidate = next(c for c in shared_partners({"pairs": pairs}) if c["a"] == "優格")
    assert (candidate["coOrders_now"], candidate["lift_now"]) == (70, 0.6)


def test_one_shared_partner_is_too_little():
    pairs = [pair("吐司", "鮮乳", 2), pair("優格", "鮮乳", 2)]
    assert shared_partners({"pairs": pairs}) == []


def test_a_pair_one_segment_buys_far_more_is_a_gap():
    everyone = {"pairs": [pair("吐司", "咖啡", 1.2), pair("吐司", "鮮乳", 2.0)]}
    segments = {
        "忠誠客戶": {"pairs": [pair("吐司", "咖啡", 2.4, 21), pair("吐司", "鮮乳", 2.1)]},
        "新客戶": {"pairs": [pair("吐司", "咖啡", 1.1)]},
    }
    found = segment_gaps(everyone, segments)
    assert [(c["a"], c["b"], c["segment"]) for c in found] == [("吐司", "咖啡", "忠誠客戶")]
    assert found[0]["lift_all_customers"] == 1.2
