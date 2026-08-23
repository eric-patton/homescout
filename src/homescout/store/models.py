"""The shapes the store reads and writes.

Plain dataclasses rather than an object-relational mapper. The whole point of this package is a
small set of tables with unusually strict rules about what may be written to them, and a mapper
would put a layer of indirection over exactly the discipline that must not be subverted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .schema import SNAPSHOT_FIELDS

Presence = Literal["observed", "disappeared"]
SourceOutcomeName = Literal["ok", "failed", "unavailable"]
RunStatus = Literal["running", "completed", "failed"]
DifferenceKind = Literal["new", "changed", "unchanged", "gone", "returned"]
EventKind = Literal[
    "first_seen", "disappeared", "returned", "price_change", "status_change", "merged", "unmerged"
]


@dataclass(frozen=True, slots=True)
class ListingFields:
    """One property's values as a source reported them.

    Every field is optional. A source that does not know a value leaves it absent, and absent is a
    distinct thing from zero or from false: a listing with no price is not a listing priced at
    nothing.
    """

    price: int | None = None
    listing_status: str | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: int | None = None
    lot_sqft: int | None = None
    year_built: int | None = None
    property_type: str | None = None
    address_line: str | None = None
    unit: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    parcel_number: str | None = None
    listing_url: str | None = None
    description: str | None = None
    photo_urls: tuple[str, ...] | None = None

    def as_row(self) -> dict[str, Any]:
        """Column values for a database row. The photo list is stored as JSON text."""
        values = asdict(self)
        urls = values.pop("photo_urls")
        values["photo_urls"] = json.dumps(list(urls)) if urls is not None else None
        return values

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> ListingFields:
        present = set(row.keys())
        values = {name: row[name] for name in SNAPSHOT_FIELDS if name in present}
        urls = values.get("photo_urls")
        values["photo_urls"] = tuple(json.loads(urls)) if urls else None
        return cls(**values)


@dataclass(frozen=True, slots=True)
class SourceRow:
    """What a source adapter hands the store: one property, as that source returned it.

    The source's own response is retained alongside the normalized fields, so a normalization bug
    found later can be corrected against what was actually received rather than guessed at.
    """

    source: str
    fields: ListingFields
    payload: Mapping[str, Any] | str
    source_listing_id: str | None = None
    fetched_at: str | None = None

    def payload_text(self) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    """What one source contributed to one run.

    `unavailable` means the source cannot serve this query at all, which is a different thing from
    having tried and failed. Both are distinct from returning nothing.
    """

    source: str
    outcome: SourceOutcomeName
    row_count: int = 0
    truncated: bool = False
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class RunRecord:
    #: Insertion order. This, not the start time, is what runs are ordered and bounded by, so that
    #: two runs recorded in the same millisecond still have an unambiguous "which came first".
    seq: int
    id: str
    search_name: str
    started_at: str
    finished_at: str | None
    status: RunStatus
    sources: tuple[SourceOutcome, ...] = ()

    @property
    def all_sources_succeeded(self) -> bool:
        """True only when every configured source reported success.

        This is the question that decides whether a listing's absence is evidence. If any source
        failed or was unavailable, absence means nothing.
        """
        return bool(self.sources) and all(s.outcome == "ok" for s in self.sources)


@dataclass(frozen=True, slots=True)
class ListingRecord:
    id: str
    first_observed_at: str
    created_in_run: str
    presence: Presence
    superseded_by: str | None = None
    retracted: bool = False


@dataclass(frozen=True, slots=True)
class SourceLink:
    """One source row underneath a canonical listing, and what justified putting it there."""

    raw_listing_id: str
    source: str
    source_listing_id: str | None
    fetched_at: str
    join_signal: str
    decided_by: Literal["automatic", "human"]
    linked_at: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One listing's complete state as of one run."""

    run_id: str
    listing_id: str
    observed_at: str
    fields: ListingFields


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class PriceChange:
    before: int | None
    after: int | None
    amount: int | None
    direction: Literal["up", "down"] | None


@dataclass(frozen=True, slots=True)
class DifferenceEvent:
    """What a comparison says about one listing. Exactly one per listing, never more."""

    kind: DifferenceKind
    listing_id: str
    changes: tuple[FieldChange, ...] = ()
    price_change: PriceChange | None = None


@dataclass(frozen=True, slots=True)
class Comparison:
    search_name: str
    baseline_run_id: str | None
    target_run_id: str
    events: tuple[DifferenceEvent, ...] = ()

    def of_kind(self, kind: DifferenceKind) -> tuple[DifferenceEvent, ...]:
        return tuple(e for e in self.events if e.kind == kind)

    @property
    def counts(self) -> dict[str, int]:
        counts = {k: 0 for k in ("new", "changed", "unchanged", "gone", "returned")}
        for event in self.events:
            counts[event.kind] += 1
        counts["matched"] = sum(
            counts[k] for k in ("new", "changed", "unchanged", "returned")
        )
        return counts


@dataclass(frozen=True, slots=True)
class ListingEvent:
    id: int
    listing_id: str
    run_id: str | None
    occurred_at: str
    kind: EventKind
    detail: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Annotation:
    """The user's own judgment. Never written by a run."""

    listing_id: str
    rank: int | None = None
    verdict: str | None = None
    red_flags: str | None = None
    summary: str | None = None
    next_step: str | None = None
    notes: str | None = None
    updated_at: str | None = None

    ANNOTATION_FIELDS = ("rank", "verdict", "red_flags", "summary", "next_step", "notes")

    def content(self) -> dict[str, Any]:
        """Everything the user wrote, without the bookkeeping. This is what must survive."""
        return {name: getattr(self, name) for name in self.ANNOTATION_FIELDS}


@dataclass(frozen=True, slots=True)
class AreaNote:
    """An observation about a place rather than about a property."""

    id: str
    area_type: str
    area_value: str
    notes: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class StoredImage:
    listing_id: str
    path: str
    retrieved_at: str
    source_url: str | None = None
    byte_size: int | None = None


@dataclass(frozen=True, slots=True)
class PriceHistoryEntry:
    observed_at: str
    run_id: str
    price: int | None


@dataclass(frozen=True, slots=True)
class ListingHistory:
    """Everything locally known about how one listing has moved.

    Days on market is derived from this tool's own first observation, never from a source's own
    value: a source that says four hundred days about a listing we first saw last month is telling
    us about its own records, not about ours.
    """

    listing_id: str
    first_observed_at: str
    days_on_market: int
    presence: Presence
    prices: tuple[PriceHistoryEntry, ...] = field(default_factory=tuple)
    events: tuple[ListingEvent, ...] = field(default_factory=tuple)
