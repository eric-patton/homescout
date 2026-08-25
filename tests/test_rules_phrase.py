"""A criterion as rows a person picks from, and back again.

The grammar is small and safe and is still a grammar, and the person this tool is for should not
have to learn that a field is spelled with an underscore and that `=` is not `==` in order to say
"flag the ones on a well". So a criterion has a second shape: rows of field, comparison and value,
which a browser can render as dropdowns.

The failure worth testing for is not a rejected expression. It is a *silently wrong* one: rows
that look like the criterion somebody wrote, are not, and get saved over it. Every test here is
pointed at that.
"""

from __future__ import annotations

import pytest

from homescout.rules.phrase import CannotCompose, Part, compose, readable

#: Real criteria, in the shapes people write. Each must survive text -> rows -> text unchanged.
ROUND_TRIPS = [
    'water_source == "well"',
    'sewer != "septic"',
    "price < 300000",
    "beds >= 4",
    'download_mbps < 25 and water_source != "well"',
    'flood_zone in ["A", "AE"]',
    'cooling not in ["refrigerated", "central"]',
    "water_source is null",
    "wildfire_hazard is not null",
    "is_new == true",
    "price_cut == false",
    'price < 300000 and lot_sqft > 87120 or beds >= 4',
]

#: Perfectly good criteria that are not rows. Each must be refused rather than approximated.
NOT_ROWS = [
    '(price < 100000 or beds > 3) and sqft > 1000',
    "price * 2 > 500000",
    "not price_cut",
    "price > sqft",
    'water_source == "well" and (sewer == "septic" or sewer is null)',
]


@pytest.mark.parametrize("text", ROUND_TRIPS)
def test_a_criterion_survives_being_rows(text: str) -> None:
    """feat-008/AC-24: what goes back into the file is what came out of it.

    Not "means the same thing", which would be a claim about the evaluator. The same text, so a
    saved search edited in the browser and one edited by hand are the same file.
    """
    parts = readable(text)

    assert parts is not None, f"{text} could not be read as rows"
    assert compose(parts) == text


@pytest.mark.parametrize("text", NOT_ROWS)
def test_a_criterion_that_is_not_rows_is_refused_rather_than_approximated(text: str) -> None:
    """feat-008/AC-24: the failure that matters is a wrong reading, not a refused one.

    `(a or b) and c` is a perfectly good criterion. Flattening it into three rows would produce
    `a or b and c`, which is a different criterion, and saving that over the original would change
    what somebody's search does without telling them.
    """
    assert readable(text) is None


def test_the_check_is_a_round_trip_rather_than_a_guess() -> None:
    """feat-008/AC-24: the parenthesised case proves the check is real.

    `(a or b) and c` flattens to rows that look right. What catches it is composing them back and
    comparing the parsed result, which differs because `and` binds tighter than `or`.
    """
    without = readable("price < 100000 or beds > 3 and sqft > 1000")
    assert without is not None, "this one is a flat chain and should read"

    with_parens = readable("(price < 100000 or beds > 3) and sqft > 1000")
    assert with_parens is None, "the parentheses change the meaning and were not noticed"


def test_the_pieces_of_a_row_are_what_a_dropdown_needs() -> None:
    """feat-008/AC-24: a field, a comparison, a value, and how it joins the row above."""
    parts = readable('download_mbps < 25 and water_source != "well"')

    assert parts is not None
    assert [p.field for p in parts] == ["download_mbps", "water_source"]
    assert [p.comparison for p in parts] == ["<", "!="]
    assert [p.value for p in parts] == [25, "well"]
    # The join belongs to the row it introduces, so the first row has none.
    assert [p.join for p in parts] == ["", "and"]


def test_a_field_that_does_not_exist_is_refused_before_anything_is_written() -> None:
    """feat-008/AC-25: the namespace is the only list of names there is, here too.

    A browser that offered a field would have got it from the same namespace, so this is about a
    hand-made request rather than a mistake somebody could make by clicking.
    """
    with pytest.raises(CannotCompose, match="not something a criterion can ask about"):
        compose([Part("hoa_dues", "==", 100)])


def test_a_comparison_that_is_not_one_is_refused() -> None:
    with pytest.raises(CannotCompose, match="not a comparison"):
        compose([Part("price", "=~", 100)])


def test_a_condition_with_nothing_to_compare_against_says_so() -> None:
    """feat-008/AC-25: an empty box is the most likely mistake, so it gets a sentence.

    Composing `price <` and letting the parser fail would report a syntax error about the end of an
    expression, which is true and is not what happened.
    """
    with pytest.raises(CannotCompose, match="needs something to compare against"):
        compose([Part("price", "<", "")])


def test_a_join_that_is_not_and_or_or_is_refused() -> None:
    with pytest.raises(CannotCompose, match="not a way of joining"):
        compose([Part("price", "<", 100), Part("beds", ">", 2, "unless")])


def test_no_conditions_at_all_is_refused() -> None:
    with pytest.raises(CannotCompose, match="at least one condition"):
        compose([])


def test_text_carrying_a_quote_is_written_with_the_other_one() -> None:
    """feat-008/AC-25: this language has no escapes, deliberately, so quoting is a real decision."""
    assert compose([Part("city", "==", 'Coeur d\'Alene')]) == "city == \"Coeur d'Alene\""
    assert compose([Part("description", "==", 'a "quoted" thing')]) == (
        "description == 'a \"quoted\" thing'"
    )


def test_text_carrying_both_quotes_is_refused_rather_than_mangled() -> None:
    """feat-008/AC-25: unwriteable is a real answer, and a mangled expression is not.

    A string ends at the next matching quote and there is nothing to escape into, which is what
    makes "a description containing a quote is a literal, never an escape" true. The cost is this
    case, and it is named rather than papered over.
    """
    with pytest.raises(CannotCompose, match="both kinds of quote"):
        compose([Part("description", "==", 'it said "don\'t"')])


def test_a_number_stays_a_number_and_a_word_stays_a_word() -> None:
    """feat-008/AC-25: quoting a price would compare a number against text and never be true."""
    assert compose([Part("price", "<", 300000)]) == "price < 300000"
    assert compose([Part("water_source", "==", "well")]) == 'water_source == "well"'
    assert compose([Part("is_new", "==", True)]) == "is_new == true"


def test_a_list_of_one_is_still_a_list() -> None:
    assert compose([Part("flood_zone", "in", ["A"])]) == 'flood_zone in ["A"]'


def test_an_empty_list_is_refused() -> None:
    """feat-008/AC-25: `in []` parses and can never be true, which is worse than a complaint."""
    with pytest.raises(CannotCompose, match="at least one value"):
        compose([Part("flood_zone", "in", [])])


def test_every_comparison_offered_can_be_composed() -> None:
    """feat-008/AC-24: a dropdown offering what the composer refuses is a broken dropdown."""
    from homescout.rules.phrase import COMPARISONS, MANY, WITHOUT_VALUE

    for comparison, said in COMPARISONS:
        assert said, f"{comparison} has no words to put in front of a person"
        if comparison in WITHOUT_VALUE:
            made = compose([Part("water_source", comparison)])
        elif comparison in MANY:
            made = compose([Part("water_source", comparison, ["well"])])
        else:
            made = compose([Part("price", comparison, 100)])
        assert made, comparison

        # And what it composed is a criterion the engine accepts, which is the whole claim.
        from homescout.rules.parse import parse

        parse(made)


def test_nonsense_text_reads_as_no_rows_rather_than_raising() -> None:
    """A surface asks "is this rows" about whatever is in the file, including a broken one."""
    assert readable("price <") is None
    assert readable("") is None
