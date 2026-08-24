"""The interface every listing site is reduced to, and the query it is asked.

Three sources, no supported API between them, each with its own query surface, its own undocumented
ceiling, and its own opinion about callers it dislikes. This module is the seam that keeps those
differences from leaking upward: an adapter answers what it can filter, what it found, and what it
could not do, and the caller works against that description rather than against any site.

The load-bearing idea is the **capability declaration**. An adapter states, once, which query fields
it applies on its own side. The request is then built by walking that declaration, so a field the
adapter never claimed has no path to the source at all, and what the caller still has to filter for
itself is simply what is left over. Neither fact depends on anyone remembering.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol, runtime_checkable

from ..records import SourceRow
from .errors import SourceFailed, SourceUnavailable
from .politeness import PacedSession

OutcomeName = Literal["ok", "failed", "unavailable"]

#: Every field a saved search can ask for. An adapter declares the subset it pushes to the source;
#: the rest come back reported as not applied, for the caller to filter locally.
QUERY_FIELDS: tuple[str, ...] = (
    "price_min",
    "price_max",
    "beds_min",
    "beds_max",
    "baths_min",
    "baths_max",
    "sqft_min",
    "sqft_max",
    "lot_sqft_min",
    "lot_sqft_max",
    "year_built_min",
    "year_built_max",
    "property_types",
    "listing_status",
    "listed_since",
)


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------

# A saved search names places in whatever form suits it. Sources accept wildly different subsets:
# Realtor.com takes named places and a radius; Zillow takes a box; nobody takes a drawn polygon.
# An area a source cannot express is `unavailable`, never quietly swapped for a nearby one.


@dataclass(frozen=True, slots=True)
class PostalCode:
    value: str

    def as_term(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class City:
    name: str
    state: str | None = None

    def as_term(self) -> str:
        return f"{self.name}, {self.state}" if self.state else self.name


@dataclass(frozen=True, slots=True)
class County:
    name: str
    state: str | None = None

    def as_term(self) -> str:
        suffix = f", {self.state}" if self.state else ""
        return f"{self.name} County{suffix}"


@dataclass(frozen=True, slots=True)
class State:
    name: str

    def as_term(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class AddressRadius:
    address: str
    miles: float

    def as_term(self) -> str:
        return self.address


@dataclass(frozen=True, slots=True)
class PointRadius:
    """A circle around a point this tool already knows the coordinates of.

    Distinct from `AddressRadius`, which names a place a source has to look up first. The difference
    matters twice: it is one request cheaper, and it is the only circle that can be asked for around
    somewhere with no name, which is what a drawn shape's covering circle is.
    """

    latitude: float
    longitude: float
    miles: float

    def as_term(self) -> str:
        return f"{self.miles:g} miles around {self.latitude:.5f}, {self.longitude:.5f}"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def as_term(self) -> str:
        return f"box({self.south},{self.west},{self.north},{self.east})"


@dataclass(frozen=True, slots=True)
class Polygon:
    """A shape drawn on a map. No listing site accepts one.

    Kept in the vocabulary anyway, because a saved search may hold one and the honest answer from an
    adapter is `unavailable`, which the query planner then turns into a coarser area the source does
    accept, followed by an exact local test.
    """

    points: tuple[tuple[float, float], ...]

    def as_term(self) -> str:
        return f"polygon({len(self.points)} points)"


Area = PostalCode | City | County | State | AddressRadius | PointRadius | BoundingBox | Polygon


@dataclass(frozen=True, slots=True)
class DateRange:
    """A half-open range over the date a listing appeared, used to split an oversized query."""

    start: str | None = None
    end: str | None = None


# ---------------------------------------------------------------------------
# The query
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """One search, in the tool's own vocabulary rather than any site's.

    Built from a saved search by feat-004. Every field beyond the area is optional, and an unset
    field is not a filter: nothing is sent for it and nothing is claimed about it.
    """

    area: Area
    price_min: int | None = None
    price_max: int | None = None
    beds_min: float | None = None
    beds_max: float | None = None
    baths_min: float | None = None
    baths_max: float | None = None
    sqft_min: int | None = None
    sqft_max: int | None = None
    lot_sqft_min: int | None = None
    lot_sqft_max: int | None = None
    year_built_min: int | None = None
    year_built_max: int | None = None
    property_types: tuple[str, ...] | None = None
    listing_status: str = "for_sale"
    #: Only ever an optimization. Freshness is computed from local history, never from this.
    listed_since: str | None = None
    #: Set by the ceiling walk when it splits an oversized query. Not something a user asks for.
    listed_between: DateRange | None = None

    def populated_fields(self) -> tuple[str, ...]:
        """The query fields this search actually constrains."""
        return tuple(
            name for name in QUERY_FIELDS if getattr(self, name, None) not in (None, (), "")
        )

    def within(self, span: DateRange) -> SearchQuery:
        return replace(self, listed_between=span)


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What a source will do on its own side.

    `applies` is the whole contract. A field named here is pushed to the source; a field not named
    here is never sent, and is reported back to the caller as still needing to be applied locally.

    `accepts_areas` is the same promise about geography, and `ceiling` is the source's undocumented
    limit on how many results one query will yield, which the caller works around rather than
    ignores.
    """

    applies: frozenset[str] = frozenset()
    accepts_areas: tuple[type, ...] = ()
    ceiling: int | None = None
    page_size: int = 200

    def __post_init__(self) -> None:
        unknown = set(self.applies) - set(QUERY_FIELDS)
        if unknown:
            raise ValueError(
                f"a source declared filters that are not query fields: {sorted(unknown)}"
            )

    def accepts(self, area: Area) -> bool:
        return isinstance(area, self.accepts_areas)

    def application(self, query: SearchQuery) -> dict[str, bool]:
        """Per constrained field, whether the source applied it.

        This is the caller's instruction sheet: everything that comes back `False` still has to be
        filtered locally, and everything that comes back `True` has already been narrowed. Deriving
        it from the declaration rather than from the request means the two cannot disagree.
        """
        return {name: name in self.applies for name in query.populated_fields()}


@dataclass(frozen=True, slots=True)
class Truncation:
    """Why a result is known to be incomplete.

    Two things produce one: a piece of the query that stayed over the source's ceiling after the
    query could no longer be split, and a source that began refusing partway through. Both mean the
    same thing to a caller (do not read this as the whole market) and are worth telling apart when
    someone asks why.
    """

    reason: str
    ceiling: int | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What one source contributed to one query."""

    source: str
    outcome: OutcomeName = "ok"
    rows: tuple[SourceRow, ...] = ()
    applied: Mapping[str, bool] = field(default_factory=dict)
    truncation: Truncation | None = None
    detail: str | None = None
    request_count: int = 0

    @property
    def locally_applied(self) -> tuple[str, ...]:
        """The fields the caller still has to filter for itself."""
        return tuple(name for name, by_source in self.applied.items() if not by_source)

    @property
    def truncated(self) -> bool:
        return self.truncation is not None


@dataclass(frozen=True, slots=True)
class Preview:
    """One small image for one row, fetched but not yet stored."""

    source_url: str
    content_type: str | None
    data: bytes


@runtime_checkable
class Source(Protocol):
    """Everything the rest of the tool may assume about a listing site.

    Four members, and adding a source means writing them once. Nothing above this layer branches on
    which site it is talking to.

    `fetch_preview` is on the interface rather than on whichever adapter happened to need it first,
    so that a source added later inherits the obligation instead of quietly declining it. The
    caller contract is that a run fetches one preview per returned row and hands each straight to
    the store, which keeps one image in memory at a time and keeps an image failure structurally
    unable to alter the query's outcome.
    """

    name: str

    def capabilities(self) -> Capabilities: ...

    def search(self, query: SearchQuery) -> SearchResult: ...

    def fetch_preview(self, row: SourceRow) -> Preview | None: ...


class BaseSource:
    """The shared half of an adapter: the failure contract, and nothing else.

    Subclasses implement `run_search`, which is free to raise. This class turns whatever comes out
    into a result, so that one site being down costs that site's listings and cannot abort a caller
    querying the others.
    """

    name: str = ""

    def __init__(self, session: PacedSession) -> None:
        self.session = session

    def capabilities(self) -> Capabilities:  # pragma: no cover - overridden
        raise NotImplementedError

    def run_search(self, query: SearchQuery) -> SearchResult:  # pragma: no cover - overridden
        raise NotImplementedError

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        """One small image for one row, or None when this source offers none.

        Deliberately not given a silent default. Inheriting a no-op would mean an adapter could
        satisfy the interface while quietly never fetching an image, and the reason preview
        retrieval sits on the interface at all is that exactly that hole was found once already, at
        the whole-product level, where nobody owned the image the email digest depends on. A source
        with no images says so by returning None on purpose.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must decide what preview retrieval means for it. "
            "Return None if this source offers no images."
        )

    def preview(self, row: SourceRow) -> Preview | None:
        """`fetch_preview`, with the same guarantee `search` gives: it cannot raise.

        An image is the least important thing a run retrieves and must never be able to interrupt
        one. This is where that is enforced, rather than in every caller.
        """
        from .errors import SourceError

        try:
            return self.fetch_preview(row)
        except SourceError:
            return None
        except Exception:  # noqa: BLE001 - an image is never worth ending a run over
            return None

    def search(self, query: SearchQuery) -> SearchResult:
        """Answer for this source, whatever happens.

        Nothing raised in here reaches the caller. The point is not tidiness: a run queries several
        sources in turn, and an exception escaping one of them would take the others' work with it.
        """
        capabilities = self.capabilities()
        applied = capabilities.application(query)
        if capabilities.accepts_areas and not capabilities.accepts(query.area):
            return SearchResult(
                source=self.name,
                outcome="unavailable",
                applied=applied,
                detail=(
                    f"{self.name} has no way to express {query.area.as_term()}; "
                    "asking for a different area would answer a different question"
                ),
            )
        try:
            return self.run_search(query)
        except SourceUnavailable as exc:
            return SearchResult(
                source=self.name, outcome="unavailable", applied=applied, detail=exc.reason
            )
        except SourceFailed as exc:
            return SearchResult(
                source=self.name, outcome="failed", applied=applied, detail=exc.reason
            )
        except Exception as exc:  # noqa: BLE001 - deliberately the end of the line
            return SearchResult(
                source=self.name,
                outcome="failed",
                applied=applied,
                detail=f"{self.name} failed unexpectedly: {exc}",
            )
