"""Product search over the catalog, checked without a database or a model."""

import pytest

from app.infra import data
from app.products import ProductHit, search_products


@pytest.fixture
def catalog(monkeypatch: pytest.MonkeyPatch):
    def use(names: dict[str, list[str]]) -> None:
        monkeypatch.setattr(data, "load_catalog", lambda: names)

    return use


def test_a_typo_still_finds_the_type(catalog):
    catalog({"teapot": ["blue teapot"], "cups": ["tea cup"]})
    hits = search_products("teapto", 20)
    assert hits[0] == ProductHit(kind="type", name="teapot", type="teapot")


def test_a_product_is_found_with_its_type(catalog):
    catalog({"teapot": ["blue teapot"], "cups": ["tea cup"]})
    hits = search_products("blue tea", 20)
    assert ProductHit(kind="product", name="blue teapot", type="teapot") in hits


def test_a_blank_query_finds_nothing(catalog, monkeypatch: pytest.MonkeyPatch):
    catalog({"teapot": ["blue teapot"]})
    assert search_products("  ", 20) == []

    # Nothing is scored, so the catalog is not even read.
    def unread():
        raise AssertionError("the catalog was read")

    monkeypatch.setattr(data, "load_catalog", unread)
    assert search_products("", 20) == []


def test_hits_are_ranked_and_capped(catalog):
    catalog({"tea": ["green tea", "tea"], "teacup": ["tea cup"], "seat": ["zz"]})
    ranked = [
        ProductHit(kind="type", name="tea", type="tea"),
        ProductHit(kind="type", name="teacup", type="teacup"),
        ProductHit(kind="product", name="green tea", type="tea"),
        ProductHit(kind="product", name="tea", type="tea"),
        ProductHit(kind="product", name="tea cup", type="teacup"),
        # Shares every letter with "tea" but does not hold it, so it scores lower.
        ProductHit(kind="type", name="seat", type="seat"),
    ]
    assert search_products("tea", 50) == ranked
    assert search_products("tea", 4) == ranked[:4]


def test_a_name_that_shares_too_little_is_left_out(catalog):
    catalog({"teapot": ["blue teapot"]})
    assert search_products("xyz", 20) == []
