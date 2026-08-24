"""Text in, tokens out, with a position on every one of them.

The first of three modules that between them turn a criterion somebody wrote into something this
tool can answer with. Nothing here imports anything that can run code, and that is checked
mechanically rather than trusted, because this is the one part of the product where a user's text
gets read at all.

Two decisions about the lexical grammar are worth stating rather than discovering:

**A number has no exponent.** `1e999` is a float literal that evaluates to infinity before anything
has had a chance to check its size, and infinity times anything is infinity, so a bound on magnitude
would arrive too late to matter. There is no honest criterion that needs one.

**A string has no escapes.** A backslash is a backslash and the string ends at the next matching
quote. The spec asks that characters meant to break out of a string be a parse failure or a literal,
never an escape; the simplest way to promise that is to have nothing to escape into.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: The longest expression this will read at all. Checked before anything else, so a pathological
#: input is refused rather than tokenized.
MAX_LENGTH = 1_000

#: The largest number an expression may contain, and the largest an arithmetic result may reach.
#: A thousand times the most expensive property ever sold, so nothing honest comes near it, and far
#: below the point where arbitrary-precision arithmetic starts costing real time.
MAX_MAGNITUDE = 10**15


class Kind(StrEnum):
    number = "number"
    text = "text"
    name = "name"
    keyword = "keyword"
    operator = "operator"
    punctuation = "punctuation"
    end = "end"


#: Words the grammar knows. A name that collides with one of these is that word, not a field.
KEYWORDS = frozenset({"and", "or", "not", "in", "is", "null", "true", "false"})

#: Longest first, so `==` is never read as two `=`.
OPERATORS = ("==", "!=", "<=", ">=", "<", ">", "+", "-", "*", "/")

PUNCTUATION = ("(", ")", "[", "]", ",")


class RuleSyntaxError(ValueError):
    """A criterion that cannot be read, and exactly where reading stopped.

    The position is a character offset from the start of the expression, which is what a person
    fixing it needs and what the file's own line number cannot give: a rule's expression is one
    string inside one line of YAML.
    """

    def __init__(self, position: int, message: str) -> None:
        self.position = position
        self.message = message
        super().__init__(f"at character {position + 1}: {message}")


@dataclass(frozen=True, slots=True)
class Token:
    kind: Kind
    text: str
    position: int

    def is_a(self, kind: Kind, text: str | None = None) -> bool:
        return self.kind is kind and (text is None or self.text == text)


def _number(source: str, start: int) -> tuple[Token, int]:
    at = start
    seen_dot = False
    while at < len(source):
        char = source[at]
        if char.isdigit():
            at += 1
            continue
        if char == "." and not seen_dot and at + 1 < len(source) and source[at + 1].isdigit():
            seen_dot = True
            at += 1
            continue
        break
    text = source[start:at]
    if at < len(source) and source[at] in "eE":
        raise RuleSyntaxError(
            at,
            "a number cannot have an exponent. Write the digits out, or use a smaller number.",
        )
    if at < len(source) and (source[at].isalpha() or source[at] == "_"):
        raise RuleSyntaxError(at, f"{source[start:at + 1]!r} is not a number")
    return Token(Kind.number, text, start), at


def _text(source: str, start: int) -> tuple[Token, int]:
    quote = source[start]
    end = source.find(quote, start + 1)
    if end == -1:
        raise RuleSyntaxError(start, "this text is never closed")
    return Token(Kind.text, source[start + 1 : end], start), end + 1


def _word(source: str, start: int) -> tuple[Token, int]:
    at = start
    while at < len(source) and (source[at].isalnum() or source[at] == "_"):
        at += 1
    word = source[start:at]
    kind = Kind.keyword if word in KEYWORDS else Kind.name
    return Token(kind, word, start), at


def tokenize(source: str) -> tuple[Token, ...]:
    """Every token in this expression, ending with one of kind `end`.

    The trailing `end` token is not tidiness: it gives the parser something with a position to
    complain about when an expression stops in the middle, instead of an index error.
    """
    if len(source) > MAX_LENGTH:
        raise RuleSyntaxError(
            MAX_LENGTH,
            f"this expression is {len(source)} characters, and the limit is {MAX_LENGTH}",
        )

    found: list[Token] = []
    at = 0
    while at < len(source):
        char = source[at]
        if char.isspace():
            at += 1
            continue
        if char.isdigit():
            token, at = _number(source, at)
            found.append(token)
            continue
        if char in "'\"":
            token, at = _text(source, at)
            found.append(token)
            continue
        if char.isalpha() or char == "_":
            token, at = _word(source, at)
            found.append(token)
            continue
        if char == ".":
            raise RuleSyntaxError(
                at, "a rule cannot reach inside a value with `.`; it may only name fields"
            )
        if char == "=" and not source.startswith("==", at):
            raise RuleSyntaxError(
                at, "a rule cannot assign. Did you mean `==`, which compares?"
            )
        matched = next((op for op in OPERATORS if source.startswith(op, at)), None)
        if matched is not None:
            found.append(Token(Kind.operator, matched, at))
            at += len(matched)
            continue
        if char in PUNCTUATION:
            found.append(Token(Kind.punctuation, char, at))
            at += 1
            continue
        raise RuleSyntaxError(at, f"{char!r} means nothing in a rule")

    found.append(Token(Kind.end, "", len(source)))
    return tuple(found)
