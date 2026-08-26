"""The default sheet is the one somebody already has, and everything else is configuration.

The first test in this file is the whole reason the column list is in `spec.md` rather than only in
the brief at the repository root. A test comparing the generated header row against the code that
generated it proves nothing; this one compares it against the specification.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from export_fakes import headers, listing, load, template_file, write
from homescout.errors import InvalidInput
from homescout.export import columns as cols
from homescout.export import templates
from homescout.store import Store

SPEC = Path(__file__).resolve().parents[1] / "spec" / "features" / "spreadsheet-export" / "spec.md"


def the_specified_columns() -> list[str]:
    """The default column list, read out of the spec rather than out of the code.

    Lifted from the block quote under "The default column list", which is where the pre-build check
    put it precisely so this test would have something independent to compare against.
    """
    text = SPEC.read_text(encoding="utf-8")
    # `[^\n]*` rather than `.*`: `re.S` makes a dot match newlines, and a greedy one swallowed the
    # rest of the document the first time this was written.
    block = re.search(r"### The default column list.*?\n\n((?:>[^\n]*\n)+)", text, re.S)
    assert block is not None, "spec.md no longer carries the default column list"
    quoted = " ".join(line.lstrip("> ").strip() for line in block.group(1).splitlines())
    return [name.strip() for name in quoted.split(",")]


def test_the_default_template_is_the_sheet_the_spec_describes() -> None:
    """feat-011/AC-1: exactly, and in that order."""
    assert list(cols.DEFAULT) == the_specified_columns()
    assert len(cols.DEFAULT) == 32


def test_the_generated_header_row_is_that_list(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-1: the criterion is about what comes out of the file, not about a constant."""
    loaded = load(store, [listing("a")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    assert headers(path) == the_specified_columns()


def test_every_default_column_exists() -> None:
    """Checked at import too, and asserted here so the import check cannot be quietly deleted."""
    for name in cols.DEFAULT:
        assert cols.find(name) is not None, name


def test_a_template_file_chooses_its_own_columns(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-7: a sheet for a different purpose is a settings change, not a code change."""
    wanted = ["Property", "Price", "Acres", "Water Source", "Verdict"]
    template_file(tmp_path, "land", wanted)
    loaded = load(store, [listing("a")])
    path = tmp_path / "land.xlsx"

    written = write(store, loaded, path, root=tmp_path, template="land")

    assert headers(path) == wanted
    assert written.template == "land"


def test_a_template_may_reorder_and_repeat_nothing(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-7: order is the template's business, and it is honoured exactly."""
    wanted = ["Listing URL", "Price", "Property"]
    template_file(tmp_path, "backwards", wanted)
    loaded = load(store, [listing("a")])
    path = tmp_path / "b.xlsx"

    write(store, loaded, path, root=tmp_path, template="backwards")
    assert headers(path) == wanted


def test_a_template_naming_a_column_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """feat-011/AC-6: at load time, naming it, and listing what does exist."""
    template_file(tmp_path, "typo", ["Property", "Wells", "Price"])

    with pytest.raises(InvalidInput) as raised:
        templates.load(tmp_path, "typo")

    said = str(raised.value)
    assert "Wells" in said
    assert "Water Source" in said, "and it says what the columns actually are"


def test_a_template_is_refused_before_a_single_row_is_built(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-6: assembling five thousand rows and then refusing is not a kindness."""
    template_file(tmp_path, "typo", ["Nope"])
    loaded = load(store, [listing("a")])
    path = tmp_path / "never.xlsx"

    with pytest.raises(InvalidInput):
        write(store, loaded, path, root=tmp_path, template="typo")

    assert not path.exists(), "and nothing was written"


@pytest.mark.parametrize(
    ("body", "complaint"),
    [
        ("columns: []\n", "no columns"),
        ("columns: Property\n", "list of column names"),
        ("template: default\n", "no `columns:` list"),
        ("columns: [Property]\nrows: 5\n", "not part of a template"),
    ],
)
def test_a_template_that_is_not_one_says_what_is_wrong(
    body: str, complaint: str, tmp_path: Path
) -> None:
    directory = tmp_path / "templates"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "odd.yaml").write_text(body, encoding="utf-8")

    with pytest.raises(InvalidInput) as raised:
        templates.load(tmp_path, "odd")
    assert complaint in str(raised.value)


def test_an_unknown_template_says_where_one_would_live(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput) as raised:
        templates.load(tmp_path, "nope")
    said = str(raised.value)
    assert "nope" in said
    assert "templates" in said


def test_a_template_name_cannot_reach_outside_its_directory(tmp_path: Path) -> None:
    """A name becomes a file name, the same rule saved searches already live by."""
    for hostile in ("../secrets", "a/b", "..", "", "with space"):
        with pytest.raises(InvalidInput):
            templates.safe_path(tmp_path, hostile)


def test_the_built_in_template_is_always_available(tmp_path: Path) -> None:
    assert templates.available(tmp_path) == ("default",)
    template_file(tmp_path, "land", ["Property"])
    assert templates.available(tmp_path) == ("default", "land")


def test_every_column_declares_where_its_value_comes_from() -> None:
    """Which is what lets the export say which kind of empty an empty column is."""
    for column in cols.COLUMNS:
        assert column.origin in (
            "listing",
            "derived",
            "extracted",
            "enriched",
            "annotation",
            "unfilled",
        ), column.name


def test_the_columns_nothing_fills_are_the_ones_the_spec_names() -> None:
    """feat-011/AC-5, the spec's own edge case: five, and the same five."""
    unfilled = {column.name for column in cols.COLUMNS if column.origin == "unfilled"}
    assert unfilled == {
        "Garage/Outbuildings",
        "Annual Taxes",
        "Crime/Safety",
        "Fire/Egress/Terrain",
        "Sewage & Reclaimed-Water Exposure",
    }
    text = SPEC.read_text(encoding="utf-8")
    for name in unfilled:
        assert name in text, f"{name} is structurally empty and the spec does not say so"


def county_row(said: str | None, looked_up: str | None):
    """One property, as far as the county columns are concerned."""

    class Fields:
        county = said

    class Row:
        fields = Fields()
        enriched = {"county_name": looked_up} if looked_up is not None else {}

    return Row()


def test_the_county_is_the_listings_where_there_is_one() -> None:
    """feat-011/AC-14: the site's own word wins, and is not overwritten by a lookup."""
    assert cols.BY_NAME["County/Region"].read(county_row("Roosevelt", "Curry")) == "Roosevelt"


def test_the_county_falls_back_to_the_one_the_public_record_gives() -> None:
    """feat-011/AC-14: because two of the three sites never send a county at all.

    Measured on the statewide run of 2026-08-26: Realtor sent one on 1,097 of 1,099 rows, Zillow on
    none of 866, Redfin on none of 58. Left to the listing alone a quarter of the column is blank,
    and the blank is one site's silence rather than a fact about the house.
    """
    assert cols.BY_NAME["County/Region"].read(county_row(None, "Roosevelt")) == "Roosevelt"


def test_a_borrowed_county_is_spelled_exactly_like_a_stated_one() -> None:
    """feat-011/AC-14: because the whole point of the column is sorting and grouping by it.

    A cell reading `Roosevelt (looked up)` would sort and group apart from `Roosevelt`, splitting
    one county into two, which costs more than the marker is worth. Provenance is kept in the
    separate column beside it instead.
    """
    stated = cols.BY_NAME["County/Region"].read(county_row("Roosevelt", None))
    borrowed = cols.BY_NAME["County/Region"].read(county_row(None, "Roosevelt"))

    assert stated == borrowed == "Roosevelt"


def test_a_county_nobody_can_say_is_an_empty_cell() -> None:
    """feat-011/AC-14, feat-011/AC-5: no placeholder, and no invention."""
    assert cols.BY_NAME["County/Region"].read(county_row(None, None)) is None


def test_which_counties_were_borrowed_stays_answerable() -> None:
    """feat-011/AC-15: the looked-up answer keeps a column of its own, outside the default sheet."""
    assert cols.BY_NAME["County (looked up)"].read(county_row("Roosevelt", "Curry")) == "Curry"
    assert cols.BY_NAME["County (looked up)"].read(county_row("Roosevelt", None)) is None
    assert "County (looked up)" not in cols.DEFAULT, "the promised sheet keeps its 32 columns"
