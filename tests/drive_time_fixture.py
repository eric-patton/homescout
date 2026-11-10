"""Disposable offline UI fixture: uv run python tests/drive_time_fixture.py.

Uses its own database under ignored data/, synthetic coordinates and a scripted routing service.
It never opens the user's workspace or sends routing requests.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from homescout import api
from homescout.search import InMemoryCatalog, InMemorySearch
from homescout.search.areas import build as area
from homescout.web.app import build
from web_fakes import listing, load


def saved_area(name="Work", direction="to", center=(34.18, -103.34)):
    return area({
        "type": "drive_time", "name": name, "address": f"{name} public library",
        "center": list(center), "minutes": 45, "direction": direction,
        "provider": "openrouteservice", "public_place": True,
        "generated_at": "2026-11-09T00:00:00+00:00",
        "geometry": {"type": "Polygon", "coordinates": [
            [[-104, 33], [-102, 33], [-102, 35], [-104, 35], [-104, 33]]]},
    })


def main():
    from homescout.enrich import result_routes

    class OfflineRouting:
        def request(self, name, request):
            body = json.loads(request.body)
            time.sleep(.6)
            to = body["sources"][0] != len(body["locations"]) - 1
            values = [54.9999, 55, 58, 60, 60.0001, None, 59] if to else [
                25, 19.999, 30, 40, 40.0001, None, 20]
            points = body["sources"] if to else body["destinations"]
            minutes = [values[round((body["locations"][i][1] - 34.1) / .001)] for i in points]
            seconds = [None if value is None else value * 60 for value in minutes]
            return SimpleNamespace(body=json.dumps({
                "durations": [[value] for value in seconds] if to else [seconds],
            }).encode())

    result_routes.credential = lambda _: "offline-fixture-only"
    result_routes.paced_session = OfflineRouting
    result_routes.BATCH_SIZE = 2
    root = Path(__file__).resolve().parents[1] / "data" / "card3-fixture"
    root.mkdir(parents=True, exist_ok=True)
    definitions = [
        InMemorySearch("Work-Family", covers=(saved_area(), saved_area(
            "Family", "from", (34.3, -103.4)))),
        InMemorySearch("No-drive-areas"),
        InMemorySearch("Large-pool", covers=(saved_area(),)),
    ]
    workspace = api.open_workspace(root / "fixture.db", shared=True,
                                   catalog=InMemoryCatalog(definitions), images=False)
    if not workspace.store.latest_snapshots():
        rows = [listing(str(i), latitude=34.1 + i * .001, longitude=-103.3,
                        address_line=f"{name} Fixture Road", price=200000 + i * 10000)
                for i, name in enumerate(["Below55", "Boundary55", "FamilyCollected58",
                                          "Boundary60", "Above60", "Unavailable", "Pending"])]
        rows.append(listing("missing", latitude=None, longitude=None,
                            address_line="Missing coordinates"))
        load(workspace.store, rows, name="Work-Family")
        load(workspace.store, rows[:3], name="No-drive-areas")
    if not workspace.store.seen_by_search("Large-pool"):
        from homescout import result_filters

        many = [listing(f"large{i:05}", latitude=34.1 + i * .000001, longitude=-103.31,
                        address_line=f"Large fixture {i:05} Road", price=100000 + i)
                for i in range(5000)]
        load(workspace.store, many, name="Large-pool")
        destination = result_filters.destinations(definitions[2])[0]
        for i, row in enumerate(many):
            key = result_filters.route_key({"latitude": row.fields.latitude,
                                           "longitude": row.fields.longitude}, destination)
            workspace.store.cache_values(result_filters.PROVIDER, key, {"route": {
                "status": "estimated", "minutes": i % 100,
            }})
    uvicorn.run(build(workspace), host="127.0.0.1", port=47833, log_level="warning")


if __name__ == "__main__":
    main()
