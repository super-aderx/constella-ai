"""Scores the analyst alone on the golden set: no router before it, and no strategist, writer
or scientist after. Needs the test database, loaded by `make golden`, and OPENAI_API_KEY.

Run from backend/:  uv run --env-file .env deepeval test run evals/roles/test_analyst.py

The cases and the scores are the whole system's (evals/golden.py, evals/system/test_golden.py),
so the two can be read side by side: a point lost here is the analyst's, and one lost only there
is the router's or the scientist's. The analyst's reply is scored as it leaves the role, after
the reviewer's checks and its one retry.
"""

import pytest

from app.roles.analyst import analyse
from evals.golden import GOLDEN, loop, score


async def ask(case: dict) -> dict:
    """The analyst's reply to a case, with its run's ledger, in the shape the scores read."""
    # The case's filters are the graph's: what the app's toolbar would be set to.
    days, segment = case["filters"]["days"], case["filters"]["segment"]
    reply, run, _ = await analyse(case["input"], days, segment)
    return {**reply.model_dump(), "ledger": run.ledger}


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda case: case["id"])
def test_case(case: dict):
    score(case, loop.run_until_complete(ask(case)))
