"""Results-only ranges and exact route identities.

feat-010/AC-111, feat-010/AC-112, feat-010/AC-113.
feat-007/AC-59, feat-007/AC-60, feat-007/AC-61.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from drive_time_fixture import saved_area
from homescout import api
from homescout import result_filters as filters
from homescout.enrich import result_routes
from homescout.enrich.matrix import durations
from homescout.enrich.provider import ProviderFailed
from homescout.errors import InvalidInput
from homescout.search import InMemorySearch
from homescout.sources.errors import SourceFailed
from web_fakes import client, held_workspace, listing, load, ours, reading, shared_store, theirs


class Routing:
    def __init__(self, answer=None):
        self.calls = []
        self.answer = answer

    def request(self, name, request):
        body = json.loads(request.body)
        self.calls.append((name, body))
        if isinstance(self.answer, Exception):
            raise self.answer
        value = self.answer
        if callable(value):
            value = value(body)
        if value is None:
            value = {"durations": [[3480] for _ in body["sources"]]}
        return SimpleNamespace(body=json.dumps(value).encode())


@pytest.fixture
def setup(store, monkeypatch):
    monkeypatch.setattr(result_routes, "credential", lambda _: "offline-test")
    work, family = saved_area(), saved_area("Family", "from", (34.3, -103.4))
    definition = InMemorySearch("portales", covers=(work, family))
    held = held_workspace(store, searches=[definition])
    load(store, [listing("family-collected", latitude=34.1, longitude=-103.3),
                 listing("missing", latitude=None, longitude=None)])
    areas = filters.destinations(definition)
    return held, definition, areas


def test_refs_ignore_duration_geometry_name_and_order_but_not_target(setup):
    held, definition, areas = setup
    work = definition.areas[0]
    work.travel["minutes"] = 60
    work.name = "Renamed Work"
    work.shape = None
    definition.covers = tuple(reversed(definition.covers))
    assert {one["ref"] for one in filters.destinations(definition)} == {a["ref"] for a in areas}
    work.address = "Different location"
    assert areas[0]["ref"] not in {a["ref"] for a in filters.destinations(definition)}
    with pytest.raises(InvalidInput, match="changed or was removed"):
        api.result_drive_time_filters(held, definition.name, [{"ref": areas[0]["ref"], "max": 60}])
    definition.name = "other-search"
    assert not {a["ref"] for a in areas} & {a["ref"] for a in filters.destinations(definition)}


@pytest.mark.parametrize("raw", [-1, "abc", "nan", "inf", True, {}, float("inf")])
def test_invalid_bounds(setup, raw):
    with pytest.raises(InvalidInput, match="finite, nonnegative"):
        filters.validate([{"ref": setup[2][0]["ref"], "min": raw}], setup[2])


def test_blank_zero_single_sided_and_invalid_order(setup):
    areas = setup[2]
    ref = areas[0]["ref"]
    assert filters.validate([], areas) == []
    assert filters.validate([{"ref": ref, "min": "  ", "max": None}], areas) == []
    assert filters.validate([{"ref": ref, "min": "0"}], areas) == [
        {"ref": ref, "min": 0, "max": None}]
    assert filters.validate([{"ref": ref, "max": 90}], areas)[0]["max"] == 90
    with pytest.raises(InvalidInput, match="greater than"):
        filters.validate([{"ref": ref, "min": 61, "max": 60}], areas)


@pytest.mark.parametrize(("minutes", "expected"), [(54.999999, "excluded"), (55, "match"),
    (58, "match"), (60, "match"), (60.000001, "excluded"), (None, "unavailable")])
def test_inclusive_unrounded_range(setup, minutes, expected):
    area = setup[2][0]
    row = {"drive_times": {area["ref"]: {"minutes": minutes,
           "status": "estimated" if minutes is not None else "unavailable"}}}
    assert filters.match(row, [{"ref": area["ref"], "min": 55, "max": 60}]) == expected
    assert filters.match(row, []) == "match"


def test_cross_area_58_minutes_no_collection_cap_and_cache_reuse(setup):
    held, _, areas = setup
    found = api.results(held, "portales")
    active = filters.validate([{"ref": areas[0]["ref"], "min": 55, "max": 60}], areas)
    routing = Routing({"durations": [[3480.000003]]})
    outcome = result_routes.calculate(held.store, found["rows"], areas, active, session=routing)
    assert outcome["saved"] == 1
    found = api.results(held, "portales")
    matched = filters.evaluate(found["rows"], active)
    assert matched["match"] == 1 and matched["unavailable"] == 1 and not matched["complete"]
    row = matched["rows"][0]
    assert row["drive_times"][areas[0]["ref"]]["minutes"] > 58
    key = filters.route_key(row, areas[0])
    areas[0]["routing"]["center"][0] += .00000001
    assert filters.route_key(row, areas[0]) != key
    areas = filters.destinations(setup[1])
    active[0]["min"] = None
    active[0]["max"] = 120
    result_routes.calculate(held.store, found["rows"], areas, active, session=routing)
    assert len(routing.calls) == 1
    family = {"ref": areas[1]["ref"], "min": 20, "max": 40}
    assert filters.match(row, [*active, family]) == "pending"
    row["drive_times"][areas[1]["ref"]] = {"minutes": 30, "status": "estimated"}
    assert filters.match(row, [*active, family]) == "match"
    row["drive_times"][areas[1]["ref"]]["minutes"] = 41
    assert filters.match(row, [*active, family]) == "excluded"


@pytest.mark.parametrize("direction", ["to", "from"])
def test_matrix_direction_and_full_precision(direction):
    routing = Routing({"durations": [[3300.000001], [3600]]} if direction == "to"
                      else {"durations": [[3300.000001, 3600]]})
    answer = list(durations(routing, [("a", (1, 2)), ("b", (3, 4))], (5, 6), direction,
                            "https://routing.invalid/matrix", "test-only"))
    body = routing.calls[0][1]
    assert body["locations"] == [[2, 1], [4, 3], [6, 5]]
    assert body["sources"] == ([0, 1] if direction == "to" else [2])
    assert body["destinations"] == ([2] if direction == "to" else [0, 1])
    assert answer[0][1] > 55 and answer[1][1] == 60


@pytest.mark.parametrize("value", [-1, True, "60", float("nan"), float("inf"), {}])
def test_malformed_matrix_is_not_numeric(value):
    routing = Routing({"durations": [[value]]})
    with pytest.raises(ProviderFailed, match="invalid durations"):
        list(durations(routing, [("a", (1, 2))], (3, 4), "to", "https://routing.invalid", "x"))


def test_failure_partial_batches_stale_retention_and_explicit_retry(setup, monkeypatch):
    held, _, areas = setup
    rows = [{"listing_id": str(i), "latitude": 34 + i * .001, "longitude": -103}
            for i in range(5)]
    active = filters.validate([{"ref": areas[0]["ref"], "max": 60}], areas)
    monkeypatch.setattr(result_routes, "BATCH_SIZE", 2)
    calls = []

    def answer(body):
        calls.append(body)
        if len(calls) > 1:
            raise SourceFailed("private credential must not escape")
        return {"durations": [[3480] for _ in body["sources"]]}

    outcome = result_routes.calculate(held.store, rows, areas, active, session=Routing(answer))
    assert outcome["degraded"] and "private credential" not in outcome["summary"]
    filters.read(held.store, rows, areas)
    assert filters.evaluate(rows, active)["match"] == 2
    assert filters.evaluate(rows, active)["unavailable"] == 3
    routing = Routing()
    result_routes.calculate(held.store, rows, areas, active, session=routing)
    assert not routing.calls
    result_routes.calculate(held.store, rows, areas, active, retry=True, session=routing)
    assert len(routing.calls) == 2
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    held.store.connection.execute("UPDATE enrichment_values SET fetched_at=?", (old,))
    held.store.connection.commit()
    key = filters.route_key(rows[0], areas[0])
    result_routes.calculate(held.store, rows, areas, active,
                            session=Routing(SourceFailed("secret")))
    assert held.store.cached_values(filters.PROVIDER, [key])[key]["route"].fetched_at == old
    filters.read(held.store, rows, areas)
    assert rows[0]["drive_times"][areas[0]["ref"]]["freshness"] == "stale"


def test_http_validation_guard_status_no_network_and_background_claim(setup, db_path, monkeypatch):
    held, definition, areas = setup
    routing = Routing()
    monkeypatch.setattr(result_routes, "paced_session", lambda: routing)
    with shared_store(db_path) as shared:
        browser = client(held_workspace(shared, searches=[definition]))
        url = "/api/result-drive-times/portales"
        response = browser.get("/api/results/portales", headers=reading()).json()
        assert len(response["drive_time_areas"]) == 2
        assert not routing.calls
        assert browser.post(url, json={}, headers=theirs()).status_code == 403
        assert browser.post(url, json={"filters": [{"ref": "old", "max": 60}]},
                            headers=ours()).status_code == 400
        active = [{"ref": areas[0]["ref"], "max": 60}]
        with api.recording(held, "another-pass"):
            result = browser.post(url, json={"filters": active}, headers=ours()).json()
            assert result["already_running"]
            assert not routing.calls
        assert browser.post(url, json={"filters": []}, headers=ours()).json()["inactive"]
        browser.post(url, json={"filters": active}, headers=ours()).raise_for_status()
        for _ in range(100):
            response = browser.get(url, headers=reading()).json()
            if response["pass"].get("finished"):
                break
            time.sleep(.02)
        assert response["pass"]["finished"] and len(routing.calls) == 1
        assert len(response["rows"]) == 2
        assert response["rows"][0]["drive_times"]


def test_unconfigured_and_no_areas(setup, monkeypatch):
    held, definition, _ = setup
    monkeypatch.setattr(result_routes, "credential", lambda _: "")
    found = api.results(held, "portales")
    assert not found["drive_time_configured"]
    assert all(value["status"] == "unavailable" for row in found["rows"]
               for value in row["drive_times"].values())
    definition.covers = ()
    assert api.results(held, "portales")["drive_time_areas"] == []


def test_shipped_javascript():
    completed = subprocess.run(["node", str(Path(__file__).with_name("results_drive_time.cjs"))],
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_include_exclude_targets_and_route_configuration_identity(setup, monkeypatch):
    from homescout.enrich import settings

    _, definition, areas = setup
    definition.covers[1].excluded = True
    assert filters.destinations(definition)[1]["excluded"]
    original = areas[0]["ref"]
    work = definition.covers[0]
    for key, changed in [("direction", "from"), ("profile", "other"),
                         ("options", {"avoid_features": ["tollways"]})]:
        before = dict(work.travel)
        work.travel[key] = changed
        assert filters.destinations(definition)[0]["ref"] != original
        work.travel = before
    work.centre = (work.centre[0] + .0000001, work.centre[1])
    assert filters.destinations(definition)[0]["ref"] != original
    monkeypatch.setenv("HOMESCOUT_ENRICH_CHURCH_DRIVE_URL", "https://different.invalid/matrix")
    assert filters.destinations(definition)[0]["routing"]["endpoint"] == settings.endpoint(
        "church_drive").url


def test_historical_result_coordinates_and_disappeared_rows(setup):
    held, _, areas = setup
    old = api.results(held, "portales")
    old_row = next(row for row in old["rows"] if row["latitude"] is not None)
    held.store.cache_values(filters.PROVIDER, filters.route_key(old_row, areas[0]), {
        "route": {"status": "estimated", "minutes": 58}})
    load(held.store, [listing("family-collected", latitude=34.2, longitude=-103.3)])
    historical = api.results(held, "portales", run_id=old["run_id"])
    historical_row = next(row for row in historical["rows"] if row["latitude"] == 34.1)
    assert historical_row["drive_times"][areas[0]["ref"]]["minutes"] == 58
    latest = api.results(held, "portales")
    new_row = next(row for row in latest["rows"] if row["latitude"] is not None)
    assert new_row["drive_times"][areas[0]["ref"]]["status"] == "pending"
    # Not-returned rows are a separate constructor and must carry their own cache values.
    held.store.connection.execute("UPDATE listings SET presence='disappeared' WHERE id=?",
                                  (new_row["listing_id"],))
    held.store.connection.commit()
    load(held.store, [listing("different", latitude=34.4, longitude=-103.4)])
    found = api.results(held, "portales")
    gone = next(row for row in found["rows"] if row["listing_id"] == new_row["listing_id"])
    assert gone["presence"] == "disappeared" and gone["latitude"] == 34.2
    assert gone["drive_times"][areas[0]["ref"]]["status"] == "pending"


def test_partial_background_remains_responsive_and_overlapping_start_deduplicates(
    setup, db_path, monkeypatch,
):
    held, definition, areas = setup
    definition.name = "background"
    areas = filters.destinations(definition)
    load(held.store, [listing(str(i), latitude=34.1 + i * .001, longitude=-103.3)
                      for i in range(4)], name="background")
    monkeypatch.setattr(result_routes, "BATCH_SIZE", 2)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def answer(body):
        calls.append(body)
        if len(calls) == 2:
            entered.set()
            assert release.wait(5)
        return {"durations": [[3480] for _ in body["sources"]]}

    monkeypatch.setattr(result_routes, "paced_session", lambda: Routing(answer))
    with shared_store(db_path) as shared:
        browser = client(held_workspace(shared, searches=[definition]))
        url = "/api/result-drive-times/background"
        body = {"filters": [{"ref": areas[0]["ref"], "min": 55, "max": 60}]}
        browser.post(url, json=body, headers=ours()).raise_for_status()
        try:
            assert entered.wait(5)
            before = time.perf_counter()
            partial = browser.get(url, headers=reading()).json()
            assert time.perf_counter() - before < 2
            assert not partial["pass"]["finished"]
            statuses = [r["drive_times"][areas[0]["ref"]]["status"] for r in partial["rows"]]
            assert statuses.count("estimated") == 2 and statuses.count("pending") == 2
            assert browser.post(url, json=body, headers=ours()).json()["already_running"]
        finally:
            release.set()
        for _ in range(100):
            final = browser.get(url, headers=reading()).json()
            if final["pass"]["finished"]:
                break
            time.sleep(.02)
        assert final["pass"]["finished"] and len(calls) == 2


def test_cli_json_core_parity(setup, db_path, monkeypatch):
    from cli_fakes import invoke, wired

    _, definition, areas = setup
    routing = Routing()
    monkeypatch.setattr(result_routes, "paced_session", lambda: routing)
    with wired([definition]):
        code, out, err = invoke(["result-drive-times", "portales", "--json"], db=db_path)
        assert code == 0, err
        assert len(json.loads(out)["areas"]) == 2 and not routing.calls
        raw = json.dumps([{"ref": areas[0]["ref"], "max": 60}])
        code, out, err = invoke(["result-drive-times", "portales", "--calculate",
                                 "--filters", raw, "--json"], db=db_path)
        assert code == 0, err
        assert json.loads(out)["outcome"]["saved"] == 1
        assert json.loads(out)["summary"]["match"] == 1
        assert json.loads(out)["summary"]["unavailable"] == 1


def test_routing_quota_clock_is_shared_between_preview_and_matrix_sessions():
    from homescout.sources.politeness import PolitenessConfig, Request, SourcePolicy
    from sources_fakes import FakeClock, FakeTransport, session_with

    clock = FakeClock()
    policy = PolitenessConfig(default=SourcePolicy(delay=6))
    first = session_with(FakeTransport(), clock=clock, config=policy)
    second = session_with(FakeTransport(), clock=clock, config=policy)
    request = Request("https://routing.invalid")
    first.request("drive_time", request)
    assert clock.now == 0
    second.request("church_drive", request)
    assert clock.now == 6
    first.request("drive_time", request)
    assert clock.now == 12


def test_failure_marks_all_unfinished_active_areas_unavailable(setup):
    held, _, areas = setup
    found = api.results(held, "portales")
    active = filters.validate([{"ref": area["ref"], "max": 60} for area in areas], areas)
    outcome = result_routes.calculate(held.store, found["rows"], areas, active,
                                      session=Routing(SourceFailed("private error")))
    assert outcome["degraded"]
    found = api.results(held, "portales", drive_time_filters=active)
    assert not found["rows"]
    assert found["drive_time_summary"]["pending"] == 0
    assert found["drive_time_summary"]["unavailable"] == 2


def test_http_core_numeric_filter_matches_full_pool(setup, db_path):
    held, definition, areas = setup
    rows = api.results(held, "portales")["rows"]
    active = [{"ref": areas[0]["ref"], "min": 55, "max": 60}]
    result_routes.calculate(held.store, rows, areas, filters.validate(active, areas),
                            session=Routing())
    with shared_store(db_path) as shared:
        browser = client(held_workspace(shared, searches=[definition]))
        found = browser.get("/api/result-drive-times/portales",
                            params={"filters": json.dumps(active)},
                            headers=reading()).json()
        assert len(found["rows"]) == 1 and found["summary"]["match"] == 1
        assert found["summary"]["unavailable"] == 1 and not found["summary"]["complete"]


def test_real_additive_collection_through_family_matches_work_58(store, monkeypatch):
    """feat-010/AC-112, feat-007/AC-59: actual collection provenance imposes no route cap."""
    from cli_fakes import FakeSource
    from homescout.matches import InMemoryQueue
    from homescout.search.definition import FileCatalog

    monkeypatch.setattr(result_routes, "credential", lambda _: "offline-test")
    folder = store.path.parent / "searches"
    folder.mkdir()
    work, family = saved_area(), saved_area("Family", center=(34.3, -103.4))
    documents = []
    for target in (work, family):
        documents.append({
            "type": "drive_time", "name": target.name, "address": target.address,
            "center": list(target.centre), "minutes": 45, "direction": "to",
            "provider": "openrouteservice", "public_place": True,
            "generated_at": "2026-11-09T00:00:00+00:00",
            "geometry": target.shape.__geo_interface__,
        })
    documents[0]["geometry"] = {"type": "Polygon", "coordinates": [
        [[-103.4, 34.2], [-103.2, 34.2], [-103.2, 34.3], [-103.4, 34.3], [-103.4, 34.2]]]}
    (folder / "cross-area.yaml").write_text(json.dumps({
        "name": "cross-area", "sources": ["realtor"], "areas": documents,
    }))
    property_row = listing("family-only", latitude=34.1, longitude=-103.3)
    source = FakeSource("realtor", per_area=((), (property_row,)), images=False)
    held = api.Workspace(store, FileCatalog(folder), InMemoryQueue(()),
                         sources={"realtor": source}, images=False)
    outcome = api.run_search(held, "cross-area")
    assert len(source.queries) == 2 and outcome.run is not None
    definition = held.catalog.load("cross-area")
    assert definition.areas[0].holds(property_row.fields) == "outside"
    assert definition.areas[1].holds(property_row.fields) == "inside"
    found = api.results(held, "cross-area")
    assert len(found["rows"]) == 1
    areas = filters.destinations(definition)
    active = [{"ref": areas[0]["ref"], "min": 55, "max": 60}]
    result_routes.calculate(store, found["rows"], areas, filters.validate(active, areas),
                            session=Routing({"durations": [[3480]]}))
    assert api.results(held, "cross-area", drive_time_filters=active)["drive_time_summary"] == {
        "match": 1, "excluded": 0, "pending": 0, "unavailable": 0, "complete": True,
    }
    assert definition.areas[0].travel["minutes"] == 45
