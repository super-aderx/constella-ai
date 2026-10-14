"""The scientist: decides whether a chart would show more than an answer's text does, and which.

It never types a number. It picks a chart type and points at one tool result in the run's ledger,
calling a tool for a wider one when the answer's own is too small to draw, and the app draws
the chart from that result. A chart cannot show a figure the tools did not return.
"""

import json
import os
from typing import Literal

from agents import Agent, ModelSettings, Runner
from openai.types.shared import Reasoning
from pydantic import BaseModel

from app.infra import progress
from app.tools import TOOLS, Run

RULES = """\
You are the scientist of Constella AI. An analyst has just answered a question about one store's
network of product types. Decide whether one chart would show the reader more than the text of
the answer does: the wider picture the answer sits in.

First decide whether to chart at all. Return `chart` as null, and call no tool, when:
- the question asks for one figure about one thing, such as one product type's revenue;
- the question is a yes or a no, such as whether a pair is bought together more than chance
  predicts;
- the answer is that something is not in the data.
This holds even when the ledger has a longer list that could be drawn: a ranking the reader did
not ask for is not the picture of their answer.

The app draws the chart from one tool result, a ledger entry. You never type a number.
- The ledger you are given shows each call's tool, its arguments and the shape of its result
  (how many rows, which fields), not the values. You do not need the values: the app reads
  them from the entry you point at.
- Use an entry already in the ledger if it has at least 3 rows: point at it and call nothing.
- Never make a call that is in the ledger already with the same arguments. Its result is
  there: point at that entry.
- Call a tool only when the answer's own result has fewer than 3 rows, and then once: the same
  tool, with a higher limit, for the scope the answer is about: {views}. When the answer names
  the top pair, top_pairs with a limit of 8 shows how far ahead it is. Never call find_item:
  the names are settled.
- Draw what the answer is about. Do not chart something else because it is easier to get.

Chart types:
- bar: rows ranked by one measure. The usual choice.
- pie: only the parts of one whole, 3 to 6 rows of clearly different sizes, such as the revenue
  of each group from `communities`. Never for a top-N list: its rows are not a whole.
- heatmap: pairs (rows with `a` and `b`) coloured by lift or coOrders. Ask top_pairs for 15 to
  30 rows.

Fields:
- `source`: the ledger id of the result to draw, e.g. "L3".
- `label`: the field that names each row (name, item, group), or "pair" for rows with a and b.
- `value`: the numeric field to draw (revenue, orders, coOrders, lift, betweenness).
- `title`: what the chart shows, in a few words, no numbers. Write it in the language the
  question is written in, whatever language the product types and the tool results are in.
"""


class Chart(BaseModel):
    """A chart as a pointer at ledger data: the app draws it."""

    type: Literal["bar", "pie", "heatmap"]
    title: str
    source: str
    label: str
    value: str


class Drawing(BaseModel):
    """What the scientist returns: a chart, or none."""

    chart: Chart | None


def chart_problems(chart: Chart, ledger: list[dict]) -> list[str]:
    """Why a chart cannot be drawn as specified; empty when it can. Code, no model."""
    entry = next((e for e in ledger if e["id"] == chart.source), None)
    if entry is None:
        return [f"{chart.source} is not in the ledger"]
    rows = entry["result"]
    if not isinstance(rows, list) or len(rows) < 3 or not all(isinstance(r, dict) for r in rows):
        return [f"{chart.source} is not a list of at least 3 rows"]
    problems = []
    if not all(isinstance(r.get(chart.value), int | float) for r in rows):
        problems.append(f"`{chart.value}` is not a number in every row of {chart.source}")
    paired = all("a" in r and "b" in r for r in rows)
    if chart.type == "heatmap" and not paired:
        problems.append("a heat map needs rows with `a` and `b`")
    if chart.label == "pair" and not paired:
        problems.append("`pair` labels need rows with `a` and `b`")
    if chart.label != "pair" and not all(chart.label in r for r in rows):
        problems.append(f"`{chart.label}` is not a field of every row of {chart.source}")
    if chart.type == "pie" and not 3 <= len(rows) <= 6:
        problems.append("a pie takes 3 to 6 rows")
    return problems


def summary(ledger: list[dict]) -> list[dict]:
    """The ledger as the scientist needs it: what each call was and the shape of its result."""
    shapes = []
    for entry in ledger:
        rows = entry["result"]
        listed = isinstance(rows, list) and rows and isinstance(rows[0], dict)
        shape = {"rows": len(rows), "fields": list(rows[0])} if listed else {"rows": 0}
        shapes.append({"id": entry["id"], "tool": entry["tool"], "args": entry["args"], **shape})
    return shapes


async def draw(question: str, reply: dict, run: Run) -> Chart | None:
    """The chart for an answer, or None: the scientist chose none, or its chart cannot be drawn."""
    views = json.dumps(reply["views"], ensure_ascii=False)
    agent = Agent[Run](
        name="Constella AI scientist",
        instructions=RULES.format(views=views),
        tools=TOOLS,
        model=os.environ.get("OPENAI_MODEL"),  # unset: the SDK's default model
        model_settings=ModelSettings(reasoning=Reasoning(effort="low")),
        output_type=Drawing,
    )
    brief = {"question": question, "answer": reply["text"], "ledger": summary(run.ledger)}
    progress.step("scientist")
    result = await Runner.run(agent, json.dumps(brief, ensure_ascii=False), context=run)
    chart = result.final_output.chart
    return chart if chart and not chart_problems(chart, run.ledger) else None
