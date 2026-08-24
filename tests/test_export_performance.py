"""Five thousand properties, thirty-two columns, and a file a spreadsheet opens.

Marked slow and excluded from the default run. The requirement is thirty seconds, and what makes it
worth measuring rather than asserting is that the obvious implementation asks the store per property
per column, which is a hundred and sixty thousand queries and would spend the whole budget on round
trips to a file on the same disk.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from export_fakes import fingerprint, listing, load, open_workbook, write
from homescout.store import Store

pytestmark = pytest.mark.slow

ROWS = 5_000
BUDGET_SECONDS = 30.0

DESCRIPTION = (
    "Comfortable home on two acres just outside town, served by a private well with its own "
    "septic system, central heat and air, and a durable metal roof installed in 2021."
)


def a_county(store: Store, count: int = ROWS):
    return load(
        store,
        [
            listing(
                f"p{index:05d}",
                price=150_000 + index * 37,
                sqft=1_200 + index % 900,
                description=DESCRIPTION if index % 3 == 0 else None,
                city="Portales" if index % 2 else "Clovis",
                latitude=34.0 + (index % 500) * 0.004,
                longitude=-103.5 + (index // 500) * 0.004,
            )
            for index in range(count)
        ],
    )


def test_five_thousand_properties_export_within_the_budget(
    store: Store, tmp_path: Path
) -> None:
    """feat-011 performance, and a file that opens without a warning."""
    loaded = a_county(store)
    store.set_area_note("city", "Portales", "Good water, long drive to a hospital.")
    path = tmp_path / "county.xlsx"

    started = time.perf_counter()
    written = write(store, loaded, path, root=tmp_path)
    took = time.perf_counter() - started

    assert written.properties == ROWS
    assert took < BUDGET_SECONDS, f"exporting {ROWS} properties took {took:.1f}s"

    book = open_workbook(path)
    assert book["Properties"].max_row == ROWS + 1
    assert book.sheetnames == ["Properties", "Areas"]


def test_five_thousand_properties_export_to_plain_text_too(
    store: Store, tmp_path: Path
) -> None:
    loaded = a_county(store, 2_000)
    path = tmp_path / "county.csv"

    started = time.perf_counter()
    write(store, loaded, path, root=tmp_path, format="csv")
    took = time.perf_counter() - started

    assert took < BUDGET_SECONDS
    assert sum(1 for _ in path.open(encoding="utf-8-sig")) >= 2_001


def test_a_county_sized_export_still_changes_nothing(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-9 at the size it runs at: a bulk read is where a write sneaks in."""
    loaded = a_county(store, 1_000)
    before = fingerprint(store)

    write(store, loaded, tmp_path / "county.xlsx", root=tmp_path)

    assert fingerprint(store) == before
