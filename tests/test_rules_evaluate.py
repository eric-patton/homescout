"""Three-valued evaluation: the tables, and why the third value is not false.

A property whose upload speed nobody fetched has not failed a test about upload speed. Every test
here is a way of pinning that difference, because rounding unknown to false excludes houses for want
of data, silently, and is indistinguishable afterwards from a house that genuinely failed.
"""

from __future__ import annotations

import pytest

from homescout.rules.evaluate import Unknown, evaluate, verdict
from homescout.rules.parse import parse
from homescout.rules.tokens import MAX_MAGNITUDE

KNOWN = {
    "beds": 4,
    "baths": 2.5,
    "sqft": 2000,
    "price": 350_000,
    "property_type": "single_family",
    "city": "Portales",
    "dom": 200,
    "is_new": False,
    "price_cut": True,
}


def answer(expression: str, values=KNOWN):
    return verdict(parse(expression), values)


def test_a_criterion_that_can_be_answered_is_answered() -> None:
    """feat-008/AC-9: the ordinary case, which everything else is measured against."""
    assert answer("beds >= 3")[0] == "fired"
    assert answer("beds >= 5")[0] == "not-fired"


def test_a_value_nobody_has_is_undetermined_and_says_which() -> None:
    """feat-008/AC-9, feat-008/AC-11: not false, and it names the field a person has to go get."""
    found, missing = answer("upload_mbps < 100")

    assert found == "undetermined"
    assert missing == ("upload_mbps",)


def test_undetermined_names_every_value_it_was_missing() -> None:
    """feat-008/AC-11: both, not the first one reached, because both have to be fetched."""
    found, missing = answer("upload_mbps < 100 and flood_zone == 'AE'")

    assert found == "undetermined"
    assert missing == ("flood_zone", "upload_mbps")


CONJUNCTION = [
    ("beds >= 3 and sqft > 1000", "fired"),
    ("beds >= 3 and sqft > 9000", "not-fired"),
    ("beds >= 9 and upload_mbps < 100", "not-fired"),
    ("beds >= 3 and upload_mbps < 100", "undetermined"),
    ("upload_mbps < 100 and flood_zone == 'AE'", "undetermined"),
]

DISJUNCTION = [
    ("beds >= 3 or sqft > 9000", "fired"),
    ("beds >= 9 or sqft > 9000", "not-fired"),
    ("beds >= 3 or upload_mbps < 100", "fired"),
    ("beds >= 9 or upload_mbps < 100", "undetermined"),
]


@pytest.mark.parametrize(("expression", "expected"), CONJUNCTION + DISJUNCTION)
def test_unknown_travels_through_and_and_or_the_way_kleene_says(
    expression: str, expected: str
) -> None:
    """feat-008/AC-12: false decides an `and` and true decides an `or`, whatever else is unknown.

    This is the pair of rows the criterion names explicitly, and they are the ones a two-valued
    implementation gets wrong: `false and unknown` has to be false, because false settles it however
    the unknown turns out.
    """
    assert answer(expression)[0] == expected


def test_not_leaves_unknown_alone() -> None:
    """feat-008/AC-12: the negation of "nobody knows" is still "nobody knows"."""
    assert answer("not upload_mbps < 100")[0] == "undetermined"
    assert answer("not beds >= 9")[0] == "fired"


def test_asking_whether_a_value_is_known_always_has_an_answer() -> None:
    """feat-008/AC-9: the one question about the third value that is never itself unknown."""
    assert answer("upload_mbps is null")[0] == "fired"
    assert answer("price is null")[0] == "not-fired"
    assert answer("price is not null")[0] == "fired"


def test_arithmetic_and_membership() -> None:
    """feat-008/AC-15: the operators the spec's own examples need."""
    assert answer("price / sqft < 200")[0] == "fired"
    assert answer("property_type in ['single_family', 'farm']")[0] == "fired"
    assert answer("property_type not in ['single_family']")[0] == "not-fired"
    assert answer("-beds + 10 > 5")[0] == "fired"


def test_dividing_by_zero_is_unknown_rather_than_an_ending() -> None:
    """feat-008/AC-9: the spec's edge case. One silly rule cannot end a run."""
    assert answer("price / 0 > 1", {"price": 1})[0] == "undetermined"
    assert answer("price / sqft > 1", {"price": 1, "sqft": 0})[0] == "undetermined"


def test_arithmetic_that_leaves_the_range_of_real_quantities_is_unknown() -> None:
    """feat-008/AC-19: the bound that keeps evaluation from consuming unbounded time.

    Python's integers are arbitrary precision, so a nested doubling would otherwise build a number
    with billions of digits from an expression of forty characters. Answering unknown at every step
    means the enormous number is never built at all.
    """
    big = {"price": MAX_MAGNITUDE - 1}

    assert answer("price * price > 0", big)[0] == "undetermined"
    assert evaluate(parse("price * price"), big) == Unknown()


def test_the_same_property_and_the_same_rules_answer_the_same_way_every_time() -> None:
    """feat-008/AC-21: no clock, no ordering, no accumulated state to drift."""
    shuffled = dict(reversed(list(KNOWN.items())))
    expressions = [
        "beds >= 3 and sqft > 1000",
        "upload_mbps < 100 or flood_zone is null",
        "price / sqft < 200",
    ]

    once = [answer(e) for e in expressions]
    again = [answer(e, shuffled) for e in expressions]
    third = [answer(e) for e in reversed(expressions)]

    assert once == again
    assert list(reversed(third)) == once


def test_an_empty_value_and_an_absent_one_are_the_same_thing() -> None:
    """feat-008/AC-9: a field this tool records as empty is a field nobody has determined.

    Product invariant 10 says an undeterminable value is empty rather than guessed, so empty and
    absent have to mean the same thing to a criterion, or a rule would read a recorded blank as a
    real value.
    """
    assert answer("flood_zone == 'AE'", {"flood_zone": None})[0] == "undetermined"
    assert answer("flood_zone == 'AE'", {})[0] == "undetermined"
