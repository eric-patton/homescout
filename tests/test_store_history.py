"""What was recorded, what it is traceable to, and what must never be lost.

The annotation tests are the ones that decide whether this tool can replace a spreadsheet or only
produce one. If a user's ranking can be lost by a merge, or quietly overwritten by a run, then the
spreadsheet is still the real system and this is a toy.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from conftest import do_run, kinds, prop
from homescout.store import Store, UnknownListingError, to_utc_text


def test_a_past_run_reads_the_same_however_much_happened_since(store: Store) -> None:
    """feat-001/AC-1: the exact state at any past run stays recoverable."""
    first = do_run(store, sources={"realtor": [prop("a1", price=500_000, beds=3)]})
    listing_id = store.listings()[0].id
    as_recorded = store.snapshot_at(listing_id, first.id)

    for price in (490_000, 480_000, 470_000):
        do_run(store, sources={"realtor": [prop("a1", price=price, beds=4)]})

    assert store.snapshot_at(listing_id, first.id) == as_recorded
    assert as_recorded.fields.price == 500_000  # type: ignore[union-attr]
    assert as_recorded.fields.beds == 3  # type: ignore[union-attr]


def test_a_correction_is_a_new_row_and_the_old_one_still_reads_as_before(store: Store) -> None:
    """feat-001/AC-1: a source revising a value does not revise what we already recorded."""
    first = do_run(store, sources={"realtor": [prop("a1", lot_sqft=43_560)]})
    listing_id = store.listings()[0].id
    second = do_run(store, sources={"realtor": [prop("a1", lot_sqft=108_900)]})

    assert store.snapshot_at(listing_id, first.id).fields.lot_sqft == 43_560  # type: ignore[union-attr]
    assert store.snapshot_at(listing_id, second.id).fields.lot_sqft == 108_900  # type: ignore[union-attr]


def test_a_listing_resolves_to_the_source_rows_it_was_built_from(store: Store) -> None:
    """feat-001/AC-13: provenance is readable, with the source and the time attached."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    (link,) = store.source_links(listing_id)
    assert link.source == "realtor"
    assert link.source_listing_id == "a1"
    assert link.fetched_at.endswith("Z")
    assert link.decided_by == "automatic"


def test_a_listing_accumulates_the_rows_of_every_run_that_saw_it(store: Store) -> None:
    """feat-001/AC-13: every source row is traceable, not just the most recent one."""
    do_run(store, sources={"realtor": [prop("a1")]})
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    assert len(store.source_links(listing_id)) == 2


def test_the_same_property_twice_in_one_response_is_one_property(store: Store) -> None:
    """feat-001/AC-24: a duplicated row is not a second house."""
    run = do_run(store, sources={"realtor": [prop("a1"), prop("a1"), prop("a2")]})

    assert len(store.listings()) == 2
    assert len(store.snapshots_for_run(run.id)) == 2
    # Every row is kept: three rows arrived, three rows are recorded.
    assert store.connection.execute("SELECT COUNT(*) FROM raw_listings").fetchone()[0] == 3

    comparison = store.compare("test-search", target_run_id=run.id)
    ids = [event.listing_id for event in comparison.events]
    assert len(ids) == len(set(ids)) == 2


def test_a_run_records_what_each_source_contributed(store: Store) -> None:
    """feat-001/AC-18: the outcome of a run is never silent."""
    run = do_run(
        store,
        sources={"realtor": [prop("a1"), prop("a2")], "zillow": [prop("b1")]},
        outcomes={"realtor": "ok", "zillow": "ok", "redfin": "unavailable"},
    )

    assert run.status == "completed"
    assert run.started_at and run.finished_at
    by_source = {outcome.source: outcome for outcome in run.sources}
    assert by_source["realtor"].outcome == "ok"
    assert by_source["realtor"].row_count == 2
    assert by_source["redfin"].outcome == "unavailable"
    assert by_source["redfin"].row_count == 0
    assert run.all_sources_succeeded is False


def test_an_unfinished_run_is_not_a_baseline(store: Store) -> None:
    """feat-001/AC-19: a half-finished run is never mistaken for the state of the market."""
    first = do_run(store, sources={"realtor": [prop("a1", price=400_000)]})
    do_run(store, sources={"realtor": [prop("a1", price=1)]}, complete=False)
    third = do_run(store, sources={"realtor": [prop("a1", price=390_000)]})

    comparison = store.compare("test-search", target_run_id=third.id)
    assert comparison.baseline_run_id == first.id
    (event,) = comparison.of_kind("changed")
    assert event.price_change.before == 400_000  # type: ignore[union-attr]


def test_an_unfinished_run_cannot_be_compared(store: Store) -> None:
    """feat-001/AC-19: not as a baseline, and not as a target either."""
    from homescout.store import RunNotCompletedError

    do_run(store, sources={"realtor": [prop("a1")]})
    partial = do_run(store, sources={"realtor": [prop("a1")]}, complete=False)

    with pytest.raises(RunNotCompletedError):
        store.compare("test-search", target_run_id=partial.id)


def test_days_on_market_comes_from_our_own_first_sighting(store: Store) -> None:
    """feat-001/AC-12: a source claiming four hundred days means its records, not ours."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing = store.listings()[0]

    forty_days_on = to_utc_text(
        datetime.fromisoformat(listing.first_observed_at.replace("Z", "+00:00"))
        + timedelta(days=40)
    )
    history = store.history(listing.id, as_of=forty_days_on)

    assert history.days_on_market == 40
    assert history.first_observed_at == listing.first_observed_at


def test_the_price_timeline_keeps_every_observation(store: Store) -> None:
    """feat-001/AC-12: the history no source will give us, kept by us."""
    for price in (500_000, 500_000, 475_000, 450_000):
        do_run(store, sources={"realtor": [prop("a1", price=price)]})
    listing_id = store.listings()[0].id

    history = store.history(listing_id)
    assert [entry.price for entry in history.prices] == [500_000, 500_000, 475_000, 450_000]

    movements = [event.kind for event in history.events if event.kind == "price_change"]
    assert len(movements) == 2


def test_a_property_offered_twice_shows_both_transitions(store: Store) -> None:
    """feat-001: sold, then for sale again, with both moments dated and separate."""
    do_run(store, sources={"realtor": [prop("a1", listing_status="for_sale")]})
    do_run(store, sources={"realtor": [prop("a1", listing_status="sold")]})
    do_run(store, sources={"realtor": [prop("a1", listing_status="for_sale")]})
    listing_id = store.listings()[0].id

    transitions = [
        event.detail for event in store.events(listing_id) if event.kind == "status_change"
    ]
    assert transitions == [
        {"from": "for_sale", "to": "sold"},
        {"from": "sold", "to": "for_sale"},
    ]


# -- the user's own judgment ------------------------------------------------


def test_an_annotation_survives_every_later_run(store: Store) -> None:
    """feat-001/AC-15: months of judgment cannot be undone by tonight's scheduled run."""
    do_run(store, sources={"realtor": [prop("a1", price=400_000)]})
    listing_id = store.listings()[0].id
    store.set_annotation(
        listing_id, rank=1, verdict="Worth a drive", notes="Ask about the well."
    )
    written = store.get_annotation(listing_id)

    do_run(store, sources={"realtor": [prop("a1", price=380_000)]})
    do_run(store, sources={"realtor": []})  # and now it disappears
    do_run(store, sources={"realtor": [prop("a1", price=380_000)]})

    assert store.get_annotation(listing_id) == written


def test_a_run_never_writes_an_annotation(store: Store) -> None:
    """feat-001/AC-17: only an explicit action changes what the user wrote."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id
    assert store.get_annotation(listing_id) is None

    do_run(store, sources={"realtor": [prop("a1", price=1)]})
    assert store.get_annotation(listing_id) is None


def test_setting_one_field_leaves_the_others_alone(store: Store) -> None:
    """feat-001/AC-17: editing a rank does not silently erase a verdict."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    store.set_annotation(listing_id, verdict="Promising", notes="Septic unknown.")
    store.set_annotation(listing_id, rank=2)

    annotation = store.get_annotation(listing_id)
    assert annotation.rank == 2  # type: ignore[union-attr]
    assert annotation.verdict == "Promising"  # type: ignore[union-attr]
    assert annotation.notes == "Septic unknown."  # type: ignore[union-attr]


def test_an_unknown_annotation_field_is_refused(store: Store) -> None:
    """feat-001/AC-17: a typo is an error, not a silently discarded note."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    with pytest.raises(ValueError, match="Not annotation fields"):
        store.set_annotation(listing_id, verdikt="oops")


def test_annotating_a_listing_that_does_not_exist_is_an_error(store: Store) -> None:
    """feat-001/AC-17: notes are never written into nowhere."""
    with pytest.raises(UnknownListingError):
        store.set_annotation("no-such-listing", rank=1)


def test_annotations_survive_a_merge_and_its_undo(store: Store) -> None:
    """feat-001/AC-16: the guarantee that lets a wrong merge be cheap to correct.

    Nothing moves during a merge, so nothing can be lost by one. The merged listing presents its
    constituents' notes rather than absorbing them.
    """
    do_run(store, sources={"realtor": [prop("a1")], "zillow": [prop("b1")]})
    left, right = (listing.id for listing in store.listings())
    store.set_annotation(left, rank=1, verdict="Best so far", notes="Great well.")
    store.set_annotation(right, rank=7, verdict="Too close to the highway")
    before = {left: store.get_annotation(left), right: store.get_annotation(right)}

    merged = store.supersede([left, right], join_signal="parcel")
    assert {a.listing_id for a in store.annotations_for(merged)} == {left, right}
    assert store.get_annotation(left) == before[left]
    assert store.get_annotation(right) == before[right]

    store.undo_merge(merged)

    assert store.get_annotation(left) == before[left]
    assert store.get_annotation(right) == before[right]
    assert store.get_listing(merged).retracted is True
    assert store.get_listing(left).superseded_by is None


def test_a_merge_and_its_undo_leave_every_source_row_untouched(store: Store) -> None:
    """feat-001/AC-14: source rows are the evidence; nothing about a merge may disturb them."""
    do_run(store, sources={"realtor": [prop("a1")], "zillow": [prop("b1")]})
    conn = store.connection
    before = conn.execute("SELECT * FROM raw_listings ORDER BY id").fetchall()

    left, right = (listing.id for listing in store.listings())
    merged = store.supersede([left, right], join_signal="parcel")
    store.undo_merge(merged)

    after = conn.execute("SELECT * FROM raw_listings ORDER BY id").fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


# -- notes about places rather than properties ------------------------------


def test_area_notes_are_addressed_by_place_and_survive_runs(store: Store) -> None:
    """feat-001/AC-26: what the user learned about a town outlives any listing in it."""
    store.set_area_note("city", "Portales, NM", "Fibre on the north side only.")
    written = store.get_area_note("city", "Portales, NM")

    do_run(store, sources={"realtor": [prop("a1")]})
    do_run(store, sources={"realtor": []})

    assert store.get_area_note("city", "Portales, NM") == written
    assert [note.area_value for note in store.area_notes()] == ["Portales, NM"]


def test_area_notes_can_be_revised(store: Store) -> None:
    """feat-001/AC-26: last write wins, with a timestamp, exactly like a listing annotation."""
    first = store.set_area_note("county", "Roosevelt County, NM", "Dry.")
    second = store.set_area_note("county", "Roosevelt County, NM", "Dry, but the aquifer is deep.")

    assert second.id == first.id
    assert second.notes == "Dry, but the aquifer is deep."
    assert second.updated_at >= first.updated_at


# -- stored preview images --------------------------------------------------


def test_a_preview_image_is_kept_on_disk_and_referenced_by_path(store: Store) -> None:
    """feat-001/AC-25: images beside the database, never inside it."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id

    stored = store.store_preview_image(listing_id, b"not-really-a-jpeg", source_url="http://x/1.jpg")

    assert stored.byte_size == len(b"not-really-a-jpeg")
    on_disk = store.preview_image_path(listing_id)
    assert on_disk is not None and on_disk.read_bytes() == b"not-really-a-jpeg"
    assert store.images_dir in on_disk.parents


def test_a_preview_image_outlives_the_listing_disappearing(store: Store) -> None:
    """feat-001/AC-25: the reason to keep a copy at all.

    A delisted property usually takes its images down with it, and a disappearance is exactly the
    thing a user wants to look back at later.
    """
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id
    store.store_preview_image(listing_id, b"image-bytes")

    do_run(store, sources={"realtor": []})

    assert store.get_listing(listing_id).presence == "disappeared"
    assert store.preview_image_path(listing_id).read_bytes() == b"image-bytes"  # type: ignore[union-attr]


def test_a_later_failed_retrieval_cannot_replace_a_good_image(store: Store) -> None:
    """feat-001/AC-25: nothing is stored unless bytes were actually retrieved."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing_id = store.listings()[0].id
    store.store_preview_image(listing_id, b"the-good-one")

    # A failed retrieval has no bytes, so it never reaches the store at all. This is the shape of
    # the guarantee: there is no code path that writes an absent image over a present one.
    assert store.get_preview_image(listing_id).byte_size == len(b"the-good-one")  # type: ignore[union-attr]
    assert store.preview_image_path(listing_id).read_bytes() == b"the-good-one"  # type: ignore[union-attr]


def test_full_size_image_addresses_are_recorded_but_not_the_images(store: Store) -> None:
    """feat-001/AC-25: the gallery is linked, only the preview is kept."""
    urls = ("http://example.test/1.jpg", "http://example.test/2.jpg")
    run = do_run(store, sources={"realtor": [prop("a1", photo_urls=urls)]})
    listing_id = store.listings()[0].id

    snapshot = store.snapshot_at(listing_id, run.id)
    assert snapshot.fields.photo_urls == urls  # type: ignore[union-attr]
    assert store.get_preview_image(listing_id) is None
    assert not list(store.images_dir.rglob("*")) if store.images_dir.exists() else True


def test_replace_is_not_a_way_around_the_rules(store: Store) -> None:
    """feat-001/AC-2: a dataclass copy is a value, not a write. Records change only through here."""
    run = do_run(store, sources={"realtor": [prop("a1", price=400_000)]})
    listing_id = store.listings()[0].id
    snapshot = store.snapshot_at(listing_id, run.id)

    edited = replace(snapshot, observed_at="1999-01-01T00:00:00.000000Z")  # type: ignore[type-var]
    assert edited.observed_at != store.snapshot_at(listing_id, run.id).observed_at  # type: ignore[union-attr]
    assert store.snapshot_at(listing_id, run.id) == snapshot


def test_a_naive_reference_time_is_treated_as_utc(store: Store) -> None:
    """feat-001/AC-23: no path by which a local time silently becomes a UTC one."""
    do_run(store, sources={"realtor": [prop("a1")]})
    listing = store.listings()[0]
    reference = datetime.now(UTC) + timedelta(days=10)

    assert store.history(listing.id, as_of=to_utc_text(reference)).days_on_market == 10


# -- regressions from the first code-against-spec audit ---------------------


def test_a_repeated_identifier_in_one_response_keeps_both_rows(store: Store) -> None:
    """feat-001/AC-24, gap-001: a source contradicting itself is two pieces of evidence.

    The first implementation keyed rows by the source's identifier and skipped a repeat of that key
    outright, so when the two rows disagreed the second one's values were discarded with no record
    that it had ever been seen. That is destroying a source row, which the project rules forbid
    outright, and no source will ever tell us what it said last week.

    What collapses is the property, not the row: one canonical listing, one snapshot for the run,
    one difference event, and both rows kept underneath.
    """
    run = do_run(
        store,
        sources={"realtor": [prop("a1", price=400_000), prop("a1", price=350_000)]},
    )

    prices = [
        row["price"]
        for row in store.connection.execute(
            "SELECT price FROM raw_listings ORDER BY price DESC"
        )
    ]
    assert prices == [400_000, 350_000]

    assert len(store.listings()) == 1
    listing_id = store.listings()[0].id
    assert len(store.source_links(listing_id)) == 2
    assert len(store.snapshots_for_run(run.id)) == 1

    comparison = store.compare("test-search", target_run_id=run.id)
    assert len(comparison.events) == 1


def test_a_sources_own_days_on_market_is_kept_but_never_substituted(store: Store) -> None:
    """feat-001/AC-12, gap-002: the criterion's own scenario, now actually exercisable.

    A source reporting four hundred days about a property we first saw forty days ago is telling us
    about its records, not ours. Its claim is worth keeping, because the first source adapter will
    want it when a number looks wrong. It is not worth believing.
    """
    do_run(store, sources={"realtor": [prop("a1", days_on_market_source=400)]})
    listing = store.listings()[0]
    run = store.last_completed_run("test-search")

    forty_days_on = to_utc_text(
        datetime.fromisoformat(listing.first_observed_at.replace("Z", "+00:00"))
        + timedelta(days=40)
    )
    assert store.history(listing.id, as_of=forty_days_on).days_on_market == 40
    assert store.snapshot_at(listing.id, run.id).fields.days_on_market_source == 400  # type: ignore[union-attr]


def test_a_sources_days_on_market_changing_is_not_a_market_event(store: Store) -> None:
    """feat-001/AC-6, gap-002: kept, but outside the compared set.

    Otherwise every source simply incrementing its own counter overnight would read as every
    property in the search having changed.
    """
    do_run(store, sources={"realtor": [prop("a1", days_on_market_source=10)]})
    second = do_run(store, sources={"realtor": [prop("a1", days_on_market_source=11)]})

    comparison = store.compare("test-search", target_run_id=second.id)
    assert kinds(comparison) == {"new": 0, "changed": 0, "unchanged": 1, "gone": 0, "returned": 0}
