"""Scores the writer's slogans, and above all its puns (諧音梗). Needs OPENAI_API_KEY only.

Run from backend/:  uv run --env-file .env deepeval test run evals/roles/test_writer.py
WRITER_MODEL=gpt-4o-2024-08-06 in front scores another model. EVAL_RUNS sets how many times the
writer is asked (3 by default): one run of a writer says little.

Each campaign's slogans get two scores (test_slogans):
- Sound offer: every slogan the writer drafted passes the writer's own code check (no number but
  the discount, a 折 that states it rightly, a pun whose word is in the slogan). Plain code.
- Real pun: when a slogan claims a pun, whether it is one. Judged by an LLM (DeepEval's G-Eval),
  since code cannot tell whether two words sound alike. A campaign with no pun claimed is not
  judged: the writer is told to write none when nothing fits.

A judge is only worth its agreement with people, and judging a pun takes the same ear as writing
one. So the judge is itself tested (test_judge) on evals/data/puns.yaml, slogans already called good
or bad by hand, and it runs on another model than the writer's, so no model marks its own work.
"""

import asyncio
import os
from pathlib import Path

import pytest
import yaml
from deepeval import assert_test
from deepeval.metrics import BaseMetric, GEval
from deepeval.models import OpenAIModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.roles import writer
from app.roles.strategist import Campaign, Strategy
from app.roles.writer import Slogan, slogan_problems

JUDGE = os.environ.get("JUDGE_MODEL", "gpt-6-luna")
RUNS = int(os.environ.get("EVAL_RUNS", "3"))
QUESTION = "幫我想促銷活動和標語"
PASS = 0.7  # of 1: the judge's score from which a pun counts as real


def campaign(name: str, items: list[str], discount: int) -> Campaign:
    return Campaign(
        name=name,
        basis="proven",
        items=items,
        discount_percent=discount,
        audience=None,
        reason="",
    )


# The first two are made up; the last two are campaigns the strategist drafted from the data.
CAMPAIGNS = {
    "breakfast": campaign("早餐組合", ["鮮乳", "吐司"], 20),
    "drinks": campaign("下班小酌", ["啤酒", "洋芋片"], 15),
    "pork": campaign("今晚豬肉配鮮蔬", ["生豬肉", "生鮮蔬菜"], 10),
    "tofu": campaign("蔬豆好煮意", ["生鮮蔬菜", "豆皮/豆腐"], 10),
}
LABELLED = yaml.safe_load((Path(__file__).parent.parent / "data" / "puns.yaml").read_text("utf-8"))


def real_pun() -> GEval:
    """The judge: whether a slogan's claimed pun is one. A new one for each case."""
    return GEval(
        name="Real pun",
        evaluation_steps=[
            "The output is a shop slogan and the pun it claims, as 'what is written ≈ what is "
            "heard'. Write out how each side is said aloud in Mandarin as spoken in Taiwan, "
            "syllable by syllable. If the two differ by more than a tone or one close sound, "
            "or either side is not a real word, it is not a pun: score 0 to 2.",
            "The heard side must come from a phrase a shopper in Taiwan knows (an idiom, a "
            "saying, an everyday expression). If there is no such phrase, score 0 to 3.",
            "The slogan must hold that phrase with the written word in the heard word's place, "
            "so the line reads two ways. If the heard word itself is written out, if the "
            "written word only sits somewhere in the line, or if extra words break the phrase, "
            "the swap was not made: score 0 to 4.",
            "A pun that passes all three scores 7 to 10: higher the closer the sounds, the "
            "better known the phrase, and the more the line still says about the products in "
            "the input. Garbled or meaningless text scores 0.",
        ],
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        # DeepEval calls Chat Completions, which OpenAI keeps in its logs only when asked to.
        # The tag is what to filter the logs by.
        model=OpenAIModel(
            model=JUDGE, generation_kwargs={"store": True, "metadata": {"eval": "writer-puns"}}
        ),
        threshold=PASS,
    )


def pun_case(offer: Campaign, slogan: str, pun: str, **metadata) -> LLMTestCase:
    products = f"{' + '.join(offer.items)}, {offer.discount_percent}% off"
    return LLMTestCase(
        input=f"A campaign for one store in Taiwan: {products}.",
        actual_output=f"Slogan: {slogan}\nPun claimed: {pun}",
        metadata=metadata,
    )


@pytest.mark.parametrize("label", LABELLED, ids=lambda label: label["slogan"][:12])
def test_judge(label: dict):
    """The judge against a verdict given by hand: it passes the good puns and fails the bad."""
    judge = real_pun()
    judge.measure(pun_case(CAMPAIGNS[label["campaign"]], label["slogan"], label["pun"]))
    print(f"\nJUDGE {label['verdict']:10} {judge.score:.2f}  {label['slogan']}  ({judge.reason})")
    if label["verdict"] != "borderline":
        assert judge.is_successful() == (label["verdict"] == "good"), judge.reason


class SoundOffer(BaseMetric):
    """The share of the slogans drafted for a campaign that pass the writer's code check."""

    threshold = 1.0

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        offer = Campaign(**test_case.metadata["campaign"])
        slogans = [Slogan(**s) for s in test_case.metadata["slogans"]]
        problems = [slogan_problems(s, offer) for s in slogans]
        failed = sum(1 for found in problems if found)
        self.score = 1 - failed / len(slogans) if slogans else 0.0
        self.reason = "; ".join(p for found in problems for p in found) or (
            "OK" if slogans else "The writer drafted no slogans."
        )
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self):
        return "Sound offer"


# One event loop for every test: the OpenAI client stays tied to the loop it first ran on.
loop = asyncio.new_event_loop()
drafts: dict[int, dict[str, list[Slogan]]] = {}


def drafted(run: int) -> dict[str, list[Slogan]]:
    """Every slogan the writer drafted on one run, by campaign name: before its code check drops
    any, so what the check catches is scored too. One call writes for all the campaigns."""
    if run not in drafts:
        drafts[run] = {}
        ask = writer.Runner.run

        async def keep(agent, brief):
            result = await ask(agent, brief)
            drafts[run] = {c.campaign: c.slogans for c in result.final_output.campaigns}
            return result

        writer.Runner.run = keep
        try:
            strategy = Strategy(text="", campaigns=list(CAMPAIGNS.values()), figures=[])
            loop.run_until_complete(writer.write(QUESTION, strategy))
        finally:
            writer.Runner.run = ask
    return drafts[run]


@pytest.mark.parametrize("run", range(RUNS))
@pytest.mark.parametrize("key", CAMPAIGNS)
def test_slogans(key: str, run: int):
    offer = CAMPAIGNS[key]
    slogans = drafted(run).get(offer.name, [])
    scored = {"campaign": offer.model_dump(), "slogans": [s.model_dump() for s in slogans]}
    puns = [s for s in slogans if s.pun]
    if puns:
        test_case = pun_case(offer, puns[0].text, puns[0].pun, **scored)
        assert_test(test_case, [SoundOffer(), real_pun()])
    else:
        lines = "\n".join(s.text for s in slogans)
        test_case = LLMTestCase(input=QUESTION, actual_output=lines, metadata=scored)
        assert_test(test_case, [SoundOffer()])
