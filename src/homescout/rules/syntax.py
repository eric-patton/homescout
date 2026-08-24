"""What a parsed criterion is: nine shapes, none of which can do anything.

Deliberately inert. These are frozen dataclasses holding other frozen dataclasses, with no methods
that act and no reference to anything outside this module. A parsed expression is a value, in the
same sense that a number is a value, and the only thing that can happen to it is being read by the
checker or the evaluator.

That is the whole safety argument, and it is worth stating in one place: there is no node type here
that names a function, an attribute, a subscript or an assignment, so no expression can parse into
one. The rejections the parser reports are courtesies, explaining what the language does not have.
They are not a filter standing between a larger language and this one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class Literal:
    """A number, a piece of text, or a truth value, written out in the expression."""

    value: object
    position: int


@dataclass(frozen=True, slots=True)
class Name:
    """A field from the declared namespace. The only way an expression reaches a value."""

    name: str
    position: int


@dataclass(frozen=True, slots=True)
class ListOf:
    items: tuple[Node, ...]
    position: int


@dataclass(frozen=True, slots=True)
class Negate:
    """Arithmetic negation: `-x`."""

    operand: Node
    position: int


@dataclass(frozen=True, slots=True)
class Arithmetic:
    operator: str
    left: Node
    right: Node
    position: int


@dataclass(frozen=True, slots=True)
class Comparison:
    operator: str
    left: Node
    right: Node
    position: int


@dataclass(frozen=True, slots=True)
class IsNull:
    """`x is null` and `x is not null`.

    The one place the three-valued logic is allowed to be asked about itself. Everywhere else an
    unknown operand makes the answer unknown, which means an expression can never test for one; this
    is how somebody asks "did we never learn this" and gets a straight yes or no.
    """

    operand: Node
    negated: bool
    position: int


@dataclass(frozen=True, slots=True)
class Not:
    operand: Node
    position: int


@dataclass(frozen=True, slots=True)
class Both:
    """`and`, in Kleene's three-valued sense."""

    left: Node
    right: Node
    position: int


@dataclass(frozen=True, slots=True)
class Either:
    """`or`, in Kleene's three-valued sense."""

    left: Node
    right: Node
    position: int


Node = Union[  # noqa: UP007 - a recursive alias needs the explicit form
    Literal, Name, ListOf, Negate, Arithmetic, Comparison, IsNull, Not, Both, Either
]
