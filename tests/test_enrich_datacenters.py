"""How close the data centres are: the arithmetic and the honesty, not the servers.

Nothing here talks to FracTracker or to OpenStreetMap. The fetching is replaced and what is tested
is everything around it, which is where this provider can be wrong in ways nobody would notice.

Two of these tests exist because of a specific failure mode rather than a criterion in the
abstract. A distance is read as measured whatever is written beside it, so the one that asserts
three confidences reporting three different ways is the one holding the whole design up. And a
site nobody could place better than "somewhere in this county" reads, if it is dropped, exactly
like a site nobody asked about, which would make a house beside a seven-thousand-megawatt proposal
look clean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homescout.enrich import datacenters
from homescout.enrich.provider import ProviderFailed

# One tracker record per confidence, all at the same place, so a test can hold the distance still
# and vary only how well the record knows where the thing is.
NEAR = (34.0000, -106.0000)


def tracker(*sites: dict) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {
                        "facility_name": site.get("name", "A data centre"),
                        "status": site.get("status", "Operating"),
                        "location_confidence": site.get("confidence", "High"),
                        "state": site.get("state", "NM"),
                        "county": site.get("county", "Socorro"),
                        "operator_name": site.get("operator", ""),
                        "mw": site.get("mw", ""),
                        "property_size_acres": site.get("acres", ""),
                        "expected_date_online": "",
                        "information_source": site.get("source", ""),
                        "city": "",
                        "tenant": "",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [site.get("longitude", -106.0), site.get("latitude", 34.0)],
                    },
                }
                for site in sites
            ],
        }
    )


def overpass(*ways: dict) -> str:
    return json.dumps(
        {
            "elements": [
                {
                    "type": "way",
                    "tags": {"telecom": "data_center", "name": way.get("name", "A building")},
                    "geometry": way["geometry"],
                }
                for way in ways
            ]
        }
    )


def answering(monkeypatch, tracked: str, built: str, asked: list | None = None):
    def fetched(url: str, what: str, body: bytes | None = None) -> bytes:
        if asked is not None:
            asked.append(url)
        return (built if body is not None else tracked).encode()

    monkeypatch.setattr(datacenters, "_fetch", fetched)


def index(tmp_path: Path, monkeypatch, tracked: str, built: str = "") -> list[dict]:
    answering(monkeypatch, tracked, built or overpass())
    sites = datacenters.tracked(tmp_path, "https://tracker.example/query")
    if built:
        sites.extend(datacenters.built(tmp_path, "https://overpass.example/api"))
    return sites


# -- the three kinds -------------------------------------------------------


def test_the_seven_statuses_become_three_kinds_and_two_that_are_not_measured(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-31: the mapping is read from a table, not inferred at the point of use."""
    sites = index(
        tmp_path,
        monkeypatch,
        tracker(
            {"status": "Operating"},
            {"status": "Expanding"},
            {"status": "Approved/Permitted/Under construction"},
            {"status": "Proposed"},
            {"status": "Pre-proposal"},
            {"status": "Suspended"},
            {"status": "Cancelled"},
        ),
    )
    assert [site["kind"] for site in sites] == [
        "operating",
        "operating",
        "approved",
        "proposed",
        "proposed",
        "suspended",
        "cancelled",
    ]
    # A cancelled project is not a thing near a house, and a suspended one is not one today.
    nearby = datacenters.Nearby(sites)
    assert {site["kind"] for site in nearby.sites} == {"operating", "approved", "proposed"}


def test_a_status_this_build_does_not_know_is_a_failure_that_names_it(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-31: never a guessed bucket, on the same principle as an unknown hazard class."""
    with pytest.raises(ProviderFailed) as raised:
        index(tmp_path, monkeypatch, tracker({"status": "Mothballed"}))
    assert "mothballed" in str(raised.value).lower()


# -- the precision is the caveat -------------------------------------------


def test_one_site_at_one_distance_reports_three_different_ways(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-32: the number's own precision is what says how well the place is known.

    The load-bearing test of this change. A distance is read as measured whatever is written in the
    next column, so the caveat has to be inside the value, and the way to prove it is inside the
    value is to hold the distance still and vary only the confidence.
    """
    # Far enough that a tenth of a mile and a whole mile are visibly different answers.
    at = {"latitude": 34.0800, "longitude": -106.0000}
    sites = index(
        tmp_path,
        monkeypatch,
        tracker(
            {"confidence": "High", "status": "Operating", **at},
            {"confidence": "Medium", "status": "Approved/Permitted/Under construction", **at},
            {"confidence": "Low", "status": "Proposed", **at},
        ),
    )
    nearby = datacenters.Nearby(sites)

    pinned = nearby.nearest("operating", *NEAR)
    roughly = nearby.nearest("approved", *NEAR)
    assert pinned is not None and roughly is not None

    exact = datacenters.rounded(pinned[1], "high")
    whole = datacenters.rounded(roughly[1], "medium")
    assert exact is not None and whole is not None
    # The same ground, told to two different precisions.
    assert round(exact) == round(whole)
    assert whole == float(round(whole)), "a town-level site must not claim a tenth of a mile"
    assert exact != whole or exact % 1 == 0

    # A county centroid gets no distance at all: there is no honest number to give.
    assert nearby.nearest("proposed", *NEAR) is None
    assert datacenters.rounded(1.234, "low") is None
    assert datacenters.rounded(1.234, "") is None


def test_no_value_ever_reports_more_precision_than_its_source_declares(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-32: asserted over the whole table rather than at one example."""
    for confidence, places in datacenters.PLACES_BY_CONFIDENCE.items():
        got = datacenters.rounded(7.123456, confidence)
        assert got is not None
        assert got == round(7.123456, places)
    assert "low" not in datacenters.PLACES_BY_CONFIDENCE


# -- somewhere in this county ----------------------------------------------


SOCORRO = {
    "type": "MultiPolygon",
    "coordinates": [[[[-107.0, 33.5], [-106.0, 33.5], [-106.0, 34.5], [-107.0, 34.5],
                      [-107.0, 33.5]]]],
}


def test_a_site_placed_no_better_than_a_county_is_an_answer_rather_than_a_gap(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-33 and feat-007/AC-7: three readings that must stay apart.

    Without this the house next to a seven-thousand-megawatt proposal reads exactly like a house
    nobody asked about, which is the confusion the whole fresh/stale/missing vocabulary exists to
    prevent, and it would be manufactured by this change rather than inherited.
    """
    sites = index(
        tmp_path,
        monkeypatch,
        tracker({"confidence": "Low", "status": "Proposed", "county": "Socorro County"}),
    )
    nearby = datacenters.Nearby(sites, [{"outline": SOCORRO, "kinds": ["proposed"]}])

    inside = nearby.counties_holding(34.0, -106.5)
    outside = nearby.counties_holding(36.5, -105.6)

    # A determined answer at the grain the source knows.
    assert inside == ("proposed",)
    # A determined negative: asked, and there is nothing here.
    assert outside == ()
    # And distinct from a distance, which this site can never produce.
    assert nearby.nearest("proposed", 34.0, -106.5) is None


def test_the_word_county_does_not_stop_the_two_records_matching() -> None:
    """feat-007/AC-33: the tracker is not consistent with itself and the boundary service is.

    This is the quietest way this provider could be wrong. "Lea County" never matching "Lea" would
    mean the county value silently never fires, and a value that never fires reads as a value
    nobody asked for.
    """
    assert datacenters.bare_county("Lea County") == datacenters.bare_county("Lea")
    assert datacenters.bare_county("Doña Ana") == "doña ana"
    assert datacenters.bare_county("St. Mary's Parish") == datacenters.bare_county("St. Mary's")
    assert datacenters.bare_county("") == ""


# -- both sources, and what a building is measured to ----------------------


def test_a_mapped_building_is_measured_to_its_outline_and_not_to_a_point_inside_it(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-34: a house beside a campus is told how far the campus is, not its middle."""
    # A building roughly a mile across, whose near edge is much closer than its centre.
    corner = [
        {"lon": -106.0100, "lat": 34.0000},
        {"lon": -106.0100, "lat": 34.0200},
        {"lon": -105.9800, "lat": 34.0200},
        {"lon": -105.9800, "lat": 34.0000},
        {"lon": -106.0100, "lat": 34.0000},
    ]
    sites = index(
        tmp_path, monkeypatch, tracker(), overpass({"name": "A campus", "geometry": corner})
    )
    nearby = datacenters.Nearby(sites)
    got = nearby.nearest("operating", 34.0100, -106.0300)
    assert got is not None
    site, miles = got
    assert site["name"] == "A campus"

    middle = datacenters.miles_between((34.0100, -106.0300), (site["latitude"], site["longitude"]))
    assert miles < middle, "measured to the middle rather than to the edge"

    # A property standing on one reads zero, which is the right answer and not an error.
    on_it = nearby.nearest("operating", 34.0100, -106.0000)
    assert on_it is not None and on_it[1] == 0.0


def test_both_sources_feed_the_running_distance_and_neither_is_de_duplicated(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-34: the nearest of two measurements of one site is that site."""
    here = [
        {"lon": -106.0010, "lat": 34.0000},
        {"lon": -106.0010, "lat": 34.0010},
        {"lon": -106.0000, "lat": 34.0010},
        {"lon": -106.0000, "lat": 34.0000},
        {"lon": -106.0010, "lat": 34.0000},
    ]
    sites = index(
        tmp_path,
        monkeypatch,
        tracker({"status": "Operating", "latitude": 34.0005, "longitude": -106.0005}),
        overpass({"name": "The same place", "geometry": here}),
    )
    nearby = datacenters.Nearby(sites)
    assert len(nearby.sites) == 2, "the two sources are kept apart, not merged"
    got = nearby.nearest("operating", 34.0500, -106.0005)
    assert got is not None
    # Whichever wins, a double count costs nothing when the answer is a minimum.
    assert got[1] > 0


# -- the indexes -----------------------------------------------------------


def test_the_two_indexes_age_at_different_speeds(tmp_path: Path, monkeypatch) -> None:
    """feat-007/AC-30: a building does not move and a project's status is the whole point."""
    assert datacenters.BUILT_DAYS > datacenters.TRACKED_DAYS
    asked: list[str] = []
    answering(monkeypatch, tracker({"status": "Operating"}), overpass(), asked)

    datacenters.tracked(tmp_path, "https://tracker.example/query")
    datacenters.tracked(tmp_path, "https://tracker.example/query")
    assert len(asked) == 1, "a fresh index was fetched twice"

    # Wound past the tracker's life but not the buildings'.
    where = tmp_path / "datacenters" / "tracked.json"
    held = json.loads(where.read_text(encoding="utf-8"))
    held["fetched_at"] = "2020-01-01T00:00:00+00:00"
    where.write_text(json.dumps(held), encoding="utf-8")

    datacenters.tracked(tmp_path, "https://tracker.example/query")
    assert len(asked) == 2, "a stale index was not refreshed"


def test_a_source_that_will_not_answer_costs_a_refresh_rather_than_the_column(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-007/AC-4 and feat-007/AC-30: stale beats nothing, and nothing is ever removed."""
    answering(monkeypatch, tracker({"name": "Still here"}), overpass())
    datacenters.tracked(tmp_path, "https://tracker.example/query")

    where = tmp_path / "datacenters" / "tracked.json"
    held = json.loads(where.read_text(encoding="utf-8"))
    held["fetched_at"] = "2020-01-01T00:00:00+00:00"
    where.write_text(json.dumps(held), encoding="utf-8")

    def broken(url: str, what: str, body: bytes | None = None) -> bytes:
        raise ProviderFailed(f"{what}: the public record did not answer")

    monkeypatch.setattr(datacenters, "_fetch", broken)
    still = datacenters.tracked(tmp_path, "https://tracker.example/query")
    assert [site["name"] for site in still] == ["Still here"]


def test_the_buildings_query_is_a_constant_that_interpolates_nothing() -> None:
    """feat-007/AC-13, D-15: a query language, and a state name would be concatenated into it."""
    assert "{" not in datacenters.BUILT_QUERY.replace("]->", "")
    assert "%s" not in datacenters.BUILT_QUERY
    assert 'ISO3166-1"="US"' in datacenters.BUILT_QUERY
    for key, value in datacenters.TAGS:
        assert f'["{key}"="{value}"]' in datacenters.BUILT_QUERY


# -- the provider in the pass ----------------------------------------------


def test_the_provider_exists_supplies_five_values_and_asks_nobody_per_property() -> None:
    """feat-007/AC-28 and feat-007/AC-29: the only provider here whose fetch makes no request."""
    from homescout.enrich.registry import create, registered

    found = [one for one in create(registered()) if one.name == "data_centers"]
    assert found, "the data centre provider is not registered"
    provider = found[0]
    assert provider.values() == (
        "data_center_miles",
        "data_center_approved_miles",
        "data_center_proposed_miles",
        "data_center_nearest",
        "data_center_in_county",
    )
    # Four places is about eleven metres, finer than the finest distance this reports. Three would
    # be about a hundred and ten, which is the same order as the 161 metres a tenth of a mile
    # resolves, and a cache key coarser than its own value would undo the precision rule.
    assert provider.precision() == 4
    assert provider.ttl_days() == datacenters.TRACKED_DAYS


def test_every_value_the_provider_supplies_is_a_name_a_criterion_can_use() -> None:
    """feat-007/AC-28: the registry's two-way check, asserted rather than trusted."""
    from homescout.enrich.registry import create, registered
    from homescout.rules import namespace as ns

    for provider in create(registered()):
        if provider.name != "data_centers":
            continue
        for name in provider.values():
            field = ns.find(name)
            assert field is not None, f"{name} is not in the rule namespace"
            assert field.origin == "enriched"


def test_a_house_with_nothing_near_it_still_gets_an_answer(tmp_path: Path, monkeypatch) -> None:
    """feat-007/AC-7: no site of a kind is a determined negative, not a value nobody obtained."""
    sites = index(tmp_path, monkeypatch, tracker({"status": "Operating"}))
    nearby = datacenters.Nearby(sites)
    assert nearby.nearest("operating", *NEAR) is not None
    # Nothing proposed anywhere in the index, which is an answer about the index rather than a gap.
    assert nearby.nearest("proposed", *NEAR) is None
