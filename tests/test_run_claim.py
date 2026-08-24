"""One run of a saved search at a time, across processes.

A scheduled task and a person at a terminal are two processes, so these use two processes. Anything
less would test a lock against itself.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli_fakes import FakeSource, row, search, workspace
from homescout import api
from homescout.claim import RunInProgress, claim_path, claim_run
from homescout.store import Store

HOLDER = """
import sys, time
sys.path.insert(0, {src!r})
from pathlib import Path
from homescout.claim import claim_run

held = dict(run_id="held-run", started_at="2026-08-23T09:00:00Z")
with claim_run(Path(sys.argv[1]), sys.argv[2], **held):
    print("HELD", flush=True)
    time.sleep(float(sys.argv[3]))
"""


def hold(directory: Path, name: str, seconds: float = 30.0) -> subprocess.Popen[str]:
    """Start a real second process holding the claim, and wait until it has it."""
    source = str(Path(__file__).resolve().parents[1] / "src")
    child = subprocess.Popen(
        [sys.executable, "-c", HOLDER.format(src=source), str(directory), name, str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None
    assert child.stdout.readline().strip() == "HELD", "the other process never took the claim"
    return child


def test_a_second_run_declines_and_says_which_one_is_going(tmp_path: Path) -> None:
    """feat-003/AC-26: it declines rather than waits, and it says enough to act on."""
    other = hold(tmp_path, "portales")
    try:
        with pytest.raises(RunInProgress) as raised, claim_run(tmp_path, "portales"):
            pytest.fail("the claim was taken twice")
    finally:
        other.kill()
        other.wait()

    message = str(raised.value)
    assert "held-run" in message
    assert "2026-08-23T09:00:00Z" in message
    assert "declined rather than waiting" in message


def test_declining_is_immediate(tmp_path: Path) -> None:
    """feat-003/AC-26: there is no wait, so a scheduled task is never queued behind a manual run."""
    other = hold(tmp_path, "portales")
    try:
        started = time.monotonic()
        with pytest.raises(RunInProgress), claim_run(tmp_path, "portales"):
            pass
        elapsed = time.monotonic() - started
    finally:
        other.kill()
        other.wait()

    assert elapsed < 1.0, "declining took long enough to look like waiting"


def test_a_claim_left_by_a_killed_process_does_not_block_the_next_run(tmp_path: Path) -> None:
    """feat-003/AC-26: no staleness policy, because the operating system already has one.

    This is the whole argument for a file lock over a file holding a process id: the holder is
    killed without any chance to clean up, and the claim is free anyway.
    """
    other = hold(tmp_path, "portales")
    other.kill()
    other.wait()

    with claim_run(tmp_path, "portales", run_id="the-next-one"):
        pass  # taken without complaint

    assert claim_path(tmp_path, "portales").exists(), "the file stays; only the lock was released"


def test_two_different_searches_do_not_block_each_other(tmp_path: Path) -> None:
    """feat-003/AC-26: the claim is per saved search, not per machine."""
    other = hold(tmp_path, "portales")
    try:
        with claim_run(tmp_path, "clovis"):
            pass
    finally:
        other.kill()
        other.wait()


def test_two_search_names_that_slug_the_same_get_different_claims(tmp_path: Path) -> None:
    """feat-003/AC-26: a claim two searches share would stop one of them for no reason."""
    assert claim_path(tmp_path, "North Side") != claim_path(tmp_path, "north-side")


def test_a_run_of_a_search_already_running_declines_before_touching_the_store(
    store: Store, db_path: Path
) -> None:
    """feat-003/AC-26: the run in progress is entirely unaffected, because nothing was started."""
    other = hold(db_path.parent, "portales")
    try:
        space = workspace(store, searches=[search()], sources={"fake": FakeSource(rows=[row("a")])})
        with pytest.raises(RunInProgress):
            api.run_search(space, "portales")
    finally:
        other.kill()
        other.wait()

    assert store.runs() == [], "no run row was written by the one that declined"
