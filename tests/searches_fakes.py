"""Definition files on disk, and the two things this feature deliberately does not implement.

Everything else in these tests is real: a real file, a real parser, real shapely, the real run loop.
What is faked is the outside world (a source) and the feature that has not been built yet (the
boundary provider), which is exactly the seam the design puts each behind.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from homescout import api
from homescout.search import boundaries as boundary_port
from homescout.search.definition import FileCatalog
from homescout.store import Store

#: A square around Portales, New Mexico, drawn the way a map surface would hand it over: GeoJSON,
#: longitude first.
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [
            [-103.40, 34.15],
            [-103.30, 34.15],
            [-103.30, 34.25],
            [-103.40, 34.25],
            [-103.40, 34.15],
        ]
    ],
}

INSIDE = (34.20, -103.35)
OUTSIDE = (34.60, -103.05)


def polygon(
    west: float, south: float, east: float, north: float
) -> dict[str, Any]:
    """A rectangle as GeoJSON, for a test that needs a shape somewhere particular."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


DEFINITION = """\
# A saved search, with a comment nobody may throw away.
name: {name}
description: "Acreage with real internet"
areas:
  - {{type: city, value: "Portales, NM"}}
filters:
  price: {{min: 100000, max: 500000}}
  lot_acres: {{min: 1.50}}
sources: [{source}]
rules: []
export:
  template: default
"""


def write(directory: Path, name: str = "portales", text: str | None = None, **fields: Any) -> Path:
    """One definition file, written the way a person would."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    filled = {"source": "fake", **fields}
    body = text if text is not None else DEFINITION.format(name=name, **filled)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def catalog(directory: Path) -> FileCatalog:
    return FileCatalog(directory)


def workspace(
    store: Store,
    *,
    sources: Mapping[str, Any] | None = None,
    images: bool = False,
) -> api.Workspace:
    """A workspace whose saved searches come from files beside the database."""
    from cli_fakes import FakeSource
    from homescout.matches import InMemoryQueue

    return api.Workspace(
        store=store,
        catalog=FileCatalog(store.path.parent / "searches"),
        queue=InMemoryQueue(()),
        sources=dict(sources or {"fake": FakeSource()}),
        images=images,
    )


@contextmanager
def sourced(*names: str) -> Iterator[None]:
    """Register source names, because validation refuses a source nobody has heard of.

    Deliberately the real registry rather than an injected list: a definition naming a source that
    does not exist is a validation problem, and the only honest way to test that is against whatever
    this installation actually has.
    """
    from cli_fakes import FakeSource
    from homescout.sources import register, unregister

    for name in names:
        register(name, lambda _session, name=name: FakeSource(name), replace=True)
    try:
        yield
    finally:
        for name in names:
            unregister(name)


class CountingBoundaries:
    """A boundary provider that answers from a script and counts what it was asked.

    Stands in for location enrichment (feat-007). The count is the point: a search run twice must
    not look a place up twice, because a real answer costs a request and a cache entry.
    """

    def __init__(
        self,
        shapes: Mapping[tuple[str, str], Any] | None = None,
        points: Mapping[str, tuple[float, float]] | None = None,
        containing: Sequence[tuple[str, str]] = (),
    ) -> None:
        self.shapes = dict(shapes or {})
        self.points = dict(points or {})
        self.places = tuple(containing)
        self.lookups: list[str] = []

    def boundary(self, kind: str, value: str) -> Any | None:
        self.lookups.append(f"{kind}:{value}")
        return self.shapes.get((kind, value))

    def locate(self, place: str) -> tuple[float, float] | None:
        self.lookups.append(f"locate:{place}")
        return self.points.get(place)

    def candidates(self, kind: str, value: str) -> tuple[str, ...]:
        return ()

    def containing(self, geometry: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
        self.lookups.append("containing")
        return self.places


@contextmanager
def boundaries(provider: Any) -> Iterator[Any]:
    boundary_port.register_boundaries(provider)
    try:
        yield provider
    finally:
        boundary_port.unregister_boundaries()


class Hostile:
    """A source that fails the test if anything at all is asked of it.

    Validation stands between a typo and an hour of throttled requests, so it may not itself make
    one. This is how that is proved rather than asserted.
    """

    name = "hostile"

    def capabilities(self) -> Any:
        raise AssertionError("validation asked a source for its capabilities")

    def search(self, query: Any) -> Any:
        raise AssertionError("validation contacted a source")

    def fetch_preview(self, row: Any) -> Any:
        raise AssertionError("validation fetched an image")
