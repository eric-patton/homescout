"""What a saved search has to be, from the run loop's point of view.

The run loop never sees a file. Saved searches and geography (feat-004) owns the hand-editable
definition and the two-stage geography behind it, and it depends on this feature rather than the
other way round, so what lives here is the contract that feature has to satisfy: a name, which
sources to ask, the coarse queries to send them, the exact local test to apply afterwards, and
whatever is wrong with the definition.

That inversion is the point. A run loop that parsed a definition file would have to be edited every
time the format grew a field, and the exact geometry test would end up in two places.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import InvalidInput
from .records import ListingFields
from .sources.base import SearchQuery


@dataclass(frozen=True, slots=True)
class SearchProblem:
    """One thing wrong with a definition.

    `location` is whatever the catalog can say about where to look: a file and a line, a key path,
    or a bare name. This layer never interprets it, it only carries it through to the person who
    has to fix the file.
    """

    location: str
    message: str


class UnknownSearch(InvalidInput):
    """No saved search by that name."""

    def __init__(self, name: str, known: Iterable[str]) -> None:
        self.name = name
        self.known = tuple(known)
        known_text = ", ".join(self.known) if self.known else "none are configured"
        super().__init__(f"There is no saved search named {name!r}. Known searches: {known_text}.")


class InvalidSearch(InvalidInput):
    """The definition exists but does not validate. Nothing is run."""

    def __init__(self, name: str, problems: Iterable[SearchProblem]) -> None:
        self.name = name
        self.problems = tuple(problems)
        detail = "; ".join(f"{p.location}: {p.message}" for p in self.problems)
        super().__init__(f"The saved search {name!r} is not valid: {detail}")


@runtime_checkable
class SearchDefinition(Protocol):
    """One saved search, in the run loop's vocabulary."""

    name: str
    #: Which adapters this search asks, by registered name.
    sources: tuple[str, ...]

    def queries(self) -> tuple[SearchQuery, ...]:
        """The coarse queries to send, one per area.

        Coarse on purpose: a source is asked for something it can express that contains the area,
        and `keeps` narrows the answer afterwards.
        """
        ...

    def keeps(self, fields: ListingFields) -> bool:
        """The exact local test a coarse query cannot express."""
        ...

    def problems(self) -> tuple[SearchProblem, ...]:
        """Everything wrong with this definition, in one pass."""
        ...


@runtime_checkable
class SearchCatalog(Protocol):
    def names(self) -> tuple[str, ...]: ...

    def load(self, name: str) -> SearchDefinition: ...

    def create(self, name: str) -> SearchDefinition: ...

    def edit(self, name: str, changes: Mapping[str, object]) -> SearchDefinition: ...


@dataclass
class InMemorySearch:
    """A definition held in memory, with no file behind it.

    This is what a test uses, and what the browser will hold while a definition is being edited. Its
    `keeps` keeps everything unless given a test, which is the honest answer for a definition
    carrying no geometry.
    """

    name: str
    sources: tuple[str, ...] = ("realtor",)
    asks: tuple[SearchQuery, ...] = ()
    faults: tuple[SearchProblem, ...] = ()
    keep: Callable[[ListingFields], bool] | None = None

    def queries(self) -> tuple[SearchQuery, ...]:
        return self.asks

    def keeps(self, fields: ListingFields) -> bool:
        return True if self.keep is None else self.keep(fields)

    def problems(self) -> tuple[SearchProblem, ...]:
        return self.faults


class InMemoryCatalog:
    """Every saved search a process happens to be holding."""

    def __init__(self, searches: Iterable[SearchDefinition] = ()) -> None:
        self.searches: dict[str, SearchDefinition] = {s.name: s for s in searches}

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.searches))

    def load(self, name: str) -> SearchDefinition:
        try:
            return self.searches[name]
        except KeyError:
            raise UnknownSearch(name, self.names()) from None

    def create(self, name: str) -> SearchDefinition:
        if name in self.searches:
            raise InvalidInput(f"A saved search named {name!r} already exists.")
        made = InMemorySearch(name=name)
        self.searches[name] = made
        return made

    def edit(self, name: str, changes: Mapping[str, object]) -> SearchDefinition:
        definition = self.load(name)
        unknown = set(changes) - {"sources"}
        if unknown:
            raise InvalidInput(
                f"An in-memory saved search has nothing named {sorted(unknown)} to change. "
                f"Editing anything else needs the definition file, which arrives with saved "
                f"searches and geography."
            )
        if "sources" in changes:
            definition.sources = tuple(changes["sources"])  # type: ignore[arg-type,call-overload]
        return definition


#: How a catalog is built for a given directory. Saved searches and geography registers the one
#: that reads files; until then every name is unknown, which is the correct answer for a machine
#: with no saved searches on it.
CatalogFactory = Callable[[Path], SearchCatalog]

_FACTORY: CatalogFactory | None = None


def register_catalog(factory: CatalogFactory) -> None:
    global _FACTORY
    _FACTORY = factory


def unregister_catalog() -> None:
    global _FACTORY
    _FACTORY = None


def default_catalog(root: Path) -> SearchCatalog:
    return _FACTORY(root) if _FACTORY is not None else InMemoryCatalog(())
