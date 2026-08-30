"""What a long operation records about itself, and who can read it.

The question that produced this: "Does the UI say when it is running and show the progress on the
screen so you can come back to it to see how far along it is in realtime?" It did not, and the
reason was here rather than on the screens. What a pass was doing lived in the memory of whichever
process started it, so a reload showed an idle-looking page, a terminal could not see the browser's
work, the browser could not see the nightly job's, and restarting the server made a pass that was
still running vanish rather than stop.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from homescout import api
from homescout.errors import PreconditionNotMet
from homescout.redact import scrub
from homescout.store import Store
from homescout.store import core as store_core


@pytest.fixture
def store(tmp_path: Path) -> Store:
    with Store.open(tmp_path / "homescout.db") as opened:
        yield opened


# -- what is recorded ------------------------------------------------------


def test_a_pass_records_that_it_is_under_way(store: Store) -> None:
    """feat-001/AC-31: the fact of the operation, the words it said, and how it ended."""
    held = store.begin_pass("extract")
    store.say_on_pass(held.id, "extract: 10 descriptions to ask about")

    running = store.passes_running()
    assert [p.kind for p in running] == ["extract"]
    assert running[0].lines == ("extract: 10 descriptions to ask about",)

    done = store.finish_pass(held.id, outcome={"summary": "10 asked"})
    assert done.status == "completed"
    assert done.outcome == {"summary": "10 asked"}
    assert store.passes_running() == []


def test_a_failure_is_recorded_as_one(store: Store) -> None:
    """feat-001/AC-31: failed is a terminal state and is not the same as stopped."""
    held = store.begin_pass("enrich")
    done = store.finish_pass(held.id, failed="the provider refused")
    assert done.status == "failed"
    assert done.failed == "the provider refused"


def test_a_pass_may_only_move_forwards(store: Store) -> None:
    """feat-001/AC-31, feat-001/AC-2: a lifecycle row, and it moves once.

    The same rule `runs` has and for the same reason. It is what stops a finished pass being
    reopened, quietly, by anything that still holds its id.
    """
    held = store.begin_pass("deliver")
    store.finish_pass(held.id, outcome={"summary": "written"})
    with pytest.raises(sqlite3.IntegrityError):
        store.finish_pass(held.id, failed="no")


def test_a_search_run_is_one_operation_and_not_two(store: Store) -> None:
    """feat-001/AC-31: the pass carries the run's id, so the two are one thing."""
    run = store.start_run("portales")
    held = store.begin_pass("run", subject="portales", run_id=run.id)
    assert store.get_pass(held.id).run_id == run.id
    assert store.get_pass(held.id).subject == "portales"


# -- stopped without finishing --------------------------------------------


def test_a_pass_nobody_ended_reads_as_stopped(store: Store, monkeypatch) -> None:
    """feat-001/AC-31: never running, never completed, never failed.

    Only the pass itself can move its row, so a killed process leaves one saying "running" for ever.
    Drawn, that is a progress panel that never advances and never ends. Computed on read, because
    the only process that could have written it is the one that died.
    """
    held = store.begin_pass("extract")
    assert store.get_pass(held.id).status == "running"

    monkeypatch.setattr(store_core, "PASS_STOPPED_AFTER", -1)
    stopped = store.get_pass(held.id)
    assert stopped.status == "stopped"
    assert not stopped.running
    assert stopped.finished
    # And it is out of the way of anything drawing what is happening now.
    assert store.passes_running() == []


def test_a_pass_that_is_merely_quiet_is_not_stopped(store: Store) -> None:
    """feat-001/AC-31: the heartbeat is why silence is not death.

    Extraction says one line and then asks a model about ten descriptions, which is minutes. A row
    whose freshness came only from its last line would read as abandoned while it was working.
    """
    held = store.begin_pass("extract")
    store.say_on_pass(held.id, "extract: 10 descriptions to ask about")
    store.touch_pass(held.id)
    assert store.get_pass(held.id).status == "running"
    assert store_core.PASS_STOPPED_AFTER > store_core.PASS_HEARTBEAT_SECONDS


# -- nothing written here may carry a credential --------------------------


def test_a_failure_carrying_a_key_is_stored_without_it(store: Store) -> None:
    """feat-001/AC-31: the finding that held the pre-build check, and why it mattered.

    Recording changes where a failure lives. It used to be a string in one process, gone when that
    process exited; now it is bytes in a database file this product tells you to keep a backup of.
    The extraction layer already strips credentials out of its own per-description failures, for the
    stated reason that an address with a query string can carry a key - and that stripping was
    applied at one call site and not to the exception that ends a pass, which is exactly the string
    this makes durable.

    Asserted through the store rather than through the scrubber, because the requirement is that the
    one function that writes does it, not that a function exists which could.
    """
    leaked = "https://proxy.example.invalid/v1/chat?api_key=sk-proj-AAAABBBBCCCCDDDDEEEE"

    held = store.begin_pass("extract")
    store.say_on_pass(held.id, f"could not reach {leaked}")
    store.finish_pass(held.id, failed=f"gave up on {leaked}")

    written = store.get_pass(held.id)
    assert "sk-proj-AAAABBBBCCCCDDDDEEEE" not in written.lines[0]
    assert "sk-proj-AAAABBBBCCCCDDDDEEEE" not in (written.failed or "")
    # The address survives, because a failure that cannot say where it was talking to is a failure
    # nobody can act on. Only the part after the question mark goes.
    assert "proxy.example.invalid" in written.lines[0]


def test_the_scrubber_leaves_ordinary_progress_alone() -> None:
    """feat-001/AC-31: a scrubber that eats real messages is one somebody turns off."""
    for said in (
        "extract: 10 descriptions to ask about, 5 already answered",
        "realtor answered 403; 12 rows kept",
        "the run could not finish: no such search 'portales'",
    ):
        assert scrub(said, {}) == said


def test_a_recorded_line_is_bounded(store: Store) -> None:
    """feat-001/AC-31: a line can carry a remote server's refusal, and that is durable now."""
    held = store.begin_pass("enrich")
    store.say_on_pass(held.id, "x" * (store_core.PASS_LINE_LIMIT * 3))
    assert len(store.get_pass(held.id).lines[0]) == store_core.PASS_LINE_LIMIT


def test_only_so_many_lines_are_kept(store: Store) -> None:
    """feat-001/AC-31: the same bound the in-memory version had, where the lines now live."""
    held = store.begin_pass("run", subject="portales")
    for i in range(store_core.PASS_KEPT_LINES + 25):
        store.say_on_pass(held.id, f"line {i}")
    lines = store.get_pass(held.id).lines
    assert len(lines) == store_core.PASS_KEPT_LINES
    assert lines[-1] == f"line {store_core.PASS_KEPT_LINES + 24}"


# -- whoever asks gets the same answer ------------------------------------


def test_a_pass_outlives_the_thing_that_started_it(tmp_path: Path) -> None:
    """feat-001/AC-31, feat-010/AC-83: the point of putting it in the store at all.

    Observed before it was specified: after the server was restarted mid-session, the interface
    reported that extraction had never been started. The work was still going; every trace of it
    had been in the memory of a process that no longer existed.
    """
    db = tmp_path / "homescout.db"
    with Store.open(db) as first:
        held = first.begin_pass("extract")
        first.say_on_pass(held.id, "extract: 10 descriptions to ask about")

    # A different connection entirely, which is what a restarted server and a terminal both are.
    with Store.open(db) as second:
        running = second.passes_running()
        assert [p.kind for p in running] == ["extract"]
        assert running[0].lines == ("extract: 10 descriptions to ask about",)


def test_the_overview_carries_what_is_under_way(tmp_path: Path) -> None:
    """feat-010/AC-84, invariant 5: reachable from both surfaces without a new command.

    `overview` is already on the command line with `--json` and already on the landing screen. That
    is what makes this satisfy "every capability is reachable from both" without inventing a verb
    for a question the product already asks.
    """
    from cli_fakes import workspace

    opened = Store.open(tmp_path / "homescout.db")
    try:
        space = workspace(opened)
        assert api.overview(space)["under_way"] == []

        opened.begin_pass("enrich")
        under = api.overview(space)["under_way"]
        assert [p["task"] for p in under] == ["enrich"]
        # `task`, not `kind`: these documents are splatted flat into an envelope whose own key is
        # `kind`, and `task` is what the pages already called it.
        assert "kind" not in under[0]
    finally:
        opened.close()


# -- one at a time, on this machine ---------------------------------------


def test_a_second_pass_is_refused_while_one_is_running(tmp_path: Path) -> None:
    """feat-010/AC-85: the case the old per-process rule could not see.

    The browser used to know only about its own work, so pressing a button while the scheduled
    nightly job was extracting started a second extraction over the same store: the same
    descriptions asked about twice, at twice the cost, each slowing the other.
    """
    from cli_fakes import workspace

    with Store.open(tmp_path / "homescout.db") as opened:
        space = workspace(opened)
        with api.recording(space, "extract") as say:
            say("working")
            # Any long operation blocks any other, not merely another of the same kind: two are
            # paced against the same sources and write to the same file, so the second only makes
            # the first take longer.
            with pytest.raises(PreconditionNotMet) as refused, api.recording(space, "enrich"):
                pass
        assert "extract" in str(refused.value)
        assert "already running" in str(refused.value)


def test_a_typed_command_is_never_refused_by_a_background_pass(tmp_path: Path) -> None:
    """feat-010/AC-85: the refusal guards a button, not a person at a keyboard.

    `alone=False` is what the command line passes. Somebody who typed the command has asked for it
    explicitly, and a tool that tells its operator what they may do on their own machine because it
    is busy is a tool that gets worked around.
    """
    from cli_fakes import workspace

    with Store.open(tmp_path / "homescout.db") as opened:
        space = workspace(opened)
        with api.recording(space, "run-all"), api.recording(
            space, "extract", alone=False
        ) as say:
            say("asked anyway")
        assert {p.kind for p in opened.passes_running()} == set()
