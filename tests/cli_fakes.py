"""Running the real loop and the real command line, with no network and no clock.

The point of these is that nothing is stubbed except the outside world. The store is real, the run
loop is real, the argument parser is real, and the digest is real. Only the sources and the saved
searches are supplied, which is exactly the seam the design puts them behind.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from homescout import api
from homescout.cli.main import main
from homescout.records import ListingFields, SourceRow
from homescout.search import InMemoryCatalog, InMemorySearch, SearchProblem
from homescout.sources import BaseSource, Capabilities, City, Preview, SearchQuery, SearchResult
from homescout.store import Store


def row(identifier: str, **fields: Any) -> SourceRow:
    """One property as a source returned it, with defaults for what a test is not about."""
    defaults: dict[str, Any] = {
        "price": 350_000,
        "listing_status": "for_sale",
        "beds": 3,
        "baths": 2,
        "sqft": 1800,
        "lot_sqft": 43_560,
        "year_built": 1995,
        "property_type": "single_family",
        "address_line": f"{identifier} Example Road",
        "city": "Portales",
        "state": "NM",
        "postal_code": "88130",
        "listing_url": f"https://example.invalid/{identifier}",
    }
    defaults.update(fields)
    return SourceRow(
        source="fake",
        fields=ListingFields(**defaults),
        payload={"id": identifier, **defaults},
        source_listing_id=identifier,
        fetched_at="2026-08-23T00:00:00.000000Z",
    )


class FakeSource(BaseSource):
    """A source that answers from a script, and counts what was asked of it.

    `per_area` answers a different set of rows for each query, which is how the overlapping-areas
    rule is exercised. `outcome` makes it fail or go unavailable without faking a network.
    """

    def __init__(
        self,
        name: str = "fake",
        *,
        rows: Sequence[SourceRow] = (),
        per_area: Sequence[Sequence[SourceRow]] | None = None,
        applies: Iterable[str] = (),
        outcome: str = "ok",
        detail: str | None = None,
        images: bool = True,
    ) -> None:
        super().__init__(session=None)  # type: ignore[arg-type]
        self.name = name
        self.rows = tuple(rows)
        self.per_area = per_area
        self._applies = frozenset(applies)
        self.outcome = outcome
        self.detail = detail
        self.images = images
        self.queries: list[SearchQuery] = []
        self.previews: list[str] = []

    def capabilities(self) -> Capabilities:
        return Capabilities(applies=self._applies, accepts_areas=(), ceiling=None, page_size=200)

    def run_search(self, query: SearchQuery) -> SearchResult:
        index = len(self.queries)
        self.queries.append(query)
        served = self.per_area[index] if self.per_area is not None else self.rows
        return SearchResult(
            source=self.name,
            outcome=self.outcome,  # type: ignore[arg-type]
            rows=tuple(served) if self.outcome == "ok" else (),
            applied=self.capabilities().application(query),
            detail=self.detail,
        )

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        if not self.images:
            return None
        self.previews.append(row.source_listing_id or "")
        return Preview(
            source_url=f"https://example.invalid/{row.source_listing_id}.jpg",
            content_type="image/jpeg",
            data=b"fake-image-bytes",
        )


def search(
    name: str = "portales",
    *,
    sources: tuple[str, ...] = ("fake",),
    areas: int = 1,
    problems: Sequence[SearchProblem] = (),
    keep: Any = None,
    **filters: Any,
) -> InMemorySearch:
    """A saved search with no file behind it."""
    asks = tuple(
        SearchQuery(area=City(f"Area {i}", "NM"), **filters) for i in range(max(areas, 1))
    )
    return InMemorySearch(
        name=name, sources=sources, asks=asks, faults=tuple(problems), keep=keep
    )


def catalog(*searches: InMemorySearch) -> InMemoryCatalog:
    return InMemoryCatalog(searches or (search(),))


def workspace(
    store: Store,
    *,
    searches: Iterable[InMemorySearch] = (),
    sources: Mapping[str, Any] | None = None,
    queue: Any = None,
    images: bool = True,
) -> api.Workspace:
    """A workspace over a real store, with supplied searches and sources."""
    from homescout.matches import InMemoryQueue

    return api.Workspace(
        store=store,
        catalog=InMemoryCatalog(tuple(searches) or (search(),)),
        queue=queue if queue is not None else InMemoryQueue(()),
        sources=dict(sources or {"fake": FakeSource()}),
        images=images,
    )


@contextmanager
def wired(
    searches: Iterable[InMemorySearch] = (),
    sources: Mapping[str, Any] | None = None,
    queue: Any = None,
) -> Iterator[None]:
    """Register a catalog, some sources and a queue, the way later features will.

    The command line builds its own workspace, so a test that drives it has to reach the same seams
    a real installation does. Registering here rather than injecting is deliberate: it is the wiring
    saved searches (feat-004) and address matching (feat-006) will use, so these tests hold it to
    its shape.
    """
    from homescout import matches as match_module
    from homescout import search as search_module
    from homescout.sources import register, unregister

    held = tuple(searches)
    search_module.register_catalog(lambda _root: InMemoryCatalog(held))
    if queue is not None:
        match_module.register_queue(lambda _store: queue)
    names = tuple(sources or {})
    for name, source in (sources or {}).items():
        register(name, lambda _session, source=source: source, replace=True)
    try:
        yield
    finally:
        search_module.unregister_catalog()
        match_module.unregister_queue()
        for name in names:
            unregister(name)


def invoke(args: Sequence[str], *, db: Any = None) -> tuple[int, str, str]:
    """Run the command line exactly as a terminal would, and capture both streams."""
    out, err = io.StringIO(), io.StringIO()
    argv = list(args)
    if db is not None and "--db" not in argv:
        argv = ["--db", str(db), *argv]
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()
