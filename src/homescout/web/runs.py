"""Starting a run from a screen, and answering "what is it doing" while it does it.

A run takes minutes, because politeness is a requirement rather than a nicety, and an HTTP request
that takes minutes is one a browser gives up on. So a run started here goes into a thread and the
page asks how it is going.

Four things about that are deliberate.

**The progress text is the run's own.** It is the same callback the terminal prints, so what a
screen shows and what a terminal shows are the same words rather than two descriptions of the same
thing.

**Nothing here holds up a request.** A pass gets a database connection of its own, so the site keeps
answering for as long as one takes. It did not always: the interface's request lock was held for the
whole of a run, which turned a twenty-minute pass into twenty minutes of a site that answered
nothing, including the endpoint that was meant to report the pass. See `api.open_beside`.

**Nothing here remembers anything.** What a pass is doing is recorded by the core, in the store, and
read back from there. This module used to hold it in a dictionary, which made a pass invisible to a
page that had not pressed the button, invisible to a terminal, and gone entirely when the process
restarted. Two answers to one question is also how they come to disagree, so there is one now:
`api.under_way` and `api.last_pass`. What is left here is the thread.

**Nothing here decides whether two may run at once.** The core refuses one long operation while
another is under way, from what the store says rather than from what this process happens to know,
so the browser will not start an extraction while the scheduled job is already running one. It used
to be a lock in this module, which could only ever see this server's own work.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from .. import api


class Tracker:
    """Starts long work on a thread. Holds no state about it.

    Per process, and there is nothing here worth persisting: what is durable about a pass is in the
    store, written by the core, and this is only the thread that runs it.
    """

    def start(self, workspace: api.Workspace, name: str) -> dict[str, Any]:
        """Run one saved search."""
        return self._go("run", workspace, subject=name, extra={"search": name})

    def start_all(self, workspace: api.Workspace) -> dict[str, Any]:
        """Run every saved search, which is what a scheduled night does.

        Paused and archived ones are left alone by the core, and reported by it as skipped rather
        than passed over in silence.
        """
        return self.start_task(
            "run-all", lambda mine, say: api.run_all(mine, progress=say), workspace
        )

    def start_task(
        self, name: str, work: Any, workspace: api.Workspace, *, subject: str | None = None
    ) -> dict[str, Any]:
        """Anything that takes minutes: every search, an enrichment pass, extraction, a digest.

        What comes back is a token to ask about, and what it says is whatever the operation's own
        progress callback said, which is the same text the terminal prints.

        `work` is handed a workspace rather than closing over one, because the workspace it gets is
        not the interface's: it has its own database connection, so the site keeps answering while
        this runs. See `api.open_beside` for why that is safe here and nowhere else.
        """
        return self._go(name, workspace, subject=subject, work=work)

    def _go(
        self,
        kind: str,
        workspace: api.Workspace,
        *,
        subject: str | None = None,
        work: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Refuse if one is already going, otherwise start it and answer at once.

        The refusal is the core's and covers every process on this machine, so "already running"
        means what a person would assume rather than "already running in this server".
        """
        found = api.already_running(workspace)
        answer: dict[str, Any] = {"task": kind, **(extra or {})}
        if found is not None:
            # Named, because "already running" about a pass you did not start and cannot see is a
            # refusal nobody can act on. It may well be the scheduled job.
            return {
                **answer,
                "already_running": True,
                "running": found.kind,
                "running_on": found.subject,
                "started_at": found.started_at,
            }

        recorded = threading.Event()

        def go() -> None:
            try:
                with api.open_beside(workspace) as mine, api.recording(
                    mine, kind, subject=subject
                ) as say:
                    recorded.set()
                    if work is not None:
                        outcome = work(mine, say)
                    else:
                        outcome = api.run_search(mine, subject or "", progress=say)
                    api.recorded(mine, say, _describe(outcome))
            except Exception:  # noqa: BLE001 - a failure is an answer, and `recording` wrote it down
                pass
            finally:
                recorded.set()

        threading.Thread(target=go, name=f"homescout-{kind}", daemon=True).start()
        # Waited for so that this answer and the poll that follows it cannot disagree: without it a
        # page can ask what is running before the row exists and be told, correctly and uselessly,
        # that nothing is.
        recorded.wait(timeout=5.0)
        return {**answer, "already_running": False}

    def task_status(self, workspace: api.Workspace, name: str) -> dict[str, Any]:
        """What the most recent pass of this kind is doing, or did."""
        return api.last_pass(workspace, name)

    def status(self, workspace: api.Workspace, name: str) -> dict[str, Any]:
        """What a run of this search is doing, on top of what the store knows about any run.

        Both halves, because they answer different questions. `run_status` says whether a run is
        recorded as under way and what the last completed one found; the pass says what it has
        printed while doing it, which is the half that used to exist only in this process.
        """
        found = api.run_status(workspace, name)
        held = api.last_pass(workspace, "run", subject=name)
        found.update(
            {
                "progress": held.get("progress", []),
                "finished": bool(held.get("finished", not found["running"])),
                "failed": held.get("failed"),
                "outcome": held.get("outcome"),
                "started_here": bool(held.get("started")),
                "status": held.get("status"),
            }
        )
        return found


def _describe(outcome: Any) -> dict[str, Any] | None:
    """What an operation produced, in the shape a page can read without knowing which one it was.

    Deliberately shallow. Each of these already has a proper document elsewhere; what a progress
    panel needs is a sentence and whether anything went wrong. A run says more than a sentence, and
    the page that shows a run reads all of it, so a run's own counts and per-source outcomes travel
    here too: that is AC-13's "per-source outcomes are shown on completion" surviving a reload.
    """
    if outcome is None:
        return None
    if isinstance(outcome, Mapping):
        return dict(outcome)

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
    found: dict[str, Any] = {"summary": ", ".join(said) or "done", "degraded": degraded}

    run = getattr(outcome, "run", None)
    if run is not None:
        found["run_id"] = getattr(run, "id", None)
        comparison = getattr(outcome, "comparison", None)
        if comparison is not None:
            found["counts"] = dict(getattr(comparison, "counts", {}) or {})
        found["sources"] = [
            {
                "source": report.source,
                "outcome": report.outcome,
                "rows": report.rows,
                "detail": report.detail,
            }
            for report in getattr(outcome, "sources", ()) or ()
        ]
    return found
