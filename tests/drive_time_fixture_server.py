"""Local browser fixture: uv run python tests/drive_time_fixture_server.py.

Uses a disposable workspace under .uv/card2-preview, never personal data or live providers.
59 minutes simulates a routing refusal; 54 minutes delays routing for cancellation checks.
Create .uv/card2-preview/fail-save to simulate a failed area save, then remove it to retry.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import uvicorn

from cli_fakes import FakeSource, row
from enrich_fakes import _Response, session
from homescout import api
from homescout.errors import InvalidInput
from homescout.search.definition import FileCatalog
from homescout.sources.base import BoundingBox, Capabilities
from homescout.web.app import build
from searches_fakes import polygon, sourced, workspace, write
from test_searches_drive_time import STAMP, area, credential
from web_fakes import shared_store


def work_geometry(minutes):
    return polygon(-90.4, 30.6, -90.4 + minutes / 300, 30.7)


class Routing:
    def __call__(self, request):
        minutes = json.loads(request.body)["range"][0] / 60
        if minutes == 54:
            time.sleep(4)
        if minutes == 59:
            return _Response(b'{"error":"Fixture routing refusal"}', 503)
        return _Response(json.dumps({"features": [{
            "geometry": work_geometry(minutes)}]}).encode(), 200)


class Source(FakeSource):
    def capabilities(self):
        return Capabilities(accepts_areas=(BoundingBox,), ceiling=None, page_size=200)


class Catalog(FileCatalog):
    def edit(self, name, changes):
        if (self.directory.parent / "fail-save").exists() and "areas" in changes:
            raise InvalidInput("Fixture save failure. Your draft can be retried.")
        return super().edit(name, changes)


if __name__ == "__main__":
    root = Path(".uv/card2-preview").resolve()
    root.mkdir(parents=True, exist_ok=True)
    credential(root)
    if not (root / "searches/commute.yaml").exists():
        work = {**area(work_geometry(45)), "minutes": 45, "direction": "from", "name": "Work",
                "matched": "Work public destination", "reason": "Keep the commute manageable."}
        family = {**area(polygon(-90.1, 30.6, -90.0, 30.7)), "name": "Family",
                  "address": "Family public destination", "center": [30.65, -90.05]}
        write(root / "searches", "commute", "# Preserve this fixture comment.\nname: commute\n"
              + "areas: " + json.dumps([work, family]) + "\nsources: [fake]\n"
              + "filters: {price: {max: 500000}} # untouched settings\n")
    source = Source(rows=[
        row("Work-original", latitude=30.63, longitude=-90.35),
        row("Work-expanded", latitude=30.63, longitude=-90.23),
        row("Family-only", latitude=30.63, longitude=-90.05),
    ])
    with shared_store(root / "homescout.db") as store, sourced("fake"), workspace(
            store, sources={"fake": source}) as held:
        held.catalog = Catalog(root / "searches")
        held._travel_session = session(Routing())
        api.run_search(held, "commute")
        print(f"Fixture editor: http://127.0.0.1:47829/search/commute ({STAMP})", flush=True)
        uvicorn.run(build(held), host="127.0.0.1", port=47829, log_level="warning")
