"""Loose-name matching: what a user typed against the names in the data.

A user rarely spells a product type as the data does. They shorten it, add a word, or name a
product instead of its type. Each candidate gets a score from 0 to 1 and the best are kept.
"""

from difflib import SequenceMatcher

GOOD_ENOUGH = 0.45  # below this, a candidate shares too little with what was typed


def tidy(text: str) -> str:
    return "".join(text.lower().split())


def score(typed: str, name: str) -> float:
    """How well a name fits what was typed: 1 when one holds the other, else by what they share."""
    typed, name = tidy(typed), tidy(name)
    if not typed or not name:
        return 0.0
    if typed in name or (len(name) >= 2 and name in typed):
        return 1.0
    matcher = SequenceMatcher(None, typed, name)
    # The longest run of characters they share, as a part of what was typed: "穀物飲" in a
    # longer name is a strong sign even when the rest differs.
    run = matcher.find_longest_match(0, len(typed), 0, len(name)).size
    shared = len(set(typed) & set(name)) / len(set(typed))
    return max(matcher.ratio(), 0.9 * run / len(typed) if run >= 2 else 0.0, 0.8 * shared)


def best(typed: str, names: list[str], limit: int) -> list[str]:
    """The names that fit what was typed, best first."""
    scored = [(score(typed, name), name) for name in names]
    kept = sorted((s, name) for s, name in scored if s >= GOOD_ENOUGH)
    return [name for s, name in sorted(kept, key=lambda pair: (-pair[0], pair[1]))][:limit]


CLOSE = 0.6  # below this, two whole names are not the same name misspelt


def likeness(typed: str, name: str) -> float:
    """How alike two whole names are, from 0 to 1. For a short list of fixed labels, such as
    customer segments, where the user means the whole label: "champion" for Champions,
    "potential to loyal" for Potential Loyalist. A word that is only part of a label ("loyal")
    counts for less the more of the label it leaves out.
    """
    typed, name = tidy(typed), tidy(name)
    if not typed or not name:
        return 0.0
    short, long = sorted((typed, name), key=len)
    held = 0.6 + 0.4 * len(short) / len(long) if len(short) >= 2 and short in long else 0.0
    return max(SequenceMatcher(None, typed, name).ratio(), held)


def closest(typed: str, names: list[str], limit: int) -> list[str]:
    """The names that could be what was typed, misspelt or reworded, most alike first."""
    scored = [(likeness(typed, name), name) for name in names]
    kept = [(s, name) for s, name in scored if s >= CLOSE]
    return [name for s, name in sorted(kept, key=lambda pair: (-pair[0], pair[1]))][:limit]
