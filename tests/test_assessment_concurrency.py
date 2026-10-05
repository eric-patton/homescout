"""Bounded concurrent model work with persistence and preparation on one thread."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from homescout import api
from homescout.assess import pass_ as P
from homescout.assess import settings
from homescout.assess.dossier import dossier_for
from homescout.assess.model import Assessment, AssessmentFailed
from test_assessment import FakeAccount, FakeRow, some_criteria
from test_assessment import watched as watched


def test_bounded_overlap_saves_ready_results_on_coordinator_and_resumes(monkeypatch):
    """feat-013/AC-23, feat-013/AC-24: a slow call cannot hide completed later calls."""
    release = threading.Event()
    both = threading.Barrier(2)
    fast_saved = threading.Event()
    owner = []
    callbacks = []
    asked = []
    recorded = {}
    active = 0
    maximum = 0
    guard = threading.Lock()
    crit = some_criteria()
    rows = [FakeRow(str(i)) for i in range(6)]
    said = []

    def ask(_session, _account, dossier, _criteria, _pictures):
        nonlocal active, maximum
        with guard:
            asked.append(dossier.listing_id)
            active += 1
            maximum = max(maximum, active)
        try:
            if dossier.listing_id in ("0", "1"):
                both.wait(timeout=4)
            if dossier.listing_id == "0":
                assert release.wait(4)
            if dossier.listing_id == "3":
                raise AssessmentFailed("a temporary model failure")
            return Assessment(listing_id=dossier.listing_id, account="", model="fake")
        finally:
            with guard:
                active -= 1

    def record(listing_id, result, mark):
        callbacks.append(threading.get_ident())
        assert result.listing_id == listing_id
        recorded[listing_id] = mark
        if listing_id == "1":
            fast_saved.set()

    def pictures(_row, _dossier):
        callbacks.append(threading.get_ident())
        return []

    def progress(line):
        callbacks.append(threading.get_ident())
        said.append(line)

    def run():
        owner.append(threading.get_ident())
        return P.run_pass(rows, account=FakeAccount(), criteria=crit, session=object(),
                          pictures_for=pictures, record=record, progress=progress, concurrency=2)

    monkeypatch.setattr(P, "ask", ask)
    with ThreadPoolExecutor(max_workers=1) as coordinator:
        future = coordinator.submit(run)
        try:
            assert fast_saved.wait(4), "a ready result waited behind the slow first request"
            assert "0" not in recorded
            assert maximum == 2
        finally:
            release.set()
        outcome = future.result(timeout=4)

    assert set(callbacks) == set(owner)
    assert maximum == 2
    assert (outcome.assessed, len(outcome.failures)) == (5, 1)
    assert len(asked) == 6
    assert "6/6 finished, 5 assessed, 0 topped up, 1 failed, 0 remaining" in said[-2]
    # Restart from durable fingerprints: only the failed property is sent again.
    monkeypatch.setattr(P, "ask", lambda _s, _a, d, _c, _p:
                        Assessment(listing_id=d.listing_id, account="", model="fake"))
    resumed = P.run_pass(rows, account=FakeAccount(), criteria=crit, session=object(),
                         already=recorded, record=record, concurrency=2)
    assert (resumed.current, resumed.assessed) == (5, 1)


def test_narrow_questions_finish_before_full_requests(monkeypatch):
    """feat-013/AC-23: existing top-up priority and the limit apply to the whole pool."""
    rows = [FakeRow("full"), FakeRow("top-a"), FakeRow("top-b")]
    crit = some_criteria()
    known = {row.listing_id: P.fingerprint_of(dossier_for(row), crit.stated()) for row in rows[1:]}
    added = []
    read = []
    barrier = threading.Barrier(2)

    def top_up(_s, _a, dossier, _c, _earlier, _pictures):
        barrier.wait(timeout=4)
        return (dossier.listing_id,)

    def ask(_s, _a, dossier, _c, _pictures):
        assert set(added) == {"top-a", "top-b"}
        read.append(dossier.listing_id)
        return Assessment(listing_id=dossier.listing_id, account="", model="fake")

    monkeypatch.setattr(P, "ask_in_favour", top_up)
    monkeypatch.setattr(P, "ask", ask)
    outcome = P.run_pass(rows, account=FakeAccount(), criteria=crit, session=object(),
                         already=known, owed={"top-a": object(), "top-b": object()},
                         add=lambda lid, _points, _prior: added.append(lid), concurrency=2, limit=2)
    assert (outcome.topped_up, outcome.assessed, outcome.left_over) == (2, 0, 1)
    assert read == []
    added.clear()
    outcome = P.run_pass(rows, account=FakeAccount(), criteria=crit, session=object(),
                         already=known, owed={"top-a": object(), "top-b": object()},
                         add=lambda lid, _points, _prior: added.append(lid), concurrency=2)
    assert (outcome.topped_up, outcome.assessed) == (2, 1)
    assert read == ["full"]


def test_preparation_and_submission_are_bounded_by_pool_size(monkeypatch):
    """feat-013/AC-23: a worker cap also bounds queued jobs and picture preparation."""
    release = threading.Event()
    wave = threading.Barrier(3)
    prepared = []

    def ask(_s, _a, dossier, _c, _pictures):
        if dossier.listing_id in ("0", "1"):
            wave.wait(timeout=4)
        assert release.wait(4)
        return Assessment(listing_id=dossier.listing_id, account="", model="fake")

    def pictures(row, _dossier):
        prepared.append(row.listing_id)
        return []

    monkeypatch.setattr(P, "ask", ask)
    with ThreadPoolExecutor(max_workers=1) as coordinator:
        future = coordinator.submit(P.run_pass, [FakeRow(str(i)) for i in range(20)],
            account=FakeAccount(), criteria=some_criteria(), session=object(),
            pictures_for=pictures, concurrency=2)
        try:
            wave.wait(timeout=4)
            assert prepared == ["0", "1"]
        finally:
            release.set()
        assert future.result(timeout=4).assessed == 20


@pytest.mark.parametrize("raw,expected", [("", 8), ("1", 1), ("8", 8), ("32", 32)])
def test_concurrency_configuration(tmp_path, raw, expected):
    """feat-013/AC-23: configuration comes from the ignored environment file or environment."""
    (tmp_path / ".env").write_text(f"{settings.CONCURRENCY}={raw}\n", encoding="utf-8")
    assert settings.concurrency(tmp_path, {}) == expected
    assert settings.concurrency(tmp_path, {settings.CONCURRENCY: "2"}) == 2


@pytest.mark.parametrize("raw", ["0", "-1", "33", "1.5", "eight", "nan"])
def test_bad_concurrency_is_rejected_before_requests(watched, raw, monkeypatch):
    """feat-013/AC-23: a bad setting cannot initiate model spending."""
    monkeypatch.setenv(settings.CONCURRENCY, raw)
    outcome = api.assess(watched.workspace)
    assert settings.CONCURRENCY in outcome.skipped
    assert not any(line.startswith("asked") for line in watched.happened)


def test_default_pool_uses_real_store_and_skips_saved_readings(watched):
    """feat-013/AC-23, feat-013/AC-24: default-worker writes use the store's owning thread."""
    outcome = api.assess(watched.workspace, progress=watched.happened.append)
    assert (outcome.assessed, outcome.current) == (3, 0)
    assert any("up to 8 workers" in line for line in watched.happened)
    assert any("3/3 finished" in line for line in watched.happened)
    watched.happened.clear()
    resumed = api.assess(watched.workspace, progress=watched.happened.append)
    assert (resumed.assessed, resumed.current) == (0, 3)
    assert not any(line.startswith("asked") for line in watched.happened)


def test_owned_session_is_closed_but_injected_session_is_not(watched, monkeypatch):
    """feat-013/AC-23: close worker connections only when the pass owns them."""
    closed = []

    class Session:
        def close(self):
            closed.append(self)

    owned = Session()
    monkeypatch.setattr("homescout.extract.pass_._session", lambda: owned)
    api.assess(watched.workspace)
    assert closed == [owned]
    borrowed = Session()
    P.assess_searches(watched.workspace.store, [watched.workspace.catalog.load("alpha")],
                      root=watched.workspace.root, session=borrowed)
    assert closed == [owned]
