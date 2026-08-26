"""The shapes the store reads and writes.

Plain dataclasses rather than an object-relational mapper. The whole point of this package is a
small set of tables with unusually strict rules about what may be written to them, and a mapper
would put a layer of indirection over exactly the discipline that must not be subverted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..records import ListingFields

Presence = Literal["observed", "disappeared"]
SourceOutcomeName = Literal["ok", "failed", "unavailable"]
RunStatus = Literal["running", "completed", "failed"]
DifferenceKind = Literal["new", "changed", "unchanged", "gone", "returned"]
EventKind = Literal[
    "first_seen", "disappeared", "returned", "price_change", "status_change", "merged", "unmerged"
]


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
    #: Where this source row can be read on the site it came from. A merged property has one per
    #: site, and they are not interchangeable: a person keeping a list on one site needs that
    #: site's page, and the single address a merged record settles on is only ever one of them.
    listing_url: str | None = None


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
    #: `keep`, `pass`, or nothing. The only annotation field that changes what a person is shown
    #: rather than only what they have written down: a passed property drops out of the default
    #: results view. Nothing means undecided, which is not the same as deciding to keep.
    judgment: str | None = None
    updated_at: str | None = None

    ANNOTATION_FIELDS = (
        "rank", "verdict", "red_flags", "summary", "next_step", "notes", "judgment",
    )

    #: What a judgment may hold. Checked in the core rather than in a form control, so a value
    #: arriving from a hand-edited file or an older client is refused in the one place every write
    #: passes through.
    JUDGMENTS = ("keep", "pass")

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
class RuleVerdict:
    """What one criterion decided about one property in one run.

    Recorded rather than recomputed, and never rewritten. Re-evaluating an edited criterion against
    an old snapshot would change what that run decided, and a run's decisions are history.

    `missing` is the names that were unknown, and it is only ever populated for an undetermined
    verdict: "not checked" and "checked and passed" are different answers and the difference is the
    point.
    """

    run_id: str
    listing_id: str
    rule_id: str
    severity: str
    verdict: str
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CachedValue:
    """One value a public data service gave about one place, and when.

    The value may be `None`, and that is a real answer: a point outside every mapped flood zone has
    been asked about and has no zone. A value nobody asked about is not a row here at all.
    """

    value: object
    fetched_at: str


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


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """One attempt to tell somebody what a run found.

    Recorded rather than logged, because it answers a question a person asks the morning after: did
    last night's run mail me and I missed it, or did it decide there was nothing worth saying?
    `suppressed` and `sent` are different answers, and `skipped` (no mail account on this
    installation) is a third.

    `target` is a path or a list of recipients. Never a credential: nothing that writes one of these
    has one to write.
    """

    id: str
    attempted_at: str
    channel: str
    outcome: str
    target: str | None = None
    detail: str | None = None
    run_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MergeDecision:
    """What a person decided about two records, and when.

    Outranks every automatic signal for as long as the database exists (non-negotiable 6), and is
    never edited: a person changing their mind is a new row, and the latest one for a pair counts.
    """

    id: str
    pair_key: str
    listing_ids: tuple[str, ...]
    verdict: str
    decided_at: str
    decided_by: str = "human"
    merged_id: str | None = None
    note: str | None = None

    @property
    def same(self) -> bool:
        return self.verdict == "same"


@dataclass(frozen=True, slots=True)
class MergeContradiction:
    """Evidence that turned up later and disagrees with what a person decided.

    Recorded and shown; acted on by nobody. A person's decision is not overruled by evidence, it is
    questioned by it, and the questioning is this.
    """

    id: str
    pair_key: str
    noticed_at: str
    detail: str
    run_id: str | None = None
