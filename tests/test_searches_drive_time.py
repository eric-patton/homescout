"""Driving polygons through the real transport, cache, areas, runs and both surfaces."""

from __future__ import annotations

import json

import pytest

from cli_fakes import FakeSource, invoke, row
from enrich_fakes import CountingTransport, _Response, session
from homescout import api
from homescout.enrich.boundaries import CensusBoundaries
from homescout.enrich.travel import DriveTimes
from homescout.errors import InvalidInput
from homescout.records import ListingFields
from homescout.search.areas import AreaError, build
from homescout.sources.base import BoundingBox, Capabilities, PointRadius
from homescout.store import Store
from searches_fakes import boundaries, sourced, workspace, write
from test_searches_radius import ADDRESS, CENTER, geocoder
from web_fakes import client, ours, reading, shared_store, theirs

GEOMETRY = {"type": "Polygon", "coordinates": [[[-90.4, 30.6], [-90.3, 30.6],
             [-90.3, 30.7], [-90.4, 30.7], [-90.4, 30.6]],
             [[-90.39, 30.65], [-90.38, 30.65], [-90.38, 30.66],
              [-90.39, 30.66], [-90.39, 30.65]]]}
STAMP = "2026-10-03T12:00:00+00:00"
KEY = "fake-routing-key-that-must-not-leak"


def area(geometry=None):
    return {"type": "drive_time", "address": ADDRESS, "center": CENTER, "minutes": 30,
            "direction": "to", "provider": "openrouteservice", "public_place": True,
            "generated_at": STAMP, "matched": None, "geometry": geometry or GEOMETRY}


class Routing(CountingTransport):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.body = {"features": [{"geometry": GEOMETRY}]}
        self.status = 200

    def __call__(self, request):
        self.requests.append(request.url)
        self.calls.append(request)
        return _Response(json.dumps(self.body).encode(), self.status)


def credential(root):
    (root / ".env").write_text(f"HOMESCOUT_ORS_API_KEY={KEY}\n", encoding="utf-8")


@pytest.mark.parametrize("changes", [
    {"minutes": 0}, {"minutes": 61}, {"minutes": True}, {"minutes": float("nan")},
    {"minutes": "30"}, {"minutes": 10**1000}, {"direction": "both"}, {"address": ""},
    {"center": [True, -90]}, {"center": [91, -90]}, {"center": [30, float("inf")]},
    {"center": [10**1000, -90]},
    {"public_place": False}, {"provider": "unknown"}, {"generated_at": "yesterday"},
    {"generated_at": "2026-10-03T12:00:00"}, {"geometry": {"type": "Point", "coordinates": [0, 0]}},
])
def test_saved_drive_time_refuses_invalid_parameters_and_geometry(changes):
    """feat-004/AC-25: a generated region must be usable and carry valid provenance."""
    with pytest.raises(AreaError):
        build({**area(), **changes})


def test_polygon_holes_multipart_coarse_coverage_and_metadata():
    """feat-004/AC-25: membership follows the saved polygon, including holes and islands."""
    generated = build({**area(), "name": "Church", "reason": "Stay within thirty minutes."})
    assert generated.label() == "Church"
    assert generated.reason == "Stay within thirty minutes."
    assert generated.travel["license"] == "CC-BY-SA 4.0"
    assert "OpenStreetMap" in generated.travel["attribution"]
    assert generated.holds(ListingFields(latitude=30.62, longitude=-90.37)) == "inside"
    assert generated.holds(ListingFields(latitude=30.655, longitude=-90.385)) == "outside"
    assert generated.holds(ListingFields(latitude=31, longitude=-90.37)) == "outside"
    assert generated.holds(ListingFields()) == "unknown"
    assert generated.coarse_for(Capabilities(accepts_areas=(BoundingBox,))) == (
        BoundingBox(30.6, -90.4, 30.7, -90.3),)
    circle = generated.coarse_for(Capabilities(accepts_areas=(PointRadius,)))[0]
    from homescout.search.geometry import miles_between
    assert circle.miles >= miles_between((circle.latitude, circle.longitude), (30.6, -90.4))
    multi = {"type": "MultiPolygon", "coordinates": [GEOMETRY["coordinates"],
             [[[-90.2, 30.8], [-90.1, 30.8], [-90.1, 30.9], [-90.2, 30.9], [-90.2, 30.8]]]]}
    assert build(area(multi)).holds(ListingFields(latitude=30.85, longitude=-90.15)) == "inside"


def test_large_drive_time_runs_realtor_with_exact_shape_and_exclusions(tmp_path):
    """feat-004/AC-25, AC-3, AC-4: a large drive polygon is covered without clipping to 50mi."""
    from homescout.search.geometry import miles_between
    from homescout.sources.realtor import RealtorSource
    from searches_fakes import polygon
    from sources_fakes import FakeResponse, FakeTransport, session_with
    from test_sources_realtor import homes

    geometry = polygon(-91.2, 30.1, -89.95, 31.1)
    geometry["coordinates"].append(polygon(-90.8, 30.5, -90.6, 30.7)["coordinates"][0])
    wanted = {"southwest": (30.11, -91.19), "southeast": (30.11, -89.96),
              "northwest": (31.09, -91.19), "northeast": (31.09, -89.96),
              "middle": (30.75, -90.5)}
    population = {**wanted, "outside": (30.01, -90.6), "hole": (30.6, -90.7),
                  "excluded": (30.6, -90.3)}
    returned = set()

    def answer(request):
        body = json.loads(request.body)
        assert body["operationName"] == "GetHomeSearch", "the saved center needs no lookup"
        radius = float(body["variables"]["radius"][:-2])
        if radius > 50:
            return FakeResponse(body=b'{"errors":[{"message":"query.nearby.radius too large"}]}')
        lon, lat = body["variables"]["coordinates"]
        found = []
        for identifier, point in population.items():
            if miles_between((lat, lon), point) <= radius:
                returned.add(identifier)
                home = json.loads(json.dumps(homes()[0]))
                home["property_id"] = identifier
                home["location"]["address"].update(line=f"{identifier} Example Road",
                    coordinate={"lat": point[0], "lon": point[1]})
                found.append(home)
        return FakeResponse(body=json.dumps({"data": {"homeSearch": {
            "total": len(found), "results": found}}}).encode())

    transport = FakeTransport(default=answer)
    source = RealtorSource(session_with(transport))
    write(tmp_path / "searches", "church", "name: church\nareas: ["
          + json.dumps({**area(geometry), "minutes": 60}) + "]\nexclude_areas: ["
          + json.dumps({"type": "polygon", "geometry": polygon(-90.4, 30.5, -90.2, 30.7)})
          + "]\nsources: [realtor]\n")
    with Store.open(tmp_path / "homescout.db") as store, workspace(
            store, sources={"realtor": source}) as held:
        definition = held.catalog.load("church")
        assert definition.queries_for(source.capabilities())[0].area.miles > 50
        outcome = api.run_search(held, "church")
        assert outcome.sources[0].outcome == "ok", outcome.sources[0].detail
        assert outcome.sources[0].rows == len(wanted)
        assert returned == set(population), "local filtering, rather than undersized queries"
        assert len(transport.requests) == 4


def test_provider_reuses_cache_refreshes_and_sends_lon_lat_and_direction(tmp_path):
    """feat-004/AC-26: one cached polygon, explicit refresh, safe request and fresh credentials."""
    transport = Routing()
    credential(tmp_path)
    with Store.open(tmp_path / "homescout.db") as store:
        provider = DriveTimes(store, session(transport))
        first = provider.polygon(CENTER, 30, "to")
        assert provider.polygon(CENTER, 30, "to") == first
        assert transport.count == 1
        request = transport.calls[0]
        assert request.url == "https://api.heigit.org/openrouteservice/v2/isochrones/driving-car"
        assert not request.allow_redirects
        assert request.headers["Authorization"] == KEY
        assert request.headers["Accept"] == "application/geo+json"
        assert json.loads(request.body) == {"locations": [[-90.369808, 30.611282]],
            "range": [1800], "range_type": "time", "location_type": "destination"}
        assert KEY not in json.dumps(first)
        provider.polygon(CENTER, 30, "from")
        assert json.loads(transport.calls[-1].body)["location_type"] == "start"
        (tmp_path / ".env").write_text("HOMESCOUT_ORS_API_KEY=changed-key\n", encoding="utf-8")
        provider.polygon(CENTER, 30, "to", refresh=True)
        assert transport.count == 3
        assert transport.calls[-1].headers["Authorization"] == "changed-key"


@pytest.mark.parametrize("body,status", [({}, 200), ({"features": []}, 200),
    ({"features": [{"geometry": {"type": "Polygon", "coordinates": []}}]}, 200),
    ({"error": {"message": KEY}}, 401), ({"error": {"message": KEY}}, 429)])
def test_failed_refresh_retains_cache_and_never_exposes_key(tmp_path, body, status):
    """feat-004/AC-26: malformed or refused refresh never replaces a good boundary."""
    credential(tmp_path)
    transport = Routing()
    with Store.open(tmp_path / "homescout.db") as store:
        provider = DriveTimes(store, session(transport))
        good = provider.polygon(CENTER, 30, "to")
        transport.body, transport.status = body, status
        with pytest.raises(InvalidInput) as caught:
            provider.polygon(CENTER, 30, "to", refresh=True)
        assert KEY not in str(caught.value)
        assert provider.polygon(CENTER, 30, "to") == good


@pytest.mark.parametrize("changes", [{"minutes": -1}, {"direction": "both"},
                                        {"public_place": False}, {"center": [90, 999]},
                                        {"refresh": "yes"}])
def test_invalid_preview_contacts_nobody(tmp_path, changes):
    """feat-004/AC-26: invalid inputs and missing public consent spend no lookup."""
    transport = geocoder()
    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store) as held, pytest.raises(InvalidInput):
            api.drive_time_area(held, **{ "address": ADDRESS, "minutes": 30,
                                        "public_place": True, **changes})
        assert transport.count == 0


def test_no_key_and_cached_polygon_remain_usable(tmp_path):
    """feat-004/AC-26: a saved calculation remains usable without a live credential."""
    transport = Routing()
    with Store.open(tmp_path / "homescout.db") as store:
        provider = DriveTimes(store, session(transport))
        with pytest.raises(InvalidInput, match="HOMESCOUT_ORS_API_KEY"):
            provider.polygon(CENTER, 30, "to")
        assert transport.count == 0
        credential(tmp_path)
        good = provider.polygon(CENTER, 30, "to")
        (tmp_path / ".env").write_text("", encoding="utf-8")
        assert provider.polygon(CENTER, 30, "to") == good
        with pytest.raises(InvalidInput):
            provider.polygon(CENTER, 30, "to", refresh=True)


def test_saved_polygon_runs_without_network_or_credentials(tmp_path):
    """feat-004/AC-25: repeated runs locally filter the stored shape with no geography lookups."""
    def no_lookup(*args):
        raise AssertionError("A saved driving polygon reached the network")
    class Offline:
        containing = no_lookup
        prepare_addresses = no_lookup
        place_address = no_lookup
    write(tmp_path / "searches", "church", text=("name: church\nareas:\n  - "
        + json.dumps(area()) + "\nexclude_areas:\n  - "
        + json.dumps({"type": "radius", "center": [30.62, -90.37], "miles": 0.01})
        + "\nsources: [fake]\n"))
    source = FakeSource(rows=[row("yes", latitude=30.63, longitude=-90.36),
                             row("excluded", latitude=30.62, longitude=-90.37),
                             row("outside", latitude=31, longitude=-90.37)])
    with (Store.open(tmp_path / "homescout.db") as store, sourced("fake"),
          boundaries(Offline()), workspace(store, sources={"fake": source}) as held):
        assert not api.validate_search(held, "church")
        api.run_search(held, "church")
        api.run_search(held, "church")
        assert len(api.results(held, "church")["rows"]) == 1


def test_geocoded_preview_http_cli_and_lossless_save(tmp_path):
    """feat-004/AC-26 feat-010/AC-108 feat-010/AC-109: shared preview, cache and area round-trip."""
    db = tmp_path / "homescout.db"
    credential(tmp_path)
    routing = Routing()
    with Store.open(db) as store:
        provider = CensusBoundaries(store, session(geocoder()), fetch=False)
        with workspace(store) as held, boundaries(provider):
            held._travel_session = session(routing)
            first = api.drive_time_area(held, ADDRESS, 30, public_place=True)
            assert not list((tmp_path / "searches").glob("*.yaml"))
    code, output, _ = invoke(["searches", "drive-time", ADDRESS, "--minutes", "30",
                             "--public-place", "--json"], db=db)
    assert code == 0
    expected = json.loads(json.dumps(first["area"]))
    assert json.loads(output)["area"] == expected
    with shared_store(db) as store, workspace(store) as held, client(held) as browser:
        denied = browser.post("/api/areas/drive-time", json={}, headers=theirs())
        assert denied.status_code == 403
        response = browser.post("/api/areas/drive-time", json={"address": ADDRESS, "minutes": 30,
            "public_place": True}, headers=ours())
        assert response.status_code == 200, response.text
        assert response.json()["area"] == expected
        browser.put("/api/searches/church", headers=ours())
        saved = browser.post("/api/searches/church", json={"set": {"areas": [
            {**expected, "name": "Church", "reason": "Keep the drive short."}],
            "exclude_areas": [expected]}}, headers=ours())
        assert saved.status_code == 200, saved.text
        result = browser.get("/api/searches/church", headers=reading()).json()["search"]
        for entry in (result["areas"][0], result["exclusions"][0]):
            for key, value in expected.items():
                if key != "type":
                    assert entry[key] == value
            assert entry["kind"] == "drive_time"
        assert result["areas"][0]["reason"] == "Keep the drive short."
        assert routing.count == 1


def test_changed_geometry_starts_new_observation_scope(tmp_path):
    """feat-004/AC-25: a regenerated boundary changes what a run compares against."""
    from homescout.search.definition import FileCatalog

    directory = tmp_path / "searches"
    write(directory, "church", text=("name: church\nareas:\n  - " + json.dumps(area())
                                    + "\nsources: [realtor]\n"))
    catalog = FileCatalog(directory)
    before = catalog.load("church").observation_revision
    changed = {"type": "Polygon", "coordinates":
               [[[-90.4, 30.6], [-90.3, 30.6], [-90.3, 30.8], [-90.4, 30.8], [-90.4, 30.6]]]}
    catalog.edit("church", {"areas": [area(changed)]})
    assert catalog.load("church").observation_revision != before
