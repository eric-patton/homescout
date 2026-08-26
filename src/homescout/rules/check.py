"""What is wrong with a criterion, before anything is evaluated.

Two kinds of thing are caught here, and both are the difference between a message and a mystery.

**A name that is not a field.** The grammar cannot construct a name, so the only way out of the
namespace would be naming something that is not in it. Refused, with the available names listed.

**A comparison that cannot mean anything.** `city > 100` compares text against a number. Python
would refuse it at evaluation time, per property, forever; the spec says it is a validation failure
at check time, once, before a run. So every node gets a type from the namespace's declarations and
the literals' own types, and the operators say what they accept.

The result of the whole expression must be true or false. A criterion that reads `price` is not a
criterion, and treating a non-empty number as true is the kind of convenience that later reads as a
bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import namespace as ns
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

Severity = str


@dataclass(frozen=True, slots=True)
class Complaint:
    """One thing wrong with one expression, and where in it.

    `severity` is `problem` for something that must be fixed and `notice` for something worth
    knowing. A rule naming a field that exists but that nothing fills yet is the second kind: it
    will simply be undetermined for every property until the feature that fills it arrives, and
    refusing to run the search would help nobody.
    """

    position: int
    message: str
    severity: Severity = "problem"


def _literal_type(value: object) -> ns.Type:
    if isinstance(value, bool):
        return ns.BOOLEAN
    if isinstance(value, int | float):
        return ns.NUMBER
    return ns.TEXT


class _Checker:
    def __init__(self) -> None:
        self.found: list[Complaint] = []

    def say(self, position: int, message: str, severity: Severity = "problem") -> None:
        self.found.append(Complaint(position, message, severity))

    def type_of(self, node: Node) -> ns.Type | None:
        """This node's type, or None when it is already broken enough not to say."""
        if isinstance(node, Literal):
            return _literal_type(node.value)

        if isinstance(node, Name):
            return self.name_type(node)

        if isinstance(node, ListOf):
            return self.list_type(node)

        if isinstance(node, IsNull):
            self.type_of(node.operand)
            return ns.BOOLEAN

        if isinstance(node, Not):
            self.expect(node.operand, ns.BOOLEAN, "`not`")
            return ns.BOOLEAN

        if isinstance(node, Both | Either):
            word = "`and`" if isinstance(node, Both) else "`or`"
            self.expect(node.left, ns.BOOLEAN, word)
            self.expect(node.right, ns.BOOLEAN, word)
            return ns.BOOLEAN

        if isinstance(node, Negate):
            self.expect(node.operand, ns.NUMBER, "`-`")
            return ns.NUMBER

        if isinstance(node, Arithmetic):
            self.expect(node.left, ns.NUMBER, f"`{node.operator}`")
            self.expect(node.right, ns.NUMBER, f"`{node.operator}`")
            return ns.NUMBER

        return self.comparison_type(node)

    def name_type(self, node: Name) -> ns.Type | None:
        field = ns.find(node.name)
        if field is None:
            self.say(
                node.position,
                f"there is no field called {node.name!r}. Available fields: "
                f"{', '.join(ns.names())}.",
            )
            return None
        # Two different reasons a real name might hold nothing, kept apart because they have
        # different fixes (AC-14): a feature that has not shipped, and one that has shipped but is
        # switched off here. Neither is a reason to refuse the rule, and saying either one about a
        # criterion that works is how somebody ends up deleting a criterion that works.
        if not field.populated:
            self.say(
                node.position,
                f"{node.name!r} is a real field, but nothing in this build fills it yet: it "
                f"arrives with {field.populated_by}. Until then this rule is undetermined for "
                "every property, which means it never drops or flags anything.",
                severity="notice",
            )
        elif (why := ns.unconfigured(node.name)) is not None:
            self.say(
                node.position,
                f"{node.name!r} is a real field and something fills it, but not here: {why}. "
                "Until that is set up this rule is undetermined for every property, which means it "
                "never drops or flags anything.",
                severity="notice",
            )
        return field.type

    def list_type(self, node: ListOf) -> ns.Type | None:
        if not node.items:
            self.say(node.position, "an empty list can never contain anything")
            return None
        kinds = [self.type_of(item) for item in node.items]
        first = next((kind for kind in kinds if kind is not None), None)
        if first is None:
            return None
        if any(kind is not None and kind != first for kind in kinds):
            self.say(node.position, "every item in a list has to be the same kind of thing")
            return None
        return ns.Type("list", first)

    def comparison_type(self, node: Comparison) -> ns.Type | None:
        left = self.type_of(node.left)
        right = self.type_of(node.right)

        if node.operator in ("in", "not in"):
            if right is not None and right.name != "list":
                self.say(node.position, f"`{node.operator}` wants a list on the right")
            elif right is not None and left is not None and right.item != left:
                self.say(
                    node.position,
                    f"this compares {left} against {right}, which can never match",
                )
            return ns.BOOLEAN

        if left is not None and right is not None and left != right:
            self.say(
                node.position,
                f"this compares {left} against {right}. A rule cannot compare one to the other.",
            )
        elif node.operator not in ("==", "!=") and left is not None and left.name != "number":
            self.say(
                node.position,
                f"`{node.operator}` orders numbers, and this asks it to order {left}",
            )
        return ns.BOOLEAN

    def expect(self, node: Node, wanted: ns.Type, where: str) -> None:
        found = self.type_of(node)
        if found is not None and found != wanted:
            self.say(node.position, f"{where} wants {wanted}, and this is {found}")


def check(node: Node) -> tuple[Complaint, ...]:
    """Everything wrong with one parsed expression, in one pass."""
    checker = _Checker()
    kind = checker.type_of(node)
    if kind is not None and kind != ns.BOOLEAN:
        checker.say(
            node.position,
            f"a rule has to ask a question with a yes or no answer, and this is {kind}",
        )
    return tuple(checker.found)
