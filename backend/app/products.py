"""Product search for the campaign wizard: the product types and products whose names fit what
the user typed, with the same loose matching the agent's tools use."""

from typing import Literal

from pydantic import BaseModel

from app.infra import data
from app.tools import search


class ProductHit(BaseModel):
    kind: Literal["type", "product"]
    name: str
    type: str  # the item_tag: a type's own name, or the type the product belongs to


def search_products(q: str, limit: int) -> list[ProductHit]:
    """Up to `limit` names that fit `q`, best first, then types before products, then by name.

    It scores each name with search.score rather than calling search.best: best returns bare
    names, so it would lose each hit's kind and type, and it breaks ties by name alone.
    """
    q = q.strip()
    if not q:
        return []
    catalog = data.load_catalog()
    candidates = [("type", tag, tag) for tag in catalog] + [
        ("product", name, tag) for tag, names in catalog.items() for name in names
    ]
    # A name that shares no character with q scores 0, so it is dropped before the slower
    # scoring: on a catalog of 20,000 names this keeps a search near 150 ms.
    letters = set(search.tidy(q))
    scored = [
        (search.score(q, name), kind, name, tag)
        for kind, name, tag in candidates
        if letters & set(name.lower())
    ]
    kept = [hit for hit in scored if hit[0] >= search.GOOD_ENOUGH]
    kept.sort(key=lambda hit: (-hit[0], hit[1] != "type", hit[2]))
    return [ProductHit(kind=kind, name=name, type=tag) for _, kind, name, tag in kept[:limit]]
