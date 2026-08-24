"""The definition file: what it holds, and what survives being written back.

The round trip is the load-bearing part. A saved search is edited two ways, by hand and by dragging
a shape on a map, and a tool that reformatted the file on every save would make the second way
destroy the first way's work without ever losing a value.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from homescout.errors import InvalidInput
from homescout.search import UnknownSearch, blocking
from homescout.search.definition import FileCatalog
from searches_fakes import SQUARE, catalog, sourced, write

pytestmark = pytest.mark.usefixtures("registered")


@pytest.fixture
def registered():
    with sourced("fake"):
        yield


def test_a_definition_carries_everything_the_brief_asks_of_it(tmp_path: Path) -> None:
    """feat-004/AC-1: a name, a description, areas, exclusions, filters, sources, rules, export."""
    text = """\
name: full
description: "Everything at once"
areas:
  - {type: polygon, name: north-portales, geometry: GEOMETRY}
  - {type: city, value: "Las Cruces, NM"}
  - {type: county, value: "Roosevelt County, NM"}
  - {type: zip, value: "88130"}
  - {type: radius, center: "Portales, NM", miles: 25}
exclude_areas:
  - {type: zip, value: "88101"}
filters:
  price: {min: 200000, max: 700000}
  beds: {min: 3}
  baths: {min: 2}
  sqft: {min: 1500}
  lot_acres: {min: 1}
  year_built: {min: 1980}
  property_type: [single_family, farm]
  listing_type: [for_sale, pending]
  listed_within_days: 30
sources: [fake]
rules: []
export:
  template: default
""".replace("GEOMETRY", str(SQUARE).replace("'", '"'))
    write(tmp_path / "searches", "full", text=text)

    definition = catalog(tmp_path / "searches").load("full")

    assert blocking(definition.problems()) == ()
    assert definition.name == "full"
    assert definition.description == "Everything at once"
    assert len(definition.areas) == 5
    assert len(definition.exclusions) == 1
    assert definition.sources == ("fake",)
    assert definition.freshness_days == 30
    assert definition.export_template == "default"
    assert definition.reading.filters["price_min"] == 200_000
    assert definition.reading.filters["property_types"] == ("single_family", "farm")
    assert definition.reading.statuses == ("for_sale", "pending")


def test_a_drawn_shape_keeps_the_name_it_was_given(tmp_path: Path) -> None:
    """feat-004/AC-2: a named polygon keeps its name, all the way to something that displays it."""
    text = f"""\
name: named
areas:
  - {{type: polygon, name: north-portales, geometry: {str(SQUARE).replace("'", '"')}}}
sources: [fake]
"""
    write(tmp_path / "searches", "named", text=text)

    definition = catalog(tmp_path / "searches").load("named")

    assert definition.problems() == ()
    assert [area.name for area in definition.areas] == ["north-portales"]
    assert definition.areas[0].label() == "north-portales"


def test_an_acre_is_forty_three_thousand_five_hundred_and_sixty_square_feet(tmp_path: Path) -> None:
    """feat-004/AC-1: the file speaks acres and the source speaks square feet.

    Pinned at the boundary on purpose. A minimum of one acre has to be 43,560 and not 43,559: a
    rounding slip here changes which properties qualify, silently, forever.
    """
    write(
        tmp_path / "searches",
        "acres",
        text='name: acres\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  lot_acres: {min: 1, max: 2.5}\nsources: [fake]\n",
    )

    definition = catalog(tmp_path / "searches").load("acres")

    assert definition.reading.filters["lot_sqft_min"] == 43_560
    assert definition.reading.filters["lot_sqft_max"] == 108_900


def test_a_definition_loaded_and_written_back_is_the_same_file(tmp_path: Path) -> None:
    """feat-004/AC-8: comments, key order, quoting and precision all survive.

    Byte equality rather than "the same values". The map surface will save this file every time
    somebody moves a corner, and a save that rewrote the whole thing would turn every edit into a
    diff nobody can read.
    """
    original = (
        "# what this search is for\n"
        'name: round\n'
        'description: "Acreage, real internet"   # kept\n'
        "areas:\n"
        '  - {type: city, value: "Portales, NM"}   # the town\n'
        "filters:\n"
        "  price: {min: 200000, max: 700000}\n"
        "  lot_acres: {min: 1.50}\n"
        "sources: [fake]\n"
    )
    path = write(tmp_path / "searches", "round", text=original)

    definition = catalog(tmp_path / "searches").load("round")
    definition.document.write()

    assert path.read_text(encoding="utf-8") == original


def test_a_shape_is_not_re_approximated_by_a_save(tmp_path: Path) -> None:
    """feat-004/AC-8: geometry precision survives a save, digit for digit.

    Written as a block sequence, which is what a map surface produces and what somebody drawing a
    shape by hand would rather read.
    """
    precise = (
        "name: precise\n"
        "areas:\n"
        "  - type: polygon\n"
        "    name: fine\n"
        "    geometry:\n"
        "      type: Polygon\n"
        "      coordinates:\n"
        "        -   - [-103.4000001, 34.1500001]\n"
        "            - [-103.3000000, 34.1500000]\n"
        "            - [-103.3, 34.25]\n"
        "            - [-103.4000001, 34.1500001]\n"
        "sources: [fake]\n"
    )
    path = write(tmp_path / "searches", "precise", text=precise)

    definition = catalog(tmp_path / "searches").load("precise")
    definition.document.write()

    after = path.read_text(encoding="utf-8")
    assert after == precise
    assert "-103.3000000" in after, "trailing zeros are a choice somebody made"


def test_a_hand_wrapped_list_keeps_its_values_though_not_its_line_breaks(tmp_path: Path) -> None:
    """feat-004/AC-8: the one thing a save does not preserve, pinned deliberately.

    Layout inside a list is normalized once: a flow list written across several lines comes back on
    one, and a compact nested sequence gets its own line. Nothing is lost but the line breaks, what
    this tool writes is already in that form, and pinning it here means the day it changes somebody
    finds out from a test rather than from a diff.
    """
    wrapped = (
        "name: wrapped\n"
        "areas:\n"
        "  - {type: polygon, name: w, geometry: {type: Polygon,\n"
        "     coordinates: [[[-103.4, 34.15], [-103.3, 34.15], [-103.3, 34.25],\n"
        "     [-103.4, 34.15]]]}}\n"
        "sources: [fake]\n"
    )
    path = write(tmp_path / "searches", "wrapped", text=wrapped)

    catalog(tmp_path / "searches").load("wrapped").document.write()
    again = catalog(tmp_path / "searches").load("wrapped")

    assert blocking(again.problems()) == ()
    assert again.areas[0].name == "w"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 4


def test_changing_one_filter_changes_one_line(tmp_path: Path) -> None:
    """feat-004/AC-12: an edit made through the tool produces a difference confined to the edit."""
    original = write(tmp_path / "searches", "edited", text=(
        "# a comment\n"
        "name: edited\n"
        'description: "Acreage"\n'
        "areas:\n"
        '  - {type: city, value: "Portales, NM"}\n'
        "filters:\n"
        "  price: {min: 200000, max: 700000}\n"
        "sources: [fake]\n"
    )).read_text(encoding="utf-8")

    edited = catalog(tmp_path / "searches").edit("edited", {"filters.price.max": "800000"})

    after = (tmp_path / "searches" / "edited.yaml").read_text(encoding="utf-8")
    changed = [
        line
        for line in difflib.unified_diff(original.splitlines(), after.splitlines(), n=0)
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    assert changed == [
        "-  price: {min: 200000, max: 700000}",
        "+  price: {min: 200000, max: 800000}",
    ]
    assert edited.reading.filters["price_max"] == 800_000


def test_a_file_written_on_windows_keeps_its_line_endings(tmp_path: Path) -> None:
    """feat-004/AC-12: an edit confined to the edit, on a file Notepad wrote.

    Normalizing line endings on the way out turns a one-line change into a diff touching every
    line, which is the same failure the comments and the key order are protected from.
    """
    directory = tmp_path / "searches"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "windows.yaml"
    path.write_bytes(
        b"# a comment\r\n"
        b"name: windows\r\n"
        b"areas:\r\n"
        b'  - {type: city, value: "Portales, NM"}\r\n'
        b"filters:\r\n"
        b"  price: {max: 700000}\r\n"
        b"sources: [fake]\r\n"
    )

    catalog(directory).edit("windows", {"filters.price.max": "800000"})

    after = path.read_bytes()
    assert b"\r\n" in after, "the file was rewritten with the other operating system's endings"
    assert after.count(b"\r\n") == after.count(b"\n"), "the file ended up with a mix of both"
    assert b"800000" in after


def test_an_edit_that_changes_nothing_writes_nothing(tmp_path: Path) -> None:
    """feat-004/AC-12: assigning a value a key already has must not restyle it.

    The map surface hands over the whole areas list on every save, so this is the ordinary case:
    open a search, press save, and a flow map written on one line should still be on one line.
    """
    directory = tmp_path / "searches"
    before = write(directory, "same", text=(
        "name: same\n"
        "areas:\n"
        '  - {type: city, value: "Portales, NM"}\n'
        "sources: [fake]\n"
    )).read_bytes()

    catalog(directory).edit("same", {"areas": [{"type": "city", "value": "Portales, NM"}]})

    assert (directory / "same.yaml").read_bytes() == before


def test_an_edit_that_would_break_the_file_is_refused_before_it_is_written(tmp_path: Path) -> None:
    """feat-004/AC-12: a slip at the command line never leaves a definition that will not run."""
    from homescout.search import InvalidSearch

    before = write(tmp_path / "searches", "guard").read_text(encoding="utf-8")

    with pytest.raises(InvalidSearch):
        catalog(tmp_path / "searches").edit("guard", {"sources": "[nowhere]"})

    assert (tmp_path / "searches" / "guard.yaml").read_text(encoding="utf-8") == before


def test_a_new_definition_explains_itself(tmp_path: Path) -> None:
    """feat-004/AC-1: what `searches create` writes is valid, and readable without documentation."""
    made = catalog(tmp_path / "searches").create("fresh")

    text = (tmp_path / "searches" / "fresh.yaml").read_text(encoding="utf-8")
    assert made.name == "fresh"
    assert text.startswith("name: fresh")
    assert "#" in text, "a first encounter with the format should explain itself"
    assert [p for p in made.problems() if p.severity == "problem"] == []


def test_the_searches_are_the_files_in_the_directory(tmp_path: Path) -> None:
    """feat-004/AC-1: no index, no database. The directory listing is the list."""
    write(tmp_path / "searches", "one")
    write(tmp_path / "searches", "two")

    assert catalog(tmp_path / "searches").names() == ("one", "two")


def test_no_searches_directory_means_no_saved_searches(tmp_path: Path) -> None:
    """feat-004/AC-1: a fresh machine has none, which is an answer rather than an error."""
    catalogue = FileCatalog(tmp_path / "searches")

    assert catalogue.names() == ()
    with pytest.raises(UnknownSearch):
        catalogue.load("portales")


def test_a_name_that_is_a_path_is_refused_before_the_file_system_is_touched(
    tmp_path: Path,
) -> None:
    """feat-004/NFR-security: a search name becomes a file name, so it may not be a path.

    The name arrives from a command line today and a browser form tomorrow. Unconstrained, it reads
    and writes anywhere the process can reach.
    """
    secret = tmp_path / "secret.yaml"
    secret.write_text("name: secret\n", encoding="utf-8")
    catalogue = FileCatalog(tmp_path / "searches")

    for name in ("../secret", "..\\secret", "/etc/passwd", "a/b", ""):
        with pytest.raises(InvalidInput):
            catalogue.load(name)
        with pytest.raises(InvalidInput):
            catalogue.create(name)

    assert not (tmp_path / "searches").exists(), "nothing was created on the way to refusing"
    assert secret.read_text(encoding="utf-8") == "name: secret\n"
