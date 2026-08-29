"""The run loop: what gets asked, what gets kept, what gets recorded.

These run the real loop against a real store. Nothing is stubbed but the sources and the saved
search, which is exactly the seam the design puts them behind, so what these tests prove about the
loop is true of the loop that talks to a real site.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_fakes import FakeSource, row, search, workspace
from homescout import api
from homescout.errors import InvalidInput
from homescout.runner import passes, run_search
from homescout.sources import City, SearchQuery
from homescout.store import Store


def run(store: Store, *searches, sources=None, images=True, name="portales"):
    space = workspace(store, searches=searches, sources=sources, images=images)
    return api.run_search(space, name)


# -- what a source is asked for --------------------------------------------


def test_a_source_is_sent_only_the_filters_it_declared(store: Store) -> None:
    """feat-003/AC-7: a source's declaration is the whole contract about what it will filter."""
    source = FakeSource(applies=["price_min", "beds_min"], rows=[row("a")])
    definition = search(price_min=200_000, beds_min=3, year_built_min=1990)

    outcome = run(store, definition, sources={"fake": source})

    report = outcome.sources[0]
    assert report.applied_by_source == ("price_min", "beds_min")
    assert report.applied_locally == ("year_built_min",)


def test_the_filters_a_source_would_not_apply_are_applied_here(store: Store) -> None:
    """feat-003/AC-7: what the source will not narrow, the tool narrows itself."""
    source = FakeSource(
        applies=["price_min"],
        rows=[row("old", year_built=1950), row("new", year_built=2005)],
    )
    definition = search(price_min=100_000, year_built_min=1990)

    outcome = run(store, definition, sources={"fake": source})

    kept = [s.fields.address_line for s in store.snapshots_for_run(outcome.run.id)]
    assert kept == ["new Example Road"]


def test_a_kind_of_property_nobody_asked_for_is_dropped_here(store: Store) -> None:
    """feat-003/AC-7, feat-005/AC-14: the half of the contract that was not being kept.

    Written for a real fault. Redfin has no code for a farm, so the adapter mapped `farm` onto its
    code for land, and a search for houses and farms went out as a search for houses and land. The
    adapter then declared that it had narrowed by kind, so nothing checked, and six vacant lots sat
    in a household's results for days looking like a photograph problem, because a lot has no
    photograph.

    The adapter no longer declares it. This is the other end: given a source that says it did not
    narrow by kind, the run drops what the search did not ask for.
    """
    source = FakeSource(
        applies=["price_max"],
        rows=[
            row("house", property_type="single_family"),
            row("ranch", property_type="farm"),
            row("lot", property_type="land"),
            row("trailer", property_type="mobile"),
        ],
    )
    definition = search(price_max=1_000_000, property_types=("single_family", "farm"))

    outcome = run(store, definition, sources={"fake": source})

    kept = sorted(s.fields.property_type for s in store.snapshots_for_run(outcome.run.id))
    assert kept == ["farm", "single_family"]
    assert "property_types" in outcome.sources[0].applied_locally


def test_a_property_whose_kind_nobody_recorded_is_still_kept(store: Store) -> None:
    """feat-003/AC-28: an unfiltered field is not a failed test.

    The rule that makes the fix above safe. Dropping every property whose kind no site bothered to
    state would trade six lots for an unknown number of houses, which is the worse error: a lot in
    the list is an annoyance, and a house missing from it is the thing this tool exists to prevent.
    """
    source = FakeSource(
        applies=[],
        rows=[row("named", property_type="single_family"), row("silent", property_type=None)],
    )

    outcome = run(store, search(property_types=("single_family",)), sources={"fake": source})

    kept = sorted(s.fields.address_line for s in store.snapshots_for_run(outcome.run.id))
    assert kept == ["named Example Road", "silent Example Road"]


def test_the_result_says_who_applied_what(store: Store) -> None:
    """feat-003/AC-8: a source's opinion and the tool's, told apart rather than merged."""
    source = FakeSource(applies=["price_max"], rows=[row("a")])

    outcome = run(store, search(price_max=500_000, sqft_min=1000), sources={"fake": source})

    report = outcome.sources[0]
    assert "price_max" in report.applied_by_source
    assert "sqft_min" in report.applied_locally
    assert set(report.applied_by_source) & set(report.applied_locally) == set()


def test_a_property_is_kept_when_the_field_being_filtered_on_is_absent(store: Store) -> None:
    """feat-003/AC-28: the tool never reports that a house failed a test it could not run.

    Dropping a row for a missing field would delete a property on the strength of an absence, which
    is the same error as reading a source's silence as a sale, one field down.
    """
    source = FakeSource(rows=[row("priced", price=400_000), row("unpriced", price=None)])

    outcome = run(store, search(price_min=300_000), sources={"fake": source})

    kept = sorted(s.fields.address_line for s in store.snapshots_for_run(outcome.run.id))
    assert kept == ["priced Example Road", "unpriced Example Road"]


def test_the_local_filter_is_not_fooled_by_a_zero(store: Store) -> None:
    """feat-003/AC-28: absent means absent. Zero is a value, and it is tested like any other."""
    fields = row("a", price=0).fields
    assert passes(fields, SearchQuery(area=City("x"), price_min=1), ["price_min"]) is False
    assert passes(fields, SearchQuery(area=City("x"), price_max=1), ["price_max"]) is True


def test_a_freshness_hint_is_never_claimed_as_a_local_filter(store: Store) -> None:
    """feat-003/AC-32: freshness comes from local history, so it is not something applied here.

    A source that pushes it, pushes it. A source that does not leaves it unapplied rather than
    handing it to a local test that would have to answer from the source's own field, against
    product invariant 7.
    """
    source = FakeSource(applies=[], rows=[row("a")])

    outcome = run(store, search(listed_since="2026-01-01"), sources={"fake": source})

    report = outcome.sources[0]
    assert "listed_since" not in report.applied_by_source
    assert "listed_since" not in report.applied_locally


def test_a_property_whose_status_changed_is_kept_rather_than_filtered_away(store: Store) -> None:
    """feat-003/AC-32: a status change is evidence, and this is where it would have been lost.

    A saved search asks for what is for sale. A source that cannot apply that filter returns
    everything, and a local status test would then drop the very property that just went pending.
    The store would see nothing where the source had told us something, and would have no way to
    report that as anything but an unexplained disappearance. So the status filter shapes the ask
    and never hides the answer.
    """
    source = FakeSource(applies=[], rows=[row("a")])
    run(store, search(), sources={"fake": source})

    changed = FakeSource(applies=[], rows=[row("a", listing_status="pending")])
    outcome = run(store, search(), sources={"fake": changed})

    assert outcome.comparison.counts["gone"] == 0
    assert outcome.comparison.counts["changed"] == 1
    snapshot = store.snapshots_for_run(outcome.run.id)[0]
    assert snapshot.fields.listing_status == "pending"


def test_a_source_that_applies_the_status_filter_is_credited_with_it(store: Store) -> None:
    """feat-003/AC-8: never applied locally is not the same as never applied."""
    source = FakeSource(applies=["listing_status"], rows=[row("a")])

    outcome = run(store, search(), sources={"fake": source})

    assert "listing_status" in outcome.sources[0].applied_by_source


# -- overlapping areas -----------------------------------------------------


def test_a_property_returned_by_two_areas_is_recorded_once(store: Store) -> None:
    """feat-003/AC-29: two overlapping areas are our own doing, so the repeat is ours to drop."""
    source = FakeSource(per_area=[[row("a"), row("b")], [row("b"), row("c")]])

    outcome = run(store, search(areas=2), sources={"fake": source})

    seen = sorted(s.fields.address_line for s in store.snapshots_for_run(outcome.run.id))
    assert seen == ["a Example Road", "b Example Road", "c Example Road"]
    assert outcome.sources[0].rows == 3


def test_a_property_returned_twice_in_one_response_is_recorded_twice(store: Store) -> None:
    """feat-003/AC-29: a source contradicting itself is evidence, and both halves are kept.

    This is the same boundary the source adapters and the store each had to get right, one layer
    up. Collapsing this repeat would destroy a source row.
    """
    source = FakeSource(rows=[row("a", price=400_000), row("a", price=350_000)])

    outcome = run(store, search(), sources={"fake": source})

    prices = [r["price"] for r in store.connection.execute("SELECT price FROM raw_listings")]
    assert sorted(prices) == [350_000, 400_000]
    assert len(store.snapshots_for_run(outcome.run.id)) == 1, "one property, two rows about it"


# -- how a run ends --------------------------------------------------------


def test_a_clean_run_records_its_observations_and_a_comparison(store: Store) -> None:
    """feat-003/AC-9: a run entry names itself, its search, its times and every source."""
    outcome = run(store, search(), sources={"fake": FakeSource(rows=[row("a"), row("b")])})

    recorded = store.get_run(outcome.run.id)
    assert recorded.search_name == "portales"
    assert recorded.status == "completed"
    assert recorded.started_at and recorded.finished_at
    assert [(s.source, s.outcome, s.row_count) for s in recorded.sources] == [("fake", "ok", 2)]
    assert outcome.comparison.counts["new"] == 2


def test_a_degraded_run_still_records_everything_it_managed(store: Store) -> None:
    """feat-003/AC-5: degraded never means discarded."""
    sources = {
        "good": FakeSource("good", rows=[row("a")]),
        "bad": FakeSource("bad", outcome="failed", detail="the site refused"),
    }
    definition = search(sources=("good", "bad"))

    outcome = run(store, definition, sources=sources)

    assert outcome.degraded is True
    assert len(store.snapshots_for_run(outcome.run.id)) == 1
    assert outcome.comparison is not None
    named = {s.source: (s.outcome, s.detail) for s in store.get_run(outcome.run.id).sources}
    assert named["bad"] == ("failed", "the site refused")


def test_a_run_where_every_source_failed_marks_nothing_as_gone(store: Store) -> None:
    """feat-003/AC-6: absence is not evidence, and this is the run where that matters most."""
    good = {"fake": FakeSource(rows=[row("a"), row("b")])}
    first = run(store, search(), sources=good)
    assert first.comparison.counts["new"] == 2

    down = {"fake": FakeSource(outcome="failed", detail="the site was down")}
    second = run(store, search(), sources=down)

    assert second.degraded is True
    assert second.comparison.counts["gone"] == 0
    assert all(listing.presence == "observed" for listing in store.listings())


def test_a_source_that_failed_for_one_area_is_failed_for_the_run(store: Store) -> None:
    """feat-003/AC-6: partial coverage is not coverage, and saying so protects the store's rule."""

    class HalfDown(FakeSource):
        def run_search(self, query):
            self.outcome = "ok" if not self.queries else "failed"
            return super().run_search(query)

    outcome = run(store, search(areas=2), sources={"fake": HalfDown(rows=[row("a")])})

    assert outcome.sources[0].outcome == "failed"
    assert store.get_run(outcome.run.id).all_sources_succeeded is False


def test_a_search_naming_no_area_is_refused_before_a_run_is_started(store: Store) -> None:
    """feat-003/AC-16: nothing is recorded for a definition that cannot be asked."""
    definition = search()
    definition.asks = ()

    with pytest.raises(InvalidInput, match="no area"):
        run_search(store, definition, {"fake": FakeSource()})

    assert store.runs() == []


# -- preview images --------------------------------------------------------


def test_an_image_is_retrieved_once_and_not_again(store: Store, db_path: Path) -> None:
    """feat-003/AC-27: a stored image is a cache hit, and a cache hit is never re-fetched.

    At the shipped pacing this is the difference between a nightly run costing seconds and costing
    minutes, spent re-downloading pictures already on disk.
    """
    first_source = FakeSource(rows=[row("a"), row("b")])
    run(store, search(), sources={"fake": first_source})
    assert sorted(first_source.previews) == ["a", "b"]

    second_source = FakeSource(rows=[row("a"), row("b")])
    run(store, search(), sources={"fake": second_source})

    assert second_source.previews == [], "nothing was asked for a second time"
    kept = [store.get_preview_image(listing.id) for listing in store.listings()]
    assert all(image is not None for image in kept)


def test_a_run_with_images_off_retrieves_none_and_records_everything_else(store: Store) -> None:
    """feat-003/AC-27: skipping images changes nothing else about what a run records."""
    source = FakeSource(rows=[row("a"), row("b")])

    outcome = run(store, search(), sources={"fake": source}, images=False)

    assert source.previews == []
    assert len(store.snapshots_for_run(outcome.run.id)) == 2
    assert all(store.get_preview_image(listing.id) is None for listing in store.listings())


def test_a_property_with_no_image_offered_is_not_a_failure(store: Store) -> None:
    """feat-003/AC-27: a source with no picture for a row is not an error."""
    source = FakeSource(rows=[row("a")], images=False)

    outcome = run(store, search(), sources={"fake": source})

    assert outcome.sources[0].outcome == "ok"
    assert store.get_preview_image(store.listings()[0].id) is None


def test_an_image_that_cannot_be_retrieved_never_ends_the_run(store: Store) -> None:
    """feat-003/AC-27: an image is the least important thing a run collects."""

    class Broken(FakeSource):
        def fetch_preview(self, row):
            raise RuntimeError("the image host fell over")

    outcome = run(store, search(), sources={"fake": Broken(rows=[row("a")])})

    assert outcome.sources[0].outcome == "ok"
    assert len(store.snapshots_for_run(outcome.run.id)) == 1
