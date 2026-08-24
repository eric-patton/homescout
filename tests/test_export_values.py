"""What lands in a cell, and what deliberately does not.

The rule the whole product is built on arrives at its last surface here: a value nobody determined
is an empty cell, with no placeholder, no default and no zero. A spreadsheet is where that rule is
most tempting to break, because a blank column looks like a bug and a zero looks like an answer.
"""

from __future__ import annotations

from pathlib import Path

from export_fakes import column_of, listing, load, template_file, write
from homescout.store import Store

WELL = "The property has its own private well and a new septic system, and a metal roof."


def test_an_undetermined_value_is_an_empty_cell(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-5: no placeholder text, no substituted default, nothing at all."""
    loaded = load(store, [listing("a", description="A quiet home near the square.")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    for name in ("Water Source", "Sewer/Septic", "Gas", "HVAC/Heat", "FEMA Flood Zone"):
        assert column_of(path, name) == [None], name


def test_a_value_the_description_supports_is_there(store: Store, tmp_path: Path) -> None:
    """Because a test that only proves emptiness would pass on a sheet that fills nothing."""
    loaded = load(store, [listing("a", description=WELL)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert column_of(path, "Water Source") == ["well"]
    assert column_of(path, "Sewer/Septic") == ["septic"]
    assert column_of(path, "Construction/Roof/Features") == ["metal"]


def test_a_property_with_no_price_has_no_price_per_square_foot(
    store: Store, tmp_path: Path
) -> None:
    """The spec's own edge case: empty rather than zero, because zero sorts."""
    loaded = load(store, [listing("a", price=None)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert column_of(path, "Price") == [None]
    assert column_of(path, "$/sq ft") == [None]


def test_a_property_with_no_floor_area_has_no_price_per_square_foot(
    store: Store, tmp_path: Path
) -> None:
    loaded = load(store, [listing("a", sqft=None)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert column_of(path, "Price") == [250_000]
    assert column_of(path, "$/sq ft") == [None]


def test_land_is_measured_in_acres(store: Store, tmp_path: Path) -> None:
    """Square feet as the sources report it, acres as land is actually sold."""
    loaded = load(store, [listing("a", lot_sqft=130_680), listing("b", lot_sqft=None)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert sorted(column_of(path, "Acres"), key=lambda v: (v is None, v)) == [3.0, None]


def test_numbers_are_numbers(store: Store, tmp_path: Path) -> None:
    """So they sort and sum in the sheet, rather than sorting as text and putting 900,000 first."""
    loaded = load(store, [listing("a", price=90_000), listing("b", price=250_000)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert all(isinstance(value, int | float) for value in column_of(path, "Price"))


def test_the_columns_nothing_fills_are_empty(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-5, the spec's own edge case: five of them, and they stay."""
    loaded = load(store, [listing("a", description=WELL)])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    for name in (
        "Garage/Outbuildings",
        "Annual Taxes",
        "Crime/Safety",
        "Fire/Egress/Terrain",
        "Sewage & Reclaimed-Water Exposure",
    ):
        assert column_of(path, name) == [None], name


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def test_the_sheet_carries_the_annotations_as_they_are_now(
    store: Store, tmp_path: Path
) -> None:
    """feat-011/AC-10: the app is where edits are made, and this is a picture of it now."""
    loaded = load(store, [listing("a")])
    store.set_annotation(loaded["a"], rank=2, verdict="worth a look", next_step="call")
    path = tmp_path / "first.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert column_of(path, "Verdict") == ["worth a look"]
    assert column_of(path, "Rank") == [2]

    store.set_annotation(loaded["a"], verdict="ruled out")
    later = tmp_path / "second.xlsx"
    write(store, loaded, later, root=tmp_path)

    assert column_of(later, "Verdict") == ["ruled out"]
    assert column_of(path, "Verdict") == ["worth a look"], "the old file is a picture of then"


def test_an_annotation_survives_being_exported(store: Store, tmp_path: Path) -> None:
    """Non-negotiable 7 arriving at a surface that could break it: nothing here writes."""
    loaded = load(store, [listing("a")])
    store.set_annotation(loaded["a"], verdict="worth a look", notes="the well is old")
    write(store, loaded, tmp_path / "a.xlsx", root=tmp_path)
    write(store, loaded, tmp_path / "b.csv", root=tmp_path, format="csv")

    held = store.get_annotation(loaded["a"])
    assert held is not None
    assert held.verdict == "worth a look"
    assert held.notes == "the well is old"


# ---------------------------------------------------------------------------
# What the export reports afterwards
# ---------------------------------------------------------------------------


def test_the_export_says_which_kind_of_empty_each_blank_column_is(
    store: Store, tmp_path: Path
) -> None:
    """The three answers are "run the enrichment pass", "write some notes" and "nobody fills it"."""
    loaded = load(store, [listing("a", description="A quiet home near the square.")])

    written = write(store, loaded, tmp_path / "sheet.xlsx", root=tmp_path)

    assert "Garage/Outbuildings" in written.empty["unfilled"]
    assert "FEMA Flood Zone" in written.empty["enriched"]
    assert "Verdict" in written.empty["annotation"]
    assert "Water Source" in written.empty["extracted"]
    assert any("enrichment pass" in reason for reason in written.reasons())


def test_a_column_with_something_in_it_is_not_reported_as_empty(
    store: Store, tmp_path: Path
) -> None:
    loaded = load(store, [listing("a", description=WELL)])
    store.set_annotation(loaded["a"], verdict="worth a look")

    written = write(store, loaded, tmp_path / "sheet.xlsx", root=tmp_path)

    everything = [name for names in written.empty.values() for name in names]
    assert "Water Source" not in everything
    assert "Verdict" not in everything
    assert "Price" not in everything


def test_a_custom_template_reports_only_its_own_columns(store: Store, tmp_path: Path) -> None:
    template_file(tmp_path, "small", ["Property", "Price", "Verdict"])
    loaded = load(store, [listing("a")])

    written = write(store, loaded, tmp_path / "s.xlsx", root=tmp_path, template="small")

    everything = [name for names in written.empty.values() for name in names]
    assert everything == ["Verdict"]
