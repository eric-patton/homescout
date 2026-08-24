"""The workbook itself: which rows, which sheets, and what a link is.

Every test here writes a real file and opens it again. A hyperlink target, a frozen header row and a
second sheet are all things that exist in a file rather than in an object, and the whole point of
this feature is a file somebody else opens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from export_fakes import (
    cells,
    column_of,
    delimited_rows,
    headers,
    listing,
    load,
    open_workbook,
    sheet_rows,
    write,
)
from homescout.errors import InvalidInput
from homescout.export import export_run
from homescout.export.workbook import AREAS_SHEET, PROPERTIES_SHEET, ExportFailed
from homescout.rules.definition import Rule
from homescout.rules.parse import parse
from homescout.rules.verdicts import record
from homescout.store import Store


def rule(expression: str, rule_id: str, severity: str) -> Rule:
    return Rule(id=rule_id, when=expression, severity=severity, expression=parse(expression))


# ---------------------------------------------------------------------------
# Which rows
# ---------------------------------------------------------------------------


def test_one_row_per_property(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-2: one row per canonical listing the search's results included."""
    load(store, [listing("a"), listing("b"), listing("c")])
    loaded = load(store, [listing("a"), listing("b"), listing("c")])
    path = tmp_path / "sheet.xlsx"

    written = write(store, loaded, path, root=tmp_path)

    assert written.properties == 3
    assert len(sheet_rows(path)) == 4, "three properties and a header"


def test_a_property_a_drop_rule_removed_is_absent(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-2: the sheet is what the search's criteria kept."""
    loaded = load(store, [listing("cheap", price=50_000), listing("dear", price=900_000)])
    record(store, [rule("price < 100000", "too-cheap", "drop")], loaded.run_id)
    path = tmp_path / "sheet.xlsx"

    written = write(store, loaded, path, root=tmp_path)

    assert written.properties == 1
    assert column_of(path, "Price") == [900_000]


def test_a_dropped_property_can_be_asked_for(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-2: "unless explicitly requested", and this is the request."""
    loaded = load(store, [listing("cheap", price=50_000), listing("dear", price=900_000)])
    record(store, [rule("price < 100000", "too-cheap", "drop")], loaded.run_id)
    path = tmp_path / "all.xlsx"

    written = write(store, loaded, path, root=tmp_path, include_dropped=True)

    assert written.properties == 2
    assert sorted(column_of(path, "Price")) == [50_000, 900_000]


def test_a_search_with_nothing_in_it_still_produces_a_workbook(
    store: Store, tmp_path: Path
) -> None:
    """The spec's own edge case: headers and no rows, rather than an error or a missing file."""
    loaded = load(store, [])
    path = tmp_path / "empty.xlsx"

    written = write(store, loaded, path, root=tmp_path)

    assert written.properties == 0
    assert path.exists()
    assert len(sheet_rows(path)) == 1
    assert headers(path)[0] == "Rank"


def test_two_source_rows_merged_into_one_property_are_one_row(
    store: Store, tmp_path: Path
) -> None:
    """The spec's own edge case: the canonical value, not a concatenation of the sources."""
    loaded = load(store, [listing("a", price=250_000), listing("b", price=260_000)])
    merged = store.supersede([loaded["a"], loaded["b"]], join_signal="a test merge")
    later = load(store, [listing("a", price=250_000)])

    path = tmp_path / "merged.xlsx"
    write(store, later, path, root=tmp_path)

    assert merged
    prices = column_of(path, "Price")
    assert len(prices) == len(set(prices)), "no property appears twice"


# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------


def test_the_address_cell_links_to_the_listing(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-3: the sheet is a way into the properties rather than a dead end."""
    loaded = load(store, [listing("a", listing_url="https://listings.example.invalid/a")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    address = cells(path)[1][headers(path).index("Property")]
    assert address.hyperlink is not None
    assert address.hyperlink.target == "https://listings.example.invalid/a"
    assert "Example Road" in str(address.value), "and it still reads as an address"


def test_a_property_with_no_link_is_plain_text(store: Store, tmp_path: Path) -> None:
    """The spec's own edge case: a cell that looks like a link and goes nowhere is worse."""
    loaded = load(store, [listing("a", listing_url=None)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    address = cells(path)[1][headers(path).index("Property")]
    assert address.value
    assert address.hyperlink is None


# ---------------------------------------------------------------------------
# The second sheet
# ---------------------------------------------------------------------------


def test_the_workbook_carries_a_second_sheet_of_area_notes(
    store: Store, tmp_path: Path
) -> None:
    """feat-011/AC-4: the context travels with the properties."""
    loaded = load(store, [listing("a")])
    store.set_area_note("city", "Portales", "Good water, long drive to a hospital.")
    store.set_area_note("county", "Roosevelt", "Mostly farmland.")
    path = tmp_path / "sheet.xlsx"

    written = write(store, loaded, path, root=tmp_path)

    book = open_workbook(path)
    assert book.sheetnames == [PROPERTIES_SHEET, AREAS_SHEET]
    rows = sheet_rows(path, AREAS_SHEET)
    assert rows[0][:3] == ["Area", "Place", "Notes"]
    # Sorted by area type then place, so city comes before county.
    assert list(rows[1][:3]) == ["city", "Portales", "Good water, long drive to a hospital."]
    assert list(rows[2][:3]) == ["county", "Roosevelt", "Mostly farmland."]
    assert written.areas == 2


def test_the_second_sheet_is_there_even_with_nothing_to_say(
    store: Store, tmp_path: Path
) -> None:
    """A workbook whose shape depends on whether somebody wrote a note is two workbooks."""
    loaded = load(store, [listing("a")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert open_workbook(path).sheetnames == [PROPERTIES_SHEET, AREAS_SHEET]
    assert len(sheet_rows(path, AREAS_SHEET)) == 1


def test_a_town_note_is_carried_onto_every_row_in_that_town(
    store: Store, tmp_path: Path
) -> None:
    """Because a note that only exists on the second sheet is one nobody sees looking at a row."""
    loaded = load(store, [listing("a", city="Portales"), listing("b", city="Clovis")])
    store.set_area_note("city", "Portales", "Good water.")
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    notes = dict(zip(column_of(path, "Town/Area"), column_of(path, "Town Analysis Notes"),
                     strict=True))
    assert notes["Portales"] == "Good water."
    assert notes["Clovis"] is None


# ---------------------------------------------------------------------------
# Writing the file
# ---------------------------------------------------------------------------


def test_an_existing_file_is_not_replaced(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-8: re-exporting is safe because it refuses rather than because it is careful."""
    loaded = load(store, [listing("a")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)
    before = path.read_bytes()

    with pytest.raises(InvalidInput) as raised:
        write(store, loaded, path, root=tmp_path)

    assert "--force" in str(raised.value)
    assert path.read_bytes() == before, "and the previous one is untouched"


def test_an_existing_file_is_replaced_when_asked(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-8: explicitly requested, which is the other half of the criterion."""
    loaded = load(store, [listing("a")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    later = load(store, [listing("a"), listing("b")])
    write(store, later, path, root=tmp_path, force=True)

    assert len(sheet_rows(path)) == 3


def test_a_failure_leaves_nothing_at_the_destination(store: Store, tmp_path: Path) -> None:
    """The reliability requirement: a failure partway through leaves no partial file."""
    loaded = load(store, [listing("a")])
    blocked = tmp_path / "taken"
    blocked.mkdir()

    # `--force`, so this gets past the refusal to replace and reaches the write itself, which is
    # what is being tested: a directory where a file is wanted.
    with pytest.raises(ExportFailed):
        write(store, loaded, blocked, root=tmp_path, force=True)

    assert list(blocked.iterdir()) == [], "and no half-written file beside it either"
    assert not (tmp_path / "taken.partial").exists()


def test_a_missing_directory_is_created(store: Store, tmp_path: Path) -> None:
    """Because the default path is `exports/` and nobody should have to make it first."""
    loaded = load(store, [listing("a")])
    path = tmp_path / "somewhere" / "new" / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)
    assert path.exists()


def test_an_unknown_format_is_refused_before_anything_is_read(
    store: Store, tmp_path: Path
) -> None:
    loaded = load(store, [listing("a")])
    with pytest.raises(InvalidInput) as raised:
        export_run(store, loaded.run_id, tmp_path / "s.ods", format="ods")
    assert "xlsx" in str(raised.value) and "csv" in str(raised.value)


# ---------------------------------------------------------------------------
# The plain-text form
# ---------------------------------------------------------------------------


def test_the_delimited_form_carries_the_same_columns(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-12: the same columns, in the same order, without the second sheet."""
    loaded = load(store, [listing("a"), listing("b")])
    path = tmp_path / "sheet.csv"

    written = write(store, loaded, path, root=tmp_path, format="csv")

    rows = delimited_rows(path)
    assert rows[0] == list(written.columns)
    assert len(rows) == 3
    assert written.format == "csv"


def test_the_delimited_form_has_no_second_sheet(store: Store, tmp_path: Path) -> None:
    """It is one table. There is nowhere for a second one to go, and it does not pretend."""
    loaded = load(store, [listing("a")])
    store.set_area_note("city", "Portales", "Good water.")
    path = tmp_path / "sheet.csv"
    write(store, loaded, path, root=tmp_path, format="csv")

    text = path.read_text(encoding="utf-8-sig")
    assert "Good water." in text, "as a column on the property's own row"
    assert text.count("Area,Place,Notes") == 0, "and not as a second table in the same file"
