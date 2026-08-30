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

import os
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

#: Where a deleted definition goes. A directory rather than an unlink, because `names()` already
#: ignores anything that is not a file directly in the searches folder, so moving one here takes it
#: out of the catalogue completely while leaving it on disk to be brought back or read.
DELETED = "deleted"

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
        self.model_assessment = reading.model_assessment
        #: What this search wants the model told about how listings in its market are written.
        #: Empty unless somebody wrote one, and written by a person rather than by any code path.
        self.extract_notes = reading.extract_notes
        #: Skipped by a run of everything. Still run when asked for by name.
        self.paused = reading.paused
        #: Put away: not listed by default, and skipped by a run of everything. Never deleted.
        self.archived = reading.archived

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


#: Keys whose default is the same state as being absent, so an edit that sets one back to its
#: default takes the key out instead of writing it. Only for keys where that is genuinely true:
#: a filter set to its widest value is not the same as no filter, and is not listed here.
#: Keys whose value is somebody's writing rather than data, taken exactly as typed. A note reading
#: "Community water: a mutual domestic association" is a sentence, and YAML cannot tell it from a
#: mapping. Everything else is still read the way the file would read it, so a price stays a number.
PROSE: frozenset[str] = frozenset({"description", "extract.notes"})

DEFAULTS_OUT: dict[str, Any] = {
    "paused": False,
    "archived": False,
    "exclude_areas": [],
    #: An emptied note is a removed key rather than an empty string, so "no note" is one state in
    #: the file as well as one state in the code.
    "extract.notes": "",
}


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
        return self._read(path)

    def _read(self, path: Path) -> FileSearch:
        """One definition from one file, cached against that file's own stamp.

        Split out of `load` because a deleted definition is a real definition in a file this
        catalogue is not otherwise looking at, and reading one should not mean a second copy of the
        parse-cache-or-report-the-breakage dance. Keyed by path, so a definition in the deleted
        folder and a live one of the same name are two entries and cannot be confused for each
        other.
        """
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

    def duplicate(self, name: str, new_name: str) -> FileSearch:
        """Copy one definition under a new name.

        The bytes, not a re-serialization: a duplicate that lost the original's comments and its
        ordering would be a different file that happens to run the same, and the comments are
        usually the part explaining why an area is shaped the way it is.

        The `name:` key is the one thing rewritten, because a definition whose name disagrees with
        its file name is a definition one of the two ways of finding it cannot see.
        """
        source = self._path(name)
        if not source.exists():
            raise UnknownSearch(name, self.names())
        target = safe_path(self.directory, new_name)
        if target.exists() or self._path(new_name).exists():
            raise InvalidInput(f"A saved search named {new_name!r} already exists.")

        text = source.read_text(encoding="utf-8")
        copied = re.sub(
            r"^name:\s*.*$", f"name: {new_name}", text, count=1, flags=re.MULTILINE
        )
        if copied == text:
            copied = f"name: {new_name}\n{text}"
        self.directory.mkdir(parents=True, exist_ok=True)
        target.write_text(copied, encoding="utf-8", newline="\n")
        return self.load(new_name)

    def delete(self, name: str) -> Path:
        """Take a saved search out of the catalogue, and keep the file.

        Moved into `deleted/` rather than unlinked, and this is a deliberate refusal to do exactly
        what was asked. A definition is something a person wrote: the areas are usually the part
        that took the longest and the comments are usually the part explaining why. It costs a
        directory entry to be able to undo this, and nothing is gained by making it final.

        It stops being a saved search immediately, which is the whole of what "delete" means here:
        it leaves the list, a run of everything skips it, and asking for it by name says it is not
        there. What the runs already recorded is untouched, because the constitution says snapshot
        history is append-only and this is not the feature that gets to be the exception.
        """
        source = self._path(name)
        if not source.exists():
            raise UnknownSearch(name, self.names())

        where = self.directory / DELETED
        where.mkdir(parents=True, exist_ok=True)
        target = where / source.name
        if target.exists():
            # Deleted, restored, deleted again. Keeping both is the point of keeping either.
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            target = where / f"{source.stem}.{stamp}{source.suffix}"

        source.replace(target)
        # When it was set aside, recorded where a surface can read it. A rename carries the file's
        # own timestamp with it, which is when somebody last edited the definition and not when
        # they stopped wanting it, and "set aside in March" against a file edited in January is the
        # sort of wrong that nobody checks and everybody believes. One touch, no second place for
        # the date to live and disagree with the file.
        os.utime(target, None)
        self._loaded.pop(source, None)
        return target

    def restore(self, name: str) -> FileSearch:
        """Bring back the most recently deleted definition of that name.

        The name is checked before the folder is read, and that order is the whole of what was
        wrong here. Every other operation on a saved search resolves through `safe_path`, which
        holds the name to `NAME` and then checks the resolved parent really is this directory. This
        one built a glob pattern out of the raw name instead and only checked where the file was
        going afterwards. A pattern is not a name: `..` in one is an ordinary path component, so
        `deleted/../../elsewhere/secret*` matched a file two directories outside the folder being
        searched, which is exactly what it looks like.

        What it could do was nothing, and the reason is the point. `safe_path` was called below, on
        the same raw name, to work out where the file was going; it refuses every name that could
        have escaped, so the move never happened. This function was saved by the order its two
        checks happened to fall in, which protects this function and says nothing about the pattern.
        The next thing written beside it removes what it finds and has no check downstream to be
        saved by.

        Resolving the target first is the fix and the whole of it. `NAME` admits letters, digits,
        dots, dashes and underscores and must start with a letter or digit, so a name that reaches
        the pattern below carries no separator and no glob character, and `..` cannot match it at
        all. The stem is still a pattern, because deleting the same name twice stamps the second
        one, and that is now a pattern over a name rather than over whatever arrived.
        """
        target = safe_path(self.directory, name)
        where = self.directory / DELETED
        kept = sorted(
            (path for path in where.glob(f"{name}*") if path.suffix in SUFFIXES and path.is_file()),
            key=lambda path: path.stat().st_mtime,
        )
        if not kept:
            raise UnknownSearch(name, ())
        if target.exists() or self._path(name).exists():
            raise InvalidInput(
                f"A saved search named {name!r} exists again, so restoring would overwrite it."
            )
        kept[-1].replace(target)
        return self.load(name)

    def deleted(self) -> tuple[str, ...]:
        """What is in the deleted folder, so a surface can offer to bring one back."""
        where = self.directory / DELETED
        if not where.is_dir():
            return ()
        return tuple(
            sorted(
                {
                    path.stem.split(".")[0]
                    for path in where.iterdir()
                    if path.suffix in SUFFIXES and path.is_file()
                }
            )
        )

    def discard(self, name: str) -> tuple[Path, ...]:
        """Remove a deleted definition for good. The only thing in this tool that unlinks a file.

        Two things guard it and they guard different mistakes.

        **The name is resolved before the folder is read**, through `safe_path`, like every other
        operation here. The resolved path itself is not what gets removed and is not used; calling
        it is how the name is held to `NAME` and to this directory before anything is looked at. A
        name is not a pattern, and this is the one function where being wrong about which file a
        name means cannot be undone. Nothing below globs: the folder is listed and each file's own
        base name is compared, so what is removed is only ever a file this catalogue put there.

        **It refuses anything that is not already deleted.** Two steps are the point rather than an
        inconvenience: to lose a definition somebody has to delete it first, which is reversible and
        says so, and only then discard it. A single irreversible step next to a reversible one is
        how an afternoon's drawing goes on a mis-aimed click.

        Every kept copy of that name goes, because deleting the same name twice keeps both and
        "discard it" means the name is not in the folder afterwards. Nothing in the store is
        touched, which is not a courtesy: non-negotiable 2 and product invariant 1 make snapshot
        history append-only, and a definition file is configuration rather than history.
        """
        safe_path(self.directory, name)
        where = self.directory / DELETED
        kept = (
            [
                path
                for path in sorted(where.iterdir())
                if path.suffix in SUFFIXES
                and path.is_file()
                and path.stem.split(".")[0] == name
            ]
            if where.is_dir()
            else []
        )
        if not kept:
            raise InvalidInput(
                f"There is no deleted saved search named {name!r} to discard. Only a search that "
                "has been deleted can be discarded, and deleting one is the step that can be "
                "undone."
            )
        for path in kept:
            path.unlink()
            self._loaded.pop(path, None)
        return tuple(kept)

    def deleted_entries(self) -> tuple[tuple[str, FileSearch, datetime], ...]:
        """Every deleted definition, read, with when it was set aside.

        The names alone were all a strip of "bring back X" buttons at the foot of the search list
        ever needed, and they are not enough for a surface that has to help somebody decide whether
        they want one back. A name six months old says nothing. The description, the areas, the
        sources and the date are all still in the kept file, so they are read from it rather than
        recorded a second time somewhere that could disagree with it.

        The date is the kept file's own timestamp, which `delete` sets to the moment it moves the
        file for exactly this reason. A definition somebody edits inside the deleted folder will
        report when they edited it, which is the honest answer for a folder of files.

        Most recently set aside first: the one somebody is most likely to want back is the one they
        just got rid of.
        """
        where = self.directory / DELETED
        if not where.is_dir():
            return ()
        newest: dict[str, Path] = {}
        for path in sorted(where.iterdir()):
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            name = path.stem.split(".")[0]
            held = newest.get(name)
            if held is None or path.stat().st_mtime > held.stat().st_mtime:
                newest[name] = path
        found = [
            (name, self._read(path), datetime.fromtimestamp(path.stat().st_mtime, UTC))
            for name, path in newest.items()
        ]
        found.sort(key=lambda entry: (entry[2], entry[0]), reverse=True)
        return tuple(found)

    def edit(self, name: str, changes: Mapping[str, object]) -> FileSearch:
        """Change named keys and write the file back, touching nothing else.

        Keys are dotted paths into the definition (`filters.price.max`), and values are read as YAML
        so that a number stays a number and a list stays a list. The file is only written when what
        results is valid, so a slip at the command line cannot leave a definition that will not run.

        A key in `DEFAULTS_OUT` set back to its default is removed rather than written. Absent and
        default are the same state for those, and a search paused and resumed twice should not end
        up carrying two lines that say nothing in a file somebody reads.
        """
        definition = self.load(name)
        document = definition.document
        if document is None:
            raise InvalidSearch(name, definition.problems())
        if not changes:
            return definition

        for key, value in changes.items():
            path = _key_path(key)
            wanted = value if key in PROSE and isinstance(value, str) else _value(value)
            # Nothing means remove the key, not write an empty one. A cleared price filter that left
            # `price:` behind in the file is a line that says nothing, that a person then has to
            # wonder about, and that a surface reads back as a filter which is somehow there and
            # empty. Absent is the state being asked for and absent is what gets written.
            if wanted is None or (key in DEFAULTS_OUT and wanted == DEFAULTS_OUT[key]):
                document.remove(path)
            else:
                document.assign(path, wanted)

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
