"""The corpus, and a store with it in.

Everything about merging is tested against one real run over one town: 140 rows from three sources,
46 keys shared by two or three of them. The properties in it are invented; the disagreements between
the sources are exactly as they arrived, and the disagreements are what makes the corpus worth
having.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterable, Sequence
from typing import Any

from homescout.records import ListingFields, SourceRow
from homescout.store import Store

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "merge" / "three-sources.json"

FIELDS = (
    "address_line", "unit", "city", "state", "postal_code", "latitude", "longitude",
    "price", "beds", "baths", "sqft", "lot_sqft", "parcel_number", "property_type",
)


def corpus() -> list[dict[str, Any]]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def as_row(entry: dict[str, Any], index: int) -> SourceRow:
    """One corpus entry as the source that produced it returned it."""
    return SourceRow(
        source=entry["source"],
        fields=ListingFields(**{name: entry.get(name) for name in FIELDS}),
        payload=dict(entry),
        source_listing_id=f"{entry['source']}-{index:04d}",
        fetched_at="2026-08-24T00:00:00.000000Z",
    )


def load(store: Store, entries: Iterable[dict[str, Any]] | None = None, *, search: str = "town"):
    """Record the corpus into a store, one run, each source recorded as itself.

    The real path: `record_observations` per source, then `complete_run`, so what the merge pass
    reads is what a run actually leaves behind rather than rows placed by hand.
    """
    held = list(entries if entries is not None else corpus())
    run = store.start_run(search)
    by_source: dict[str, list[SourceRow]] = {}
    for index, entry in enumerate(held):
        by_source.setdefault(entry["source"], []).append(as_row(entry, index))
    from homescout.store import SourceOutcome

    for source, rows in sorted(by_source.items()):
        store.record_observations(run.id, source, rows)
        store.record_source_outcome(
            run.id, SourceOutcome(source=source, outcome="ok", row_count=len(rows))
        )
    return store.complete_run(run.id)


def properties(entries: Sequence[dict[str, Any]], line: str) -> list[dict[str, Any]]:
    """Every corpus entry whose address line starts with this, for a test that names one."""
    return [entry for entry in entries if (entry["address_line"] or "").startswith(line)]


def two(line: str, other: str | None = None) -> list[dict[str, Any]]:
    """The corpus rows for one address, or for two."""
    held = corpus()
    wanted = properties(held, line)
    if other is not None:
        wanted += properties(held, other)
    return wanted
