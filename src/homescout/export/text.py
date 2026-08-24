"""Three guards on every piece of text that reaches a cell, and none of them optional.

All three came out of probing the library rather than out of caution, and all three are cases where
its default behaviour is the wrong one for text that came off the web:

- **A string beginning with `=` is recorded as a formula.** That is `openpyxl`'s default, not an
  edge case, so a listing description beginning `=cmd|'/c calc'!A1` would arrive in somebody's
  spreadsheet as something to run. The requirement is that no cell is written in a form a
  spreadsheet application will evaluate, so **every** text cell has its type forced rather than the
  ones somebody thought to check.
- **A cell longer than the format allows is truncated in silence.** Forty thousand characters go in
  and 32,767 come back with no error. The spec asks for truncation with the truncation visible, so
  it happens here, first, with a marker.
- **A single control character raises and kills the export.** One bad byte in one listing would cost
  the whole workbook, so they are removed before anything is written.

The comma-separated format has no cell types, so its only guard is the leading apostrophe a
spreadsheet application reads as "this is text". That is the one place the two formats hold
different bytes, and it is a recorded decision rather than an accident.
"""

from __future__ import annotations

import re

#: What one cell may hold. The format's own limit, and the library truncates past it without saying.
CELL_LIMIT = 32_767

#: What a truncated cell ends with, so the cut is visible rather than a sentence that stops.
TRUNCATION_MARK = " [truncated]"

#: Characters XML cannot carry, which is what the library refuses. Tab, newline and carriage return
#: are deliberately absent: they are legal, they occur in real notes, and removing them would lose
#: the shape of something somebody wrote.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

#: What a spreadsheet application treats as the start of an expression. Leading whitespace is
#: stripped before this is consulted, which is what covers the tab and carriage-return variants that
#: some importers let through.
FORMULA_STARTS = ("=", "+", "-", "@")


def clean(value: str) -> str:
    """Text with nothing in it that would refuse to be written."""
    return _CONTROL.sub("", value)


def bounded(value: str, limit: int = CELL_LIMIT) -> str:
    """Text that fits, cut visibly rather than silently.

    The marker is inside the limit rather than added past it, which is the whole point: a cut that
    pushes the value back over the line is a cut the library then makes again, invisibly.
    """
    if len(value) <= limit:
        return value
    return value[: limit - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def for_cell(value: object) -> object:
    """One value on its way into a spreadsheet cell.

    Numbers pass through as numbers, so they can be sorted and summed. Everything else becomes
    cleaned, bounded text, and the caller forces the cell's type afterwards.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # Before the number check, because a bool is an int in Python and a column of TRUE and FALSE
        # reads as a bug rather than as an answer.
        return "yes" if value else "no"
    if isinstance(value, int | float):
        return value
    return bounded(clean(str(value)))


def looks_like_a_formula(value: str) -> bool:
    """Would a spreadsheet application try to evaluate this?

    The first **non-whitespace** character, not the first character. A leading space or tab
    does not stop the evaluation, and checking only position zero is how the guard gets walked
    around.
    """
    stripped = value.lstrip()
    return bool(stripped) and stripped[0] in FORMULA_STARTS


def for_delimited(value: object) -> str:
    """One value on its way into a comma-separated file.

    Where a spreadsheet cell carries a type, this carries an apostrophe, because that is the only
    thing a text file has to say "read what follows as text". It changes the bytes by one character
    for a value that begins with an expression character, which is the recorded difference between
    the two formats, and it fires for none of the real listing descriptions this project has
    measured.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int | float):
        return str(value)
    text = bounded(clean(str(value)))
    return f"'{text}" if looks_like_a_formula(text) else text
