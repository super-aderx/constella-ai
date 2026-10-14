"""A first eval of the v1 agent with DeepEval. Needs the database and OPENAI_API_KEY.

Run from backend/:  uv run --env-file .env deepeval test run evals/system/test_v1.py

No dataset is needed yet: the data brief the agent was given is the ground truth. Each answer
gets two scores:
- Known items: every product type and pair it names exists in the network. Plain code, no judge.
- Faithfulness: every claim in its text is supported by the brief. Judged by an LLM.
"""

import asyncio

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from app.infra.data import load_network
from app.versions import v1 as agent

QUESTIONS = [
    "What are the top 5 product types by revenue?",
    "Which two product types are bought together most often?",
    "Which pair has the highest lift?",
    # A trap: single products are not in the brief, so the right answer is that it is not there.
    "Which single product sells best?",
]


class KnownItems(BaseMetric):
    """The share of the items and pairs an answer names that exist in the network."""

    # DeepEval copies a metric by calling its class again, so every argument needs a default.
    def __init__(self, threshold: float = 1.0):
        network = load_network()
        self.threshold = threshold
        self.items = {i["name"] for i in network["items"]}
        self.pairs = {frozenset((p["a"], p["b"])) for p in network["pairs"]}

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        named = test_case.metadata
        unknown = [i for i in named["items"] if i not in self.items]
        unknown += [" + ".join(p) for p in named["pairs"] if frozenset(p) not in self.pairs]
        total = len(named["items"]) + len(named["pairs"])
        self.score = 1 - len(unknown) / total if total else 1.0
        self.reason = f"Not in the network: {', '.join(unknown)}" if unknown else "All known."
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self):
        return "Known items"


# One event loop for every test: the agent's OpenAI client stays tied to the loop it first ran on,
# so a new loop per test (asyncio.run) fails from the second test on.
loop = asyncio.new_event_loop()


@pytest.mark.parametrize("question", QUESTIONS)
def test_answer(question: str):
    answer = loop.run_until_complete(agent.ask(question, days=None, segment=None))
    test_case = LLMTestCase(
        input=question,
        actual_output=answer.text,
        retrieval_context=[agent.brief(load_network(), days=None, segment=None)],
        metadata={"items": answer.items, "pairs": [[p.a, p.b] for p in answer.pairs]},
    )
    assert_test(test_case, [KnownItems(), FaithfulnessMetric(threshold=0.8)])
