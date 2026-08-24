"""Nothing this writes is something a spreadsheet application will run.

A listing description is text somebody else wrote, and a spreadsheet is a place where text can be an
instruction. The library's own default is the wrong one here: a string beginning with `=` is
recorded as a formula unless the cell is told otherwise, so every one of these tests writes a real
file and opens it again, because a cell's type only exists once it has been saved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from export_fakes import cells, column_of, delimited_rows, listing, load, template_file, write
from homescout.export.text import CELL_LIMIT, TRUNCATION_MARK, clean, for_delimited
from homescout.store import Store

#: The classic one. In a spreadsheet that is not text, it is a request to run a program.
HOSTILE = "=cmd|'/c calc'!A1"

DANGEROUS = (
    HOSTILE,
    "=1+1",
    '=HYPERLINK("http://evil.invalid","click here")',
    "+1+1",
    "-1+1",
    "@SUM(1,2)",
    "  =1+1",
    "\t=1+1",
)

COLUMNS = ["Property", "Description", "Notes", "Summary"]


def with_text(store: Store, tmp_path: Path, text: str, path_name: str = "sheet.xlsx"):
    template_file(tmp_path, "text", COLUMNS)
    loaded = load(store, [listing("a", description=text)])
    store.set_annotation(loaded["a"], summary=text, notes=text)
    path = tmp_path / path_name
    write(store, loaded, path, root=tmp_path, template="text")
    return path


@pytest.mark.parametrize("text", DANGEROUS)
def test_a_dangerous_cell_is_text_in_the_workbook(text: str, store: Store, tmp_path: Path) -> None:
    """The security requirement: written so a spreadsheet displays it rather than evaluates it."""
    path = with_text(store, tmp_path, text)

    for row in cells(path)[1:]:
        for cell in row:
            if cell.value is None:
                continue
            # `s` is a shared string, which a spreadsheet displays. `f` is a formula, which it runs.
            # The value itself is deliberately unchanged: the text is what the listing said.
            assert cell.data_type == "s", f"{cell.value!r} came back as {cell.data_type}"

    assert column_of(path, "Description") == [text], "and the text itself is unchanged"
    assert b"<f>" not in _sheet_xml(path), "no cell in the file is a formula"


def _sheet_xml(path: Path) -> bytes:
    """The properties sheet as it actually sits in the file.

    Read from the archive rather than through the library, because the claim is about what a
    spreadsheet application will find when it opens this, not about what the library reports.
    """
    import zipfile

    with zipfile.ZipFile(path) as archive:
        return archive.read("xl/worksheets/sheet1.xml")


@pytest.mark.parametrize("text", DANGEROUS)
def test_a_dangerous_cell_is_guarded_in_the_delimited_form(text: str) -> None:
    """The only place the two formats differ, and the reason is in `text.py`."""
    guarded = for_delimited(text)
    assert guarded.startswith("'")
    assert guarded[1:] == text


def test_an_ordinary_value_is_not_guarded() -> None:
    """The guard fires on expressions, not on everything, or every cell would gain an apostrophe."""
    for ordinary in ("1828 Redwine", "Portales, NM", "well", "3.5", ""):
        assert not for_delimited(ordinary).startswith("'")


def test_the_two_formats_agree_on_every_value_that_needs_no_guard(
    store: Store, tmp_path: Path
) -> None:
    """feat-011/AC-12: the same columns and the same values, one format at a time."""
    template_file(tmp_path, "both", COLUMNS)
    loaded = load(store, [listing("a", description="A quiet home with a private well.")])
    store.set_annotation(loaded["a"], summary="Worth a look", notes="Call the agent")

    book = tmp_path / "b.xlsx"
    text = tmp_path / "b.csv"
    write(store, loaded, book, root=tmp_path, template="both")
    write(store, loaded, text, root=tmp_path, template="both", format="csv")

    from export_fakes import sheet_rows

    from_book = [[("" if v is None else str(v)) for v in row] for row in sheet_rows(book)]
    assert delimited_rows(text) == from_book


def test_text_past_the_cell_limit_is_cut_visibly(store: Store, tmp_path: Path) -> None:
    """The spec's own edge case, and the library's own behaviour is to cut it in silence."""
    enormous = "A lovely home. " * 4_000
    assert len(enormous) > CELL_LIMIT
    path = with_text(store, tmp_path, enormous)

    written = column_of(path, "Description")[0]
    assert len(written) == CELL_LIMIT
    assert written.endswith(TRUNCATION_MARK), "and the cut is visible rather than a sentence ending"


def test_a_control_character_does_not_end_the_export(store: Store, tmp_path: Path) -> None:
    """One bad byte in one listing would otherwise cost the whole workbook."""
    text = "A home with a\x0bprivate well\x00 and a septic system."
    path = with_text(store, tmp_path, text)

    written = column_of(path, "Description")[0]
    assert "private well" in written
    assert "\x0b" not in written and "\x00" not in written


def test_the_shape_of_something_somebody_typed_is_kept() -> None:
    """Newlines and tabs are legal, occur in real notes, and are not control characters here."""
    assert clean("first line\nsecond line\twith a tab") == "first line\nsecond line\twith a tab"


def test_characters_outside_ascii_survive_the_workbook(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-13: descriptions routinely carry them, and a mangled sheet is a broken one."""
    text = "Casita \u2014 caf\u00e9 \u00f1 30\u00b0 \u00bd acre \u2018quoted\u2019"
    path = with_text(store, tmp_path, text)
    assert column_of(path, "Description") == [text]


def test_characters_outside_ascii_survive_the_delimited_form(
    store: Store, tmp_path: Path
) -> None:
    """feat-011/AC-13: and this is the format where it goes wrong quietly.

    Without a byte-order mark a spreadsheet application on Windows reads the file as the system code
    page, and every accent in it comes out wrong while the file itself looks fine.
    """
    text = "Casita \u2014 caf\u00e9 \u00f1 30\u00b0 \u00bd acre"
    template_file(tmp_path, "text", COLUMNS)
    loaded = load(store, [listing("a", description=text)])
    path = tmp_path / "sheet.csv"
    write(store, loaded, path, root=tmp_path, template="text", format="csv")

    assert path.read_bytes().startswith(b"\xef\xbb\xbf"), "the byte-order mark is there"
    rows = delimited_rows(path)
    assert rows[1][rows[0].index("Description")] == text


def test_a_hyperlink_target_has_to_be_a_web_address(store: Store, tmp_path: Path) -> None:
    """A listing URL is text a listing site chose, and a hyperlink is a thing somebody clicks.

    A `file://` target in a spreadsheet is not a broken link, it is a request to whatever path it
    names, which on Windows can be somewhere else entirely.
    """
    from homescout.export.workbook import link_target

    for refused in (
        "file:///C:/Windows/System32/calc.exe",
        r"\\attacker.invalid\share\x",
        "javascript:alert(1)",
        "data:text/html,<script>",
        "",
        None,
    ):
        assert link_target(refused) is None

    assert link_target("https://listings.example.invalid/a") == "https://listings.example.invalid/a"


def test_a_property_whose_link_is_refused_is_still_written(store: Store, tmp_path: Path) -> None:
    """Plain text rather than a link, which is the spec's edge case for a missing one."""
    loaded = load(store, [listing("a", listing_url="file:///C:/Windows/System32/calc.exe")])
    path = tmp_path / "sheet.xlsx"
    write(store, loaded, path, root=tmp_path)

    address = cells(path)[1][2]
    assert address.value, "the address is there"
    assert address.hyperlink is None, "and it is not clickable"
