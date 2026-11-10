"""Offline multi-batch fixture with explicit release gates for review regressions.

Run with uv run python tests/drive_time_progress_fixture.py. All data is disposable, all
routing is scripted, and the HTTP server binds only to 127.0.0.1:47835.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from drive_time_fixture import saved_area
from homescout import api
from homescout.enrich import result_routes
from homescout.search import InMemoryCatalog, InMemorySearch
from homescout.sources.errors import SourceFailed
from homescout.web.app import build
from web_fakes import listing, load


def main():
    root = Path("data/card3-progress-review1-5ec11ee0").resolve()
    root.mkdir(parents=True, exist_ok=True)
    names = ("Clear-during-routing", "Navigate-during-routing")
    definitions = []
    targets = {}
    for index, name in enumerate(names):
        work = saved_area(center=(34.18 + index * .01, -103.34))
        family = saved_area("Family", "from", (34.3 + index * .01, -103.4))
        definitions.append(InMemorySearch(name, covers=(work, family)))
        for target in (work, family):
            targets[tuple(round(coordinate, 6) for coordinate in target.centre)] = name
    gates = {name: threading.Event() for name in names}
    calls = dict.fromkeys(names, 0)
    waiting = dict.fromkeys(names, False)

    class Routing:
        def request(self, _, request):
            body = json.loads(request.body)
            lon, lat = body["locations"][-1]
            name = targets[(round(lat, 6), round(lon, 6))]
            calls[name] += 1
            if calls[name] > 1 and not gates[name].is_set():
                waiting[name] = True
                if not any(gates[name].wait(5) for _ in range(36)):
                    raise SourceFailed("Offline fixture batch was not released in time")
                waiting[name] = False
            to = body["sources"][0] != len(body["locations"]) - 1
            values = [54.9999, 55, 58, 60, 60.0001, None, 59] if to else [
                25, 19.999, 30, 40, 40.0001, None, 20]
            points = body["sources"] if to else body["destinations"]
            minutes = [values[round((body["locations"][i][1] - 34.1) / .001)] for i in points]
            seconds = [None if value is None else value * 60 for value in minutes]
            return SimpleNamespace(body=json.dumps({
                "durations": [[value] for value in seconds] if to else [seconds],
            }).encode())

    result_routes.credential = lambda _: "offline-review-fixture-only"
    result_routes.paced_session = Routing
    result_routes.BATCH_SIZE = 2
    with api.open_workspace(root / "fixture.db", shared=True,
                            catalog=InMemoryCatalog(definitions), images=False) as workspace:
        if not workspace.store.latest_snapshots():
            rows = [listing(str(i), latitude=34.1 + i * .001, longitude=-103.3,
                            address_line=f"{label} Fixture Road", price=200000 + i * 10000)
                    for i, label in enumerate(["Below55", "Boundary55", "FamilyCollected58",
                                               "Boundary60", "Above60", "Unavailable", "Pending"])]
            rows.append(listing("missing", latitude=None, longitude=None,
                                address_line="Missing coordinates"))
            for name in names:
                load(workspace.store, rows, name=name)
        app = build(workspace)

        @app.get("/fixture/status")
        def status():
            return {"calls": calls, "waiting": waiting}

        @app.post("/fixture/release/{name}")
        def release(name: str):
            gates[name].set()
            return {"released": name}

        uvicorn.run(app, host="127.0.0.1", port=47835, log_level="warning")


if __name__ == "__main__":
    main()
