"""Latest observations stay correct and cheap as snapshot history accumulates."""

from __future__ import annotations

import pytest

from conftest import do_run, prop
from homescout.store import Store


@pytest.mark.parametrize("subset", [False, True])
def test_latest_snapshots_follow_run_sequence_not_snapshot_insertion(
    store: Store, subset: bool
) -> None:
    """feat-001/AC-20, feat-006/AC-9: concurrent searches can write snapshots out of order."""
    older = store.start_run("earlier-search")
    newer = store.start_run("later-search")
    shared, extra = store.record_observations(
        newer.id, "realtor", [prop("shared", price=450_000), prop("extra")]
    )
    store.record_observations(older.id, "realtor", [prop("shared", price=350_000)])
    # A newer run with no observation must not hide the property's last known state.
    do_run(store, "empty-search")
    changes = store.connection.total_changes

    latest = store.latest_snapshots([shared, shared, "unknown"] if subset else None)

    assert set(latest) == ({shared} if subset else {shared, extra})
    assert latest[shared].run_id == newer.id
    assert latest[shared].fields.price == 450_000
    assert store.latest_snapshots([]) == {}
    assert store.connection.total_changes == changes


def test_latest_snapshots_exclude_superseded_and_retracted_listings(store: Store) -> None:
    """feat-006/AC-16: undoing a merge restores only its original live records."""
    do_run(store, sources={"realtor": [prop("one"), prop("two"), prop("three")]})
    one, two, three = sorted(store.latest_snapshots())
    merged = store.supersede([one, two], join_signal="human review")

    assert set(store.latest_snapshots()) == {three}
    assert store.latest_snapshots([one, two, merged]) == {}
    store.undo_merge(merged)
    assert set(store.latest_snapshots([one, two, merged])) == {one, two}


@pytest.mark.parametrize("subset", [False, True])
def test_latest_snapshot_lookup_does_not_scan_each_property_history(
    store: Store, subset: bool
) -> None:
    """feat-001/NFR-performance, feat-006/AC-23: merge refresh must not reread every old row.

    Count SQLite instructions instead of elapsed time so the regression holds across machines.
    The same current properties should cost about the same after forty more nightly runs.
    """
    rows = [prop(f"house-{index}") for index in range(12)]
    do_run(store, sources={"realtor": rows})
    wanted = sorted(store.latest_snapshots())[:3] if subset else None

    def work() -> int:
        steps = 0

        def progress() -> int:
            nonlocal steps
            steps += 100
            return 0

        store.connection.set_progress_handler(progress, 100)
        try:
            latest = store.latest_snapshots(wanted)
        finally:
            store.connection.set_progress_handler(None, 0)
        assert len(latest) == (3 if subset else len(rows))
        return steps

    first = work()
    for _ in range(40):
        do_run(store, sources={"realtor": rows})
    accumulated = work()

    assert accumulated < first * 3, (
        f"snapshot lookup grew from {first} to {accumulated} SQLite instructions"
    )
