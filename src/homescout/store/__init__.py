"""The record of what HomeScout has observed, and the arithmetic over it.

This is the substrate every other part of the product reads from or writes to. Two guarantees are
worth stating at the door, because everything else depends on them holding:

**Recorded history is never rewritten.** Not by convention, but because the database's own triggers
abort an update or a delete on any history table. Corrections are new rows.

**Absence is not evidence.** A listing is only marked as gone when every configured source reported
success and none of them returned it. If any source failed, its silence means nothing.
"""

from ..records import ListingFields, SourceRow
from .core import Store
from .db import to_utc_text, utc_now
from .errors import (
    HistoryIsAppendOnlyError,
    NoBaselineError,
    RunNotCompletedError,
    SchemaTooNewError,
    StoreError,
    StoreLockedError,
    UnknownListingError,
)
from .models import (
    Annotation,
    AreaNote,
    Comparison,
    DifferenceEvent,
    FieldChange,
    ListingEvent,
    ListingHistory,
    ListingRecord,
    PriceChange,
    PriceHistoryEntry,
    RuleVerdict,
    RunRecord,
    Snapshot,
    SourceLink,
    SourceOutcome,
    StoredImage,
)
from .schema import COMPARED_FIELDS, SCHEMA_VERSION, SNAPSHOT_FIELDS

__all__ = [
    "COMPARED_FIELDS",
    "SCHEMA_VERSION",
    "SNAPSHOT_FIELDS",
    "Annotation",
    "AreaNote",
    "Comparison",
    "DifferenceEvent",
    "FieldChange",
    "HistoryIsAppendOnlyError",
    "ListingEvent",
    "ListingFields",
    "ListingHistory",
    "ListingRecord",
    "NoBaselineError",
    "PriceChange",
    "PriceHistoryEntry",
    "RunNotCompletedError",
    "RuleVerdict",
    "RunRecord",
    "SchemaTooNewError",
    "Snapshot",
    "SourceLink",
    "SourceOutcome",
    "SourceRow",
    "Store",
    "StoreError",
    "StoreLockedError",
    "StoredImage",
    "UnknownListingError",
    "to_utc_text",
    "utc_now",
]
