"""A running interface over a real store, and a client that behaves the way a browser does.

The client is the interesting part. FastAPI's own test client sends no `Origin` and no custom
header, which is exactly what a hostile page's request looks like, so a test that used it plainly
would be testing the guard by accident every time. `ours()` sends what the interface's own pages
send; `theirs()` sends what somebody else's page would.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from cli_fakes import FakeSource, row, search, workspace
from homescout import api
from homescout.records import ListingFields, SourceRow
from homescout.store import SourceOutcome, Store
from homescout.web.app import build

HOST = "127.0.0.1:8765"
ORIGIN = f"http://{HOST}"


def client(held: api.Workspace) -> Any:
    from fastapi.testclient import TestClient

    return TestClient(build(held), base_url=ORIGIN)


def shared_store(db_path: Path) -> Store:
    """A second connection to the same file, opened the way the interface opens one.

    A web server hands requests to worker threads and SQLite refuses a connection used from a thread
    other than the one that opened it. The interface holds a lock around every request, which is
    what makes lifting that check safe; see `store.db.connect`.
    """
    return Store.open(db_path, shared=True)


def ours(**extra: str) -> dict[str, str]:
    """The headers this interface's own pages send."""
    return {"Host": HOST, "Origin": ORIGIN, "X-Homescout": "1", **extra}


def reading() -> dict[str, str]:
    """A read from the interface's own page: no guard header needed."""
    return {"Host": HOST, "Origin": ORIGIN}


def theirs(origin: str = "https://evil.invalid") -> dict[str, str]:
    """What a page on somebody else's site sends when it tries this."""
    return {"Host": HOST, "Origin": origin}


def listing(identifier: str, **fields: Any) -> SourceRow:
    values: dict[str, Any] = {
        "price": 250_000,
        "listing_status": "for_sale",
        "beds": 3,
        "baths": 2,
        "sqft": 1_800,
        "lot_sqft": 43_560,
        "year_built": 1995,
        "property_type": "single_family",
        "address_line": f"{identifier} Example Road",
        "city": "Portales",
        "state": "NM",
        "postal_code": "88130",
        "county": "Roosevelt",
        "latitude": 34.1862,
        "longitude": -103.3452,
        "listing_url": f"https://listings.example.invalid/{identifier}",
    }
    values.update(fields)
    return SourceRow(
        source="realtor",
        fields=ListingFields(**values),
        payload={"id": identifier},
        source_listing_id=identifier,
    )


class Loaded:
    def __init__(self, run_id: str, by_source_id: Mapping[str, str]) -> None:
        self.run_id = run_id
        self.ids = dict(by_source_id)

    def __getitem__(self, source_listing_id: str) -> str:
        return self.ids[source_listing_id]


def load(store: Store, rows: Iterable[SourceRow], *, name: str = "portales") -> Loaded:
    held = list(rows)
    run = store.start_run(name)
    listing_ids = store.record_observations(run.id, "realtor", held) if held else []
    store.record_source_outcome(
        run.id, SourceOutcome(source="realtor", outcome="ok", row_count=len(held))
    )
    store.complete_run(run.id)
    return Loaded(
        run.id,
        {
            r.source_listing_id or "": listing_id
            for r, listing_id in zip(held, listing_ids, strict=False)
        },
    )


def held_workspace(store: Store, **kwargs: Any) -> api.Workspace:
    return workspace(
        store,
        searches=kwargs.pop("searches", None) or [search()],
        sources=kwargs.pop("sources", None) or {"fake": FakeSource(rows=[row("a")])},
        **kwargs,
    )


def fingerprint(store: Store) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of every table, for asking whether an action changed anything at all."""
    conn = store.connection
    tables = [
        name
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    found: dict[str, list[tuple[Any, ...]]] = {}
    for table in sorted(tables):
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 - names from sqlite
        found[table] = sorted(tuple(r) for r in rows)
    return found


WEB = Path(__file__).resolve().parents[1] / "src" / "homescout" / "web"
STATIC = WEB / "static"
VENDOR = WEB / "vendor"
