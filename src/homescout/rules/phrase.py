"""A criterion as rows a person picks from, and back again.

The grammar this feature owns is small and safe, and it is still a grammar: `water_source == "well"`
asks somebody to know that a field is spelled with an underscore, that text takes double quotes, and
that `=` is not `==`. The person this tool is for should not have to know any of that to say "flag
the ones on a well".

So a criterion has a second shape. `readable` turns an expression into a flat list of rows, each a
field, a comparison and a value, joined by and or or. `compose` turns rows back into the expression
text that is what gets stored and evaluated. The stored form does not change: a saved search still
carries `when: water_source == "well"`, still readable and editable by hand, and a builder is a way
of writing that line rather than a second way of storing it.

**Not every expression is rows, and this says so rather than mangling one.** `(a or b) and c` is a
perfectly good criterion and is not a flat chain. `readable` answers `None` for anything it cannot
represent, and the surface falls back to showing the text. The test for that is exact rather than
hopeful: the rows are composed back into text, parsed again, and compared to the original tree. If
anything moved, the rows were not a faithful reading and are refused.

Nothing here evaluates anything. It reads a parsed expression and writes text; the parser and the
evaluator are unchanged and remain the only things that decide what a criterion means.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .parse import parse
from .syntax import Both, Comparison, Either, IsNull, ListOf, Literal, Name, Node
from .tokens import RuleSyntaxError

#: The comparisons a row may use, and how to say each one to somebody who is not writing code.
#: Ordered as a dropdown should offer them: the two everybody wants first.
COMPARISONS: tuple[tuple[str, str], ...] = (
    ("==", "is"),
    ("!=", "is not"),
    (">=", "is at least"),
    (">", "is more than"),
    ("<=", "is at most"),
    ("<", "is less than"),
    ("in", "is any of"),
    ("not in", "is none of"),
    ("is not null", "is known"),
    ("is null", "was never found out"),
)

#: The two that take no value at all, because they ask about the value's absence.
WITHOUT_VALUE: frozenset[str] = frozenset({"is null", "is not null"})

#: The one that takes several.
MANY: frozenset[str] = frozenset({"in", "not in"})


class CannotCompose(Exception):
    """These rows cannot be written as an expression, and why."""


@dataclass(frozen=True, slots=True)
class Part:
    """One row of a criterion: a field, a comparison, a value, and how it joins the row above."""

    field: str
    comparison: str
    value: Any = None
    #: Empty on the first row. `and` or `or` on every row after it.
    join: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "comparison": self.comparison,
            "value": self.value,
            "join": self.join,
        }


def readable(text: str) -> tuple[Part, ...] | None:
    """This expression as rows, or nothing when it is not a flat chain of comparisons.

    Answering `None` is a real answer and the surfaces treat it as one: the criterion is shown as
    text and stays editable that way. Silently dropping the part that would not fit is the failure
    mode worth being careful about, which is why the check below is a round trip rather than a
    guess.
    """
    try:
        expression = parse(text)
    except RuleSyntaxError:
        return None

    parts = _flatten(expression)
    if parts is None:
        return None

    try:
        again = parse(compose(parts))
    except (RuleSyntaxError, CannotCompose):
        return None
    return parts if _same(expression, again) else None


def compose(parts: Sequence[Part]) -> str:
    """Rows as the expression text a saved search stores.

    Written without parentheses, which is what makes the round trip in `readable` meaningful: rows
    are a flat chain, and a flat chain is exactly what re-parses to the same tree.
    """
    if not parts:
        raise CannotCompose("a criterion needs at least one condition")

    pieces: list[str] = []
    for index, part in enumerate(parts):
        if index:
            join = (part.join or "and").strip()
            if join not in ("and", "or"):
                raise CannotCompose(f"{join!r} is not a way of joining two conditions")
            pieces.append(join)
        pieces.append(_one(part))
    return " ".join(pieces)


def _one(part: Part) -> str:
    field = (part.field or "").strip()
    if not field:
        raise CannotCompose("every condition needs a field")

    from . import namespace as ns

    if ns.find(field) is None:
        raise CannotCompose(f"{field!r} is not something a criterion can ask about")

    comparison = (part.comparison or "").strip()
    if comparison not in {name for name, _said in COMPARISONS}:
        raise CannotCompose(f"{comparison!r} is not a comparison this understands")

    if comparison in WITHOUT_VALUE:
        return f"{field} {comparison}"

    if comparison in MANY:
        values = part.value if isinstance(part.value, (list, tuple)) else [part.value]
        if not values:
            raise CannotCompose(f"{field} needs at least one value to compare against")
        inside = ", ".join(_literal(value) for value in values)
        return f"{field} {comparison} [{inside}]"

    if part.value is None or part.value == "":
        raise CannotCompose(f"{field} needs something to compare against")
    return f"{field} {comparison} {_literal(part.value)}"


def _literal(value: Any) -> str:
    """One value, written the way the grammar reads it.

    Text has no escapes in this language, deliberately: a string ends at the next matching quote and
    there is nothing to escape into. So a value carrying both kinds of quote cannot be written, and
    that is said rather than papered over with a mangled expression.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    held = str(value)
    if '"' not in held:
        return f'"{held}"'
    if "'" not in held:
        return f"'{held}'"
    raise CannotCompose(
        f"{held!r} has both kinds of quote in it, and this language has no escapes. "
        "Compare against a shorter piece of it, or write the criterion by hand."
    )


def _flatten(node: Node) -> tuple[Part, ...] | None:
    """The expression as rows, left to right, or nothing if it is not a chain of comparisons."""
    if isinstance(node, (Both, Either)):
        join = "and" if isinstance(node, Both) else "or"
        left = _flatten(node.left)
        right = _flatten(node.right)
        if left is None or right is None:
            return None
        # The join belongs to the row it introduces, which is the first row of the right side.
        first, *rest = right
        return (*left, Part(first.field, first.comparison, first.value, join), *rest)

    if isinstance(node, IsNull):
        if not isinstance(node.operand, Name):
            return None
        return (Part(node.operand.name, "is not null" if node.negated else "is null"),)

    if isinstance(node, Comparison):
        if not isinstance(node.left, Name):
            return None
        if node.operator in MANY:
            if not isinstance(node.right, ListOf):
                return None
            values = [item.value for item in node.right.items if isinstance(item, Literal)]
            if len(values) != len(node.right.items):
                return None
            return (Part(node.left.name, node.operator, values),)
        if not isinstance(node.right, Literal):
            return None
        return (Part(node.left.name, node.operator, node.right.value),)

    return None


def _same(left: Node, right: Node) -> bool:
    """Two parsed expressions, compared without their positions.

    Positions move when an expression is rewritten with different spacing, and this question is
    about meaning rather than about layout.
    """
    if type(left) is not type(right):
        return False
    for name in left.__slots__:
        if name == "position":
            continue
        a, b = getattr(left, name), getattr(right, name)
        if isinstance(a, tuple) and isinstance(b, tuple):
            if len(a) != len(b) or not all(_same(x, y) for x, y in zip(a, b, strict=True)):
                return False
            continue
        if isinstance(a, Node) or isinstance(b, Node):
            if not _same(a, b):
                return False
            continue
        if a != b:
            return False
    return True
