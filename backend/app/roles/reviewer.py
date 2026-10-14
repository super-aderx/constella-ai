"""The reviewer's code checks: what an answer may say, checked against what the tools returned.

These are exact and need no model. They run on every answer before it goes out (roles/analyst.py),
and the eval uses the same checks, so the app and the scores agree on what "grounded" means.
"""

import json
import re

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def close(a: float, b: float) -> bool:
    """Whether two figures are the same, allowing for rounding: 5.204 written as 5.2."""
    return abs(a - b) <= max(0.01, 0.005 * abs(b))


def numbers(value) -> list[float]:
    """Every number in a tool result, however it is nested."""
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    return [value] if isinstance(value, int | float) and not isinstance(value, bool) else []


def written(text: str) -> list[float]:
    """Every number written in a piece of text: 1,234.5 as 1234.5."""
    return [float(n.replace(",", "")) for n in NUMBER.findall(text)]


def scopes(ledger: list[dict]) -> list[dict]:
    """Every scope the tools were asked about, as {days, segment}."""
    found = []
    for entry in ledger:
        args = entry["args"]
        sides = [args["a"], args["b"]] if entry["tool"] == "compare" else [args]
        found += [{"days": side["days"], "segment": side["segment"]} for side in sides]
    return found


def review(reply: dict, ledger: list[dict], networks: list[dict], context: str = "") -> list[str]:
    """What is wrong with a reply, as notes the agent can act on; empty when it is sound.

    `networks` are the graph's networks for the reply's views, in the same order. `context` is
    text the reply may take numbers from besides the tools: the question, and the graph's scope
    as the agent was told it.
    """
    notes = []
    results = {entry["id"]: numbers(entry["result"]) for entry in ledger}

    # 1. Every figure is in the tool result it cites.
    for figure in reply["figures"]:
        label = f"{figure['name']} = {figure['value']:g}"
        if figure["source"] not in results:
            notes.append(f"{label} cites {figure['source']}, which is not a tool call you made.")
        elif not any(close(figure["value"], n) for n in results[figure["source"]]):
            notes.append(f"{label} is not in {figure['source']}. State it as the tool returned it.")

    # 2. Every number in the text comes from the question or from a tool: none worked out,
    #    rounded into another unit or made up. A tool result's text counts too, such as the
    #    "930ml" in a product's name.
    known = written(context) + written(json.dumps(ledger, ensure_ascii=False))
    for number in dict.fromkeys(written(reply["text"])):
        if not any(close(number, n) for n in known):
            notes.append(f"{number:g} in your text is not in the question or any tool result.")

    # 3. A reply with figures is about scopes it looked up: one view, or two for a comparison.
    if len(reply["views"]) > 2:
        notes.append("`views` holds one scope, or two for a comparison.")
    if reply["figures"]:
        asked = scopes(ledger)
        for view in reply["views"]:
            if view not in asked:
                notes.append(f"`views` has {view}, but no tool was called for that scope.")

    # 4. Every item and pair listed is on one of the graphs shown, so it can be highlighted.
    on_graph = {i["name"] for network in networks for i in network["items"]}
    pairs = {frozenset((p["a"], p["b"])) for network in networks for p in network["pairs"]}
    for name in reply["items"]:
        if name not in on_graph:
            notes.append(f"{name} is not a product type on the graph. Leave it out of `items`.")
    for pair in reply["pairs"]:
        if frozenset((pair["a"], pair["b"])) not in pairs:
            a, b = pair["a"], pair["b"]
            notes.append(f"{a} + {b} is not a pair on the graph. Leave it out of `pairs`.")
    return notes
