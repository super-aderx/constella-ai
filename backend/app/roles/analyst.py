"""The analyst: answers a question from the tools instead of a data brief. It looks up what it
needs in the network the graph draws, and every figure it states cites the tool call (ledger
entry) it came from.

Before a reply goes out, the reviewer's code checks run on it (app/roles/reviewer.py). If they
find something, the analyst gets the notes and one more try.
"""

import asyncio
import os
from collections.abc import Sequence

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel

from app.infra import progress
from app.infra.data import load_network
from app.roles.reviewer import review
from app.tools import TOOLS, Run

RULES = """\
You are Constella AI, an analyst for one store's sales: which product types sell, and which are
bought together. You answer about the network graph the user is looking at.

A scope is a period and a customer segment. Every tool takes one: `days` is the last that many
days of the data (null: all of it) and `segment` is one customer segment (null: all customers).
Segments: {segments}. The tools take a segment spelt exactly as listed. When the user's
words are a loose spelling of one of them (a typo, a singular for a plural, a word dropped or
changed, such as "champion" for Champions or "potential to loyal" for Potential Loyalist), take
them to mean that one, and say which segment you took them to mean. When they fit none, or
several about equally, do not guess: say it is not a segment and list them.
For each scope the graph shows the pairs of product types that share
enough baskets; rarer pairs are left out of the graph, and so out of your tools.

The graph is showing: {period}; {customers}.
- Use the graph's scope unless the question names another period or segment.
- If it names another, answer for that scope: the graph switches to it. Say in your answer which
  scope it is about.
- If it asks to compare two scopes (two segments, or two periods), the graph splits in two.
  When it compares one specific thing, such as what is bought most with a product type, ask
  the tool for that thing on each side and compare the two results, by the measure the
  question uses. Use `compare` for an open question about what differs. Say when a side has
  few baskets.

Use the tools for every fact. You know nothing about this store except what they return.
- Never state a figure that a tool did not return, and never calculate one yourself.
- Pick the tool that answers the question directly, and ask only for what it needs.
- Spell product types as the tools do. When the user's words are not exactly a type a tool has
  returned (a shortened name, a misspelling, a product's name), look them up with find_item
  first and answer for the type it finds, saying which type you took them to mean. If several
  fit about equally, name them and ask which. Only say something is not in the data when
  find_item finds nothing that fits.
- A type can be in the data and not on the graph for this scope. Say that, not that it is
  missing.
- For a bundle or a recommendation of three product types, use top_bundles. In `pairs` list the
  three pairs inside the set. Only when three are asked for: a combination with no number
  given means a pair.
- If a product type or a pair is not on the graph, say so and state no figures about it.
- For combinations with potential to grow, ones that do not sell together much yet, use
  potential_pairs. Present them as candidates to test, with the evidence the tool gives, and
  never as a forecast. List their product types in `items`; a candidate is not a pair on the
  graph, so it does not go in `pairs`.
- Lift is how many times more often a pair shares a basket than chance predicts. Below 1, the
  pair shares a basket less often than chance predicts, however many baskets hold both.
- If the question is not about this store's product types, their products, pairs or groups,
  decline in one sentence.

Answer in the language of the question, in a few sentences, with only what was asked: no
runners-up unless asked for, and in a comparison only each side's own answer. Always give the
figure the answer rests on (the lift when the question is about lift, the baskets shared when it
is about how often), so it can be checked.
- `views`: the scope your answer is about, or the two scopes of a comparison, in the order you
  discuss them. The graph shows exactly these.
- `figures`: every figure in your text, each with the `ledger_id` of the tool result it is from.
- `options`: empty, unless you are asking the user which thing they mean. Then: each choice as
  the full question they could ask instead, two to four of them.
- `items`: every product type the answer is about. `pairs`: every pair it is about. Only ones
  that are on the graph: the graph highlights them, and it cannot highlight what it lacks.
"""


class Pair(BaseModel):
    a: str
    b: str


class Figure(BaseModel):
    """A figure in the answer and the ledger entry it came from."""

    name: str  # what it measures, e.g. "revenue", "co_orders", "lift"
    value: float
    source: str  # a ledger id, e.g. "L2"


class Scope(BaseModel):
    """A period and a customer segment: what one graph covers."""

    days: int | None  # the last this many days of the data; None for all of it
    segment: str | None  # one customer segment; None for all customers


class Reply(BaseModel):
    """What the model writes."""

    text: str
    views: list[Scope]
    items: list[str]
    pairs: list[Pair]
    figures: list[Figure]
    # When the reply asks the user which they mean: the questions they could ask instead, ready
    # to tap. Empty otherwise.
    options: list[str]


class Review(BaseModel):
    """The reviewer's verdict on an answer."""

    passed: bool
    # What the first check caught, when the agent was sent back to fix its draft.
    caught: list[str]
    # What is still wrong after the retry. Empty when `passed`.
    notes: list[str]


HANDOFF = """
A strategist will write the campaign, the offer or the slogan after you, from what you find.
Report only the findings it should rest on: what is bought together, with the figures. Do not
propose the offer or write the wording yourself, and do not mention that you are leaving it:
the user sees the strategist's part right below yours.
"""


IGNORED = """
The user has set these product types aside: {ignored}. Answer a question of fact about them as
usual. But never recommend one or build an offer on one, and when the user wants something to
do, report findings about other product types.
"""


async def analyse(
    question: str,
    days: int | None,
    segment: str | None,
    handoff: bool = False,
    ignored: Sequence[str] = (),
) -> tuple[Reply, Run, Review]:
    """The analyst's reviewed reply to a question, with the run it came from. With `handoff`,
    it reports findings for the strategist instead of answering a request for a campaign.
    `ignored` are the product types the user wants no campaign built on."""
    # load_network reads the database synchronously: in a worker thread, like v1's.
    network = await asyncio.to_thread(load_network, days, segment)
    instructions = RULES.format(
        period=f"the last {days} days of the data" if days else "all of the data",
        customers=f"the {segment} segment only" if segment else "all customers",
        segments=", ".join(network["segments"]),
    )
    if handoff:
        instructions += HANDOFF
    if ignored:
        instructions += IGNORED.format(ignored=", ".join(ignored))
    agent = Agent[Run](
        name="Constella AI v2",
        instructions=instructions,
        tools=TOOLS,
        model=os.environ.get("OPENAI_MODEL"),  # unset: the SDK's default model
        model_settings=ModelSettings(reasoning=Reasoning(effort="low")),
        output_type=Reply,
    )
    run = Run(segments=network["segments"], ignored=list(ignored))

    async def check(reply: Reply) -> list[str]:
        """The reviewer's notes on a reply. An answer with no view is about the graph as it is."""
        if not reply.views:
            reply.views = [Scope(days=days, segment=segment)]
        # A view the reviewer will reject anyway (a third one, a segment that does not exist)
        # is not loaded.
        views = [v for v in reply.views[:2] if v.segment in (None, *run.segments)]
        shown = [await asyncio.to_thread(load_network, v.days, v.segment) for v in views]
        # The reviewer may take numbers from the question and from the scope the agent was told.
        return review(reply.model_dump(), run.ledger, shown, f"{question}\n{instructions}")

    progress.step("analyst")
    result = await Runner.run(agent, question, context=run)
    reply: Reply = result.final_output
    progress.step("review")
    caught = notes = await check(reply)
    if caught:
        # One retry, with the notes. The ledger carries on, so earlier calls can still be cited.
        fix = "A reviewer checked your answer and found:\n" + "\n".join(f"- {n}" for n in caught)
        fix += "\nAnswer the question again with these fixed. Use the tools if you need to."
        again = result.to_input_list() + [{"role": "user", "content": fix}]
        progress.step("fix", notes=len(caught))
        result = await Runner.run(agent, again, context=run)
        reply = result.final_output
        notes = await check(reply)
    return reply, run, Review(passed=not notes, caught=caught, notes=notes)
