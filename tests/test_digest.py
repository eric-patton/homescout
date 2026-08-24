"""The digest: everything that moved, and nothing that did not.

The load-bearing property is size. A scheduled run over a county holds thousands of properties and
all of them are already in the store, so what an agent reads has to be a function of what changed
rather than of how much matched. These tests hold it to that.
"""

from __future__ import annotations

import json

from cli_fakes import FakeSource, row, search, workspace
from homescout import api, digest
from homescout.store import Store


def run(store: Store, *searches, sources=None, name="portales"):
    space = workspace(store, searches=searches, sources=sources)
    return api.run_search(space, name)


def entry_for(store: Store, outcome, name="portales"):
    return digest.entry(
        store, search_name=name, comparison=outcome.comparison, outcome=outcome
    )


def test_a_digest_names_its_search_its_sources_and_its_counts(store: Store) -> None:
    """feat-003/AC-10: everything an agent needs to act, in one entry per search."""
    source = FakeSource(applies=["price_min"], rows=[row("a"), row("b")])

    outcome = run(store, search(price_min=100_000), sources={"fake": source})
    entry = entry_for(store, outcome)

    assert entry["name"] == "portales"
    assert entry["run_id"] == outcome.run.id
    assert entry["counts"]["matched"] == 2
    assert entry["counts"]["new"] == 2
    assert entry["sources"][0]["source"] == "fake"
    assert entry["sources"][0]["applied_by_source"] == ["price_min"]
    assert len(entry["new"]) == 2


def test_running_everything_emits_one_document_with_an_entry_each(store: Store) -> None:
    """feat-003/AC-10: one digest covering every search, not one document per search."""
    space = workspace(
        store,
        searches=[search("north"), search("south")],
        sources={"fake": FakeSource(rows=[row("a")])},
    )

    result = api.run_all(space)
    document = digest.build(
        [entry_for(store, o, o.run.search_name) for o in result.outcomes], kind="run"
    )

    assert [s["name"] for s in document["searches"]] == ["north", "south"]
    assert document["homescout"]["digest_version"] == digest.DIGEST_VERSION


def test_a_digest_carries_no_row_for_a_property_that_did_not_move(store: Store) -> None:
    """feat-003/AC-11: the changed subset is the whole payload."""
    rows = [row(f"p{i:03d}") for i in range(40)]
    run(store, search(), sources={"fake": FakeSource(rows=rows)})
    second = run(store, search(), sources={"fake": FakeSource(rows=rows)})

    entry = entry_for(store, second)

    assert entry["counts"]["matched"] == 40
    assert entry["new"] == []
    assert entry["price_changes"] == []
    assert entry["gone"] == []
    assert entry["returned"] == []
    assert entry["flagged"] == []


def test_a_digest_does_not_grow_with_the_number_of_properties_matched(store: Store) -> None:
    """feat-003/AC-11: over N properties of which none changed, size is a function of nothing.

    Two runs of different sizes are compared directly, because "small" is not a property anyone can
    assert. The two documents differ only where they must: the matched count is a different number.
    """
    small = [row(f"s{i:04d}") for i in range(20)]
    large = [row(f"l{i:04d}") for i in range(2_000)]

    space_small = workspace(
        store, searches=[search("small")], sources={"fake": FakeSource(rows=small)}
    )
    api.run_search(space_small, "small")
    small_second = api.run_search(
        workspace(store, searches=[search("small")], sources={"fake": FakeSource(rows=small)}),
        "small",
    )

    space_large = workspace(
        store, searches=[search("large")], sources={"fake": FakeSource(rows=large)}
    )
    api.run_search(space_large, "large")
    large_second = api.run_search(
        workspace(store, searches=[search("large")], sources={"fake": FakeSource(rows=large)}),
        "large",
    )

    small_entry = entry_for(store, small_second, "small")
    large_entry = entry_for(store, large_second, "large")

    assert small_entry["counts"]["matched"] == 20
    assert large_entry["counts"]["matched"] == 2_000

    # Identical but for the counts and the identifiers, and both comfortably small. A hundred-fold
    # difference in what matched buys a few characters.
    small_size = len(json.dumps(small_entry))
    large_size = len(json.dumps(large_entry))
    assert abs(large_size - small_size) < 20
    assert large_size < 1_000


def test_a_price_change_carries_both_values_and_a_direction(store: Store) -> None:
    """feat-003/AC-12: a cut is a before, an after, and which way it went."""
    run(store, search(), sources={"fake": FakeSource(rows=[row("a", price=400_000)])})
    second = run(store, search(), sources={"fake": FakeSource(rows=[row("a", price=350_000)])})

    entry = entry_for(store, second)

    assert len(entry["price_changes"]) == 1
    change = entry["price_changes"][0]["price_change"]
    assert change == {"before": 400_000, "after": 350_000, "amount": 50_000, "direction": "down"}


def test_gaining_a_price_is_a_change_but_not_a_direction(store: Store) -> None:
    """feat-003/AC-12: a listing with no price is not a listing priced at nothing."""
    run(store, search(), sources={"fake": FakeSource(rows=[row("a", price=None)])})
    second = run(store, search(), sources={"fake": FakeSource(rows=[row("a", price=300_000)])})

    change = entry_for(store, second)["price_changes"][0]["price_change"]

    assert change["before"] is None
    assert change["after"] == 300_000
    assert change["direction"] is None


def test_status_changes_disappearances_and_returns_are_separate_sets(store: Store) -> None:
    """feat-003/AC-12: four different things that are not four kinds of one thing."""
    both = [row("stays"), row("vanishes")]
    run(store, search(), sources={"fake": FakeSource(rows=both)})
    second = run(
        store,
        search(),
        sources={"fake": FakeSource(rows=[row("stays", listing_status="pending")])},
    )

    entry = entry_for(store, second)

    assert [r["address_line"] for r in entry["gone"]] == ["vanishes Example Road"]
    assert len(entry["status_changes"]) == 1
    assert entry["status_changes"][0]["status_change"] == {
        "before": "for_sale",
        "after": "pending",
    }
    assert entry["returned"] == []

    third = run(store, search(), sources={"fake": FakeSource(rows=both)})
    back = entry_for(store, third)
    assert [r["address_line"] for r in back["returned"]] == ["vanishes Example Road"]


def test_a_property_that_is_gone_is_still_described(store: Store) -> None:
    """feat-003/AC-12: a disappearance a reader cannot identify is not a report."""
    run(store, search(), sources={"fake": FakeSource(rows=[row("a", price=250_000)])})
    second = run(store, search(), sources={"fake": FakeSource(rows=[])})

    gone = entry_for(store, second)["gone"]

    assert gone[0]["address_line"] == "a Example Road"
    assert gone[0]["price"] == 250_000, "described by the last run that saw it"


def test_the_flagged_set_is_always_there_and_empty_without_rules(store: Store) -> None:
    """feat-003/AC-12: the document's shape does not depend on the rule engine existing."""
    outcome = run(store, search(), sources={"fake": FakeSource(rows=[row("a")])})

    entry = entry_for(store, outcome)

    assert entry["flagged"] == []
    assert entry["counts"]["flagged"] == 0


def test_a_summary_carries_the_stored_image_and_local_days_on_market(store: Store) -> None:
    """feat-003/AC-10: the email digest is built from these, so they carry what it shows.

    Days on market is this tool's own figure. The source's claim is recorded on the record and is
    deliberately not what a digest reports (product invariant 7).
    """
    source = FakeSource(rows=[row("a", days_on_market_source=999)])

    outcome = run(store, search(), sources={"fake": source})
    summary = entry_for(store, outcome)["new"][0]

    assert summary["image"] is not None
    assert summary["days_on_market"] == 0
    assert "days_on_market_source" not in summary
    assert summary["listing_url"] == "https://example.invalid/a"


def test_a_comparison_entry_has_the_same_keys_as_a_run_entry(store: Store) -> None:
    """feat-003/AC-10: one shape, so a reader never branches on which command produced it."""
    outcome = run(store, search(), sources={"fake": FakeSource(rows=[row("a")])})
    space = workspace(store, searches=[search()], sources={"fake": FakeSource()})

    comparison = api.changes(space, "portales")
    without_run = digest.entry(store, search_name="portales", comparison=comparison)

    assert set(without_run) == set(entry_for(store, outcome))
    assert without_run["sources"] == []
    assert without_run["outcome"] is None
