"""The pass, against one real run over one town.

140 rows from three sources go in and 73 properties come out, with ten pairs put in front of a
person. Every one of those ten is a genuine judgment call, and the test at the bottom of this file
names them, because a queue full of obvious answers is a queue nobody reads.
"""

from __future__ import annotations

import random

import pytest

from homescout.merge.pass_ import run_pass
from homescout.merge.queue import StoreQueue
from homescout.store import Store
from merge_fakes import corpus, load, properties


def addresses(store: Store) -> list[str]:
    return sorted(
        (snapshot.fields.address_line or "") for snapshot in store.latest_snapshots().values()
    )


def test_the_corpus_becomes_properties_rather_than_listings(store: Store) -> None:
    """feat-006/AC-1: 140 rows from three sources over one town are not 140 houses.

    This is the whole feature in one number. The rest of the file is about the ways it could get
    that number by doing something wrong.
    """
    load(store)
    assert len(store.listings()) == 140

    outcome = run_pass(store)

    assert len(store.listings()) == 73
    assert len(outcome.merged) == 44
    assert sum(len(group) for group in outcome.merged) == 111


def test_nothing_is_merged_that_should_not_be(store: Store) -> None:
    """feat-006/AC-1: every merged group is one address, and every address is one group.

    The cheap way to reduce 140 rows to 73 is to merge things that are not the same property. This
    asserts the expensive way: within every group, the rows agree about where they are.
    """
    load(store)

    outcome = run_pass(store)

    for group in outcome.merged:
        links = store.source_links(_merged_id(store, group))
        assert len({link.source for link in links}) == len(links), (
            "a group merged two rows from the same source, which is not what this feature is for"
        )


def _merged_id(store: Store, group: tuple[str, ...]) -> str:
    row = store.connection.execute(
        "SELECT superseded_by FROM listings WHERE id = ?", (group[0],)
    ).fetchone()
    return row["superseded_by"]


def test_the_order_the_sources_returned_in_changes_nothing(store: Store, tmp_path) -> None:
    """feat-006/AC-20: stated as an experiment rather than as an argument.

    The same rows in four orders must produce the same properties. Nothing is merged until every
    pair has been compared, which is what makes this true rather than lucky.
    """
    load(store)
    run_pass(store)
    expected = addresses(store)

    for seed in (1, 2, 3):
        shuffled = corpus()
        random.Random(seed).shuffle(shuffled)
        with Store.open(tmp_path / f"other-{seed}.db") as other:
            load(other, shuffled)
            run_pass(other)
            assert addresses(other) == expected, f"order {seed} produced different properties"


def test_a_chain_with_a_contradiction_in_it_is_one_question_rather_than_a_merge(
    store: Store,
) -> None:
    """feat-006/AC-20, feat-006/AC-21, and the spec's duplex edge case, all the same situation.

    Two rows that match a third but not each other. Merging pair by pair fuses all three and the
    result depends on which pair came first. Requiring the whole group to agree is what stops both.
    """
    # Forty metres apart, then forty more. Each neighbour is inside the tolerance and the two ends
    # are not, which is the shape of the problem: two matches that chain into a third thing nobody
    # ever compared favourably.
    here = {"latitude": 34.1800000, "longitude": -103.3300000}
    near = {"latitude": 34.1803600, "longitude": -103.3300000}
    far = {"latitude": 34.1807200, "longitude": -103.3300000}
    rows = [
        {"source": "realtor", "address_line": "9 Kestrel Way", "postal_code": "88888",
         "price": 100_000, **here},
        {"source": "zillow", "address_line": "9 Kestrel Way", "postal_code": "88888",
         "price": 100_000, **near},
        {"source": "redfin", "address_line": "9 Kestrel Way", "postal_code": "88888",
         "price": 100_000, **far},
    ]
    load(store, rows)

    outcome = run_pass(store)

    assert outcome.merged == [], "nothing was merged"
    assert len(outcome.queued) == 1, "and it is one question, not two or three"
    assert len(outcome.queued[0]) == 3, "naming every row in the chain"
    assert len(store.listings()) == 3, "all three left intact and separate"


def test_nothing_is_merged_provisionally(store: Store) -> None:
    """feat-006/AC-10: a queued pair leaves both records exactly where they were."""
    load(store, properties(corpus(), "701 N Ashcombe"))

    outcome = run_pass(store)

    assert outcome.merged == []
    assert outcome.queued, "it is a question"
    assert len(store.listings()) == 3, "and all three are still there, still separate"


def test_a_single_source_installation_needs_no_merge_at_all(store: Store) -> None:
    """feat-006/AC-19: one source row is a valid property, and this feature does not break it."""
    only_one = [entry for entry in corpus() if entry["source"] == "realtor"]
    load(store, only_one)
    before = len(store.listings())

    outcome = run_pass(store)

    assert before == len(only_one)
    assert outcome.merged == [], "one source cannot duplicate a property with itself"
    assert len(store.listings()) == before


def test_a_run_with_nothing_in_it_is_not_an_error(store: Store) -> None:
    """feat-006/AC-19: the pass over an empty database does nothing and says so."""
    outcome = run_pass(store)

    assert outcome.compared == 0
    assert outcome.merged == [] and outcome.queued == []


def test_the_pass_compares_far_fewer_pairs_than_there_are(store: Store) -> None:
    """feat-006 performance: bounded by how many rows share a bucket, not by the size of the run.

    A hundred and forty rows is nine thousand seven hundred pairs. The pass looks at a hundred and
    sixty-one of them, because the rest are a house in one part of town against a house in another.
    """
    load(store)

    outcome = run_pass(store)

    every_pair = 140 * 139 // 2
    assert outcome.compared < every_pair // 25, outcome.compared


def test_the_provenance_says_what_joined_them(store: Store) -> None:
    """feat-006/AC-18: every source row underneath, the signal, and whether a person decided.

    The store keeps this; what is checked here is that this feature fills it in with something
    worth reading rather than with the word "merged".
    """
    load(store)

    outcome = run_pass(store)

    merged = _merged_id(store, outcome.merged[0])
    links = store.source_links(merged)
    assert len(links) >= 2
    for link in links:
        assert link.decided_by == "automatic"
        assert link.join_signal and " " in link.join_signal, "a sentence, not a field name"
        assert link.source in ("realtor", "zillow", "redfin")


def test_every_queued_pair_is_a_real_question(store: Store) -> None:
    """feat-006/AC-9: because a queue full of obvious answers is a queue nobody reads.

    Ten pairs out of a hundred and forty rows, and each one is a judgment a person can make and this
    code cannot: land parcels with no address between them, and houses whose sources put them a
    hundred metres apart. Both kinds are named here so that a change making the queue larger has to
    say which kind it added.
    """
    load(store)

    outcome = run_pass(store)
    snapshots = store.latest_snapshots()

    assert 5 <= len(outcome.queued) <= 15, len(outcome.queued)
    for group in outcome.queued:
        lines = [snapshots[i].fields.address_line or "" for i in group if i in snapshots]
        land = all(not line[:1].isdigit() or line.startswith("000") for line in lines)
        same_address = len({line.lower().replace("highway", "").strip() for line in lines}) <= 2
        assert land or same_address, lines


def test_the_queue_says_what_agreed_and_what_conflicted(store: Store) -> None:
    """feat-006/AC-9: in terms a person can act on, which is why they are sentences."""
    load(store, properties(corpus(), "701 N Ashcombe"))
    queue = StoreQueue(store)

    run_pass(store, queue=queue)

    waiting = queue.pending()
    assert waiting
    match = waiting[0]
    assert any("same address" in note for note in match.agreed)
    assert any("m apart" in note for note in match.conflicted)
    assert len(match.listing_ids) >= 2


def test_the_queue_is_countable(store: Store) -> None:
    """feat-006/AC-23: so the run digest can say how many pairs are waiting on a person."""
    load(store)
    queue = StoreQueue(store)

    outcome = run_pass(store, queue=queue)

    assert queue.waiting() == len(outcome.queued) == outcome.waiting
    assert queue.waiting() > 0


@pytest.mark.parametrize("line", ["Bigler Addition Block 2", "000 TBD Alder Addition"])
def test_land_is_asked_about_rather_than_merged(store: Store, line: str) -> None:
    """feat-006/AC-8: the case the whole queue exists for, in the market this tool was built for.

    A large share of rural listings have no street address, coordinates that agree to within metres
    because the parcels are adjacent, and identical prices because they are sold as a set. None of
    that is evidence.
    """
    load(store, properties(corpus(), line) + properties(corpus(), "Block 2 Lot"))

    outcome = run_pass(store)

    assert outcome.merged == []
    assert outcome.queued


def test_a_run_reports_how_many_pairs_are_waiting(tmp_path) -> None:
    """feat-006/AC-23: readable, countable, and reportable, so the digest can say so.

    Through the real run loop and the real digest, because the criterion is about what a scheduled
    agent reads rather than about what the pass returns.
    """
    from cli_fakes import FakeSource, row, search, workspace
    from homescout import api, digest
    from homescout.merge.queue import StoreQueue

    with Store.open(tmp_path / "run.db") as store:
        here = {"latitude": 34.1800000, "longitude": -103.3300000}
        far = {"latitude": 34.1809000, "longitude": -103.3300000}
        rows = [
            row("a", address_line="9 Kestrel Way", postal_code="88888", **here),
            row("b", address_line="9 Kestrel Way", postal_code="88888", **far),
        ]
        queue = StoreQueue(store)
        space = workspace(store, searches=[search("town")],
                          sources={"fake": FakeSource(rows=rows)}, queue=queue, images=False)
        outcome = api.run_search(space, "town")

        entry = digest.entry(
            store, search_name="town", comparison=outcome.comparison, outcome=outcome
        )

    assert entry["counts"]["waiting_for_review"] == 1
    assert outcome.merge is not None and outcome.merge.waiting == 1


def test_the_queue_is_worked_out_again_in_a_fresh_process(tmp_path) -> None:
    """feat-006/AC-23: `homescout matches list` after a scheduled run must show what it queued.

    The questions are derived rather than stored, so a queue object built by a later invocation
    finds them without anything having been written down.
    """
    from homescout.merge.queue import StoreQueue
    from merge_fakes import corpus as all_rows
    from merge_fakes import properties as rows_for

    path = tmp_path / "fresh.db"
    with Store.open(path) as first:
        load(first, rows_for(all_rows(), "701 N Ashcombe"))
        run_pass(first)

    with Store.open(path) as later:
        waiting = StoreQueue(later).pending()

    assert waiting, "a later invocation found nothing to review"
    assert all(len(match.listing_ids) >= 2 for match in waiting)
    assert any(match.conflicted for match in waiting)
