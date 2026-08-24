"""Which columns appear, as configuration rather than as code.

`default` is built in and is not a file. It is a promise about a document somebody has been keeping
by hand for months, and a promise that lives in an editable file is one that changes when somebody
tidies up.

Everything else is a file, `<root>/templates/<name>.yaml`, holding nothing but a list of column
names. That is the whole of AC-7: a sheet for a different purpose is a settings change, and nothing
in this package has to be touched to make one.

A template is checked when it is **loaded**, not when a cell is written. A name that is not a column
is refused before a single row is built, with the message naming it and listing what exists, because
finding out about a typo after five thousand rows have been assembled helps nobody.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..errors import InvalidInput
from . import columns as cols

#: What a template may be called. The same narrow shape a saved search's name has, and for the same
#: reason: this becomes a file name, and a name that can contain a separator can read outside the
#: directory it belongs to.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

DIRECTORY = "templates"
DEFAULT_NAME = "default"


class UnknownTemplate(InvalidInput):
    def __init__(self, name: str, directory: Path) -> None:
        super().__init__(
            f"There is no export template called {name!r}. `default` is built in; anything else is "
            f"a file at {directory / (name + '.yaml')}."
        )


class BadTemplate(InvalidInput):
    """A template that exists and cannot be used. Named, with what is wrong and what exists."""


@dataclass(frozen=True, slots=True)
class Template:
    """A named column set, already checked against what exists."""

    name: str
    columns: tuple[cols.Column, ...]

    @property
    def headers(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


def _resolve(names: Sequence[str], where: str) -> tuple[cols.Column, ...]:
    """Column names to columns, or a refusal naming the first one that is not."""
    if not names:
        raise BadTemplate(f"{where} names no columns, so it would produce an empty sheet.")
    made: list[cols.Column] = []
    for name in names:
        if not isinstance(name, str):
            raise BadTemplate(f"{where} lists {name!r}, which is not a column name.")
        found = cols.find(name.strip())
        if found is None:
            raise BadTemplate(
                f"{where} names a column that does not exist: {name!r}. "
                f"Available columns: {', '.join(cols.names())}."
            )
        made.append(found)
    return tuple(made)


def default() -> Template:
    """The hand-built consolidated sheet, exactly, in order."""
    return Template(DEFAULT_NAME, _resolve(cols.DEFAULT, "the default template"))


def safe_path(root: Path, name: str) -> Path:
    """The file this template name means, or a refusal.

    Both halves, the same way saved searches do it: the pattern rejects the obvious, and the
    containment check rejects what a pattern cannot see.
    """
    if not NAME.match(name or ""):
        raise InvalidInput(
            f"{name!r} is not a usable name for an export template. Use letters, digits, dashes, "
            "underscores and dots, up to sixty-four characters. The name becomes a file name."
        )
    directory = root / DIRECTORY
    resolved = (directory / f"{name}.yaml").resolve()
    if directory.resolve() != resolved.parent:
        raise InvalidInput(f"{name!r} would be read from outside the templates directory.")
    return directory / f"{name}.yaml"


def load(root: Path, name: str | None = None) -> Template:
    """The named template, or the built-in default."""
    wanted = (name or DEFAULT_NAME).strip()
    if wanted == DEFAULT_NAME:
        return default()

    path = safe_path(root, wanted)
    if not path.exists():
        raise UnknownTemplate(wanted, root / DIRECTORY)

    from ..search.document import Document, DocumentError

    try:
        document = Document.read(path)
    except DocumentError as exc:
        raise BadTemplate(f"{path.name} could not be read: {exc.message}") from None
    if not isinstance(document.data, dict):
        raise BadTemplate(f"{path.name} has to be an object with a `columns:` list in it.")

    listed = document.data.get("columns")
    if listed is None:
        raise BadTemplate(f"{path.name} has no `columns:` list, which is all a template is.")
    if isinstance(listed, str) or not isinstance(listed, Sequence):
        raise BadTemplate(f"{path.name}'s `columns:` has to be a list of column names.")

    unknown = [key for key in document.data if key != "columns"]
    if unknown:
        raise BadTemplate(
            f"{path.name} has keys that are not part of a template: "
            f"{', '.join(map(str, unknown))}. "
            "A template is one list, called `columns`."
        )
    return Template(wanted, _resolve(list(listed), path.name))


def available(root: Path) -> tuple[str, ...]:
    """Every template that can be asked for, the built-in one first."""
    directory = root / DIRECTORY
    found = sorted(p.stem for p in directory.glob("*.yaml")) if directory.is_dir() else []
    return (DEFAULT_NAME, *(name for name in found if name != DEFAULT_NAME))
