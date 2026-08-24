"""One saved search, read from a file, and the directory of them.

This is where the pieces meet: the document (round-trip YAML with line numbers), the areas (coarse
forms out, three-valued containment back), and the validation (everything wrong, in one pass). What
comes out satisfies the contract in this package's `__init__`, which is all the run loop knows.

Two things here are deliberate rather than incidental.

**A name is not a path.** It arrives from a command line today and a browser form tomorrow, and it
is turned into a file name. So it is checked against a narrow shape and the resolved path is checked
to still be inside the searches directory, before the file system is touched at all.

**A file that cannot be parsed still loads.** It comes back as a definition whose only content is
the problem, so `searches validate` can report it with its line and `run` can refuse it, rather than
an exception escaping from somewhere with no name attached.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..errors import InvalidInput
from ..records import ListingFields
from ..sources.base import Capabilities, SearchQuery
from . import (
    InvalidSearch,
    Placement,
    SearchProblem,
    UnknownSearch,
    blocking,
)
from .areas import SearchArea
from .document import Document, DocumentError
from .validate import Reading, examine

#: What a saved search may be called. Narrow on purpose: this becomes a file name, and a name that
#: can contain a separator or a parent reference is a name that can read and write outside the
#: directory it belongs to.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

SUFFIXES = (".yaml", ".yml")

TEMPLATE = """\
name: {name}
description: What this search is for, in your own words

# A property qualifies if it falls inside any area and inside none of the exclusions.
# Types: polygon (GeoJSON), city, county, zip, state, radius.
areas:
  - {{type: county, value: "Roosevelt County, NM"}}

# A drawn shape is GeoJSON, longitude first, and keeps whatever name you gave it:
# exclude_areas:
#   - type: polygon
#     name: east-side
#     geometry:
#       type: Polygon
#       coordinates: [[[-103.3, 34.1], [-103.2, 34.1], [-103.2, 34.2],
#                     [-103.3, 34.2], [-103.3, 34.1]]]

filters:
  price: {{min: 100000, max: 500000}}
  # beds: {{min: 3}}
  # baths: {{min: 2}}
  # sqft: {{min: 1500}}
  # lot_acres: {{min: 1}}
  # year_built: {{min: 1980}}
  # property_type: [single_family, farm]
  # listing_type: [for_sale]
  # Freshness is measured from when this tool first saw a property, never from a source's own
  # field, and it never removes anything from a run. It narrows what you are shown.
  # listed_within_days: 30

sources: [realtor]

rules: []

export:
  template: default
"""


def safe_path(directory: Path, name: str) -> Path:
    """The file this name means, or a refusal.

    Both halves matter. The pattern rejects the obvious (`../../etc/passwd`), and the containment
    check rejects what a pattern cannot see, such as a directory that is itself a link somewhere
    else.
    """
    if not NAME.match(name or ""):
        raise InvalidInput(
            f"{name!r} is not a usable name for a saved search. Use letters, digits, dashes, "
            "underscores and dots, up to sixty-four characters. The name becomes a file name."
        )
    resolved = (directory / f"{name}.yaml").resolve()
    root = directory.resolve()
    if root != resolved.parent:
        raise InvalidInput(f"{name!r} would be written outside the searches directory.")
    return directory / f"{name}.yaml"


def _known_sources() -> tuple[str, ...]:
    from ..sources import registered

    return tuple(registered())


class FileSearch:
    """One definition, as read from one file."""

    def __init__(self, document: Document | None, reading: Reading, path: Path) -> None:
        self.document = document
        self.reading = reading
        self.path = path
        self.name = reading.name or path.stem
        self.sources = reading.sources
        self.description = reading.description
        self.areas: tuple[SearchArea, ...] = tuple(a for a in reading.areas if not a.excluded)
        self.exclusions: tuple[SearchArea, ...] = tuple(a for a in reading.areas if a.excluded)
        self.freshness_days = reading.freshness_days
        self.export_template = reading.export_template
        #: Parsed once, when the file is read, so a run never re-reads the grammar per property.
        self.rules = reading.rules
        #: Whether this search asks for the optional model extraction pass. Off unless the file
        #: turned it on, and off is what makes the whole tool work with no model configured.
        self.model_extraction = reading.model_extraction

    # -- the contract --------------------------------------------------------

    def problems(self) -> tuple[SearchProblem, ...]:
        return tuple(
            SearchProblem(location=location, message=message, severity=severity)  # type: ignore[arg-type]
            for location, message, severity in self.reading.found
        )

    def queries_for(self, capabilities: Capabilities) -> tuple[SearchQuery, ...]:
        """One coarse query per area this source can express, per listing status asked for.

        The status fans out rather than being folded into one query because a source takes one
        status at a time and this tool never applies a status locally: a property whose status just
        changed is the most interesting thing a run can find, so it may shape what is asked for and
        must not hide what comes back.
        """
        made: list[SearchQuery] = []
        for area in self.areas:
            for coarse in area.coarse_for(capabilities):
                for status in self.reading.statuses:
                    made.append(
                        SearchQuery(area=coarse, listing_status=status, **self.reading.filters)
                    )
        return tuple(made)

    def place(self, fields: ListingFields) -> Placement:
        """Inside any area, inside no exclusion, and honest when it cannot tell.

        An exclusion only excludes on positive evidence. One that cannot be evaluated does not
        remove a property, for the same reason a filter never removes a property whose value is
        absent: a test that could not be run is not a test that failed.
        """
        unknown = False
        inside = False
        for area in self.exclusions:
            verdict = area.holds(fields)
            if verdict == "inside":
                return Placement.outside
            unknown = unknown or verdict == "unknown"
        for area in self.areas:
            verdict = area.holds(fields)
            if verdict == "inside":
                inside = True
                break
            unknown = unknown or verdict == "unknown"
        if inside:
            return Placement.inside
        return Placement.unlocatable if unknown else Placement.outside

    # -- freshness -----------------------------------------------------------

    def fresh_enough(self, first_observed_at: str | None, *, now: datetime | None = None) -> bool:
        """Is this property new enough for this search, by this tool's own reckoning?

        Asked when results are read, never during a run. A run that dropped a property for being old
        would stop recording it, and the store reads a property that stopped being recorded as one
        that may have sold. Freshness narrows what you are shown; it never narrows history.
        """
        if self.freshness_days is None:
            return True
        if not first_observed_at:
            return True
        moment = _moment(first_observed_at)
        if moment is None:
            return True
        age = (now or datetime.now(UTC)) - moment
        return age.days < self.freshness_days


def _moment(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _stamp(path: Path) -> tuple[int, int]:
    """What a file looks like from outside: when it changed, and how big it is.

    A hand edit while a browser is running changes both, so a held definition is dropped rather
    than served stale. Two edits inside one clock tick that left the size identical would not be
    noticed, which is a fair trade for not re-preparing every shape on every page view.
    """
    found = path.stat()
    return (found.st_mtime_ns, found.st_size)


def _broken(path: Path, exc: DocumentError) -> FileSearch:
    reading = Reading(name=path.stem)
    reading.say(exc.location, exc.message)
    return FileSearch(None, reading, path)


class FileCatalog:
    """The `searches/` directory beside the database: one file per saved search."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        #: One definition per file, for as long as the file is untouched. Loading is cheap; what is
        #: not cheap is what a loaded definition holds, which is a prepared geometry and whatever a
        #: boundary provider was asked. A run of every saved search, or a browser serving a page,
        #: loads the same definition several times, and each fresh load would ask again.
        self._loaded: dict[Path, tuple[tuple[int, int], FileSearch]] = {}

    def names(self) -> tuple[str, ...]:
        """Every saved search on this machine.

        A directory that does not exist means none, which is the right answer for a fresh install
        and not an error to report at every command.
        """
        if not self.directory.is_dir():
            return ()
        found = {
            path.stem
            for path in self.directory.iterdir()
            if path.suffix in SUFFIXES and path.is_file()
        }
        return tuple(sorted(found))

    def _path(self, name: str) -> Path:
        path = safe_path(self.directory, name)
        if path.exists():
            return path
        for suffix in SUFFIXES:
            other = path.with_suffix(suffix)
            if other.exists():
                return other
        return path

    def load(self, name: str) -> FileSearch:
        path = self._path(name)
        if not path.is_file():
            raise UnknownSearch(name, self.names())
        stamp = _stamp(path)
        held = self._loaded.get(path)
        if held is not None and held[0] == stamp:
            return held[1]
        try:
            document = Document.read(path)
        except DocumentError as exc:
            return _broken(path, exc)
        definition = FileSearch(document, examine(document, known_sources=_known_sources()), path)
        self._loaded[path] = (stamp, definition)
        return definition

    def create(self, name: str) -> FileSearch:
        path = safe_path(self.directory, name)
        if path.exists() or self._path(name).exists():
            raise InvalidInput(f"A saved search named {name!r} already exists.")
        self.directory.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE.format(name=name), encoding="utf-8", newline="\n")
        return self.load(name)

    def edit(self, name: str, changes: Mapping[str, object]) -> FileSearch:
        """Change named keys and write the file back, touching nothing else.

        Keys are dotted paths into the definition (`filters.price.max`), and values are read as YAML
        so that a number stays a number and a list stays a list. The file is only written when what
        results is valid, so a slip at the command line cannot leave a definition that will not run.
        """
        definition = self.load(name)
        document = definition.document
        if document is None:
            raise InvalidSearch(name, definition.problems())
        if not changes:
            return definition

        for key, value in changes.items():
            path = _key_path(key)
            document.assign(path, _value(value))

        reading = examine(document, known_sources=_known_sources())
        stopping = blocking(
            SearchProblem(location=where, message=message, severity=severity)  # type: ignore[arg-type]
            for where, message, severity in reading.found
        )
        if stopping:
            raise InvalidSearch(name, stopping)
        document.write()
        return self.load(name)


def _key_path(key: str) -> tuple[Any, ...]:
    steps: list[Any] = []
    for step in key.split("."):
        if not step:
            raise InvalidInput(f"{key!r} is not a key in a saved search.")
        steps.append(int(step) if step.isdigit() else step)
    return tuple(steps)


def _value(raw: object) -> Any:
    """A value from the command line, read the way the file would read it.

    `--set filters.price.max=800000` has to become a number, and `--set sources=[realtor]` a list,
    or an edit would quietly turn typed values into strings the next run cannot use.
    """
    if not isinstance(raw, str):
        return raw
    from .document import _reader

    try:
        return _reader().load(raw)
    except Exception:  # noqa: BLE001 - anything unreadable is simply the text as typed
        return raw


def build(directory: Path) -> FileCatalog:
    return FileCatalog(directory)


__all__ = ["TEMPLATE", "FileCatalog", "FileSearch", "build", "safe_path"]
