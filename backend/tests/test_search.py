"""Loose-name matching, on the ways a user's words differ from the data's. No database."""

import pytest

from app.tools.search import best, closest

TYPES = ["堅果穀物飲品", "鮮乳", "洗髮精", "衛生紙", "洋芋片", "咖啡"]


def test_a_shortened_name_finds_its_type():
    assert best("堅果穀物飲", TYPES, 3)[0] == "堅果穀物飲品"


def test_a_name_inside_a_longer_phrase_is_found():
    assert best("瑞穗鮮乳 930ml", TYPES, 3)[0] == "鮮乳"


def test_a_near_miss_finds_the_closest_type():
    assert best("洗髮乳", TYPES, 3)[0] == "洗髮精"


def test_spacing_and_case_do_not_matter():
    assert best(" Milk  2L", ["milk 2l", "tea"], 3) == ["milk 2l"]


def test_nothing_alike_finds_nothing():
    assert best("寵物食品", TYPES, 3) == []


SEGMENTS = ["At Risk", "Champions", "Lost", "Loyal Accounts", "Potential Loyalist", "Promising"]


@pytest.mark.parametrize(
    ("typed", "segment"),
    [
        ("champion", "Champions"),
        ("potential to loyal", "Potential Loyalist"),
        ("potential loyalists", "Potential Loyalist"),
        ("lost", "Lost"),
        ("at-risk", "At Risk"),
        ("promissing", "Promising"),
    ],
)
def test_a_loosely_named_segment_finds_the_one_meant(typed: str, segment: str):
    assert closest(typed, SEGMENTS, 3) == [segment]


def test_a_word_two_segments_share_finds_both():
    assert closest("loyal", SEGMENTS, 3) == ["Loyal Accounts", "Potential Loyalist"]


@pytest.mark.parametrize("typed", ["platinum members", "VIP", "白金會員", ""])
def test_a_segment_that_does_not_exist_finds_nothing(typed: str):
    assert closest(typed, SEGMENTS, 3) == []
