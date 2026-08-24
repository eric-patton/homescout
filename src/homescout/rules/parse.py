"""The grammar, by recursive descent, with its bounds checked as it goes.

The whole language, in the order the parser reads it:

    expression  := disjunction
    disjunction := conjunction ( "or" conjunction )*
    conjunction := negation ( "and" negation )*
    negation    := "not" negation | comparison
    comparison  := sum ( ("=="|"!="|"<"|"<="|">"|">=") sum
                       | ("in" | "not in") sum
                       | "is" "null" | "is" "not" "null" )?
    sum         := product ( ("+"|"-") product )*
    product     := unary ( ("*"|"/") unary )*
    unary       := "-" unary | primary
    primary     := NUMBER | TEXT | "true" | "false" | NAME | "(" expression ")" | list
    list        := "[" ( expression ( "," expression )* )? "]"

There is no rule that produces a call, an attribute, a subscript or an assignment, which is what
makes the safety claim a property of the grammar rather than of a filter someone has to maintain.
Where one of those would have gone, the parser reports what the language does not have, because
"unexpected `(`" sends a person looking for a typo they did not make.

Three bounds are enforced while descending rather than afterwards. Length is checked before
tokenizing; depth is counted on the way down, so a deeply nested expression is refused before it can
exhaust this interpreter's own stack; node count is tallied as nodes are built.
"""

from __future__ import annotations

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
from .tokens import MAX_MAGNITUDE, Kind, RuleSyntaxError, Token, tokenize

#: How deeply an expression may nest. Thirty-two is far past any criterion a person writes, and far
#: below the recursion limit this parser is itself running under.
MAX_DEPTH = 32

#: How many pieces an expression may have. A guard against a long flat expression, which nesting
#: bounds do not catch.
MAX_NODES = 200

COMPARISONS = ("==", "!=", "<", "<=", ">", ">=")


class Parser:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self.tokens = tokens
        self.at = 0
        self.depth = 0
        self.nodes = 0

    # -- reading tokens ------------------------------------------------------

    @property
    def here(self) -> Token:
        return self.tokens[self.at]

    def take(self) -> Token:
        token = self.tokens[self.at]
        self.at += 1
        return token

    def accept(self, kind: Kind, text: str) -> bool:
        if self.here.is_a(kind, text):
            self.at += 1
            return True
        return False

    def expect(self, kind: Kind, text: str, what: str) -> Token:
        if not self.here.is_a(kind, text):
            raise RuleSyntaxError(self.here.position, f"expected {what}")
        return self.take()

    def counted(self, node: Node) -> Node:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise RuleSyntaxError(
                self.here.position,
                f"this expression has more than {MAX_NODES} pieces, which is past what a rule is",
            )
        return node

    # -- the grammar ---------------------------------------------------------

    def expression(self) -> Node:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise RuleSyntaxError(
                self.here.position,
                f"this expression nests more than {MAX_DEPTH} deep, which is past what a rule is",
            )
        try:
            return self.disjunction()
        finally:
            self.depth -= 1

    def disjunction(self) -> Node:
        left = self.conjunction()
        while self.here.is_a(Kind.keyword, "or"):
            position = self.take().position
            left = self.counted(Either(left, self.conjunction(), position))
        return left

    def conjunction(self) -> Node:
        left = self.negation()
        while self.here.is_a(Kind.keyword, "and"):
            position = self.take().position
            left = self.counted(Both(left, self.negation(), position))
        return left

    def negation(self) -> Node:
        if self.here.is_a(Kind.keyword, "not"):
            position = self.take().position
            return self.counted(Not(self.negation(), position))
        return self.comparison()

    def comparison(self) -> Node:
        left = self.sum()

        if self.here.is_a(Kind.keyword, "is"):
            position = self.take().position
            negated = self.accept(Kind.keyword, "not")
            self.expect(Kind.keyword, "null", "`null` after `is`")
            node = self.counted(IsNull(left, negated, position))
            self._refuse_chain()
            return node

        if self.here.is_a(Kind.keyword, "in") or (
            self.here.is_a(Kind.keyword, "not")
            and self.tokens[self.at + 1].is_a(Kind.keyword, "in")
        ):
            negated = self.accept(Kind.keyword, "not")
            position = self.take().position
            node = self.counted(
                Comparison("not in" if negated else "in", left, self.sum(), position)
            )
            self._refuse_chain()
            return node

        if self.here.kind is Kind.operator and self.here.text in COMPARISONS:
            token = self.take()
            node = self.counted(Comparison(token.text, left, self.sum(), token.position))
            self._refuse_chain()
            return node

        return left

    def _refuse_chain(self) -> None:
        """`a < b < c` reads as a question about three things and answers about two."""
        if (self.here.kind is Kind.operator and self.here.text in COMPARISONS) or self.here.is_a(
            Kind.keyword, "in"
        ):
            raise RuleSyntaxError(
                self.here.position,
                "comparisons do not chain in a rule. Write it as two comparisons joined by `and`.",
            )

    def sum(self) -> Node:
        left = self.product()
        while self.here.kind is Kind.operator and self.here.text in ("+", "-"):
            token = self.take()
            left = self.counted(Arithmetic(token.text, left, self.product(), token.position))
        return left

    def product(self) -> Node:
        left = self.unary()
        while self.here.kind is Kind.operator and self.here.text in ("*", "/"):
            token = self.take()
            left = self.counted(Arithmetic(token.text, left, self.unary(), token.position))
        return left

    def unary(self) -> Node:
        if self.here.is_a(Kind.operator, "-"):
            position = self.take().position
            return self.counted(Negate(self.unary(), position))
        return self.primary()

    def primary(self) -> Node:
        token = self.here

        if token.kind is Kind.number:
            self.take()
            value: object = float(token.text) if "." in token.text else int(token.text)
            if abs(float(value)) > MAX_MAGNITUDE:
                raise RuleSyntaxError(
                    token.position,
                    f"{token.text} is larger than {MAX_MAGNITUDE:,}, which is past any number a "
                    "property carries",
                )
            return self.counted(self._after(Literal(value, token.position)))

        if token.kind is Kind.text:
            self.take()
            return self.counted(self._after(Literal(token.text, token.position)))

        if token.is_a(Kind.keyword, "true") or token.is_a(Kind.keyword, "false"):
            self.take()
            return self.counted(self._after(Literal(token.text == "true", token.position)))

        if token.kind is Kind.name:
            self.take()
            return self.counted(self._after(Name(token.text, token.position)))

        if token.is_a(Kind.punctuation, "("):
            self.take()
            inside = self.expression()
            self.expect(Kind.punctuation, ")", "a closing `)`")
            return self._after(inside)

        if token.is_a(Kind.punctuation, "["):
            return self.counted(self._after(self.list_of()))

        if token.kind is Kind.end:
            raise RuleSyntaxError(token.position, "this expression stops in the middle")

        raise RuleSyntaxError(token.position, f"{token.text!r} cannot start a value")

    def list_of(self) -> Node:
        position = self.expect(Kind.punctuation, "[", "a list").position
        items: list[Node] = []
        if not self.here.is_a(Kind.punctuation, "]"):
            items.append(self.expression())
            while self.accept(Kind.punctuation, ","):
                items.append(self.expression())
        self.expect(Kind.punctuation, "]", "a closing `]`")
        return ListOf(tuple(items), position)

    def _after(self, node: Node) -> Node:
        """What follows a value, when what follows it is something the language does not have.

        Each of these is a construct somebody could reasonably expect to work, and each one is a way
        out of the namespace if it did. Naming them is worth more than a position and a shrug.
        """
        token = self.here
        if token.is_a(Kind.punctuation, "("):
            raise RuleSyntaxError(
                token.position,
                "a rule cannot call a function. A rule compares fields and values, nothing else.",
            )
        if token.is_a(Kind.punctuation, "["):
            raise RuleSyntaxError(
                token.position,
                "a rule cannot index into a value. Name the field you mean.",
            )
        return node


def parse(source: str) -> Node:
    """One expression, or a failure naming where reading stopped and why."""
    parser = Parser(tokenize(source))
    node = parser.expression()
    if parser.here.kind is not Kind.end:
        raise RuleSyntaxError(
            parser.here.position, f"{parser.here.text!r} was not expected here"
        )
    return node
