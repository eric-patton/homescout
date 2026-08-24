"""What a saved search is, from the run loop's point of view.

The run loop never sees a file. The definition file, the geometry, and the validation live in this
package (feat-004); what lives in this module is the contract between them and everything above:
a name, which sources to ask, the coarse queries to send each one, the exact local test to apply
afterwards, and whatever is wrong with the definition.

Two of those five are shaped by facts that only become visible with more than one source and more
than one kind of area, and both were got wrong by an earlier, simpler version of this module:

**Coarse queries are per source.** Realtor.com takes named places and a radius, Zillow takes a box,
and neither takes a drawn shape. One set of coarse queries sent to every source cannot be correct
for both, so the asking source's capability declaration is an argument rather than an assumption.

**The exact test has three answers, not two.** A property a source returned without coordinates
cannot be placed. Keeping it as though it qualified and dropping it as though it did not are both
lies, and the second one is worse, because the store reads an unexplained absence as a house that
may have sold.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from ..errors import InvalidInput
from ..records import ListingFields
from ..sources.base import Capabilities, SearchQuery

Severity = Literal["problem", "notice"]


@dataclass(frozen=True, slots=True)
class SearchProblem:
    """One thing worth saying about a definition.

    `location` is whatever the catalog can say about where to look: a file and a line, a key path,
    or a bare name. This layer never interprets it, it only carries it through to the person who
    has to fix the file.

    `severity` separates the two things a reader needs told apart. A `problem` makes the definition
    invalid and stops the run. A `notice` does not: a search whose exclusions cover every one of its
    areas is a valid search that matches nothing, and it has to be able to say so without being
    refused. Both travel the same channel because both are read by the same person in the same
    place.
    """

    location: str
    message: str
    severity: Severity = "problem"


def blocking(found: Iterable[SearchProblem]) -> tuple[SearchProblem, ...]:
    """Just the ones that make a definition invalid and stop a run."""
    return tuple(p for p in found if p.severity == "problem")


def notices(found: Iterable[SearchProblem]) -> tuple[SearchProblem, ...]:
    return tuple(p for p in found if p.severity == "notice")


class Placement(StrEnum):
    """Where one property sits relative to a search's geometry.

    `unlocatable` is the whole reason this is not a boolean. It means the tests that would have
    answered could not be run, which is a different fact from failing them, and the row is kept and
    counted rather than being either believed or discarded.
    """

    inside = "inside"
    outside = "outside"
    unlocatable = "unlocatable"


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
    #: The criteria this search applies, parsed and checked (feat-008). Empty is the honest answer
    #: for a search that states none, and is what every definition carried before the rule engine
    #: existed.
    rules: tuple[Any, ...]
    #: One entry per geographic component, in this tool's own vocabulary rather than any source's
    #: (`search.areas.SearchArea` for a definition read from a file). Source-independent, so it is
    #: what a surface counts and names; the source layer's own area types appear only inside
    #: `queries_for`, on the way out.
    areas: tuple[Any, ...]

    def queries_for(self, capabilities: Capabilities) -> tuple[SearchQuery, ...]:
        """The coarse queries to send one source, given what that source accepts.

        Coarse on purpose, and never narrower than the area: whatever is sent contains the area, so
        that `place` can only remove properties afterwards and never has to add one. A source that
        can express none of this search's areas gets no queries, which is a different answer from
        getting a query for somewhere else.
        """
        ...

    def place(self, fields: ListingFields) -> Placement:
        """The exact local test a coarse query cannot express."""
        ...

    def problems(self) -> tuple[SearchProblem, ...]:
        """Everything worth saying about this definition, in one pass."""
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
    `place` keeps everything unless given a test, which is the honest answer for a definition
    carrying no geometry.
    """

    name: str
    sources: tuple[str, ...] = ("realtor",)
    asks: tuple[SearchQuery, ...] = ()
    faults: tuple[SearchProblem, ...] = ()
    where: Callable[[ListingFields], Placement] | None = None
    covers: tuple[Any, ...] | None = None
    rules: tuple[Any, ...] = ()

    @property
    def areas(self) -> tuple[Any, ...]:
        return self.covers if self.covers is not None else tuple(ask.area for ask in self.asks)

    def queries_for(self, capabilities: Capabilities) -> tuple[SearchQuery, ...]:
        """Every ask this search carries that the source can express.

        A source declaring no accepted areas at all accepts anything, which is what the fakes in the
        test suite do and what the source layer's own `accepts` already means.
        """
        if not capabilities.accepts_areas:
            return self.asks
        return tuple(ask for ask in self.asks if capabilities.accepts(ask.area))

    def place(self, fields: ListingFields) -> Placement:
        return Placement.inside if self.where is None else self.where(fields)

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
                f"Editing anything else needs the definition file."
            )
        if "sources" in changes:
            definition.sources = tuple(changes["sources"])  # type: ignore[arg-type,call-overload]
        return definition


#: How a catalog is built for a given directory. Registering one replaces the file-backed default,
#: which is how a test runs the whole loop against searches that were never written to disk.
CatalogFactory = Callable[[Path], SearchCatalog]

_FACTORY: CatalogFactory | None = None


def register_catalog(factory: CatalogFactory) -> None:
    global _FACTORY
    _FACTORY = factory


def unregister_catalog() -> None:
    global _FACTORY
    _FACTORY = None


def default_catalog(root: Path) -> SearchCatalog:
    """The catalog for a workspace: the `searches/` directory beside the database.

    Imported here rather than at module scope because the file catalog is built on this module's own
    contract, and importing it at the top would be a cycle.
    """
    if _FACTORY is not None:
        return _FACTORY(root)
    from .definition import FileCatalog

    return FileCatalog(root / "searches")


__all__ = [
    "CatalogFactory",
    "InMemoryCatalog",
    "InMemorySearch",
    "InvalidSearch",
    "Placement",
    "SearchCatalog",
    "SearchDefinition",
    "SearchProblem",
    "Severity",
    "UnknownSearch",
    "blocking",
    "default_catalog",
    "notices",
    "register_catalog",
    "unregister_catalog",
]
