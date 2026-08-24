"""Answering one criterion about one property, in three-valued logic.

The third value is the whole point. A property whose upload speed nobody has fetched has not failed
a test about upload speed; the test could not be run. Rounding that to false would exclude houses
for want of data, which is the same error as reading an absence as evidence one layer down, and it
is the error the spec spends four criteria preventing.

So an unknown propagates, and it carries the names that produced it, so the report can say which
value was missing rather than that something was.

Two things about combination are deliberate:

**Kleene's tables, not Python's.** `false and unknown` is false, because false decides it whatever
the unknown turns out to be. `true or unknown` is true, for the same reason. Everything else
touching an unknown is unknown.

**Both sides are always evaluated.** Not short-circuiting costs nothing here (an expression is at
most two hundred nodes and evaluation has no effects) and buys a complete set of missing names
rather than however many were reached before the answer settled.

Nothing in this module reads a file, opens a connection, or calls anything it was not handed. That
is checked mechanically by a test rather than promised here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from typing import Literal as Only

from .syntax import (
    Arithmetic,
    Both,
    Comparison,
    Either,
    IsNull,
    ListOf,
    Literal,
    Name,
    Negate,
    Node,
    Not,
)
from .tokens import MAX_MAGNITUDE

Verdict = Only["fired", "not-fired", "undetermined"]


@dataclass(frozen=True, slots=True)
class Unknown:
    """No answer, and what was missing. An arithmetic overflow or a division by zero has no name."""

    missing: tuple[str, ...] = ()


def _merge(*values: object) -> Unknown:
    found: set[str] = set()
    for value in values:
        if isinstance(value, Unknown):
            found.update(value.missing)
    return Unknown(tuple(sorted(found)))


def _bounded(value: float | int) -> object:
    """An arithmetic result, or unknown when it has left the range of real quantities.

    A criterion that overflowed a thousand times the most expensive property ever sold was not a
    question about a house. Answering unknown rather than raising keeps one silly rule from ending a
    run, and answering it *here*, at every step, is what stops a nested doubling from ever building
    the enormous number in the first place.
    """
    if value != value or abs(value) > MAX_MAGNITUDE:  # noqa: PLR0124 - the first test is for NaN
        return Unknown()
    return value


def evaluate(node: Node, values: Mapping[str, Any]) -> object:
    """This expression's value for this property, or `Unknown`."""
    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Name):
        found = values.get(node.name)
        return Unknown((node.name,)) if found is None else found

    if isinstance(node, ListOf):
        items = [evaluate(item, values) for item in node.items]
        if any(isinstance(item, Unknown) for item in items):
            return _merge(*items)
        return items

    if isinstance(node, IsNull):
        found = evaluate(node.operand, values)
        missing = isinstance(found, Unknown)
        return not missing if node.negated else missing

    if isinstance(node, Not):
        found = evaluate(node.operand, values)
        return found if isinstance(found, Unknown) else not found

    if isinstance(node, Both):
        left, right = evaluate(node.left, values), evaluate(node.right, values)
        if left is False or right is False:
            return False
        if isinstance(left, Unknown) or isinstance(right, Unknown):
            return _merge(left, right)
        return bool(left and right)

    if isinstance(node, Either):
        left, right = evaluate(node.left, values), evaluate(node.right, values)
        if left is True or right is True:
            return True
        if isinstance(left, Unknown) or isinstance(right, Unknown):
            return _merge(left, right)
        return bool(left or right)

    if isinstance(node, Negate):
        found = evaluate(node.operand, values)
        return found if isinstance(found, Unknown) else _bounded(-found)

    if isinstance(node, Arithmetic):
        return _arithmetic(node, values)

    if isinstance(node, Comparison):
        return _compare(node, values)

    raise TypeError(f"a parsed rule cannot contain {type(node).__name__}")  # pragma: no cover


def _arithmetic(node: Arithmetic, values: Mapping[str, Any]) -> object:
    left, right = evaluate(node.left, values), evaluate(node.right, values)
    if isinstance(left, Unknown) or isinstance(right, Unknown):
        return _merge(left, right)
    if node.operator == "+":
        return _bounded(left + right)
    if node.operator == "-":
        return _bounded(left - right)
    if node.operator == "*":
        return _bounded(left * right)
    if right == 0:
        # Not an error. A rule dividing by a field that happens to be zero for one property is a
        # question with no answer for that property, which is exactly what unknown means.
        return Unknown()
    return _bounded(left / right)


def _compare(node: Comparison, values: Mapping[str, Any]) -> object:
    left, right = evaluate(node.left, values), evaluate(node.right, values)
    if isinstance(left, Unknown) or isinstance(right, Unknown):
        return _merge(left, right)
    if node.operator == "==":
        return left == right
    if node.operator == "!=":
        return left != right
    if node.operator == "in":
        return left in right
    if node.operator == "not in":
        return left not in right
    if node.operator == "<":
        return left < right
    if node.operator == "<=":
        return left <= right
    if node.operator == ">":
        return left > right
    return left >= right


def verdict(node: Node, values: Mapping[str, Any]) -> tuple[Verdict, tuple[str, ...]]:
    """Fired, not fired, or undetermined, with the names that were missing when undetermined."""
    answer = evaluate(node, values)
    if isinstance(answer, Unknown):
        return ("undetermined", answer.missing)
    return ("fired" if answer else "not-fired", ())
