"""Starting a run from a screen, and answering "what is it doing" while it does it.

A run takes minutes, because politeness is a requirement rather than a nicety, and an HTTP request
that takes minutes is one a browser gives up on. So a run started here goes into a thread and the
page asks how it is going.

Two things about that are deliberate.

**The progress text is the run's own.** It is the same callback the terminal prints, so what a
screen shows and what a terminal shows are the same words rather than two descriptions of the same
thing.

**Nothing here stops two runs colliding.** The store's own claim does, which means a run started
here while one is running from a terminal is refused by the core, with the message the core already
has, and the store-is-locked case is answered in the one place that can answer it correctly.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .. import api

#: How many progress lines one run keeps. Enough to watch, few enough that a run over a county does
#: not accumulate a megabyte of text in a process that never restarts.
KEPT_LINES = 200


@dataclass
class Progress:
    """One run in flight, and what it has said."""

    search: str
    lines: list[str] = field(default_factory=list)
    finished: bool = False
    failed: str | None = None
    outcome: dict[str, Any] | None = None
    lock: Any = field(default_factory=threading.Lock)

    def say(self, message: str) -> None:
        with self.lock:
            self.lines.append(message)
            if len(self.lines) > KEPT_LINES:
                del self.lines[: len(self.lines) - KEPT_LINES]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "progress": list(self.lines),
                "finished": self.finished,
                "failed": self.failed,
                "outcome": self.outcome,
            }


class Tracker:
    """The runs this process started, by search name.

    Per process and deliberately not persisted: what is durable about a run is in the store, and
    this holds only the commentary, which is worth nothing once the run is over.
    """

    def __init__(self) -> None:
        self._held: dict[str, Progress] = {}
        self._lock = threading.Lock()

    def start(self, workspace: api.Workspace, name: str, guard: Any = None) -> dict[str, Any]:
        with self._lock:
            existing = self._held.get(name)
            if existing is not None and not existing.finished:
                return {"search": name, "already_running": True}
            held = Progress(search=name)
            self._held[name] = held

        def go() -> None:
            try:
                # The same lock every request takes, because this thread reaches the same single
                # database connection they do.
                with (guard if guard is not None else _nothing()):
                    outcome = api.run_search(workspace, name, progress=held.say)
                held.outcome = {
                    "run_id": outcome.run.id,
                    "degraded": outcome.degraded,
                    "counts": dict(outcome.comparison.counts),
                    "sources": [
                        {
                            "source": report.source,
                            "outcome": report.outcome,
                            "rows": report.rows,
                            "detail": report.detail,
                        }
                        for report in outcome.sources
                    ],
                }
            except Exception as exc:  # noqa: BLE001 - a failed run is an answer, not a crash here
                held.failed = str(exc)
                held.say(f"the run could not finish: {exc}")
            finally:
                held.finished = True

        threading.Thread(target=go, name=f"homescout-run-{name}", daemon=True).start()
        return {"search": name, "already_running": False}

    def status(self, workspace: api.Workspace, name: str) -> dict[str, Any]:  # noqa: D401
        """What this process's run is doing, on top of what the store knows about any run.

        Both halves, because a run started from a terminal is invisible to this tracker and still
        needs to show up on a screen as a run in progress.
        """
        found = api.run_status(workspace, name)
        held = self._held.get(name)
        if held is not None:
            found.update(held.snapshot())
            found["started_here"] = True
        else:
            found["progress"] = []
            found["finished"] = not found["running"]
            found["failed"] = None
            found["outcome"] = None
            found["started_here"] = False
        return found


@contextmanager
def _nothing() -> Any:
    """No lock at all, for a caller that has already taken one or has no threads to worry about."""
    yield
