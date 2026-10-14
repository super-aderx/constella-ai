"""v3: roles. A router plans the run, the analyst answers from the tools, the strategist drafts a
campaign when one is asked for and the writer words its slogans, the scientist adds a chart, and
the reviewer's code checks stand between each of them and the user.

    router -> analyst (reviewed) -> strategist (reviewed, if planned) -> writer
           -> scientist (if planned)

The analyst is v2's (roles/analyst.py), unchanged, so v2 and v3 give the same answer to a
question of fact.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from app.roles import router, strategist, writer
from app.roles.analyst import Review, analyse
from app.versions import v2


class Route(BaseModel):
    """What the router planned, for the app to show."""

    route: str
    strategy: bool
    chart: bool


class Answer(v2.Answer):
    """v2's answer, with the plan it was made under and the strategist's campaigns, if any, each
    with the writer's slogans."""

    plan: Route
    strategy: writer.Pitched | None


async def ask(
    question: str, days: int | None, segment: str | None, ignored: Sequence[str] = ()
) -> Answer:
    plan = await router.plan(question)
    route = Route(route=plan.route, strategy=plan.strategy, chart=plan.chart)
    if plan.route == "refuse":
        # Outside the store's sales: no tools are called, so there is nothing to review.
        return Answer(
            text=plan.reply,
            views=[],
            items=[],
            pairs=[],
            figures=[],
            options=plan.options,
            ledger=[],
            review=Review(passed=True, caught=[], notes=[]),
            chart=None,
            plan=route,
            strategy=None,
        )

    reply, run, verdict = await analyse(question, days, segment, plan.strategy, ignored)
    strategy = None
    # A campaign only on findings that passed review, and that state something to build on.
    if plan.strategy and verdict.passed and reply.figures:
        drafted, caught, notes = await strategist.draft(question, reply, run)
        verdict = Review(
            passed=not notes, caught=verdict.caught + caught, notes=verdict.notes + notes
        )
        # Slogans only for campaigns that can run as written: the rest go out with their notes.
        strategy = (
            writer.pitched(drafted) if notes else await writer.write(question, drafted, ignored)
        )
    chart = await v2.chart_for(question, reply, run, verdict) if plan.chart else None
    return Answer(
        **reply.model_dump(),
        ledger=run.ledger,
        review=verdict,
        chart=chart,
        plan=route,
        strategy=strategy,
    )
