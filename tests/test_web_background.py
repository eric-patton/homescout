"""What a slow operation is allowed to hold while it runs.

The fault these pin was reported as 502s from a reverse proxy and looked like a crashed server. It
was not. A pass over the store took the interface's own request lock and held it for the whole run,
so every page and every API call queued behind it, including the progress endpoint whose entire job
is to say how the run is going. Measured against a real database: a request that normally answered
in 0.29s took 15.6s, and a pass over everything would have held the site for the better part of an
hour.

The guarantee that mattered is kept and is tested here too: two heavy operations still do not run at
the same time. What changed is who waits for them, which is now nobody.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from homescout import api
from homescout.web.app import build
from web_fakes import ORIGIN, STATIC, held_workspace, ours, shared_store

#: Long enough that a request queueing behind the task cannot pass by luck, short enough that a
#: broken build fails a test run rather than stalling it.
HELD_FOR = 3.0

#: What a request may take while a pass is running. Generously more than a request costs and far
#: less than the pass, so this cannot pass by being fast.
PATIENCE = 1.5


@pytest.fixture
def interface(db_path: Path) -> Any:
    """The app over a connection opened the way the server opens one."""
    from fastapi.testclient import TestClient

    store = shared_store(db_path)
    held = held_workspace(store)
    app = build(held)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, app, held
    store.close()


def test_a_pass_does_not_hold_the_lock_every_request_takes(interface) -> None:
    """feat-010/AC-64: a slow operation must not stop the interface answering.

    The direct statement of the fault. A task is started that does nothing but wait, and while it
    waits the lock that every database-touching request has to take is asked for. Under the old
    arrangement this lock was held by the task for its whole duration and this assertion failed
    after the task's own timeout; under the fixed one it is free the entire time.
    """
    _client, app, held = interface

    began = threading.Event()
    release = threading.Event()

    def work(mine: api.Workspace, say: Any) -> None:
        assert mine is not held, "the pass must not be handed the interface's own workspace"
        began.set()
        release.wait(HELD_FOR)

    app.state.runs.start_task("extract", work, held)
    assert began.wait(HELD_FOR), "the task never started"

    try:
        # `False` here is the whole test: not "eventually", but "not held at all".
        assert app.state.lock.acquire(blocking=False), (
            "a background pass is holding the interface's request lock, so every page and every "
            "API call is queued behind it for as long as the pass takes"
        )
        app.state.lock.release()
    finally:
        release.set()


def test_the_progress_endpoint_answers_while_its_own_task_runs(interface) -> None:
    """feat-010/AC-64: the page asking how a run is going must not queue behind that run.

    The symptom as a person met it. Watching a pass is a poll every second and a half against
    `/api/tasks/{name}`, which needs the database and therefore took the lock the pass was holding.
    Every poll timed out, the proxy turned that into a 502, and the panel that was meant to show
    progress showed nothing at all.
    """
    client, app, held = interface

    began = threading.Event()
    release = threading.Event()

    def work(mine: api.Workspace, say: Any) -> None:
        say("working")
        began.set()
        release.wait(HELD_FOR)

    app.state.runs.start_task("slow", work, held)
    assert began.wait(HELD_FOR), "the task never started"

    try:
        started = time.monotonic()
        answered = client.get("/api/tasks/slow", headers=ours())
        took = time.monotonic() - started

        assert answered.status_code == 200
        assert took < PATIENCE, f"the progress endpoint took {took:.1f}s while its own task ran"
        assert answered.json()["running"] is True
        assert "working" in answered.json()["progress"]
    finally:
        release.set()


def test_two_heavy_operations_still_do_not_run_at_once(interface) -> None:
    """feat-010/AC-64, feat-010/AC-85: dropping the request lock must not let two passes overlap.

    The half of the old behaviour that was right. One lock was doing two jobs and only one of them
    was worth doing, so this pins that the surviving one survived - and that it survived somewhere
    better. It is no longer a lock in this process but a refusal in the core, read from what the
    store says, which means it now covers a pass started by the scheduled job as well.
    """
    _client, app, held = interface

    running = threading.Semaphore(0)
    overlapped: list[bool] = []
    inside = threading.Lock()
    depth = [0]
    release = threading.Event()

    def work(mine: api.Workspace, say: Any) -> None:
        with inside:
            depth[0] += 1
            overlapped.append(depth[0] > 1)
        running.release()
        release.wait(HELD_FOR)
        with inside:
            depth[0] -= 1

    app.state.runs.start_task("first", work, held)
    app.state.runs.start_task("second", work, held)

    try:
        assert running.acquire(timeout=HELD_FOR), "neither task started"
        assert not any(overlapped), "two heavy operations ran at the same time"
    finally:
        release.set()


def test_a_pass_gets_a_database_connection_of_its_own(db_path: Path) -> None:
    """feat-010/AC-64: the connection is what makes the rest of this safe.

    Not an implementation detail. Sharing the interface's single connection is exactly why the lock
    had to be held for the whole pass, so a second view of the same workspace with a connection of
    its own is the fix rather than a tidying of it.
    """
    store = shared_store(db_path)
    held = held_workspace(store)

    try:
        with api.open_beside(held) as beside:
            assert beside.store is not held.store
            assert beside.store.connection is not held.store.connection
            assert beside.store.path == held.store.path
            # Shared because it reads files; rebuilt because it is bound to a store.
            assert beside.catalog is held.catalog
            assert beside.queue is not held.queue
            # Registering process-wide would hand the server's threads somebody else's connection.
            assert beside.owns_boundaries is False
            # Both answer at the same time, which is the thing write-ahead logging is for.
            assert isinstance(beside.store.listings(), list)
            assert isinstance(held.store.listings(), list)
            kept = beside.store
    finally:
        store.close()

    # Given back on the way out, so a pass cannot leave a connection open for the life of the
    # process. One per pass, and there is a pass every night.
    with pytest.raises(sqlite3.ProgrammingError):
        kept.listings()


def test_one_threads_geography_stays_on_that_thread() -> None:
    """feat-010/AC-64: a thread's own boundary provider must not outlive it or escape it.

    A search that filters by area resolves place names through a database connection, so a pass has
    to resolve them through the one it holds. Registering that the usual way is process-wide, which
    would hand every other thread a connection belonging to this one, and would leave the process
    resolving geography through a connection that has since been closed.
    """
    from homescout.search.boundaries import boundaries, boundaries_on_this_thread

    before = boundaries()
    mine = object()
    seen: list[Any] = []

    def elsewhere() -> None:
        seen.append(boundaries())

    with boundaries_on_this_thread(mine):
        assert boundaries() is mine, "this thread did not get its own provider"
        other = threading.Thread(target=elsewhere)
        other.start()
        other.join(timeout=5)

    assert seen == [before], "one thread's provider was visible to another"
    assert boundaries() is before, "the provider was not put back"

def test_a_pass_started_elsewhere_refuses_the_button(interface) -> None:
    """feat-010/AC-85: one at a time means on this machine, not in this process.

    The case the old per-process rule could not see. The scheduled nightly job runs in its own
    process, so pressing a button in the browser while it was extracting started a second extraction
    over the same store: the same descriptions asked about twice, at twice the cost, each slowing
    the other. The store is what both processes have in common, so the refusal is read from there.
    """
    client, app, held = interface

    release = threading.Event()
    began = threading.Event()

    def elsewhere(mine: api.Workspace, say: Any) -> None:
        began.set()
        release.wait(HELD_FOR)

    app.state.runs.start_task("extract", elsewhere, held)
    assert began.wait(HELD_FOR), "the first pass never started"

    try:
        answered = client.post("/api/enrich", json={}, headers=ours())
        assert answered.status_code == 200
        body = answered.json()
        assert body["already_running"] is True
        # Named, because a refusal about a pass you did not start and cannot see is one nobody can
        # act on.
        assert body["running"] == "extract"
        assert body["started_at"]
    finally:
        release.set()


# -- coming back to a pass that is already running -------------------------


def test_the_tools_page_asks_whether_anything_is_running_when_it_loads() -> None:
    """feat-010/AC-83: the gap this change exists to close.

    The page fetched the configuration and the notes and never asked about a pass, so extraction
    could be twenty minutes in and the page looked idle with the button sitting there inviting a
    second press. The live panel was real; it was started in exactly one place, the button handler.
    """
    settings = (STATIC / "settings.js").read_text(encoding="utf-8")
    assert "rejoinAnythingRunning()" in settings, "the tools surface never asks on load"
    assert "TOOL_PASSES" in settings, "it must ask about each of its passes, not only one"
    for kind in ("enrich", "extract", "deliver", "broadband"):
        assert f'"{kind}"' in settings

    searches = (STATIC / "searches.js").read_text(encoding="utf-8")
    assert "rejoinAnythingRunning()" in searches, "the list of searches never asks on load"
    assert "entry.running" in searches, "it must pick up the run its own cards already know about"


def test_every_screen_carries_the_marker() -> None:
    """feat-010/AC-84: one ask on one schedule, in the frame every page draws.

    In `nav` rather than in nine HTML files and started from there rather than by each surface
    remembering to, because a surface that forgets is a screen that silently says nothing.
    """
    common = (STATIC / "common.js").read_text(encoding="utf-8")
    assert "watchTheMachine()" in common
    assert 'el("span", {id: "running"' in common, "the marker has nowhere to be drawn"
    assert "/api/under-way" in common, "the marker must ask the one endpoint, not one per kind"

    # Six surfaces polling for themselves would be six answers that can disagree.
    assert common.count("/api/under-way") == 1

    # It runs on the results table too, whose own read is the most expensive here.
    assert "RUNNING_EVERY" in common


def test_the_marker_removes_itself_and_remeasures() -> None:
    """feat-010/AC-84: it goes away on its own, and the table below it still fits.

    Appearing and disappearing both change the height above a table that measures its own, which is
    the fault AC-53 exists to prevent, reintroduced by a marker.
    """
    common = (STATIC / "common.js").read_text(encoding="utf-8")
    strip = common[common.index("function watchTheMachine"):common.index("async function rejoin")]
    assert "where.replaceChildren()" in strip, "an idle machine must draw nothing at all"
    assert "fit === \"function\"" in strip, "a change in height must remeasure the table"


def test_a_stopped_pass_is_never_drawn_as_running_or_as_finished() -> None:
    """feat-010/AC-83: what the store cannot distinguish, the screen must not pretend to."""
    for name in ("common.js", "searches.js"):
        body = (STATIC / name).read_text(encoding="utf-8")
        assert 'status.status === "stopped"' in body, f"{name} does not read the stopped state"
        assert "stopped without finishing" in body


def test_what_is_under_way_is_one_endpoint(interface) -> None:
    """feat-010/AC-84: and it answers with nothing when nothing is happening."""
    client, app, held = interface

    answered = client.get("/api/under-way", headers=ours())
    assert answered.status_code == 200
    assert answered.json()["passes"] == []

    release = threading.Event()
    began = threading.Event()

    def work(mine: api.Workspace, say: Any) -> None:
        say("working")
        began.set()
        release.wait(HELD_FOR)

    app.state.runs.start_task("extract", work, held)
    assert began.wait(HELD_FOR)
    try:
        passes = client.get("/api/under-way", headers=ours()).json()["passes"]
        assert [p["task"] for p in passes] == ["extract"]
        assert passes[0]["running"] is True
    finally:
        release.set()
