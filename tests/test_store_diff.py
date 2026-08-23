"""What changed: the arithmetic this whole product exists to perform.

The tests that matter most here are the ones about absence. A listing missing from a run means one
of two completely different things depending on whether the sources were healthy, and getting that
wrong would mean the tool announcing that houses had sold when a website merely had a bad afternoon.
"""

from __future__ import annotations

from conftest import do_run, kinds, prop
from homescout.store import Store


def test_a_first_ever_run_is_all_new(store: Store) -> None:
    """feat-001/AC-3: N properties, N new events, and nothing else."""
    run = do_run(store, sources={"realtor": [prop("a1"), prop("a2"), prop("a3")]})
    comparison = store.compare("test-search", target_run_id=run.id)

    assert comparison.baseline_run_id is None
    assert kinds(comparison) == {"new": 3, "changed": 0, "unchanged": 0, "gone": 0, "returned": 0}


def test_a_repeated_run_with_nothing_moving_reports_nothing_moving(store: Store) -> None:
    """feat-001/AC-4: an unchanged result set produces no news, only unchanged."""
    do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    second = do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    comparison = store.compare("test-search", target_run_id=second.id)

    assert kinds(comparison) == {"new": 0, "changed": 0, "unchanged": 2, "gone": 0, "returned": 0}


def test_a_price_cut(store: Store) -> None:
    """feat-001/AC-5: the previous value, the new value, the difference, and the direction."""
    do_run(store, sources={"realtor": [prop("a1", price=449_000)]})
    second = do_run(store, sources={"realtor": [prop("a1", price=435_000)]})

    (event,) = store.compare("test-search", target_run_id=second.id).of_kind("changed")
    assert event.price_change is not None
    assert event.price_change.before == 449_000
    assert event.price_change.after == 435_000
    assert event.price_change.amount == 14_000
    assert event.price_change.direction == "down"


def test_a_price_increase(store: Store) -> None:
    """feat-001/AC-5: a rise is reported as a rise, not as an unsigned difference."""
    do_run(store, sources={"realtor": [prop("a1", price=435_000)]})
    second = do_run(store, sources={"realtor": [prop("a1", price=449_000)]})

    (event,) = store.compare("test-search", target_run_id=second.id).of_kind("changed")
    assert event.price_change is not None
    assert event.price_change.amount == 14_000
    assert event.price_change.direction == "up"


def test_gaining_a_price_is_a_change_but_not_a_cut(store: Store) -> None:
    """feat-001/AC-5: a listing with no price is not a listing priced at nothing."""
    do_run(store, sources={"realtor": [prop("a1", price=None)]})
    second = do_run(store, sources={"realtor": [prop("a1", price=300_000)]})

    (event,) = store.compare("test-search", target_run_id=second.id).of_kind("changed")
    assert event.price_change is not None
    assert event.price_change.before is None
    assert event.price_change.direction is None
    assert event.price_change.amount is None


def test_a_status_change_names_the_field_that_moved(store: Store) -> None:
    """feat-001/AC-6: every differing compared field is named, with before and after."""
    do_run(store, sources={"realtor": [prop("a1", listing_status="for_sale")]})
    second = do_run(store, sources={"realtor": [prop("a1", listing_status="pending")]})

    (event,) = store.compare("test-search", target_run_id=second.id).of_kind("changed")
    (change,) = event.changes
    assert change.field == "listing_status"
    assert change.before == "for_sale"
    assert change.after == "pending"


def test_a_field_the_tool_does_not_compare_never_appears(store: Store) -> None:
    """feat-001/AC-6: a rewritten description is not a market event.

    The compared set is declared rather than inferred. Without that, every source rewording a blurb
    would look like something happening.
    """
    do_run(store, sources={"realtor": [prop("a1", description="Charming.")]})
    second = do_run(store, sources={"realtor": [prop("a1", description="Charming! Motivated.")]})

    comparison = store.compare("test-search", target_run_id=second.id)
    assert kinds(comparison)["changed"] == 0
    assert kinds(comparison)["unchanged"] == 1


def test_several_fields_moving_produce_one_event(store: Store) -> None:
    """feat-001/AC-21: one listing, one event, however much moved."""
    do_run(store, sources={"realtor": [prop("a1", price=400_000, beds=3)]})
    second = do_run(store, sources={"realtor": [prop("a1", price=380_000, beds=4)]})

    comparison = store.compare("test-search", target_run_id=second.id)
    assert len(comparison.events) == 1
    (event,) = comparison.events
    assert {change.field for change in event.changes} == {"price", "beds"}


def test_absent_from_every_source_in_a_healthy_run_is_gone(store: Store) -> None:
    """feat-001/AC-8: with every source succeeding, absence is evidence."""
    do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    second = do_run(store, sources={"realtor": [prop("a1")]})

    comparison = store.compare("test-search", target_run_id=second.id)
    assert kinds(comparison)["gone"] == 1

    gone_id = comparison.of_kind("gone")[0].listing_id
    assert store.get_listing(gone_id).presence == "disappeared"


def test_absent_while_a_source_failed_is_not_gone(store: Store) -> None:
    """feat-001/AC-9: a source outage must never read as a market that emptied out.

    This is the failure the whole design is organized against. A provider being down is a normal
    Tuesday, and the tool announcing that every house sold would destroy trust in all of it.
    """
    do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    second = do_run(
        store, sources={"realtor": [prop("a1")]}, outcomes={"realtor": "failed"}
    )

    comparison = store.compare("test-search", target_run_id=second.id)
    assert kinds(comparison)["gone"] == 0
    assert all(listing.presence == "observed" for listing in store.listings())


def test_absent_while_a_source_is_unavailable_is_not_gone(store: Store) -> None:
    """feat-001/AC-9: unavailable is not success, so absence still means nothing."""
    do_run(store, sources={"realtor": [prop("a1")], "redfin": [prop("b1")]})
    second = do_run(
        store,
        sources={"realtor": [prop("a1")]},
        outcomes={"realtor": "ok", "redfin": "unavailable"},
    )

    assert kinds(store.compare("test-search", target_run_id=second.id))["gone"] == 0


def test_every_source_failing_marks_nothing_gone(store: Store) -> None:
    """feat-001/AC-9: a run where nothing succeeded is not a run where nothing exists."""
    do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    second = do_run(store, sources={}, outcomes={"realtor": "failed"})

    assert kinds(store.compare("test-search", target_run_id=second.id))["gone"] == 0
    assert all(listing.presence == "observed" for listing in store.listings())


def test_absent_from_one_source_but_returned_by_another_is_not_gone(store: Store) -> None:
    """feat-001/AC-7: one source's silence is not the last word when another one saw it.

    Two sources describing one house only becomes one record once they are merged, so the merge is
    part of the setup rather than the point of the test.
    """
    do_run(store, sources={"realtor": [prop("a1")], "redfin": [prop("b1")]})
    left, right = (listing.id for listing in store.listings())
    merged = store.supersede([left, right], join_signal="parcel")

    do_run(store, sources={"realtor": [prop("a1")], "redfin": [prop("b1")]})
    third = do_run(store, sources={"realtor": [prop("a1")]}, outcomes={"redfin": "ok"})

    comparison = store.compare("test-search", target_run_id=third.id)
    assert kinds(comparison)["gone"] == 0
    assert store.get_listing(merged).presence == "observed"


def test_a_disappeared_listing_that_comes_back(store: Store) -> None:
    """feat-001/AC-10: the return is its own event, and both moments are on the timeline.

    A listing that vanishes and returns is signal: it usually means a contract fell through.
    """
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    do_run(store, sources={"realtor": []})
    assert store.get_listing(listing_id).presence == "disappeared"

    third = do_run(store, sources={"realtor": [prop("a1")]})
    comparison = store.compare("test-search", target_run_id=third.id)

    assert kinds(comparison)["returned"] == 1
    assert comparison.of_kind("returned")[0].listing_id == listing_id
    assert store.get_listing(listing_id).presence == "observed"

    trail = [event.kind for event in store.events(listing_id)]
    assert trail == ["first_seen", "disappeared", "returned"]
    stamps = [event.occurred_at for event in store.events(listing_id)]
    assert len(set(stamps)) == 3


def test_a_listing_already_gone_is_not_reported_gone_again(store: Store) -> None:
    """feat-001/AC-21: gone is news once, not every run thereafter."""
    do_run(store, sources={"realtor": [prop("a1")]})
    do_run(store, sources={"realtor": []})
    third = do_run(store, sources={"realtor": []})

    assert kinds(store.compare("test-search", target_run_id=third.id))["gone"] == 0


def test_a_disappeared_listing_is_still_fully_readable(store: Store) -> None:
    """feat-001/AC-11: disappeared is a status, not a deletion."""
    run = do_run(store, sources={"realtor": [prop("a1", price=250_000)]})
    listing_id = store.listings()[0].id
    do_run(store, sources={"realtor": []})

    assert store.get_listing(listing_id).presence == "disappeared"
    assert any(listing.id == listing_id for listing in store.listings())
    assert store.snapshot_at(listing_id, run.id).fields.price == 250_000  # type: ignore[union-attr]
    assert store.source_links(listing_id)


def test_disappeared_listings_can_be_excluded_when_the_caller_asks(store: Store) -> None:
    """feat-001/AC-11: excluded only on request, never silently."""
    do_run(store, sources={"realtor": [prop("a1"), prop("a2")]})
    do_run(store, sources={"realtor": [prop("a1")]})

    assert len(store.listings()) == 2
    assert len(store.listings(include_disappeared=False)) == 1


def test_each_listing_appears_exactly_once(store: Store) -> None:
    """feat-001/AC-21: no listing carries two verdicts about the same interval."""
    do_run(store, sources={"realtor": [prop("a1"), prop("a2"), prop("a3")]})
    second = do_run(
        store, sources={"realtor": [prop("a1", price=1), prop("a2"), prop("a4")]}
    )

    comparison = store.compare("test-search", target_run_id=second.id)
    ids = [event.listing_id for event in comparison.events]
    assert len(ids) == len(set(ids))
    assert kinds(comparison) == {"new": 1, "changed": 1, "unchanged": 1, "gone": 1, "returned": 0}


def test_the_same_comparison_gives_the_same_answer_later(store: Store) -> None:
    """feat-001/AC-20: a digest generated today about last week matches the one from last week.

    Every query behind a comparison is bounded by the baseline run, so runs that happen afterwards
    cannot reach back and change what an earlier interval meant.
    """
    first = do_run(store, sources={"realtor": [prop("a1", price=400_000), prop("a2")]})
    second = do_run(store, sources={"realtor": [prop("a1", price=390_000)]})
    original = store.compare("test-search", target_run_id=second.id, baseline_run_id=first.id)

    for price in (380_000, 370_000, 360_000):
        do_run(store, sources={"realtor": [prop("a1", price=price), prop("a3")]})

    again = store.compare("test-search", target_run_id=second.id, baseline_run_id=first.id)
    assert again == original


def test_a_run_of_a_different_search_does_not_disturb_this_one(store: Store) -> None:
    """feat-001/AC-8: one search not seeing a property says nothing about another search."""
    do_run(store, "search-one", sources={"realtor": [prop("a1")]})
    do_run(store, "search-two", sources={"realtor": [prop("b1")]})

    assert all(listing.presence == "observed" for listing in store.listings())
    assert kinds(store.compare("search-one"))["gone"] == 0
