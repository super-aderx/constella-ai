"""Freezes what the scientist is given on each of its cases (evals/data/scientist.yaml): the
analyst's reply and the run's tool results, into evals/data/scientist.json. Needs the test
database, loaded by `make golden`, and OPENAI_API_KEY.

Run from backend/:  uv run --env-file .env python -m evals.build_scientist

The analyst words an answer differently each time, so rebuild only when the cases change, and
do not compare the scientist's scores across two builds.
"""

import asyncio
import json
import os
from pathlib import Path

import yaml

# The analyst reads the sample, never the real data.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.roles.analyst import analyse  # noqa: E402

DATA = Path(__file__).parent / "data"
TRIES = 3


async def given(case: dict) -> dict:
    """The analyst's reply to a case and its run, as the app would hand them to the scientist."""
    filters = case.get("filters", {})
    for _ in range(TRIES):
        reply, run, verdict = await analyse(
            case["input"], filters.get("days"), filters.get("segment")
        )
        # The app asks the scientist only about a sound answer with figures, about one scope.
        if verdict.passed and reply.figures and len(reply.views) == 1:
            return {"reply": reply.model_dump(), "segments": run.segments, "ledger": run.ledger}
    raise AssertionError(f"{case['id']}: no answer the scientist would be asked about")


async def main() -> None:
    cases = yaml.safe_load((DATA / "scientist.yaml").read_text("utf-8"))
    frozen = {case["id"]: await given(case) for case in cases}
    out = DATA / "scientist.json"
    out.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out}: {len(frozen)} cases")


if __name__ == "__main__":
    asyncio.run(main())
