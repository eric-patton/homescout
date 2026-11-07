"""Church driving times, including batching, failures and saved surfaces."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from enrich_fakes import FakeProvider
from homescout import api
from homescout.enrich import cache, settings
from homescout.enrich.church import BATCH_SIZE, DESTINATION, ChurchDrive
from homescout.enrich.pass_ import run_pass
from homescout.enrich.provider import ProviderFailed
from homescout.enrich.travel import KEY
from homescout.export import export_run
from homescout.sources.errors import SourceFailed
from web_fakes import client, held_workspace, listing, load, reading, shared_store

LA = (30.55, -90.52)


class Routing:
    def __init__(self, answer=None):
        self.requests = []
        self.answer = answer

    def request(self, name, request):
        self.requests.append(request)
        body = json.loads(request.body)
        answer = self.answer
        if callable(answer):
            answer = answer(body)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            answer = {"durations": [[720 + i * 60] for i in body["sources"]]}
        return SimpleNamespace(body=json.dumps(answer).encode())


@pytest.fixture(autouse=True)
def credential(monkeypatch):
    monkeypatch.setenv(KEY, "test-routing-credential")


def seed(store, count=1):
    return load(store, [listing(f"la{i}", state="LA", latitude=LA[0] + i * .001,
                                longitude=LA[1]) for i in range(count)])


def values(store, place=LA):
    return cache.values_for(store, [ChurchDrive()], *place)


def test_direction_numeric_minutes_and_coordinate_only_request(store):
    """feat-007/AC-56, feat-007/AC-57: origins precede one fixed destination."""
    seed(store)
    routing = Routing({"durations": [[754.2]]})
    outcome = run_pass(store, [ChurchDrive()], session=routing)
    assert not outcome.degraded
    assert values(store)["church_drive_minutes"].value == 12.6
    request = routing.requests[0]
    assert json.loads(request.body) == {
        "locations": [[LA[1], LA[0]], [DESTINATION[1], DESTINATION[0]]],
        "sources": [0], "destinations": [1], "metrics": ["duration"],
        "resolve_locations": False,
    }
    assert request.headers["Authorization"] == "test-routing-credential"
    assert request.allow_redirects is False
    assert request.max_bytes == 1_000_000
    assert settings.pacing(("church_drive",)).per_source["church_drive"].delay == 6


def test_louisiana_only_and_unlocatable_with_no_requests_for_other_states(store):
    """feat-007/AC-56: actual state, not a Louisiana bounding box containing Mississippi."""
    load(store, [listing("ms", state="MS", latitude=31, longitude=-90),
                 listing("missing", state="LA", latitude=None, longitude=None)])
    routing = Routing()
    outcome = run_pass(store, [ChurchDrive()], session=routing)
    assert outcome.without_location == 1
    assert not routing.requests
    found = values(store, (31, -90))
    assert found["church_drive_minutes"].value is None
    assert found["church_drive_status"].value == "outside coverage"


def test_key_comes_from_attached_database_and_missing_key_skips(store, monkeypatch):
    """feat-007/AC-57: the selected store's .env, not an unrelated default workspace."""
    monkeypatch.delenv(KEY)
    seed(store)
    (store.path.parent / ".env").write_text(f"{KEY}=from-attached-store\n", encoding="utf-8")
    routing = Routing()
    run_pass(store, [ChurchDrive()], session=routing)
    assert routing.requests[0].headers["Authorization"] == "from-attached-store"
    (store.path.parent / ".env").write_text("", encoding="utf-8")
    result = run_pass(store, [ChurchDrive()], session=Routing())
    assert result.providers[0].outcome == "skipped"
    assert KEY in result.providers[0].detail


def test_batches_are_bounded_and_fresh_second_pass_costs_zero(store):
    """feat-007/AC-58: many-to-one, at most 100 origins and fresh-cache reuse."""
    seed(store, BATCH_SIZE + 3)
    routing = Routing()
    provider = ChurchDrive()
    first = run_pass(store, [provider], session=routing)
    assert first.providers[0].looked_up == BATCH_SIZE + 3
    assert sorted(len(json.loads(r.body)["sources"]) for r in routing.requests) == [3, 100]
    second = run_pass(store, [provider], session=routing)
    assert second.providers[0].looked_up == 0
    assert len(routing.requests) == 2


@pytest.mark.parametrize("answer", [
    {}, {"durations": []}, {"durations": [[-1]]}, {"durations": [[True]]},
    {"durations": [["20"]]}, {"durations": [[float("nan")]]},
    {"durations": [[float("inf")]]}, {"durations": [[2, 3]]},
])
def test_invalid_durations_never_replace_a_stale_value(store, answer):
    """feat-007/AC-57, feat-007/AC-58: malformed values are failures, never guesses."""
    seed(store)
    key = cache.key_for(*LA, 6)
    old = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    store.cache_values("church_drive", key,
                       {"church_drive_minutes": 22.4, "church_drive_status": "estimated"})
    store.connection.execute(
        "UPDATE enrichment_values SET fetched_at=? WHERE provider='church_drive'", (old,)
    )
    store.connection.commit()
    outcome = run_pass(store, [ChurchDrive()], session=Routing(answer))
    assert outcome.degraded
    assert values(store)["church_drive_minutes"].value == 22.4
    assert values(store)["church_drive_minutes"].status == "stale"
    assert values(store)["church_drive_minutes"].fetched_at == old


def test_null_route_is_blank_with_a_reason(store):
    """feat-007/AC-56: an unreachable route is different from zero minutes."""
    seed(store)
    run_pass(store, [ChurchDrive()], session=Routing({"durations": [[None]]}))
    assert values(store)["church_drive_minutes"].value is None
    assert values(store)["church_drive_status"].value == "route unavailable"


def test_point_snapping_failure_isolated_without_losing_other_houses(store):
    """feat-007/AC-58: split a bad origin, with good rows still saved."""
    seed(store, 3)

    def answer(body):
        if any(location[1] == LA[0] for location in body["locations"][:-1]):
            return SourceFailed("point not found", status=404,
                                detail='{"error":{"code":6010}}')
        return {"durations": [[600] for _ in body["sources"]]}

    result = run_pass(store, [ChurchDrive()], session=Routing(answer))
    assert not result.degraded
    assert values(store)["church_drive_status"].value == "route unavailable"
    assert values(store, (LA[0] + .001, LA[1]))["church_drive_minutes"].value == 10


def test_failed_later_batch_keeps_completed_values_and_other_provider_runs(store):
    """feat-007/AC-58: streaming persistence and provider failure isolation."""
    seed(store, BATCH_SIZE + 1)
    calls = 0

    def answer(body):
        nonlocal calls
        calls += 1
        if calls == 2:
            return SourceFailed("test-routing-credential", status=429,
                                detail="test-routing-credential")
        return {"durations": [[600] for _ in body["sources"]]}

    result = run_pass(store, [ChurchDrive(), FakeProvider()], session=Routing(answer))
    assert result.providers[0].looked_up == BATCH_SIZE
    assert result.providers[0].outcome == "failed"
    assert "test-routing-credential" not in result.providers[0].detail
    assert result.providers[1].outcome == "ok"
    assert calls == 2, "quota errors must not cause recursive batch splitting"


def test_unencrypted_endpoint_is_refused(store, monkeypatch):
    """feat-007/AC-57: never send the credential over HTTP."""
    seed(store)
    monkeypatch.setenv("HOMESCOUT_ENRICH_CHURCH_DRIVE_URL", "http://invalid.example/matrix")
    routing = Routing()
    result = run_pass(store, [ChurchDrive()], session=routing)
    assert result.degraded and not routing.requests


def test_results_detail_and_exports_use_saved_numeric_minutes_only(store, tmp_path, monkeypatch):
    """feat-010/AC-110, feat-011/AC-17: shared saved data, numeric XLSX and matching CSV."""
    from homescout.export.columns import DEFAULT

    loaded = seed(store)
    run_pass(store, [ChurchDrive()], session=Routing())

    def no_fetch(*_args, **_kwargs):
        raise ProviderFailed("a read must not route")

    monkeypatch.setattr(ChurchDrive, "fetch_many", no_fetch)
    held = held_workspace(shared_store(store.path))
    found = api.results(held, "portales")
    name = "Drive to Church (min)"
    column = next(c for c in found["columns"] if c["name"] == name)
    assert column["kind"] == "number"
    assert found["rows"][0]["values"][name] == 12
    with client(held) as browser:
        response = browser.get("/api/results/portales", headers=reading())
        assert response.json()["rows"][0]["values"][name] == 12
        detail = browser.get(f"/api/listings/{loaded['la0']}", headers=reading()).json()
        assert detail["listing"]["enrichment"]["church_drive_minutes"] == 12
        saved = detail["listing"]["church_drive"]
        assert saved["minutes"] == 12 and saved["status"] == "estimated"
        assert saved["freshness"] == "fresh" and saved["fetched_at"]
    assert name not in DEFAULT
    templates = tmp_path / "templates"
    templates.mkdir(exist_ok=True)
    (templates / "church.yaml").write_text(f'columns: ["Property", "{name}"]\n', encoding="utf-8")
    for format_ in ("xlsx", "csv"):
        target = tmp_path / f"church.{format_}"
        export_run(store, loaded.run_id, target, root=tmp_path, template="church", format=format_)
        if format_ == "xlsx":
            book = load_workbook(target)
            assert book.worksheets[0].cell(2, 2).value == 12
            assert book.worksheets[0].cell(2, 2).data_type == "n"
        else:
            with target.open(encoding="utf-8-sig", newline="") as file:
                assert list(csv.reader(file))[1][1] == "12.0"


def test_cli_selects_only_church_and_reports_unknown_provider(store, db_path):
    """feat-007/AC-56: the optional provider can be selected on its own from the CLI."""
    from cli_fakes import invoke

    code, output, _ = invoke(["enrich", "--provider", "church_drive", "--json"], db=db_path)
    assert code == 0
    assert [p["provider"] for p in json.loads(output)["providers"]] == ["church_drive"]
    code, _, error = invoke(["enrich", "--provider", "unknown"], db=db_path)
    assert code == 2 and "no provider named unknown" in error


def test_real_table_sort_and_arrangement_functions_keep_blanks_last_and_preferences():
    """feat-010/AC-110: execute shipped table functions, without launching a browser."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable for the JavaScript unit check")
    source = Path(__file__).parents[1] / "src/homescout/web/static/results.js"
    script = r'''
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
let saved = null;
const context = vm.createContext({whenReady() {}, window: {localStorage: {
  getItem() { return saved; }, setItem() {},
}}});
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
const run = code => JSON.parse(vm.runInContext("JSON.stringify(" + code + ")", context));
assert.deepEqual(run("[100, null, 9, 20, undefined, 0, ''].sort((a,b)=>compare(a,b,1))"),
  [0,9,20,100,null,"",null]);
assert.deepEqual(run("[100, null, 9, 20, 0, ''].sort((a,b)=>compare(a,b,-1))"),
  [100,20,9,0,null,""]);
vm.runInContext(`state.declared = ["Property", "Price", "Drive to Church (min)", "Beds"]
  .map(name => ({name, kind: "number", origin: "enriched"}));
  arrange(state.declared);`, context);
assert.equal(run("state.hidden['Drive to Church (min)'] || false"), false);
saved = JSON.stringify({order: ["Beds", "Price", "Property"], hidden: ["Beds"], view: "custom"});
assert.deepEqual(run("arrange(state.declared).filter(sortable).map(c=>c.name)"),
  ["Beds", "Price", "Drive to Church (min)", "Property"]);
assert.equal(run("state.hidden.Beds"), true);
assert.equal(run("state.hidden['Drive to Church (min)'] || false"), false);
'''
    result = subprocess.run([node, "-e", script, str(source)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
