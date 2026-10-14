"""The golden set (evals/data/golden.json) and its scores, shared by the evals that run on it:
the whole system's (evals/system/test_golden.py) and the analyst's alone
(evals/roles/test_analyst.py). Needs the test database, loaded by `make golden`.

Each case gets three scores, all plain code with no judge:
- Correct answer: it is about the right scope (the graph's, the one the question names, or the
  two it compares); the expected items and pairs are there and nothing else is named; the figure
  the question asks for is stated; and every figure stated is in the tool result it cites.
  On a trap (something the graph cannot answer), the answer states no figures. On an open
  question (no single right answer), it names only what the expected tool returned.
- Right tools: every expected tool was called with the expected arguments.
- No wasted calls: no call was made twice with the same arguments, and the run made few more
  calls than the case expects.

An answer is a dict in the shape of v2's: text, views, items, pairs, figures and ledger. One
from something with no tools carries `tools: False`, and the two scores about tools pass it by.
"""

import asyncio
import json
import os
from pathlib import Path

from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# The agent reads the sample, never the real data.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.roles.reviewer import cited, close  # noqa: E402

GOLDEN = json.loads((Path(__file__).parent / "data" / "golden.json").read_text("utf-8"))


def answer_problems(case: dict, answer: dict) -> list[str]:
    """What is wrong with an answer; empty when it is correct."""
    figures = [f["value"] for f in answer["figures"]]
    if case["kind"] == "trap":
        return ["states figures on a trap: the graph cannot answer this"] if figures else []
    items = set(answer["items"])
    pairs = {frozenset((p["a"], p["b"])) for p in answer["pairs"]}
    if not figures and not items and not pairs:
        return ["abstained: no answer given"]

    def scope(view: dict) -> tuple:
        return (view["days"], view["segment"])

    if {scope(v) for v in answer["views"]} != {scope(v) for v in case["expected_views"]}:
        return [f"about {answer['views']}, expected {case['expected_views']}"]
    if case["kind"] == "open":
        # No single right answer: what it names must be something the expected tool returned.
        tools = {expected["name"] for expected in case["expected_tools"]}
        returned = {s for e in answer["ledger"] if e["tool"] in tools for s in strings(e["result"])}
        unknown = items.union(*pairs) - returned
        return [f"names what the tool did not return: {sorted(unknown)}"] if unknown else []

    expected_items = set(case["expected_items"])
    expected_pairs = {frozenset(p) for p in case["expected_pairs"]}
    # What an answer may name: the expected, and the types the question itself names.
    allowed = expected_items.union(*expected_pairs, case["fills"].values())
    problems = []
    if absent := expected_items - items:
        problems.append(f"missing items: {sorted(absent)}")
    if extra := items - allowed:
        problems.append(f"extra items: {sorted(extra)}")
    if absent := expected_pairs - pairs:
        problems.append(f"missing pairs: {[sorted(p) for p in absent]}")
    if extra := [sorted(p) for p in pairs if not p <= allowed]:
        problems.append(f"extra pairs: {extra}")
    # Words the answer must contain, such as a product's name. Spacing is the writer's choice.
    text = answer["text"].replace(" ", "")
    for words in case["expected_text"]:
        if words.replace(" ", "") not in text:
            problems.append(f"does not name {words}")
    for figure in case["expected_figures"]:
        if not any(close(value, figure["value"]) for value in figures):
            problems.append(f"missing figure: {figure['name']} = {figure['value']}")
    # A figure is grounded when the ledger entry it cites holds that number. v1 cites nothing.
    results = {entry["id"]: entry["result"] for entry in answer["ledger"]}
    for figure in answer["figures"]:
        if figure["source"] and not cited(figure, results.get(figure["source"], [])):
            problems.append(f"{figure['name']} = {figure['value']} is not in {figure['source']}")
    return problems


def strings(value) -> list[str]:
    """Every piece of text in a tool result, however it is nested."""
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return [value] if isinstance(value, str) else []


def tool_problems(case: dict, ledger: list[dict]) -> list[str]:
    """Why an expected tool call is not in the ledger; empty when they all are."""

    def comparable(args: dict) -> dict:
        # `limit` is the agent's to choose, and a pair is the same either way round: two product
        # types, or the two scopes of a comparison.
        args = {key: value for key, value in args.items() if key != "limit"}
        if "a" in args and "b" in args:
            sides = (args.pop("a"), args.pop("b"))
            args["pair"] = frozenset(
                tuple(sorted(side.items())) if isinstance(side, dict) else side for side in sides
            )
        return args

    for expected in case.get("expected_tools", []):
        want = comparable(expected["args"])
        calls = [comparable(e["args"]) for e in ledger if e["tool"] == expected["name"]]
        if not calls:
            called = sorted({e["tool"] for e in ledger})
            return [f"{expected['name']} was not called (called: {called})"]
        if not any(all(call.get(k) == v for k, v in want.items()) for call in calls):
            return [f"{expected['name']} was called with {calls}, expected {want}"]
    return []


SPARE_CALLS = 3  # more than a case expects: a name looked up, a retry, the scientist's wider one


def wasted_calls(case: dict, ledger: list[dict]) -> list[str]:
    """Calls a run did not need; empty when there are none."""
    problems = []
    seen = []
    for entry in ledger:
        call = (entry["tool"], entry["args"])
        if call in seen:
            problems.append(
                f"{entry['id']} repeats an earlier call: {entry['tool']} {entry['args']}"
            )
        seen.append(call)
    most = len(case.get("expected_tools", [])) + SPARE_CALLS
    if len(ledger) > most:
        tools = [entry["tool"] for entry in ledger]
        problems.append(f"{len(ledger)} calls, at most {most} expected: {tools}")
    return problems


class Scored(BaseMetric):
    """A metric that passes when `problems` finds nothing. DeepEval copies a metric by calling
    its class with no arguments, so the case travels in the test case's metadata."""

    name = ""
    threshold = 1.0

    def problems(self, case: dict, answer: dict) -> list[str]:
        raise NotImplementedError

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        problems = self.problems(test_case.metadata["case"], test_case.metadata["answer"])
        self.score = 0.0 if problems else 1.0
        self.reason = "; ".join(problems) or "OK"
        self.success = not problems
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self):
        return self.name


class CorrectAnswer(Scored):
    name = "Correct answer"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return answer_problems(case, answer)


class RightTools(Scored):
    name = "Right tools"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return tool_problems(case, answer["ledger"]) if answer.get("tools", True) else []


class NoWastedCalls(Scored):
    name = "No wasted calls"

    def problems(self, case: dict, answer: dict) -> list[str]:
        return wasted_calls(case, answer["ledger"]) if answer.get("tools", True) else []


# One event loop for every test: the agent's OpenAI client stays tied to the loop it first ran on.
loop = asyncio.new_event_loop()


def score(case: dict, answer: dict) -> None:
    """Scores an answer to a case, and fails the test when a score does."""
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=answer["text"],
        metadata={"case": case, "answer": answer},
    )
    assert_test(test_case, [CorrectAnswer(), RightTools(), NoWastedCalls()])
