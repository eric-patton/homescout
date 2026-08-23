"""Shared fixtures for the store's tests.

The helpers here exist so a test can say what it is about ("this run saw these two properties, and
one source failed") without twenty lines of setup burying the point.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest

from homescout.store import ListingFields, RunRecord, SourceOutcome, SourceRow, Store


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "homescout.db"


@pytest.fixture
def store(db_path: Path) -> Iterator[Store]:
    with Store.open(db_path) as opened:
        yield opened


def prop(source_listing_id: str, **fields: object) -> SourceRow:
    """One property as a source returned it.

    Defaults are supplied for the fields a test is not talking about, so that a test about price
    changes does not have to invent an address.
    """
    defaults: dict[str, object] = {
        "price": 350_000,
        "listing_status": "for_sale",
        "beds": 3,
        "baths": 2,
        "sqft": 1800,
        "lot_sqft": 43_560,
        "year_built": 1995,
        "property_type": "single_family",
        "address_line": f"{source_listing_id} Example Road",
        "city": "Portales",
        "state": "NM",
        "postal_code": "88130",
    }
    defaults.update(fields)
    return SourceRow(
        source="",  # set by record_observations' caller; kept for readability of the payload
        fields=ListingFields(**defaults),  # type: ignore[arg-type]
        payload={"id": source_listing_id, **defaults},
        source_listing_id=source_listing_id,
    )


def do_run(
    store: Store,
    search: str = "test-search",
    *,
    sources: Mapping[str, Sequence[SourceRow]] | None = None,
    outcomes: Mapping[str, str] | None = None,
    complete: bool = True,
) -> RunRecord:
    """Run one search end to end.

    `sources` maps a source name to what it returned. `outcomes` overrides a source's result, which
    is how a test says "this source was down" without having to fake a network.
    """
    sources = sources or {}
    outcomes = outcomes or {}
    run = store.start_run(search)
    for source in sorted(set(sources) | set(outcomes)):
        rows = list(sources.get(source, ()))
        if rows:
            store.record_observations(run.id, source, rows)
        store.record_source_outcome(
            run.id,
            SourceOutcome(
                source=source,
                outcome=outcomes.get(source, "ok"),  # type: ignore[arg-type]
                row_count=len(rows),
            ),
        )
    if not complete:
        return run
    return store.complete_run(run.id)


def kinds(comparison: object) -> dict[str, int]:
    """Difference-event counts, for tests that only care about the shape of the answer."""
    return comparison.counts  # type: ignore[attr-defined,no-any-return]
