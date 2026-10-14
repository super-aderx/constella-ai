"""v2: one agent, the analyst, with tools instead of a data brief (app/roles/analyst.py).

Its reply is reviewed before it goes out. A sound answer with figures then goes to the scientist
(app/roles/scientist.py), which may add a chart drawn from the ledger.
"""

import os
from collections.abc import Sequence

from app.roles.analyst import Reply, Review, analyse
from app.roles.scientist import Chart, draw
from app.tools import Run


class Answer(Reply):
    """The reply, with the run's ledger (every tool call, its arguments and its result) and the
    reviewer's verdict."""

    ledger: list[dict]
    review: Review
    chart: Chart | None


async def chart_for(question: str, reply: Reply, run: Run, verdict: Review) -> Chart | None:
    """The scientist's chart for a reviewed reply, when one is called for."""
    # A chart only for an answer that passed and states figures: there is something to draw, and
    # it is sound. Not for a comparison yet: a chart draws one tool result, so it would show one
    # side only. CHARTS=0 turns the scientist off, for a faster answer.
    wanted = verdict.passed and reply.figures and len(reply.views) == 1
    wanted = wanted and os.environ.get("CHARTS") != "0"
    return await draw(question, reply.model_dump(), run) if wanted else None


async def ask(
    question: str, days: int | None, segment: str | None, ignored: Sequence[str] = ()
) -> Answer:
    reply, run, verdict = await analyse(question, days, segment, ignored=ignored)
    chart = await chart_for(question, reply, run, verdict)
    return Answer(**reply.model_dump(), ledger=run.ledger, review=verdict, chart=chart)
