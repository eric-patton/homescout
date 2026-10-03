"""Address circles through real parsing, cached geocoding, runs and both surfaces."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from cli_fakes import FakeSource, invoke, row
from enrich_fakes import CountingTransport, session
from homescout import api
from homescout.enrich.boundaries import CensusBoundaries
from homescout.records import ListingFields
from homescout.search.areas import AreaError, build
from homescout.sources.base import BoundingBox, Capabilities, PointRadius
from homescout.store import Store
from searches_fakes import boundaries, sourced, workspace, write
from web_fakes import client, ours, reading, shared_store

ADDRESS = "52150 Taylor Dr, Loranger, LA 70446"
CENTER = [30.611282, -90.369808]
MATCHED = "52150 TAYLOR DR, LORANGER, LA, 70446"


def geocoder(*, matched: bool = True) -> CountingTransport:
    return CountingTransport({"onelineaddress": {"result": {"addressMatches": [{
        "coordinates": {"x": CENTER[1], "y": CENTER[0]},
        "matchedAddress": MATCHED,
        "addressComponents": {"zip": "70446"},
    }] if matched else []}}})


def test_coordinate_radius_retains_address_name_reason_and_exact_distance() -> None:
    """feat-004/AC-23: explicit coordinates need no lookup and retain radius metadata."""
    area = build({"type": "radius", "address": ADDRESS, "center": CENTER, "miles": 10,
                  "name": "Near family", "reason": "Stay nearby."})
    assert area.label() == "Near family"
    assert area.reason == "Stay nearby."
    assert area.address == ADDRESS
    assert area.holds(ListingFields(latitude=30.62, longitude=-90.37)) == "inside"
    assert area.holds(ListingFields(latitude=31.0, longitude=-90.37)) == "outside"
    assert area.holds(ListingFields()) == "unknown"
    assert area.coarse_for(Capabilities(accepts_areas=(PointRadius,))) == (
        PointRadius(*CENTER, 10),
    )
    box = area.coarse_for(Capabilities(accepts_areas=(BoundingBox,)))[0]
    assert isinstance(box, BoundingBox)


@pytest.mark.parametrize("miles", [0, -1, True, "10", float("inf"), float("nan")])
def test_radius_rejects_invalid_mileage(miles) -> None:
    """feat-004/AC-23: invalid radii cannot become an unbounded search."""
    with pytest.raises(AreaError):
        build({"type": "radius", "address": ADDRESS, "center": CENTER, "miles": miles})


@pytest.mark.parametrize("center", [[40, -100], [75, -155], [89, 10], [30, 179]])
def test_radius_box_contains_its_entire_great_circle(center) -> None:
    """feat-004/AC-4 feat-004/AC-23: bounding-box adapters cannot lose the circle's edges."""
    area = build({"type": "radius", "center": center, "miles": 200})
    box = area.coarse_for(Capabilities(accepts_areas=(BoundingBox,)))[0]
    # Points 200 miles away at every bearing, from the spherical destination formula.
    latitude, longitude = map(math.radians, center)
    arc = 200 / 3958.7613
    for bearing in map(math.radians, range(360)):
        lat = math.asin(math.sin(latitude) * math.cos(arc)
                        + math.cos(latitude) * math.sin(arc) * math.cos(bearing))
        lon = longitude + math.atan2(math.sin(bearing) * math.sin(arc) * math.cos(latitude),
                                    math.cos(arc) - math.sin(latitude) * math.sin(lat))
        lat = math.degrees(lat)
        lon = (math.degrees(lon) + 180) % 360 - 180
        assert box.south - 1e-9 <= lat <= box.north + 1e-9
        assert box.west - 1e-9 <= lon <= box.east + 1e-9


def test_failed_address_lookup_keeps_other_areas_running(tmp_path: Path) -> None:
    """feat-004/AC-23: a failed circle does not block the search's other areas."""
    write(tmp_path / "searches", "mixed", text=(
        f"name: mixed\nareas:\n  - {{type: radius, address: '{ADDRESS}', miles: 10}}\n"
        "  - {type: city, value: 'Portales, NM'}\nsources: [fake]\n"
    ))
    source = FakeSource(rows=[row("inside")])
    transport = geocoder(matched=False)
    with sourced("fake"), Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store, sources={"fake": source}) as held:
            api.run_search(held, "mixed")
            assert len(source.queries) == 1
            assert source.queries[0].area.as_term() == "Portales, NM"
            assert len(api.results(held, "mixed")["rows"]) == 1


@pytest.mark.parametrize("address,miles", [("", 10), (True, 10), (ADDRESS, 0), (ADDRESS, True)])
def test_invalid_preview_makes_no_lookup(tmp_path: Path, address, miles) -> None:
    """feat-004/AC-24: reject malformed input before spending a geocoder request."""
    from homescout.errors import InvalidInput

    transport = geocoder()
    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store) as held, pytest.raises(InvalidInput):
            api.radius_area(held, address, miles)
        assert transport.count == 0


def test_unmatched_preview_is_reported_without_writing_a_search(tmp_path: Path) -> None:
    """feat-004/AC-24: an unmatched address never produces an invented circle."""
    from homescout.errors import InvalidInput

    transport = geocoder(matched=False)
    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with (
            boundaries(provider), workspace(store) as held,
            pytest.raises(InvalidInput, match="Census could not place"),
        ):
            api.radius_area(held, ADDRESS, 10)
        assert transport.count == 1
        assert not list((tmp_path / "searches").glob("*.yaml"))


def test_address_radius_is_prepared_before_queries_even_after_validation(tmp_path: Path) -> None:
    """feat-004/AC-23: validation fetches nothing; two runs share one address lookup."""
    write(tmp_path / "searches", "nearby", text=(
        f"name: nearby\nareas:\n  - {{type: radius, address: '{ADDRESS}', miles: 10}}\n"
        "sources: [fake]\n"
    ))
    transport = geocoder()
    source = FakeSource(rows=[
        row("inside", latitude=30.62, longitude=-90.37),
        row("outside", latitude=31.0, longitude=-90.37),
    ])
    with sourced("fake"), Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store, sources={"fake": source}) as held:
            assert not [p for p in api.validate_search(held, "nearby") if p.severity == "problem"]
            assert transport.count == 0
            api.run_search(held, "nearby")
            api.run_search(held, "nearby")
            assert transport.count == 1
            assert source.queries[0].area == PointRadius(*CENTER, 10)
            assert len(api.results(held, "nearby")["rows"]) == 1


def test_unmatched_address_radius_never_delegates_to_a_source() -> None:
    """feat-004/AC-23: unresolved addresses do not turn into unrestricted/source lookups."""
    area = build({"type": "radius", "address": ADDRESS, "miles": 10})
    with boundaries(None):
        assert area.coarse_for(Capabilities()) == ()
        assert area.holds(ListingFields(latitude=30.62, longitude=-90.37)) == "unknown"
        assert not area.delegated


def test_preview_uses_cached_lookup_and_returns_the_matched_address(tmp_path: Path) -> None:
    """feat-004/AC-24: preview is reusable and writes no search definition."""
    transport = geocoder()
    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store) as held:
            found = api.radius_area(held, ADDRESS, 10)
            assert found == {"area": {
                "type": "radius", "address": ADDRESS, "center": CENTER, "miles": 10.0,
            }, "matched": MATCHED}
            assert api.radius_area(held, ADDRESS, 5)["area"]["miles"] == 5
            assert transport.count == 1
            assert not list((tmp_path / "searches").glob("*.yaml"))


def test_preview_cli_and_http_share_the_result_and_radius_round_trip(tmp_path: Path) -> None:
    """feat-004/AC-24 feat-010/AC-106 feat-010/AC-107: one preview, lossless save/reopen."""
    db = tmp_path / "homescout.db"
    transport = geocoder()
    with Store.open(db) as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store) as held:
            expected = api.radius_area(held, ADDRESS, 10)
    code, output, _ = invoke(["searches", "radius", ADDRESS, "--miles", "10", "--json"], db=db)
    assert code == 0
    assert json.loads(output)["area"] == expected["area"]
    with shared_store(db) as store, workspace(store) as held, client(held) as browser:
        response = browser.post("/api/areas/radius", json={"address": ADDRESS, "miles": 10},
                                headers=ours())
        assert response.status_code == 200, response.text
        assert response.json()["area"] == expected["area"]
        browser.put("/api/searches/nearby", headers=ours())
        area = {**expected["area"], "name": "Near family", "reason": "Stay nearby."}
        saved = browser.post("/api/searches/nearby", json={"set": {"areas": [area],
                             "exclude_areas": [{**area, "miles": 1}]}}, headers=ours())
        assert saved.status_code == 200, saved.text
        found = browser.get("/api/searches/nearby", headers=reading()).json()["search"]
        assert found["areas"][0]["center"] == CENTER
        assert found["areas"][0]["miles"] == 10
        assert found["areas"][0]["address"] == ADDRESS
        assert found["areas"][0]["name"] == "Near family"
        assert found["areas"][0]["reason"] == "Stay nearby."
        assert found["exclusions"][0]["miles"] == 1
        assert found["exclusions"][0]["excluded"] is True
