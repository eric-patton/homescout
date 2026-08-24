"""The expression language: what it accepts, what it refuses, and where it says the trouble is.

The refusals matter more than the acceptances here. This is the only place in the product where text
a person wrote is read at all, and every construct the language does not have is a construct that
could otherwise reach outside the field namespace.
"""

from __future__ import annotations

import pytest

from homescout.rules.parse import MAX_DEPTH, MAX_NODES, parse
from homescout.rules.syntax import Both, Comparison, IsNull, Literal, Name
from homescout.rules.tokens import MAX_LENGTH, MAX_MAGNITUDE, RuleSyntaxError

WRITTEN = [
    "dom > 180",
    "price_raised_after_days > 120",
    "water_source == 'well' and not over_principal_aquifer",
    "upload_mbps < 100",
    "beds >= 3 and (baths >= 2 or sqft > 2000)",
    "property_type in ['single_family', 'farm']",
    "property_type not in ['condo']",
    "price / sqft < 200",
    "price is null",
    "flood_zone is not null",
    "-price + 10 > 0",
    "is_new and price_cut",
    "city == 'Portales' and state == 'NM'",
]


@pytest.mark.parametrize("expression", WRITTEN)
def test_the_criteria_a_person_writes_all_parse(expression: str) -> None:
    """feat-008/AC-15: the language covers what the brief and the spec ask criteria to say."""
    assert parse(expression) is not None


def test_precedence_is_the_one_everybody_expects() -> None:
    """feat-008/AC-15: `and` binds tighter than `or`, comparison tighter than both."""
    node = parse("beds >= 3 and sqft > 1000")

    assert isinstance(node, Both)
    assert isinstance(node.left, Comparison)
    assert isinstance(node.right, Comparison)
    assert isinstance(node.left.left, Name)
    assert isinstance(node.left.right, Literal)


def test_asking_whether_a_value_is_known_is_its_own_question() -> None:
    """feat-008/AC-9: `is null` is the one way to ask about the third value directly."""
    node = parse("price is not null")

    assert isinstance(node, IsNull)
    assert node.negated is True


REFUSED = [
    ("open('secrets')", "cannot call a function"),
    ("price.real > 1", "cannot reach inside a value"),
    ("photo_urls[0] == 'a'", "cannot index into a value"),
    ("price = 5", "cannot assign"),
    ("__import__('os')", "cannot call a function"),
    ("1 < 2 < 3", "do not chain"),
    ("beds > 1; price > 2", "means nothing in a rule"),
    ("price > 1e999", "cannot have an exponent"),
    ("'unclosed", "never closed"),
    ("price >", "stops in the middle"),
    ("(price > 1", "expected a closing"),
    ("price @ 1", "means nothing in a rule"),
    ("", "stops in the middle"),
]


@pytest.mark.parametrize(("expression", "because"), REFUSED, ids=[r[1] for r in REFUSED])
def test_each_construct_the_language_does_not_have_is_refused_by_name(
    expression: str, because: str
) -> None:
    """feat-008/AC-17: one at a time, each with a message that says what was wrong.

    A parser that answered "unexpected token" would send somebody looking for a typo they did not
    make. Each of these is a thing a person could reasonably expect to work, and each is a way out
    of the namespace if it did.
    """
    with pytest.raises(RuleSyntaxError) as raised:
        parse(expression)

    assert because in raised.value.message
    assert raised.value.position >= 0


def test_a_failure_says_where_it_stopped() -> None:
    """feat-008/AC-15: the position, because a rule's expression is one string inside one line."""
    with pytest.raises(RuleSyntaxError) as raised:
        parse("beds >= 3 and $ > 1")

    assert raised.value.position == 14
    assert "at character 15" in str(raised.value)


def test_an_expression_longer_than_the_limit_is_refused_before_it_is_read() -> None:
    """feat-008/AC-18: bounded in size, and the bound is stated in the message."""
    with pytest.raises(RuleSyntaxError, match=str(MAX_LENGTH)):
        parse("x" * (MAX_LENGTH + 1))


def test_an_expression_nested_past_the_limit_is_refused_while_descending() -> None:
    """feat-008/AC-18: checked on the way down, so it cannot exhaust this parser's own stack."""
    with pytest.raises(RuleSyntaxError, match="nests more than"):
        parse("(" * (MAX_DEPTH + 5) + "1" + ")" * (MAX_DEPTH + 5))


def test_an_expression_with_too_many_pieces_is_refused() -> None:
    """feat-008/AC-18: a long flat expression is bounded too, which nesting alone would miss."""
    with pytest.raises(RuleSyntaxError, match=str(MAX_NODES)):
        parse("1+" * (MAX_NODES + 10) + "1")


def test_a_number_larger_than_any_property_is_refused() -> None:
    """feat-008/AC-19: the bound that stops arbitrary-precision arithmetic from being a weapon.

    Nothing about a house is measured in quadrillions. Refusing the literal is half of the answer;
    the other half is that an arithmetic result past the same bound is undetermined rather than
    computed, which is what stops a nested doubling from ever building the number.
    """
    with pytest.raises(RuleSyntaxError, match="larger than"):
        parse(f"price > {MAX_MAGNITUDE * 10}")

    assert parse(f"price > {MAX_MAGNITUDE - 1}") is not None
