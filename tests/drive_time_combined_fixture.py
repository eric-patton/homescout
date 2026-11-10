"""Offline integration fixture for cards #2 and #3, at 127.0.0.1:47834."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from cli_fakes import row
from drive_time_fixture_server import Routing, Source, work_geometry
from enrich_fakes import session
from homescout import api, result_filters
from homescout.enrich import result_routes
from homescout.web.app import build
from searches_fakes import polygon, sourced, workspace, write
from test_searches_drive_time import area, credential
from web_fakes import shared_store


def main():
    root = Path(".uv/card3-combined").resolve()
    root.mkdir(parents=True, exist_ok=True)
    credential(root)
    if not (root / "searches/commute.yaml").exists():
        work = {**area(work_geometry(45)), "minutes": 45, "direction": "from", "name": "Work",
                "matched": "Work public destination"}
        family = {**area(polygon(-90.1, 30.6, -90.0, 30.7)), "name": "Family",
                  "address": "Family public destination", "center": [30.65, -90.05]}
        write(root / "searches", "commute", "name: commute\nareas: " + json.dumps([
            work, family]) + "\nsources: [fake]\n")

    class Matrix:
        calls = 0

        def request(self, name, request):
            self.calls += 1
            body = json.loads(request.body)
            return SimpleNamespace(body=json.dumps({"durations": [
                [3480 for _ in body["destinations"]] for _ in body["sources"]]}).encode())

    class Polygons(Routing):
        calls = 0

        def __call__(self, request):
            self.calls += 1
            return super().__call__(request)

    matrix, polygons = Matrix(), Polygons()
    result_routes.credential = lambda _: "offline-combined-only"
    result_routes.paced_session = lambda: matrix
    source = Source(rows=[row("Work-original", latitude=30.63, longitude=-90.35),
                          row("Work-expanded", latitude=30.63, longitude=-90.23),
                          row("Family-only", latitude=30.63, longitude=-90.05)])
    with shared_store(root / "homescout.db") as store, sourced("fake"), workspace(
        store, sources={"fake": source},
    ) as held:
        held._travel_session = session(polygons)
        api.run_search(held, "commute")
        found = api.results(held, "commute")
        for target in found["drive_time_areas"]:
            for listing in found["rows"]:
                store.cache_values(result_filters.PROVIDER, result_filters.route_key(
                    listing, target), {"route": {"minutes": 58 if target["name"] == "Work"
                                                else 30, "status": "estimated"}})
        app = build(held)

        @app.get("/fixture/counts")
        def counts():
            return {"matrix": matrix.calls, "polygons": polygons.calls,
                    "collection_queries": len(source.queries)}

        uvicorn.run(app, host="127.0.0.1", port=47834, log_level="warning")


if __name__ == "__main__":
    main()
