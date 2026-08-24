"""A person's decision, which outranks everything and is never asked for twice.

Non-negotiable 6 and non-negotiable 7 meet here. An ambiguous merge is flagged for a human and never
guessed, and losing a user's judgment is the one failure this tool cannot have, because a user's
judgment is what the tool replaces. Both of those are only true if the answer survives the process
that asked the question.
"""

from __future__ import annotations

import pytest

from homescout.merge.pass_ import run_pass
from homescout.merge.queue import StoreQueue
from homescout.store import Store, pair_key
from merge_fakes import corpus, load, properties

#: Two rows the signals will call ambiguous: same address, coordinates a hundred metres apart.
DISAGREES = properties(corpus(), "701 N Ashcombe")


def apart(store: Store) -> list[str]:
    return sorted(store.latest_snapshots())


def test_a_decision_is_recorded_and_takes_effect_at_once(store: Store) -> None:
    """feat-006/AC-11: durably, and immediately."""
    load(store, DISAGREES)
    queue = StoreQueue(store)
    run_pass(store, queue=queue)
    waiting = queue.pending()
    assert waiting

    match = waiting[0]
    merged = store.supersede(list(match.listing_ids), join_signal="a person said so")
    queue.record(match.id, "same", merged)

    assert match.id not in {other.id for other in queue.pending()}, "it left the queue"
    standing = store.merge_decisions()
    assert standing[pair_key(match.listing_ids)].verdict == "same"
    assert standing[pair_key(match.listing_ids)].merged_id == merged


def test_a_decision_survives_the_process_that_made_it(store: Store, tmp_path) -> None:
    """feat-006/AC-11: written to the database, not held in a queue object.

    A decision that lived only in memory would be a decision lost the next time the tool exited,
    which is the failure this feature cannot have.
    """
    path = tmp_path / "decisions.db"
    with Store.open(path) as opened:
        load(opened, DISAGREES)
        queue = StoreQueue(opened)
        run_pass(opened, queue=queue)
        match = queue.pending()[0]
        queue.record(match.id, "different", None)
        key = pair_key(match.listing_ids)

    with Store.open(path) as reopened:
        assert reopened.merge_decisions()[key].verdict == "different"


def test_a_decision_to_separate_outranks_the_signals(store: Store) -> None:
    """feat-006/AC-12: in the direction the automatic comparison would have merged them.

    Which is the half of the criterion that actually needs a test: a decision that agrees with the
    signals proves nothing about whose answer wins.
    """
    matching = properties(corpus(), "1401 E Ember")
    load(store, matching)
    first = run_pass(store)
    assert first.merged, "the signals would merge these on their own"

    # Undo it and record the opposite decision, then run again.
    merged = store.connection.execute(
        "SELECT superseded_by AS m FROM listings WHERE superseded_by IS NOT NULL LIMIT 1"
    ).fetchone()["m"]
    constituents = store.undo_merge(merged)
    # Said about the group, and recorded as every pair inside it, because the comparison that will
    # consult it works pairwise.
    store.record_merge_decision(constituents, "different")

    second = run_pass(store)

    assert second.merged == [], "the person's answer stands"
    assert second.honored >= 1
    assert len(store.listings()) == len(constituents)


def test_a_decision_to_merge_outranks_the_signals(store: Store) -> None:
    """feat-006/AC-12: and in the other direction, which the criterion asks for by name."""
    load(store, DISAGREES)
    ids = apart(store)
    store.record_merge_decision(ids[:2], "same")

    outcome = run_pass(store)

    assert any(set(group) == set(ids[:2]) for group in outcome.merged), (
        "the signals said ambiguous and the person said the same property"
    )
    assert outcome.honored >= 1


def test_a_decided_pair_never_comes_back(store: Store) -> None:
    """feat-006/AC-13: however many later runs see the same evidence again.

    Answering the same question every night is how a review queue becomes something nobody opens.
    """
    load(store, DISAGREES)
    queue = StoreQueue(store)
    run_pass(store, queue=queue)
    match = queue.pending()[0]
    queue.record(match.id, "different", None)

    for _ in range(3):
        outcome = run_pass(store, queue=queue)
        assert match.id not in {other.id for other in queue.pending()}, "it came back"
        assert not any(set(group) == set(match.listing_ids) for group in outcome.queued)


def test_new_evidence_against_a_decision_is_surfaced_and_not_acted_on(store: Store) -> None:
    """feat-006/AC-14: a decision is not overruled by evidence, it is questioned by it.

    The person who answered knows something the signals do not, which is why they were asked. So the
    contradiction is recorded and shown, and the merge state does not move.
    """
    rows = properties(corpus(), "1401 E Ember")
    # The parcel numbers disagree, which on its own says these are two different properties.
    rows[0] = {**rows[0], "parcel_number": "111-222-333"}
    rows[1] = {**rows[1], "parcel_number": "999-888-777"}
    load(store, rows[:2])
    ids = apart(store)

    # And a person has already said they are one property. They know something the signals do not.
    store.record_merge_decision(ids, "same")
    outcome = run_pass(store)

    assert store.contradictions(), "the disagreement was recorded"
    assert "parcel" in store.contradictions()[0].detail
    assert any(set(group) == set(ids) for group in outcome.merged), (
        "and the person's decision still stands"
    )


def test_the_same_contradiction_is_not_recorded_every_night(store: Store) -> None:
    """feat-006/AC-14: because a pair a person decided about is compared on every single run.

    One that recorded itself each time would bury last night's disagreement under three hundred
    copies of the one from March.
    """
    rows = properties(corpus(), "1401 E Ember")[:2]
    rows[0] = {**rows[0], "parcel_number": "111-222-333"}
    rows[1] = {**rows[1], "parcel_number": "999-888-777"}
    load(store, rows)
    store.record_merge_decision(apart(store), "same")

    run_pass(store)
    once = len(store.contradictions())
    run_pass(store)

    assert once == 1
    assert len(store.contradictions()) == once


def test_a_decision_that_agrees_with_the_evidence_is_not_a_contradiction(store: Store) -> None:
    """feat-006/AC-14: because a queue of things that are fine is a queue nobody reads."""
    load(store, properties(corpus(), "1401 E Ember"))
    ids = apart(store)
    store.record_merge_decision(ids[:2], "same")

    run_pass(store)

    assert store.contradictions() == []


def test_a_decision_is_found_whichever_way_round_the_pair_is_met(store: Store) -> None:
    """feat-006/AC-13: a later run has no reason to compare two records the same way round.

    A decision that could not be found again would be a decision lost.
    """
    assert pair_key(["b", "a"]) == pair_key(["a", "b"]) == "a,b"

    store.record_merge_decision(["z", "a"], "different")
    assert "a,z" in store.merge_decisions()


def test_a_change_of_mind_is_a_new_row_and_the_latest_one_counts(store: Store) -> None:
    """feat-006/AC-11: append-only, because the sequence of answers is itself worth reading.

    Somebody working out why a record looks wrong needs to see that it was called different in
    March and the same in June, which an edit would have erased.
    """
    store.record_merge_decision(["a", "b"], "different")
    store.record_merge_decision(["a", "b"], "same", merged_id="m1")

    standing = store.merge_decisions()
    assert standing["a,b"].verdict == "same"
    assert len(store.connection.execute("SELECT * FROM merge_decisions").fetchall()) == 2


def test_a_decision_cannot_be_edited_or_removed(store: Store) -> None:
    """feat-006/AC-11: the database enforces it, not a convention in the code above it."""
    import sqlite3

    store.record_merge_decision(["a", "b"], "same")

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("UPDATE merge_decisions SET verdict = 'different'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("DELETE FROM merge_decisions")


def test_a_verdict_that_is_not_one_of_the_two_is_refused(store: Store) -> None:
    """feat-006/AC-11: there are two answers to this question and no third."""
    with pytest.raises(ValueError, match="'same' or 'different'"):
        store.record_merge_decision(["a", "b"], "maybe")
    with pytest.raises(ValueError, match="at least two"):
        store.record_merge_decision(["a"], "same")


def _reobserve(store: Store, listing_id: str, **changes) -> None:
    """Write a new snapshot for one listing in a new run, with something different about it."""
    from dataclasses import replace

    from homescout.records import SourceRow
    from homescout.store import SourceOutcome

    snapshot = store.latest_snapshots()[listing_id]
    link = store.source_links(listing_id)[0]
    run = store.start_run("again")
    store.record_observations(
        run.id,
        link.source,
        [
            SourceRow(
                source=link.source,
                fields=replace(snapshot.fields, **changes),
                payload={},
                source_listing_id=link.source_listing_id,
                fetched_at="2026-08-25T00:00:00.000000Z",
            )
        ],
    )
    store.record_source_outcome(
        run.id, SourceOutcome(source=link.source, outcome="ok", row_count=1)
    )
    store.complete_run(run.id)
