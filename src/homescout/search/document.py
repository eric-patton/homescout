"""The definition file itself: read it, say where anything in it is, and write it back unchanged.

A saved search is edited two ways, by hand in a text editor and by dragging a shape on a map, and
neither may destroy what the other did. That is a stronger requirement than "we can parse YAML": it
means comments, key order, quoting and number formatting all have to survive a load and a save
untouched, and only the key that was actually edited may move.

So this module parses in round-trip mode and keeps the parsed document, rather than converting to
plain dictionaries and re-emitting from scratch. The same choice pays for itself twice: the parsed
tree carries the line and column of every node, which is what lets a validation problem say
`searches/nm.yaml:14:7 areas[0].geometry` instead of "somewhere in your file".

What survives exactly: comments, key order, quoting style, number formatting including trailing
zeros, and whether lists are written flush with their key or indented under it. What is normalized,
once: layout inside a list, so a flow list hand-wrapped over several lines comes back on one. No
value changes, and what this tool writes is already in the normalized form, so a file it has saved
once is a fixed point.

A definition is data. The loader used here does not construct objects, so a tag asking for one is
reported as a problem in the file rather than imported and called. That is stated out loud, and
tested, because the difference between a safe loader and an unsafe one is one keyword in every YAML
library in wide use.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

#: Wide enough that nothing already in a file gets re-wrapped on the way out. Round-trip fidelity is
#: the requirement, and the default width would reflow a long description into two lines the first
#: time a person changed a price.
_WIDTH = 100_000


#: The tags a YAML document is allowed to carry. Everything here is data: a map, a list, a string,
#: a number. A tag outside this set is asking for something to be built, which a saved search never
#: does, so it is reported against its line rather than obeyed.
_KNOWN_TAGS = frozenset(
    f"tag:yaml.org,2002:{name}"
    for name in (
        "map", "omap", "seq", "set", "str", "int", "float", "bool", "null", "binary",
        "timestamp", "merge", "value",
    )
)


def _reader(sequence: int = 4, offset: int = 2) -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = _WIDTH
    yaml.indent(mapping=2, sequence=sequence, offset=offset)
    return yaml


def _sequence_indent(text: str) -> tuple[int, int]:
    """How this particular file indents its lists, so writing it back does not restyle it.

    Both common styles are in the wild (a list flush with its key, and a list indented under it) and
    a tool that silently converted one to the other would produce a diff touching every area in the
    file the first time somebody changed a price.
    """
    parent = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("- "):
            offset = max(indent - parent, 0)
            return (offset + 2, offset)
        if stripped.endswith(":"):
            parent = indent
    return (4, 2)


def _foreign_tags(text: str) -> tuple[tuple[str, int, int], ...]:
    """Every tag in the document that asks for something other than plain data."""
    try:
        root = _reader().compose(text)
    except YAMLError:
        return ()
    found: list[tuple[str, int, int]] = []

    def walk(node: Any) -> None:
        tag = str(getattr(node, "tag", ""))
        if tag and tag not in _KNOWN_TAGS:
            mark = node.start_mark
            found.append((tag, mark.line, mark.column))
        value = getattr(node, "value", None)
        if node.id == "scalar" or value is None:
            return
        for child in value:
            for part in child if isinstance(child, tuple) else (child,):
                walk(part)

    if root is not None:
        walk(root)
    return tuple(found)


class DocumentError(ValueError):
    """The file is not readable as a definition at all. Carries its own location."""

    def __init__(self, location: str, message: str) -> None:
        self.location = location
        self.message = message
        super().__init__(f"{location}: {message}")


class Document:
    """One definition file, parsed, with everything needed to write it back."""

    def __init__(
        self,
        path: Path,
        data: Any,
        *,
        style: tuple[int, int] = (4, 2),
        foreign: tuple[tuple[str, int, int], ...] = (),
        newline: str = "\n",
    ) -> None:
        self.path = path
        self.data = data
        self.style = style
        #: How this particular file ends its lines. Kept because a file written in Notepad ends
        #: them with a carriage return too, and rewriting the whole file to this tool's preference
        #: the first time somebody changes a price is exactly the diff AC-3 exists to prevent.
        self.newline = newline
        #: Tags found in the file that ask for something other than plain data, with their lines.
        #: Reported by validation; never acted on.
        self.foreign = foreign

    # -- reading -------------------------------------------------------------

    @classmethod
    def read(cls, path: Path) -> Document:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DocumentError(str(path), f"could not be read: {exc}") from None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentError(str(path), f"is not UTF-8 text: {exc}") from None
        # Read as bytes on purpose: `read_text` translates line endings on the way in, which is
        # exactly the fact this needs to know before it is lost.
        newline = "\r\n" if b"\r\n" in raw else "\n"
        return cls.parse(text.replace("\r\n", "\n"), path, newline=newline)

    @classmethod
    def parse(cls, text: str, path: Path, *, newline: str = "\n") -> Document:
        style = _sequence_indent(text)
        foreign = _foreign_tags(text)
        try:
            data = _reader(*style).load(text)
        except YAMLError as exc:
            raise DocumentError(_from_mark(path, exc), _tidy(exc)) from None
        if data is None:
            raise DocumentError(str(path), "the file is empty")
        if not isinstance(data, Mapping):
            raise DocumentError(
                str(path),
                f"expected a definition object with a name and areas, got {type(data).__name__}",
            )
        return cls(path, data, style=style, foreign=foreign, newline=newline)

    # -- locations -----------------------------------------------------------

    def at(self, *path: Any) -> str:
        """Where in the file this key is, as `file:line:column key.path`.

        Falls back to the deepest position it can prove. A key that was never written has no line of
        its own, so the location of its parent is the honest answer and is still enough to find.
        """
        node: Any = self.data
        line, column = 0, 0
        for step in path:
            found = _position(node, step)
            if found is not None:
                line, column = found
            node = _descend(node, step)
            if node is None:
                break
        trail = "".join(f"[{s}]" if isinstance(s, int) else f".{s}" for s in path).lstrip(".")
        where = f"{self.path.name}:{line + 1}:{column + 1}"
        return f"{where} {trail}" if trail else where

    # -- writing -------------------------------------------------------------

    def dumps(self) -> str:
        stream = io.StringIO()
        _reader(*self.style).dump(self.data, stream)
        return stream.getvalue()

    def write(self, path: Path | None = None) -> None:
        target = path or self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.dumps(), encoding="utf-8", newline=self.newline)

    def assign(self, path: Sequence[Any], value: Any) -> None:
        """Set one value, creating only the containers on the way to it.

        Deliberately surgical. Everything not on this path keeps its node, and therefore its
        comments, its quoting and its formatting, which is what makes an edit through the browser
        produce a difference confined to what was edited.
        """
        node: Any = self.data
        for step in path[:-1]:
            nxt = _descend(node, step)
            if nxt is None:
                nxt = {}
                node[step] = nxt
            node = nxt
        if _same(node, path[-1], value):
            # An assignment that changes nothing changes nothing, including the style it is
            # written in. The parsed nodes carry their own formatting, so replacing a list with an
            # equal list would rewrite it flush or wrapped according to this tool's taste rather
            # than the file's. The map surface saves the whole areas list on every save, so
            # without this, opening a search and pressing save restyles a list nobody edited.
            return
        node[path[-1]] = value

    def remove(self, path: Sequence[Any]) -> bool:
        """Take one key out, if it is there, and leave everything around it alone.

        The counterpart to `assign`, and it exists because a setting returning to its default should
        leave no trace: a search that was paused and resumed reads `paused: false` forever
        otherwise, which is two lines of nothing in a file somebody edits by hand. Missing is the
        same state as false here, so removing it says exactly as much and says it more quietly.
        """
        node: Any = self.data
        for step in path[:-1]:
            node = _descend(node, step)
            if node is None:
                return False
        if not isinstance(node, MutableMapping) or path[-1] not in node:
            return False
        del node[path[-1]]
        return True


def _same(node: Any, step: Any, value: Any) -> bool:
    """Is this key already exactly this value?

    The round-trip types compare equal to the plain ones they stand for, so a `CommentedSeq` of two
    maps equals the list of dicts that would replace it. That equality is what makes this safe:
    "equal" here means the document would say the same thing, not that the objects are the same.
    """
    held = _descend(node, step)
    if held is None:
        return False
    try:
        return bool(held == value)
    except Exception:  # noqa: BLE001 - a type that refuses comparison is simply not the same
        return False


def _descend(node: Any, step: Any) -> Any:
    if isinstance(step, int):
        if isinstance(node, Sequence) and not isinstance(node, str) and step < len(node):
            return node[step]
        return None
    if isinstance(node, Mapping):
        return node.get(step)
    return None


def _position(node: Any, step: Any) -> tuple[int, int] | None:
    where = getattr(node, "lc", None)
    if where is None:
        return None
    try:
        found = where.item(step) if isinstance(step, int) else where.key(step)
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return (found[0], found[1]) if found else None


def _from_mark(path: Path, exc: YAMLError) -> str:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None:
        return path.name
    return f"{path.name}:{mark.line + 1}:{mark.column + 1}"


def _tidy(exc: YAMLError) -> str:
    """The library's complaint, in one line, with the unsafe-tag case named for what it is."""
    problem = str(getattr(exc, "problem", "") or "").strip()
    text = problem or " ".join(str(exc).split())
    if "constructor" in text or "tag" in text:
        return (
            f"{text}. A saved search is data: nothing in it is executed, so a tag asking for an "
            "object to be built is refused rather than obeyed."
        )
    return text
