"""The conversation so far, so a follow-up ("and new customers?", "a smaller discount") can be read.

Earlier turns tell a role what the user means, never what is true: an earlier answer's figures
were checked against its own run's ledger, which this run does not have. So the reviewer never
reads them, and a figure an answer states again has to be looked up again.
"""

from collections.abc import Sequence

from pydantic import BaseModel


class Turn(BaseModel):
    """An earlier question and what the user was told: the answer's text, and the campaigns it
    offered, if any."""

    question: str
    answer: str


def messages(question: str, history: Sequence[Turn] = ()) -> list[dict]:
    """The question as a model's input, after the earlier turns."""
    earlier = [
        message
        for turn in history
        for message in (
            {"role": "user", "content": turn.question},
            {"role": "assistant", "content": turn.answer},
        )
    ]
    return [*earlier, {"role": "user", "content": question}]
