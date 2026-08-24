"""Reading an address, against the forms three real sources actually produce.

Every case here is in `tests/fixtures/merge/three-sources.json`, which is one real run over one
town: 140 rows, 46 of the keys shared by two or three sources. The properties in it are invented and
the disagreements are not, and the disagreements are the whole point.

The failure this module exists to prevent is quiet. A house written `2016 N Sable Ave` by one source
and `2016 N Sable St` by two others, compared as strings, is two properties forever, and nothing in
the output ever says so.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from homescout.merge.address import MAX_LENGTH, Address, of, parse

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "merge" / "three-sources.json"
ZIP = "88888"


def key(line: str, unit: str | None = None, postal: str = ZIP) -> str | None:
    return parse(line, unit=unit, postal=postal).key()


def test_the_briefs_own_example_pair_is_one_property() -> None:
    """feat-006/AC-1: the pair the brief names, which is what the criterion asks for by name."""
    assert key("1747 S Roosevelt Rd 10 1/2") == key("1747 South Roosevelt Road 10 1/2")
    assert key("1747 S Roosevelt Rd 10 1/2") == "88888|1747|roosevelt|10 1/2"


@pytest.mark.parametrize(
    ("one", "other", "why"),
    [
        ("2016 N Sable Ave", "2016 N Sable St", "sources disagree about the street type"),
        ("1414 Gable", "1414 Gable Cir", "one source drops the type entirely"),
        ("405 N Ave DOVETAIL Ave", "405 N Avenue DOVETAIL", "one source repeats it"),
        ("725 Halstead Parkway Dr", "725 Halstead Pkwy", "one carries two types"),
        ("2214 NM Highway 236", "2214 Nm 236 Rd", "a state highway, named two ways"),
        ("317 E 17th St", "317 East 17th Street", "abbreviated against expanded"),
        ("1015 N Ave N", "1015 N Avenue N", "a street actually called Avenue N"),
        ("1015 N Ave. N", "1015 N Avenue N", "and with a full stop in it"),
        ("2128B Verity", "2128 B Verity", "a lettered house number, spaced two ways"),
        ("2139 S Willow Rd S #7", "2139 S Willow Road 7", "one house, two of three formats"),
        ("2139 S Willow Rd 7", "2139 S Willow Road 7", "and the third"),
    ],
)
def test_the_formatting_differences_the_sources_actually_produce(
    one: str, other: str, why: str
) -> None:
    """feat-006/AC-2: every one of these is in the corpus, and every one is one property.

    The list is the argument for comparing parts rather than one normalized string: four of these
    pairs disagree about the street type, and a string comparison calls each of them two houses.
    """
    assert key(one) == key(other) is not None, why


def test_a_unit_is_read_however_it_is_decorated() -> None:
    """feat-006/AC-3: `Unit B`, `# B`, `Apt B` and `B` are one unit, and the corpus has all four."""
    assert parse("2128 Verity", unit="Unit B").unit == "b"
    assert parse("2128 Verity", unit="# B").unit == "b"
    assert parse("2128 Verity", unit="Apt B").unit == "b"
    assert parse("2128 Verity", unit="B").unit == "b"
    assert parse("2139 S Willow Rd S #7", unit="# 7").unit == "7"


def test_a_unit_that_differs_makes_a_different_key() -> None:
    """feat-006/AC-3: different units are different properties, so the key has to carry it."""
    assert key("2128 Verity", unit="Unit B") != key("2128 Verity", unit="Unit C")
    assert key("2128 Verity", unit="Unit B") != key("2128 Verity")


def test_a_fractional_unit_survives_normalization() -> None:
    """feat-006/AC-3: `10 1/2` is a real unit designation and is not punctuation to be scrubbed."""
    assert parse("1747 S Roosevelt Rd 10 1/2").unit == "10 1/2"


def test_a_placeholder_house_number_is_no_house_number() -> None:
    """feat-006/AC-8: land listings carry these constantly.

    Treating `000` as a number would match every parcel in a subdivision to every other one, which
    is the wrong merge this feature exists to prevent, arrived at by arithmetic.
    """
    for line in (
        "000 TBD Alder Addition Block 2 Lot 2 Rd",
        "Bigler Addition Block 2 Lot 3",
        "Block 2 Lot 2",
        "TBD County Road 8",
    ):
        assert key(line) is None, line


def test_a_house_number_is_only_a_house_number_at_the_front() -> None:
    """feat-006/AC-8: because the parser will happily offer the 2 out of `Block 2`.

    An American address begins with its number. One that does not is a parcel description, and a
    parcel description has no street to key on.
    """
    assert parse("Bigler Addition Block 2 Lot 3").number == ""
    assert parse("612 E 17th Ln").number == "612"


def test_an_address_the_parser_refuses_keeps_its_row() -> None:
    """feat-006/AC-22: retained, compared by what is left, and never dropped or fatal.

    `usaddress` raises on this one rather than returning anything, and real land listings are
    written this way.
    """
    found = parse("Lot 14 Blk 2 Curry Road AA")

    assert found.parsed is False
    assert found.key() is None
    assert found.raw == "Lot 14 Blk 2 Curry Road AA", "what the source said is kept"


def test_no_address_at_all_is_an_address_with_nothing_in_it() -> None:
    """feat-006/AC-22: and not an exception, because a run must survive a row like this."""
    assert parse(None).key() is None
    assert parse("").key() is None
    assert parse("   ").key() is None
    assert of(object()).key() is None


def test_a_very_long_address_is_bounded_before_it_is_parsed() -> None:
    """feat-006 security: nothing here has its running time set by a value somebody else chose."""
    monstrous = "1747 " + ("Roosevelt " * 500) + "Rd"

    found = parse(monstrous, postal=ZIP)

    assert found.raw == monstrous, "the row keeps what the source said"
    assert len(found.street) < MAX_LENGTH * 2


def test_the_postal_code_is_digits_and_comes_from_the_row() -> None:
    """feat-006/AC-1: a field is cleaner than anything parsed out of a free-text line."""
    assert parse("612 E 17th Ln", postal="88888-1234").postal == "88888"
    assert parse("612 E 17th Ln", postal=None).postal == ""


def test_a_missing_postal_code_weakens_the_key_without_destroying_it() -> None:
    """feat-006, the spec's missing-ZIP edge case.

    The key still exists and is simply less specific, rather than vanishing.
    """
    without = parse("612 E 17th Ln", postal=None)

    assert without.key() == "|612|17th|"
    assert without.key() != key("612 E 17th Ln")


def test_the_street_type_and_direction_are_read_but_kept_out_of_the_key() -> None:
    """feat-006/AC-2: they are corroborating, and the corpus is why.

    Read, because agreement on them is worth something to a comparison. Out of the key, because
    three sources disagree about them for the same house and a key built from a part sources
    disagree about separates a house from itself.
    """
    avenue = parse("2016 N Sable Ave")
    street = parse("2016 N Sable St")

    assert avenue.street_type == "ave" and street.street_type == "st"
    assert avenue.direction == street.direction == "n"
    assert avenue.key() == street.key()


def test_every_row_in_the_corpus_is_read_without_raising() -> None:
    """feat-006/AC-22: 140 rows from three sources, and none of them may be fatal.

    The reliability requirement in one sentence: a malformed row degrades that row and nothing else.
    """
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert len(rows) == 140

    keyed = 0
    for row in rows:
        found = parse(row["address_line"], unit=row["unit"], postal=row["postal_code"])
        assert isinstance(found, Address)
        keyed += found.key() is not None

    assert keyed == len(rows) - 7, "the seven without a key are the land parcels"


def test_the_corpus_collapses_to_about_sixty_properties() -> None:
    """feat-006/AC-1: 140 rows from three sources over one town are not 140 houses.

    The number is the point of the whole feature. It is asserted as a range rather than a figure
    because the corpus is real and a future re-record will move it slightly; what must not move is
    that it is close to a third of the rows.
    """
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))
    keys = {
        parse(row["address_line"], unit=row["unit"], postal=row["postal_code"]).key()
        for row in rows
    }
    keys.discard(None)

    assert 55 <= len(keys) <= 65, len(keys)
