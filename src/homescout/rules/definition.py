"""A rule: an identifier, an expression, and what firing means.

This is the piece a saved search carries and this feature reads. The file format owns the section's
place in the document (feat-004); what is inside each entry is owned here, which is why validating
the section is a call into this module rather than a second copy of the grammar living in the file
parser.

Every problem in a section is collected rather than raised, because a person fixing five criteria
should learn about all five at once. That is the same discipline the definition file already
follows, and the shape it returns is the shape that file already carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .check import check
from .parse import parse
from .syntax import Node
from .tokens import RuleSyntaxError

#: What firing means. Nothing else is a severity, because each of these has a defined effect and a
#: fifth would have none.
SEVERITIES: tuple[str, ...] = ("drop", "flag", "boost", "demote")


@dataclass(frozen=True, slots=True)
class Rule:
    """One criterion, parsed and checked."""

    id: str
    when: str
    severity: str
    expression: Node


@dataclass(frozen=True, slots=True)
class Problem:
    """One thing to say about a rules section, and where in it."""

    where: tuple[Any, ...]
    message: str
    severity: str = "problem"


def read(entries: Sequence[Any]) -> tuple[tuple[Rule, ...], tuple[Problem, ...]]:
    """Every rule in a section, and everything wrong with it.

    Returns the rules that were readable alongside the problems, rather than nothing at all when one
    entry is broken, so that a caller validating a file can also say what the good rules were.
    """
    made: list[Rule] = []
    found: list[Problem] = []
    seen: dict[str, int] = {}

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            found.append(Problem((index,), "a rule is written as an id, a when, and a severity"))
            continue

        unknown = [key for key in entry if key not in ("id", "when", "severity")]
        for key in unknown:
            found.append(
                Problem((index, key), f"{key!r} is not part of a rule (id, when, severity)")
            )

        identifier = entry.get("id")
        expression_text = entry.get("when")
        severity = entry.get("severity")

        if not isinstance(identifier, str) or not identifier.strip():
            found.append(Problem((index, "id"), "every rule needs an id, so a badge can name it"))
            identifier = None
        elif identifier in seen:
            found.append(
                Problem(
                    (index, "id"),
                    f"two rules are both called {identifier!r}. An id names one criterion, and a "
                    f"flag that could mean either of two says nothing.",
                )
            )
        elif identifier is not None:
            seen[identifier] = index

        if severity not in SEVERITIES:
            found.append(
                Problem(
                    (index, "severity"),
                    f"{severity!r} is not a severity. One of: {', '.join(SEVERITIES)}.",
                )
            )

        if not isinstance(expression_text, str) or not expression_text.strip():
            found.append(Problem((index, "when"), "every rule needs a `when` to test"))
            continue

        try:
            expression = parse(expression_text)
        except RuleSyntaxError as exc:
            found.append(
                Problem(
                    (index, "when"),
                    f"{_named(identifier)} cannot be read, {exc.args[0]}",
                )
            )
            continue

        for complaint in check(expression):
            found.append(
                Problem(
                    (index, "when"),
                    f"{_named(identifier)} at character {complaint.position + 1}: "
                    f"{complaint.message}",
                    severity=complaint.severity,
                )
            )

        if identifier and severity in SEVERITIES:
            made.append(Rule(identifier, expression_text, str(severity), expression))

    return tuple(made), tuple(found)


def _named(identifier: str | None) -> str:
    return f"the rule {identifier!r}" if identifier else "this rule"


def check_section(entries: Sequence[Any]) -> tuple[Problem, ...]:
    """Everything worth saying about a rules section. Nothing is evaluated, nothing is fetched."""
    return read(entries)[1]
