"""Scores the router on its labelled set (evals/data/router.yaml). Needs OPENAI_API_KEY only.

Run from backend/:  uv run --env-file .env pytest evals/roles/test_router.py -q
"""

import asyncio
from pathlib import Path

import pytest
import yaml

from app.roles import router

CASES = yaml.safe_load((Path(__file__).parent.parent / "data" / "router.yaml").read_text("utf-8"))

# One event loop for every test: the OpenAI client stays tied to the loop it first ran on.
loop = asyncio.new_event_loop()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["input"][:24])
def test_plan(case: dict):
    plan = loop.run_until_complete(router.plan(case["input"]))
    assert plan.route == case["route"]
    assert plan.strategy == case["strategy"]
    # A refusal says what it can do instead and offers two questions; an answer adds nothing.
    assert bool(plan.reply) == (case["route"] == "refuse")
    assert len(plan.options) == (2 if case["route"] == "refuse" else 0)
