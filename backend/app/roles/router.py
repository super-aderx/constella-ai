"""The router: plans the run for a question, and answers nothing itself.

It decides whether the question is the store's business at all, and which roles the answer
needs after the analyst: the strategist, for something to do, and the scientist, for a chart.
"""

import os
from typing import Literal

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel

from app.infra import progress

RULES = """\
You are the router of Constella AI, an assistant for one retail store's sales data: which
product types sell, which are bought together, in which customer segments and periods. Plan the
run for the user's question. You do not answer it.

`route`:
- "answer": the question is about this store's sales. Product types and their products, what
  is bought with what, bundles, groups, bridges, segments, periods, comparisons, and marketing
  built on them. When in doubt, choose this: the analyst says so if the data cannot answer.
- "refuse": anything else. General knowledge, other companies, code, writing that has nothing to
  do with the store's sales.

`strategy`: true when the user wants something to do with a finding: a campaign, a promotion, a
discount, a bundle offer, a slogan, a marketing plan. False for a question of fact, which
includes asking what goes with a product or which sets are bought together.

`chart`: false when the answer can only be a single fact, a yes or a no. True otherwise.

For "refuse" only, in the user's language:
- `reply`: one sentence on what you can help with instead.
- `options`: two questions about a store's sales the user could ask.
Leave both empty for "answer".
"""


class Plan(BaseModel):
    """The roles a question's run needs."""

    route: Literal["answer", "refuse"]
    strategy: bool
    chart: bool
    reply: str
    options: list[str]


async def plan(question: str) -> Plan:
    progress.step("router")
    agent = Agent(
        name="Constella AI router",
        instructions=RULES,
        # A smaller model is enough here: ROUTER_MODEL, else the same one as the other roles.
        model=os.environ.get("ROUTER_MODEL") or os.environ.get("OPENAI_MODEL"),
        model_settings=ModelSettings(reasoning=Reasoning(effort="low")),
        output_type=Plan,
    )
    return (await Runner.run(agent, question)).final_output
