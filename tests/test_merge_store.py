"""What a merge must not cost, exercised through a merge-and-undo cycle.

The store already promises all of this and already tests it. What is checked here is narrower and
is the honest form of four of this feature's criteria: **merging and unmerging, as this feature
performs them, do not defeat guarantees that were made one layer down.**

That distinction matters. A test that re-proved the store's own guarantee would pass whether or not
this feature used it correctly, which is exactly the sort of test that gives false comfort.
"""

from __future__ import annotations

import json

from homescout.merge.pass_ import run_pass
from homescout.store import Store
from merge_fakes import corpus, load, properties

TOGETHER = properties(corpus(), "1401 E Ember")


def raw_rows(store: Store) -> list[tuple]:
    return [
        tuple(row)
        for row in store.connection.execute(
            "SELECT id, run_id, source, source_listing_id, fetched_at, payload, "
            "price, address_line, latitude, longitude FROM raw_listings ORDER BY id"
        )
    ]


def test_no_source_row_is_touched_by_a_merge_or_its_undo(store: Store) -> None:
    """feat-006/AC-15: compared before and after, for exact equality.

    Non-negotiable 5: canonical merged records are built on top of raw per-source rows, so a wrong
    merge can always be inspected and undone. That is only true if the rows underneath never move.
    """
    load(store, TOGETHER)
    before = raw_rows(store)
    assert before

    outcome = run_pass(store)
    merged = _merged_id(store, outcome.merged[0][0])
    during = raw_rows(store)
    store.undo_merge(merged)
    after = raw_rows(store)

    assert during == before, "a merge edited a source row"
    assert after == before, "an undo edited a source row"


def test_undoing_a_merge_restores_the_records_that_were_there(store: Store) -> None:
    """feat-006/AC-16: each backed by the same source rows it had beforehand.

    Recovered rather than reconstructed: the store merges by writing a new record over the old ones
    and leaving them exactly where they were, so there is nothing to rebuild.
    """
    load(store, TOGETHER)
    before = {
        listing.id: [link.raw_listing_id for link in store.source_links(listing.id)]
        for listing in store.listings()
    }

    outcome = run_pass(store)
    merged = _merged_id(store, outcome.merged[0][0])
    restored = store.undo_merge(merged)

    assert sorted(restored) == sorted(before)
    for listing_id in restored:
        assert [link.raw_listing_id for link in store.source_links(listing_id)] == before[
            listing_id
        ]


def test_an_annotation_survives_a_merge_and_its_undo(store: Store) -> None:
    """feat-006/AC-17: on both records, with its original content, attached to its own record.

    Non-negotiable 7, exercised through this feature's own operations. Losing a user's judgment is
    the one failure this tool cannot have, because it is what the tool replaces.
    """
    load(store, TOGETHER)
    first, second = sorted(store.latest_snapshots())[:2]
    store.set_annotation(first, verdict="worth a look", notes="the shed is the point")
    store.set_annotation(second, rank=2, next_step="ask about the well")

    outcome = run_pass(store)
    merged = _merged_id(store, outcome.merged[0][0])
    store.undo_merge(merged)

    kept = store.get_annotation(first)
    other = store.get_annotation(second)
    assert kept is not None and kept.verdict == "worth a look"
    assert kept.notes == "the shed is the point"
    assert other is not None and other.rank == 2
    assert other.next_step == "ask about the well"


def test_an_annotation_is_not_moved_by_the_merge_either(store: Store) -> None:
    """feat-006/AC-17: while merged, each annotation is still on the record it described.

    A merge that moved annotations onto the new record would pass the undo test above by putting
    them back, and would still have destroyed which property each one was about.
    """
    load(store, TOGETHER)
    first = sorted(store.latest_snapshots())[0]
    store.set_annotation(first, notes="mine")

    run_pass(store)

    assert store.get_annotation(first) is not None
    assert store.get_annotation(first).notes == "mine"


def test_the_provenance_names_every_row_and_what_joined_it(store: Store) -> None:
    """feat-006/AC-18: every source row underneath, the signal, and whether a person decided."""
    load(store, TOGETHER)

    outcome = run_pass(store)
    merged = _merged_id(store, outcome.merged[0][0])
    links = store.source_links(merged)

    assert len(links) == len(TOGETHER)
    assert {link.source for link in links} == {entry["source"] for entry in TOGETHER}
    for link in links:
        assert link.raw_listing_id
        assert link.join_signal, "every join says why"
        assert link.decided_by in ("automatic", "human")


def test_a_provenance_says_when_a_person_decided_it(store: Store) -> None:
    """feat-006/AC-18: which is the distinction somebody investigating a bad record needs first."""
    load(store, properties(corpus(), "701 N Ashcombe"))
    ids = sorted(store.latest_snapshots())[:2]

    merged = store.supersede(ids, join_signal="a person said so", decided_by="human")

    assert all(link.decided_by == "human" for link in store.source_links(merged))


def test_a_merge_keeps_the_earliest_first_observation(store: Store) -> None:
    """feat-006/AC-16: days on market is computed from it, so the merged record inherits it.

    A merged record that took the newest constituent's first sighting would report a house that has
    been on the market for months as listed this week, which is the one number this tool computes
    itself precisely so no source can get it wrong.
    """
    load(store, TOGETHER)
    earliest = min(listing.first_observed_at for listing in store.listings())

    outcome = run_pass(store)
    merged = store.get_listing(_merged_id(store, outcome.merged[0][0]))

    assert merged.first_observed_at == earliest


def test_the_corpus_survives_a_merge_and_an_undo_of_everything(store: Store) -> None:
    """feat-006/AC-15, feat-006/AC-16: at the size of a real run rather than on a pair.

    Forty-four merges and forty-four undos, and every one of the 140 source rows is byte for byte
    what it was.
    """
    load(store)
    before = raw_rows(store)
    payloads = {row[0]: json.loads(row[5]) for row in before if row[5]}

    outcome = run_pass(store)
    for group in outcome.merged:
        store.undo_merge(_merged_id(store, group[0]))

    after = raw_rows(store)
    assert after == before
    assert {row[0]: json.loads(row[5]) for row in after if row[5]} == payloads
    assert len(store.listings()) == 140, "every record is back"


def _merged_id(store: Store, listing_id: str) -> str:
    return store.connection.execute(
        "SELECT superseded_by AS m FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()["m"]
