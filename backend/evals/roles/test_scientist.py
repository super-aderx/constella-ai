"""Scores the scientist alone: given an answer, whether it adds a chart, and whether the chart
fits. Needs the test database, loaded by `make golden`, and OPENAI_API_KEY.

Run from backend/:  uv run --env-file .env deepeval test run evals/roles/test_scientist.py

What the scientist is given is frozen (evals/data/scientist.json, built by
evals/build_scientist.py from the cases in evals/data/scientist.yaml), so the scores are about
the scientist and not about the analyst's answer that day. Each case gets three scores, all
plain code with no judge: a chart is a type and a pointer at a tool result, so it can be checked.
- Right chart: a chart where the answer calls for one and none where it does not; of a type
  that fits; drawn from the tool that answers the question, for the answer's scope; of the
  measure the question asks about.
- Good title: in the language of the question, with no numbers.
- No wasted calls: at most one tool call, for a wider result, and never one already made.
"""

import copy
import json
import re
from pathlib import Path

import pytest
import yaml
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from app.roles import scientist
from app.tools import Run
from evals.golden import Scored, loop

DATA = Path(__file__).parent.parent / "data"
CASES = yaml.safe_load((DATA / "scientist.yaml").read_text("utf-8"))
GIVEN = json.loads((DATA / "scientist.json").read_text("utf-8"))
CJK = re.compile(r"[一-鿿]")


def chart_problems(case: dict, drawn: dict) -> list[str]:
    """What is wrong with the chart for a case, or with there being none; empty when it fits."""
    chart = drawn["chart"]
    if not case["chart"]:
        return [f"a {chart['type']} chart where the answer calls for none"] if chart else []
    if not chart:
        return ["no chart: none was chosen, or the one chosen cannot be drawn"]
    problems = []
    if chart["type"] not in case["types"]:
        problems.append(f"a {chart['type']} chart, expected one of {case['types']}")
    if chart["value"] not in case["values"]:
        problems.append(f"draws `{chart['value']}`, expected one of {case['values']}")
    if "label" in case and chart["label"] != case["label"]:
        problems.append(f"rows named by `{chart['label']}`, expected `{case['label']}`")
    source = next(e for e in drawn["ledger"] if e["id"] == chart["source"])
    if source["tool"] not in case["tools"]:
        problems.append(f"drawn from {source['tool']}, expected one of {case['tools']}")
    scope = {"days": source["args"].get("days"), "segment": source["args"].get("segment")}
    if scope != drawn["view"]:
        problems.append(f"drawn from a result for {scope}, but the answer is about {drawn['view']}")
    return problems


def title_problems(case: dict, drawn: dict) -> list[str]:
    """What is wrong with a chart's title; empty when it is sound, or there is no chart."""
    if not drawn["chart"]:
        return []
    title = drawn["chart"]["title"]
    problems = []
    if bool(CJK.search(title)) != bool(CJK.search(case["input"])):
        problems.append(f"'{title}' is not in the language of the question")
    if re.search(r"\d", title):
        problems.append(f"'{title}' has a number in it")
    return problems


def call_problems(case: dict, drawn: dict) -> list[str]:
    """Tool calls the scientist did not need; empty when there are none."""
    before, after = drawn["ledger"][: drawn["given"]], drawn["ledger"][drawn["given"] :]
    problems = []
    seen = [(entry["tool"], entry["args"]) for entry in before]
    for entry in after:
        call = (entry["tool"], entry["args"])
        if call in seen:
            problems.append(
                f"{entry['id']} repeats an earlier call: {entry['tool']} {entry['args']}"
            )
        seen.append(call)
    if len(after) > 1:
        problems.append(f"{len(after)} calls, at most 1 expected: {[e['tool'] for e in after]}")
    return problems


class RightChart(Scored):
    name = "Right chart"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return chart_problems(case, answer)


class GoodTitle(Scored):
    name = "Good title"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return title_problems(case, answer)


class NoWastedCalls(Scored):
    name = "No wasted calls"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return call_problems(case, answer)


async def draw(case: dict) -> dict:
    """The scientist's chart for a case, and the ledger after it, in the shape the scores read."""
    given = GIVEN[case["id"]]
    # The run as the analyst left it. A copy: the scientist's calls are added to the ledger.
    run = Run(segments=given["segments"], ledger=copy.deepcopy(given["ledger"]))
    chart = await scientist.draw(case["input"], given["reply"], run)
    return {
        "chart": chart.model_dump() if chart else None,
        "ledger": run.ledger,
        "given": len(given["ledger"]),
        "view": given["reply"]["views"][0],
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_chart(case: dict):
    drawn = loop.run_until_complete(draw(case))
    chart = drawn["chart"]
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=json.dumps(chart, ensure_ascii=False) if chart else "no chart",
        metadata={"case": case, "answer": drawn},
    )
    assert_test(test_case, [RightChart(), GoodTitle(), NoWastedCalls()])
