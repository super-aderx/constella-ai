"""Progress: what a run is doing now, for the app to show while the answer is being made.

Each role reports when it starts, and each tool call when it is made. A request that wants to
follow its run listens (main.ask_stream); with no listener, reporting does nothing, so the
roles need not know whether anyone is watching.
"""

from collections.abc import Callable
from contextvars import ContextVar

# Per request: a task started for one request sees only that request's listener, and so do the
# worker threads its tools run in.
_listener: ContextVar[Callable[[dict], None] | None] = ContextVar("listener", default=None)


def listen(send: Callable[[dict], None]) -> None:
    """Sends every step of the current task's run to `send`. It may be called from a thread."""
    _listener.set(send)


def step(name: str, **detail) -> None:
    """Reports that a step has started: a role ("analyst"), or "tool" with the call made."""
    if send := _listener.get():
        send({"step": name, **detail})
