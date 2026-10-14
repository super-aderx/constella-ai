"""The strategist: turns the analyst's findings into marketing actions, two or three campaign
options for the user to choose from.

Its facts come from the same tools and the same ledger as the analyst's. The reviewer checks
its figures the same way, and code checks that each campaign can be run as written: its product
types are a set on the graph (or a candidate the data suggested, for a bet on growth), its
discount is in range, its audience is a real segment.
"""

import asyncio
import json
import os
from collections.abc import Sequence
from typing import Literal

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel

from app.infra import progress
from app.infra.data import load_network
from app.roles.analyst import Figure, Reply
from app.roles.reviewer import review
from app.tools import TOOLS, Run

DISCOUNT = (5, 30)  # per cent: below is no offer, above gives too much away to draft unasked

RULES = """\
You are the strategist of Constella AI. An analyst has answered a question about one store's
sales, and the user wants something to do with it. Draft campaigns from the findings: two or
three options that really differ, so the user has a choice.

Your facts come from the tools, like the analyst's. Use the ledger you are given, and call a
tool when a campaign needs a fact that is not there yet: top_bundles for a set of three,
item_neighbors for what goes with a product type, pair_stats for one pair, potential_pairs for
a combination that could grow. Never state a figure a tool did not return, and never calculate
one. Keep to the scope the analyst answered for: {views}. Segments: {segments}.

Make the options differ in what they bundle or whom they are for, not only in wording. No two
may bundle the same product types.

Each campaign:
- `basis`: "proven" when its product types already sell together on the graph. "potential"
  when it is a candidate from potential_pairs that does not sell together much yet: a bet to
  test. Offer a potential one when the user asks about growth or new combinations, and at most
  one otherwise.
- `items`: for "proven", two or three product types, each a pair on the graph with another in
  the set. For "potential", exactly the two types of one potential_pairs candidate. Spell them
  as the tools do.
- `discount_percent`: from {low} to {high}.
- `audience`: one segment, exactly as listed, or null for all customers. Name a segment only
  when the findings are about it.
- `reason`: one sentence with the figures the campaign rests on. For "potential", the evidence
  the tool gave, and that it is untested.

`text`: two to four sentences in the user's language: what the options are and how they differ.
There is no cost or margin data, so say once that the discounts are not checked against margin.
`figures`: every figure in `text` and in each `reason`, each with the ledger id it is from.
"""

SET_ASIDE = """
The user has set these product types aside: {ignored}. No campaign may include one of them,
whatever the figures say. Build every option on other product types.
"""


class Campaign(BaseModel):
    name: str
    basis: Literal["proven", "potential"]
    items: list[str]
    discount_percent: int
    audience: str | None
    reason: str


class Strategy(BaseModel):
    """What the strategist writes."""

    text: str
    campaigns: list[Campaign]
    figures: list[Figure]


def candidates(ledger: list[dict]) -> set[frozenset[str]]:
    """Every potential pair the tools have returned in this run."""
    rows = [r for e in ledger if e["tool"] == "potential_pairs" for r in e["result"] or []]
    return {frozenset((r["a"], r["b"])) for r in rows if isinstance(r, dict) and "a" in r}


def campaign_problems(
    campaign: Campaign, network: dict, ledger: list[dict], ignored: Sequence[str] = ()
) -> list[str]:
    """Why a campaign cannot be run as written; empty when it can. Code, no model. `ignored`
    are the product types the user has set aside."""
    problems = []
    on_graph = {i["name"] for i in network["items"]}
    pairs = {frozenset((p["a"], p["b"])) for p in network["pairs"]}
    items = campaign.items
    for name in items:
        if name not in on_graph:
            problems.append(f"{name} is not a product type on the graph.")
        if name in ignored:
            problems.append(f"The user has set {name} aside. Build on other product types.")
    if campaign.basis == "potential":
        # A bet has to be one the data suggested: a candidate a tool returned in this run.
        if len(items) != 2 or len(set(items)) != 2:
            problems.append("`items` takes exactly two different product types for a potential.")
        elif frozenset(items) not in candidates(ledger):
            problems.append(f"{' + '.join(items)} is not a candidate potential_pairs returned.")
    else:
        if not 2 <= len(set(items)) <= 3 or len(set(items)) != len(items):
            problems.append("`items` takes two or three different product types.")
        for name in set(items) & on_graph:
            if not any(frozenset((name, other)) in pairs for other in items if other != name):
                problems.append(f"{name} is not a pair on the graph with another in the set.")
    low, high = DISCOUNT
    if not low <= campaign.discount_percent <= high:
        problems.append(f"`discount_percent` must be from {low} to {high}.")
    if campaign.audience is not None and campaign.audience not in network["segments"]:
        problems.append(f"{campaign.audience} is not a segment. Segments: {network['segments']}")
    return [f"{campaign.name}: {problem}" for problem in problems]


def strategy_problems(
    strategy: Strategy, networks: list[dict], ledger: list[dict], ignored: Sequence[str] = ()
) -> list[str]:
    """Why a set of options cannot go out as written; empty when it can. `networks` are the
    graphs of the reply's views: a campaign after a comparison runs on one of the two scopes, so
    it passes when it can run on either. Otherwise it shows what is wrong on the closest one."""
    campaigns = strategy.campaigns
    problems = [
        p
        for c in campaigns
        for p in min((campaign_problems(c, n, ledger, ignored) for n in networks), key=len)
    ]
    if not 2 <= len(campaigns) <= 3:
        problems.append("Give two or three campaigns.")
    sets = [frozenset(c.items) for c in campaigns]
    if len(set(sets)) != len(sets):
        problems.append("Two campaigns bundle the same product types. Make the options differ.")
    return problems


async def draft(question: str, reply: Reply, run: Run) -> tuple[Strategy, list[str], list[str]]:
    """Campaign options for a reviewed reply: the strategy, what the reviewer caught first, and
    what is still wrong after the one retry."""
    # One graph per view: two for a comparison, and a campaign may build on either side.
    networks = list(
        await asyncio.gather(
            *(asyncio.to_thread(load_network, v.days, v.segment) for v in reply.views)
        )
    )
    low, high = DISCOUNT
    instructions = RULES.format(
        views=json.dumps([v.model_dump() for v in reply.views], ensure_ascii=False),
        segments=", ".join(run.segments),
        low=low,
        high=high,
    )
    if run.ignored:
        instructions += SET_ASIDE.format(ignored=", ".join(run.ignored))
    agent = Agent[Run](
        name="Constella AI strategist",
        instructions=instructions,
        tools=TOOLS,
        model=os.environ.get("OPENAI_MODEL"),  # unset: the SDK's default model
        model_settings=ModelSettings(reasoning=Reasoning(effort="low")),
        output_type=Strategy,
    )

    def check(strategy: Strategy) -> list[str]:
        campaigns = strategy.campaigns
        # The reviewer reads the claims: the text and each campaign's reason.
        claims = {
            "text": "\n".join([strategy.text, *(c.reason for c in campaigns)]),
            "figures": [f.model_dump() for f in strategy.figures],
            "views": [v.model_dump() for v in reply.views],
            "items": [name for c in campaigns for name in c.items],
            "pairs": [],
        }
        # Besides the question, the offers' own numbers may appear in the text.
        discounts = " ".join(str(c.discount_percent) for c in campaigns)
        context = f"{question}\n{instructions}\n{discounts}"
        problems = strategy_problems(strategy, networks, run.ledger, run.ignored)
        return problems + review(claims, run.ledger, networks, context)

    brief = {"question": question, "analyst_answer": reply.text, "ledger": run.ledger}
    progress.step("strategist")
    result = await Runner.run(agent, json.dumps(brief, ensure_ascii=False), context=run)
    strategy: Strategy = result.final_output
    progress.step("strategy_review")
    caught = notes = check(strategy)
    if caught:
        fix = "A reviewer checked your campaigns and found:\n" + "\n".join(f"- {n}" for n in caught)
        fix += "\nDraft them again with these fixed. Use the tools if you need to."
        again = result.to_input_list() + [{"role": "user", "content": fix}]
        progress.step("strategy_fix", notes=len(caught))
        result = await Runner.run(agent, again, context=run)
        strategy = result.final_output
        notes = check(strategy)
    return strategy, caught, notes
