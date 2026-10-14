"""Scores the whole system on the golden set: a question in, the answer the app would show out.
Needs the test database, loaded by `make golden`, and OPENAI_API_KEY.

Run from backend/:  uv run --env-file .env deepeval test run evals/system/test_golden.py
EVAL_AGENT=1 in front scores v1, the prompt-only agent, as the baseline, and 2 scores v2, one
agent with tools; the default is v3, the roles.

The cases and the scores are in evals/golden.py. Every case is a question of fact, so the run is
router, analyst, reviewer and scientist; the strategist and the writer are never called. To tell
whether a lost point is the analyst's, run the same cases on it alone:
evals/roles/test_analyst.py.

Every agent is given each case's filters, the way the app's toolbar would set them. v1 has no
tools, no ledger and no list of figures: its figures are the numbers in its text, the two scores
about tools do not apply to it, and it cannot change what the graph shows, so its answer is
always about the case's filters.
"""

import os
import re

import pytest

from app.versions import v1, v2, v3
from evals.golden import GOLDEN, loop, score

VERSION = os.environ.get("EVAL_AGENT", "3")


def text_figures(text: str, question: str) -> list[dict]:
    """The numbers in a v1 answer, as figures with no source. Numbers that only repeat the
    question (a 30-basket floor, a 90-day period) are not figures it is stating."""
    found = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    asked = set(re.findall(r"\d[\d,]*(?:\.\d+)?", question))
    return [
        {"name": "in text", "value": float(n.replace(",", "")), "source": None}
        for n in found
        if n not in asked
    ]


async def ask(case: dict) -> dict:
    """One agent's answer to a case, in the shape the scores read."""
    # The case's filters are the graph's: what the app's toolbar would be set to.
    days, segment = case["filters"]["days"], case["filters"]["segment"]
    if VERSION == "1":
        reply = await v1.ask(case["input"], days, segment)
        figures = text_figures(reply.text, case["input"])
        view = {"days": days, "segment": segment}
        answer = {**reply.model_dump(), "views": [view], "figures": figures, "ledger": []}
        return {**answer, "tools": False}
    version = v2 if VERSION == "2" else v3
    return (await version.ask(case["input"], days, segment)).model_dump()


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda case: case["id"])
def test_case(case: dict):
    score(case, loop.run_until_complete(ask(case)))
