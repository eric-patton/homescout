"""The claim that a criterion cannot become code, checked rather than asserted.

The constitution says no `eval`, and the spec says no general-purpose interpreter, dynamic
evaluation facility, or code-compilation facility anywhere in the evaluation path, verified by
inspection as well as by test. This file is that inspection, written as a test so it runs on every
change rather than on every code review that happens to look.

It is deliberately blunt: it reads the source of the modules a user's text passes through and fails
if any of them so much as names one of the dangerous facilities. A cleverer check that understood
context could be argued with. This one cannot.

This whole file is the test for feat-008/NFR-security.
"""

from __future__ import annotations

import pathlib

import pytest

from homescout.rules import check, evaluate, namespace, parse, syntax, tokens
from homescout.rules.parse import parse as parse_expression
from homescout.rules.tokens import RuleSyntaxError

#: Every module a user's text passes through, from the characters they typed to the verdict.
THE_PATH = (tokens, syntax, parse, namespace, check, evaluate)

#: Anything that turns text into behavior, reaches an attribute by name, or touches the world.
FORBIDDEN = (
    "eval",
    "exec",
    "compile",
    "__import__",
    "importlib",
    "ast",
    "getattr",
    "setattr",
    "globals",
    "locals",
    "vars",
    "open",
    "input",
    "subprocess",
    "socket",
    "pathlib",
    "sqlite3",
    "pickle",
    "marshal",
    "os",
    "sys",
    "builtins",
)


def _names_in(module) -> set[str]:
    """Every identifier a module's code actually uses, prose excluded.

    Read with Python's own tokenizer rather than by searching the text, because searching the text
    finds `eval` inside the word "evaluation" and would fail this file's own subject matter. The
    tokenizer is used here, in a test, and not anywhere a criterion travels.
    """
    import tokenize

    with tokenize.open(module.__file__) as source:
        return {
            token.string
            for token in tokenize.generate_tokens(source.readline)
            if token.type == tokenize.NAME
        }


@pytest.mark.parametrize("module", THE_PATH, ids=[m.__name__.rsplit(".", 1)[-1] for m in THE_PATH])
def test_no_module_in_the_evaluation_path_names_a_way_to_run_code(module) -> None:
    """feat-008/AC-16, feat-008/AC-19: verified by inspection, mechanically, every time.

    This is why the parser here is written by hand rather than borrowed from Python's own.
    `ast.parse` is `compile` with a flag, and a module that called it could not pass this test: a
    reviewer would have to be argued out of what they can plainly see in the source.
    """
    used = _names_in(module)

    for word in FORBIDDEN:
        assert word not in used, f"{module.__name__} names {word!r}"


def test_the_path_imports_nothing_that_can_reach_the_world() -> None:
    """feat-008/AC-19: evaluating a rule cannot read a file or open a connection.

    Checked at the import line rather than at the call, because a module that cannot import the
    filesystem cannot use it however it is called.
    """
    allowed = {"__future__", "collections.abc", "dataclasses", "enum", "typing"}
    for module in THE_PATH:
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if not line.startswith(("import ", "from ")):
                continue
            named = line.split()[1]
            assert named in allowed or named.startswith("."), (
                f"{module.__name__} imports {named}, which is outside the evaluation path"
            )


ESCAPES = [
    "__import__('os').system('echo pwned')",
    "open('/etc/passwd').read() == 'x'",
    "().__class__.__bases__[0] == 1",
    "price.__class__ == 1",
    "eval('1+1') > 0",
    "[x for x in [1]] == [1]",
    "lambda: 1",
    "price := 5",
    "f'{price}' == 'x'",
    "exec('x=1')",
    "globals()['price'] > 1",
    "price if price else 1",
]


@pytest.mark.parametrize("attempt", ESCAPES)
def test_nothing_that_looks_like_an_escape_parses_at_all(attempt: str) -> None:
    """feat-008/AC-17: every one of these is Python, and none of them is this language.

    They fail at parse time, not at evaluation time, because the grammar has no rule that could
    produce any of them. That is stronger than rejecting them: there is nothing here to reject.
    """
    with pytest.raises(RuleSyntaxError):
        parse_expression(attempt)


def test_a_nested_doubling_answers_in_no_time_at_all() -> None:
    """feat-008/AC-19: the denial of service that bounded size and depth do not prevent.

    `(x*x)*(x*x)` squares the digit count at every level, and Python's integers are arbitrary
    precision, so the question is how far a criterion can push that. This builds the worst nested
    doubling that fits inside the length bound, which is what an expression can actually reach, and
    asserts it is answered rather than computed.
    """
    import time

    from homescout.rules.evaluate import verdict
    from homescout.rules.tokens import MAX_LENGTH

    expression = "price"
    while len(f"({expression}*{expression})") <= MAX_LENGTH - 10:
        expression = f"({expression}*{expression})"

    started = time.perf_counter()
    found, _ = verdict(parse_expression(f"{expression} > 0"), {"price": 999_999})
    took = time.perf_counter() - started

    assert found == "undetermined", "arithmetic past the bound answers unknown"
    assert took < 0.1, f"a doubling expression took {took:.3f}s"


def test_a_rule_cannot_reach_a_field_that_was_deliberately_withheld() -> None:
    """feat-008/AC-16: the namespace is the only door, and it is a list somebody wrote."""
    with pytest.raises(RuleSyntaxError):
        parse_expression("price.__dict__ is not null")

    from homescout.rules.check import check as check_expression

    found = check_expression(parse_expression("days_on_market_source > 1"))
    assert [c.severity for c in found] == ["problem"]
