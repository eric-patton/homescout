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
from web_fakes import ORIGIN, held_workspace, ours, shared_store

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

    client.post("/api/extract", json={"limit": 1}, headers=ours())
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
    """feat-010/AC-64: dropping the request lock must not let two passes fight over the store.

    The half of the old behaviour that was right. One lock was doing two jobs, and only one of them
    was worth doing; this pins that the surviving one survived.
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
