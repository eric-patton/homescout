"""The database's own guarantees.

Most of this file talks to a raw connection rather than to the store's API. That is deliberate: the
point of these protections is that they hold for a caller who bypasses the store entirely, and the
only way to prove that is to bypass it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import do_run, prop
from homescout.store import (
    SCHEMA_VERSION,
    HistoryIsAppendOnlyError,
    SchemaTooNewError,
    Store,
    StoreLockedError,
    to_utc_text,
)
from homescout.store.db import translating_errors
from homescout.store.schema import APPEND_ONLY_TABLES


def test_a_new_file_is_created_at_the_current_version(db_path: Path) -> None:
    """feat-001/AC-22: a missing file is created at the version this build understands."""
    assert not db_path.exists()
    with Store.open(db_path) as store:
        assert store.schema_version == SCHEMA_VERSION
    assert db_path.exists()


def test_an_empty_file_is_treated_as_a_new_one(db_path: Path) -> None:
    """feat-001/AC-22: an empty file is initialized rather than rejected."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()
    with Store.open(db_path) as store:
        assert store.schema_version == SCHEMA_VERSION


def test_a_file_from_a_newer_build_is_refused_by_name(db_path: Path) -> None:
    """feat-001/AC-22: a newer schema is refused by name, never opened hopefully."""
    with Store.open(db_path):
        pass
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")
    conn.commit()
    conn.close()

    with pytest.raises(SchemaTooNewError) as caught:
        Store.open(db_path)
    message = str(caught.value)
    assert str(SCHEMA_VERSION + 5) in message
    assert str(SCHEMA_VERSION) in message


def test_reopening_an_existing_file_leaves_its_contents_alone(db_path: Path) -> None:
    """feat-001/AC-22: migration is forward-only and does not disturb what is already there."""
    with Store.open(db_path) as store:
        do_run(store, sources={"realtor": [prop("a1")]})
        first = store.listings()[0].id
    with Store.open(db_path) as store:
        assert [listing.id for listing in store.listings()] == [first]


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_history_tables_refuse_an_update(store: Store, table: str) -> None:
    """feat-001/AC-2: no recorded observation can be edited, by anyone, ever."""
    do_run(store, sources={"realtor": [prop("a1")]})
    conn = store.connection
    row = conn.execute(f"SELECT rowid AS rid FROM {table} LIMIT 1").fetchone()
    assert row is not None, f"{table} should have a row to attempt to rewrite"

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"UPDATE {table} SET rowid = rowid WHERE rowid = ?", (row["rid"],))


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_history_tables_refuse_a_delete(store: Store, table: str) -> None:
    """feat-001/AC-2: recorded history is never removed."""
    do_run(store, sources={"realtor": [prop("a1")]})
    conn = store.connection
    row = conn.execute(f"SELECT rowid AS rid FROM {table} LIMIT 1").fetchone()
    assert row is not None

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (row["rid"],))


def test_a_rewrite_attempt_through_the_store_is_reported_in_plain_words(store: Store) -> None:
    """feat-001/AC-2: the refusal reaches a caller as an error that explains itself."""
    do_run(store, sources={"realtor": [prop("a1")]})
    with pytest.raises(HistoryIsAppendOnlyError, match="never edited"), translating_errors(
        store.path
    ):
        store.connection.execute("DELETE FROM listing_snapshots")


def test_a_listing_identity_cannot_be_rewritten(store: Store) -> None:
    """feat-001/AC-2: presence moves; identity and first observation do not."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing = store.listings()[0]
    conn = store.connection

    with pytest.raises(sqlite3.IntegrityError, match="fixed"):
        conn.execute(
            "UPDATE listings SET first_observed_at = ? WHERE id = ?",
            ("1999-01-01T00:00:00.000000Z", listing.id),
        )
    # But presence is allowed to move, which is what makes disappearance recordable at all.
    conn.execute("UPDATE listings SET presence = 'disappeared' WHERE id = ?", (listing.id,))
    assert store.get_listing(listing.id).presence == "disappeared"


def test_a_completed_run_cannot_be_reopened(store: Store) -> None:
    """feat-001/AC-19: a run's outcome moves forwards once and then stops."""
    run = do_run(store, sources={"realtor": [prop("a1")]})
    with pytest.raises(sqlite3.IntegrityError, match="only go from running"):
        store.connection.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run.id,))


def test_every_stored_timestamp_is_utc(store: Store) -> None:
    """feat-001/AC-23: nothing local is ever written, so ordering is never ambiguous."""
    run = do_run(store, sources={"realtor": [prop("a1")]})
    listing = store.listings()[0]

    stamps = [
        run.started_at,
        run.finished_at,
        listing.first_observed_at,
        store.snapshot_at(listing.id, run.id).observed_at,  # type: ignore[union-attr]
        *[event.occurred_at for event in store.events(listing.id)],
    ]
    assert all(stamp.endswith("Z") for stamp in stamps), stamps
    assert all(datetime.fromisoformat(s.replace("Z", "+00:00")) for s in stamps)


def test_ordering_survives_a_daylight_saving_transition() -> None:
    """feat-001/AC-23: two moments an hour apart across a clock change still sort correctly.

    This is the spring-forward morning in the mountain zone. Locally these read as 01:30 and 03:30,
    two hours apart on the wall clock but one hour apart in reality, and the zone's offset differs
    between them. Written as UTC they are simply an hour apart and sort correctly as text, which is
    the whole point of never storing a local time.

    Fixed offsets rather than a named zone, so the test does not depend on a time zone database
    being installed, which on the target platform it often is not.
    """
    mst = timezone(timedelta(hours=-7))
    mdt = timezone(timedelta(hours=-6))
    before = datetime(2026, 3, 8, 1, 30, tzinfo=mst)
    after = datetime(2026, 3, 8, 3, 30, tzinfo=mdt)

    assert (after - before).total_seconds() == 3600
    assert to_utc_text(before) < to_utc_text(after)
    assert to_utc_text(before) == "2026-03-08T08:30:00.000000Z"
    assert to_utc_text(after) == "2026-03-08T09:30:00.000000Z"


def test_a_naive_timestamp_is_taken_as_utc() -> None:
    """feat-001/AC-23: there is no path by which a local time gets stored as if it were UTC."""
    assert to_utc_text(datetime(2026, 3, 8, 8, 30)) == "2026-03-08T08:30:00.000000Z"


def test_run_order_does_not_depend_on_timestamp_resolution(store: Store) -> None:
    """feat-001/AC-20: "the previous run" is never ambiguous, however close together two runs are.

    Ordering and every "at or before" boundary use insertion sequence rather than the clock, so
    the answer does not rest on timestamp resolution at all.
    """
    first = do_run(store, "same-instant", sources={"realtor": [prop("a1")]})
    second = do_run(store, "same-instant", sources={"realtor": [prop("a1")]})

    assert first.seq < second.seq
    assert store.last_completed_run("same-instant", before_seq=second.seq).id == first.id  # type: ignore[union-attr]
    assert store.last_completed_run("same-instant").id == second.id  # type: ignore[union-attr]


def test_a_locked_database_is_reported_in_terms_of_the_likely_cause(db_path: Path) -> None:
    """feat-001: a lock is routine on this platform, so it must not surface as a raw error.

    The browser interface being open while a scheduled command runs is the normal case, not an
    exotic one, and "database is locked" tells a person nothing about what to do next.
    """
    with Store.open(db_path) as store:
        do_run(store, sources={"realtor": [prop("a1")]})

    blocker = sqlite3.connect(db_path, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with Store.open(db_path, timeout=0.2) as store:  # noqa: SIM117
            with pytest.raises(StoreLockedError) as caught:
                store.start_run("blocked")
        assert "browser interface" in str(caught.value)
        assert str(db_path) in str(caught.value)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()


def test_a_failed_write_leaves_the_last_completed_run_usable(db_path: Path) -> None:
    """feat-001/AC-19: a failure part-way costs the attempt, never the baseline."""
    with Store.open(db_path) as store:
        first = do_run(store, sources={"realtor": [prop("a1", price=400_000)]})

        run = store.start_run("test-search")
        with pytest.raises(sqlite3.IntegrityError):
            store.record_observations("no-such-run", "realtor", [prop("a2")])
        store.fail_run(run.id)

        assert store.last_completed_run("test-search").id == first.id  # type: ignore[union-attr]
        assert len(store.listings()) == 1

        third = do_run(store, sources={"realtor": [prop("a1", price=390_000)]})
        comparison = store.compare("test-search", target_run_id=third.id)
        assert comparison.baseline_run_id == first.id


#: The question the results table asks for every property on it, in the shape the store asks it.
SOURCE_LINKS_QUERY = (
    "SELECT ls.listing_id, ls.raw_listing_id, ls.join_signal, ls.decided_by, ls.linked_at, "
    "       rl.source, rl.source_listing_id, rl.fetched_at, rl.listing_url "
    "FROM listing_sources ls INDEXED BY idx_listing_sources_link "
    "JOIN raw_listings rl INDEXED BY idx_raw_link_columns ON rl.id = ls.raw_listing_id "
    "WHERE ls.listing_id IN (?, ?) ORDER BY rl.fetched_at, ls.raw_listing_id"
)
LINK_INDEXES = ("idx_listing_sources_link", "idx_raw_link_columns")


def _plan(conn: sqlite3.Connection) -> str:
    return " | ".join(
        str(row[3]) for row in conn.execute("EXPLAIN QUERY PLAN " + SOURCE_LINKS_QUERY, ("a", "b"))
    )


def test_source_links_are_answered_from_indexes_rather_than_raw_rows(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    """feat-001/AC-13, feat-001/AC-27: the road from a property to its source rows is short.

    A raw listing row carries the whole record the source returned ahead of the few small columns
    a source link needs, and SQLite reads a row in column order, so answering "which rows was this
    built from, and where can each be read" by reading the rows means walking through every
    payload first. On a real workspace after sixteen runs that was 61,700 page reads and 250
    megabytes on every results page, three quarters of everything the page read, growing by one
    raw row per source per night. Two covering indexes answer the join without touching a row.

    Asserted on the plan rather than on timing, because the plan is the guarantee and the time is
    only its symptom. The store names both indexes in the query, so the plan cannot drift with the
    size of the table; the cost of that is that a database without them cannot answer the query at
    all, which is why the second half of this brings a file from the build before the indexes
    forward and asks again: an index a migration forgot is a results page that stops answering.
    """
    from homescout.store.migrations import MIGRATIONS, _apply

    def indexes(conn: sqlite3.Connection) -> set[str]:
        held = conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        return {name for (name,) in held}

    store.close()
    with sqlite3.connect(db_path) as fresh:
        assert indexes(fresh) >= set(LINK_INDEXES)
        found = _plan(fresh)
    for index in LINK_INDEXES:
        assert f"USING COVERING INDEX {index}" in found, found

    #: A file from the build before the indexes, brought forward.
    older = tmp_path / "older.db"
    with sqlite3.connect(older) as conn:
        for target in range(1, SCHEMA_VERSION):
            _apply(conn, MIGRATIONS[target - 1], target)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION - 1
        assert not indexes(conn) & set(LINK_INDEXES), "the older schema already has them"
        with pytest.raises(sqlite3.OperationalError):
            _plan(conn)
    with Store.open(older) as migrated:
        assert migrated.schema_version == SCHEMA_VERSION
    with sqlite3.connect(older) as conn:
        assert indexes(conn) >= set(LINK_INDEXES)
        found = _plan(conn)
    for index in LINK_INDEXES:
        assert f"USING COVERING INDEX {index}" in found, found
