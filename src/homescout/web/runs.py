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

**Nothing here holds up a request.** A pass gets a database connection of its own, so the site
keeps answering for as long as one takes. It did not always: the interface's request lock was held
for the whole of a run, which turned a twenty-minute pass into twenty minutes of a site that
answered nothing, including the endpoint that was meant to report the pass. See `api.open_beside`.
"""

from __future__ import annotations

import threading
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
        self._tasks: dict[str, Progress] = {}
        self._lock = threading.Lock()
        #: One heavy operation at a time, and this is the only thing it holds up.
        #:
        #: It replaces the interface's own request lock, which used to be held for the whole of a
        #: run. That serialised the right things and one wrong one: every page and every API call,
        #: for as long as the run took. This keeps the guarantee that mattered, which is that two
        #: passes do not fight over the store, and drops the one that took the site down.
        self._work = threading.Lock()

    def start(self, workspace: api.Workspace, name: str) -> dict[str, Any]:
        with self._lock:
            existing = self._held.get(name)
            if existing is not None and not existing.finished:
                return {"search": name, "already_running": True}
            held = Progress(search=name)
            self._held[name] = held

        def go() -> None:
            try:
                with self._work, api.open_beside(workspace) as mine:
                    outcome = api.run_search(mine, name, progress=held.say)
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

    def start_all(self, workspace: api.Workspace) -> dict[str, Any]:
        """Run every saved search, which is what a scheduled night does.

        Paused and archived ones are left alone by the core, and reported by it as skipped rather
        than passed over in silence.
        """
        return self.start_task(
            "run-all", lambda mine, say: api.run_all(mine, progress=say), workspace
        )

    def start_task(self, name: str, work: Any, workspace: api.Workspace) -> dict[str, Any]:
        """Anything that takes minutes: every search, an enrichment pass, extraction, a digest.

        The same shape as a run and for the same reason: politeness makes these slow, and an HTTP
        request that takes minutes is one a browser gives up on. What comes back is a token to ask
        about, and what it says is whatever the operation's own progress callback said, which is the
        same text the terminal prints.

        `work` is handed a workspace rather than closing over one, because the workspace it gets is
        not the interface's: it has its own database connection, so the site keeps answering while
        this runs. See `api.open_beside` for why that is safe here and nowhere else.
        """
        with self._lock:
            existing = self._tasks.get(name)
            if existing is not None and not existing.finished:
                return {"task": name, "already_running": True}
            held = Progress(search=name)
            self._tasks[name] = held

        def go() -> None:
            try:
                with self._work, api.open_beside(workspace) as mine:
                    outcome = work(mine, held.say)
                held.outcome = _describe(outcome)
                if not held.lines:
                    held.say("done")
            except Exception as exc:  # noqa: BLE001 - a failure is an answer, not a crash here
                held.failed = str(exc)
                held.say(f"could not finish: {exc}")
            finally:
                held.finished = True

        threading.Thread(target=go, name=f"homescout-{name}", daemon=True).start()
        return {"task": name, "already_running": False}

    def task_status(self, name: str) -> dict[str, Any]:
        held = self._tasks.get(name)
        if held is None:
            return {"task": name, "running": False, "progress": [], "finished": True,
                    "failed": None, "outcome": None, "started": False}
        found = held.snapshot()
        found.update({"task": name, "running": not held.finished, "started": True})
        return found

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




def _describe(outcome: Any) -> dict[str, Any] | None:
    """What an operation produced, in the shape a page can read without knowing which one it was.

    Deliberately shallow. Each of these already has a proper document elsewhere; what a progress
    panel needs is a sentence and whether anything went wrong.
    """
    if outcome is None:
        return None
    degraded = bool(getattr(outcome, "degraded", False))
    said: list[str] = []
    for name in ("properties", "descriptions", "asked", "recorded", "cached"):
        value = getattr(outcome, name, None)
        if value:
            said.append(f"{value} {name.replace('_', ' ')}")
    for name in ("outcomes", "skipped", "failures"):
        value = getattr(outcome, name, None)
        if isinstance(value, tuple | list) and value:
            said.append(f"{len(value)} {name}")
    return {"summary": ", ".join(said) or "done", "degraded": degraded}
