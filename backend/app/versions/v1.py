"""v1: one agent, prompt only. No tools: all it knows is the data brief in its instructions."""

import asyncio
import os
from collections.abc import Sequence

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel

from app.infra.data import load_network
from app.roles.analyst import Pair

RULES = """\
You are Constella AI, an analyst for one store's network of product types: which types sell, and
which are bought together.

Answer from the data brief below and nothing else.
- Every figure you state must appear in the brief. Never estimate or invent one.
- The data is about product types, not single products. Spell their names exactly as the brief does.
- If a product type or a figure is not in the brief, say it is not in the data.
- Lift is how many times more often a pair shares a basket than chance predicts. Below 1, the
  pair shares a basket less often than chance predicts, however many baskets hold both.
- If the question is not about this store's product types, pairs or groups, decline in one sentence.
- Keep the answer to a few sentences.

In `items` list every product type your answer names, and in `pairs` every pair it names.
The graph highlights them.
"""


class Answer(BaseModel):
    text: str
    items: list[str]
    pairs: list[Pair]


def brief(network: dict, days: int | None, segment: str | None) -> str:
    """The whole network as text: its scope, product types, pairs and groups."""
    items, pairs, communities = network["items"], network["pairs"], network["communities"]
    members = [[i["name"] for i in items if i["community"] == c] for c in range(len(communities))]
    return "\n".join(
        [
            f"# Data brief: the store's {len(items)} product types that pair with another, "
            "and its revenue leaders",
            f"Period: {f'the last {days} days of the data' if days else 'all of the data'}",
            f"Customers: {f'the {segment} segment only' if segment else 'all segments'}",
            "",
            "## Product types (name | orders | revenue)",
            *(f"{i['name']} | {i['orders']:,} | ${i['revenue']:,.0f}" for i in items),
            "",
            f"## Pairs: every pair found in at least {network['minCoOrders']} baskets",
            "(type + type | baskets with both | lift)",
            *(f"{p['a']} + {p['b']} | {p['coOrders']:,} | {p['lift']:.2f}x" for p in pairs),
            "",
            "## Groups (product types often bought together)",
            *(
                f"{label}: {', '.join(names)}"
                for label, names in zip(communities, members, strict=True)
            ),
        ]
    )


async def ask(
    question: str, days: int | None, segment: str | None, ignored: Sequence[str] = ()
) -> Answer:
    # load_network reads the database synchronously: in a worker thread, so a filter it has not
    # seen yet does not hold up every other request.
    network = await asyncio.to_thread(load_network, days, segment)
    rules = RULES
    if ignored:
        rules += f"- Never recommend these product types: {', '.join(ignored)}. Facts are fine.\n"
    agent = Agent(
        name="Constella AI v1",
        instructions=f"{rules}\n{brief(network, days, segment)}",
        model=os.environ.get("OPENAI_MODEL"),  # unset: the SDK's default model
        model_settings=ModelSettings(reasoning=Reasoning(effort="low")),
        output_type=Answer,
    )
    result = await Runner.run(agent, question)
    return result.final_output
