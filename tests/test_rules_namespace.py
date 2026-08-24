"""The field namespace: what a criterion may name, and the three ways a name can be wrong.

The three are worth telling apart because they have three different fixes. A name that does not
exist is a typo. A name that exists but that nothing fills is a rule waiting on a feature. A name
that exists and is filled but empty for one property is that property's own answer, and belongs in a
verdict rather than in a validation message.
"""

from __future__ import annotations

import pytest

from homescout.records import FIELD_NAMES
from homescout.rules import namespace as ns
from homescout.rules.check import check
from homescout.rules.parse import parse


def complaints(expression: str):
    return check(parse(expression))


def test_the_namespace_is_enumerable_and_is_exactly_what_a_rule_may_name() -> None:
    """feat-008/AC-20: one declaration, and nothing reachable that is not in it."""
    declared = ns.names()

    assert declared == tuple(sorted(set(declared))), "no duplicates, stable order"
    for name in declared:
        assert not [c for c in complaints(f"{name} is not null") if c.severity == "problem"], name

    assert [c.severity for c in complaints("nonexistent is not null")] == ["problem"]


def test_every_listing_field_is_either_reachable_or_withheld_on_purpose() -> None:
    """feat-008/AC-20: a field added to a listing tomorrow cannot quietly become unreachable."""
    reachable = {name for name, field in ns.FIELDS.items() if field.origin == "listing"}

    assert reachable | ns.WITHHELD == set(FIELD_NAMES)


def test_what_a_source_claims_about_time_on_market_is_not_reachable() -> None:
    """feat-008/AC-20: freshness here is ours, and a rule may not quietly prefer a source's.

    Product invariant 7 says freshness is computed from this tool's own first observation. A
    criterion able to name the source's own figure would be a way around that, one rule at a time.
    `dom` is the honest one and it is in the namespace.
    """
    assert "days_on_market_source" in ns.WITHHELD
    assert ns.find("days_on_market_source") is None
    assert ns.find("dom") is not None

    found = complaints("days_on_market_source > 100")
    assert [c.severity for c in found] == ["problem"]
    assert "there is no field" in found[0].message


def test_a_name_that_does_not_exist_lists_the_ones_that_do() -> None:
    """feat-008/AC-13: the message a person can act on without opening the source."""
    found = complaints("uplaod_mbps < 100")

    assert len(found) == 1
    assert "no field called 'uplaod_mbps'" in found[0].message
    assert "upload_mbps" in found[0].message, "the near miss is in the list"


def test_a_name_nothing_fills_yet_is_a_notice_and_not_a_refusal() -> None:
    """feat-008/AC-14: the spec's edge case, and the brief's own example search.

    The brief drops on `upload_mbps < 100`, and that value arrives with location enrichment, which
    is not built. Refusing to run the brief's own example until an unrelated feature ships would be
    answering a question nobody asked. Saying so once, plainly, is the useful thing.
    """
    found = complaints("upload_mbps < 100")

    assert [c.severity for c in found] == ["notice"]
    assert "nothing in this build fills it yet" in found[0].message
    assert "location enrichment" in found[0].message
    assert "undetermined for every property" in found[0].message


def test_the_two_kinds_of_unknown_name_read_differently() -> None:
    """feat-008/AC-14: different problems, different fixes, different words."""
    absent = complaints("not_a_field > 1")[0]
    unfilled = complaints("flood_zone is not null")[0]

    assert absent.severity == "problem"
    assert unfilled.severity == "notice"
    assert absent.message != unfilled.message


MISMATCHES = [
    ("city > 100", "compares text against a number"),
    ("price == 'expensive'", "compares a number against text"),
    ("beds + city > 2", "wants a number"),
    ("price and beds", "wants true or false"),
    ("price", "yes or no answer"),
    ("city in [1, 2]", "can never match"),
    ("price in 'text'", "wants a list"),
    ("beds in ['a', 1]", "same kind of thing"),
]


@pytest.mark.parametrize(("expression", "because"), MISMATCHES, ids=[m[1] for m in MISMATCHES])
def test_a_comparison_that_cannot_mean_anything_is_caught_before_a_run(
    expression: str, because: str
) -> None:
    """feat-008/AC-15: the spec's edge case. A type mismatch is a validation failure, not a false.

    Left to evaluation it would be a per-property error forever, or worse, a quiet false that
    excludes every property for a reason nobody can see.
    """
    found = [c for c in complaints(expression) if c.severity == "problem"]

    assert found, "nothing was said about an expression that cannot mean anything"
    assert any(because in c.message for c in found), [c.message for c in found]


def test_a_field_that_is_a_list_can_be_asked_what_it_contains() -> None:
    """feat-008/AC-20: the one field that holds several values behaves like it."""
    assert not [c for c in complaints("'photo' in photo_urls") if c.severity == "problem"]
