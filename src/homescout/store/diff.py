"""Turning recorded observations into what changed.

Every query here is bounded by the baseline run's start time, which is what makes a comparison
reproducible: asking the same question about the same two points in time gives the same answer
however many runs have happened since.
"""

from __future__ import annotations

import sqlite3

from .models import (
    Comparison,
    DifferenceEvent,
    FieldChange,
    ListingFields,
    PriceChange,
    RunRecord,
)
from .schema import COMPARED_FIELDS, SNAPSHOT_FIELDS

_SNAPSHOT_COLUMNS = ", ".join(f"sn.{name}" for name in SNAPSHOT_FIELDS)
_PLAIN_SNAPSHOT_COLUMNS = ", ".join(SNAPSHOT_FIELDS)

# Every listing addressed by whichever listing currently represents it. A merge writes a new
# listing and points its constituents at it, so history recorded before a merge sits under the
# constituents' ids. Without this, the run after a merge would report the merged listing as
# new and both constituents as gone, which is a fiction: the house did not move.
_LIVE_IDS = """
WITH RECURSIVE live(id, live_id) AS (
    SELECT id, id FROM listings WHERE superseded_by IS NULL
    UNION ALL
    SELECT l.id, live.live_id FROM listings l JOIN live ON l.superseded_by = live.id
)
"""

# The most recent snapshot for each listing, among completed runs of this search at or before the
# cutoff. The cutoff is a run sequence number rather than a time, so the boundary is unambiguous
# even for runs recorded in the same instant, and later runs cannot change a past answer.
_LATEST_SNAPSHOT_AT_OR_BEFORE = f"""
{_LIVE_IDS},
scoped AS (
    SELECT live.live_id AS listing_id, sn.id AS snapshot_id, r.seq, {_SNAPSHOT_COLUMNS}
    FROM listing_snapshots sn
    JOIN runs r ON r.id = sn.run_id
    JOIN live ON live.id = sn.listing_id
    WHERE r.search_name = :search
      AND r.status = 'completed'
      AND r.seq <= :cutoff
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY listing_id ORDER BY seq DESC, snapshot_id DESC
    ) AS rn
    FROM scoped
)
SELECT * FROM ranked WHERE rn = 1
"""

# Presence as it stood at the cutoff, from the dated event trail rather than from the listing's
# current state, because the current state reflects every run since.
_PRESENCE_AT_OR_BEFORE = f"""
{_LIVE_IDS},
scoped AS (
    SELECT live.live_id AS listing_id, e.kind, e.id AS event_id, r.seq
    FROM listing_events e
    JOIN runs r ON r.id = e.run_id
    JOIN live ON live.id = e.listing_id
    WHERE e.kind IN ('first_seen', 'disappeared', 'returned')
      AND r.search_name = :search
      AND r.status = 'completed'
      AND r.seq <= :cutoff
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY listing_id ORDER BY seq DESC, event_id DESC
    ) AS rn
    FROM scoped
)
SELECT listing_id, kind FROM ranked WHERE rn = 1
"""

# What the target run saw, likewise addressed by the currently-representing listing.
_OBSERVED_IN_RUN = f"""
{_LIVE_IDS}
SELECT live.live_id AS listing_id, {_PLAIN_SNAPSHOT_COLUMNS}
FROM listing_snapshots sn
JOIN live ON live.id = sn.listing_id
WHERE sn.run_id = :run
"""


def _fields_from(row: sqlite3.Row) -> ListingFields:
    return ListingFields.from_row({name: row[name] for name in SNAPSHOT_FIELDS})


def _compare_fields(before: ListingFields, after: ListingFields) -> tuple[FieldChange, ...]:
    """Only declared compared fields may appear.

    A field the tool does not compare never shows up in a change.
    """
    changes = []
    for name in COMPARED_FIELDS:
        old = getattr(before, name)
        new = getattr(after, name)
        if old != new:
            changes.append(FieldChange(field=name, before=old, after=new))
    return tuple(changes)


def _price_change(before: ListingFields, after: ListingFields) -> PriceChange | None:
    if before.price == after.price:
        return None
    if before.price is None or after.price is None:
        # Gaining or losing a price is a change, but it is not a cut or a rise. A listing with
        # no price is not a listing priced at nothing.
        return PriceChange(before=before.price, after=after.price, amount=None, direction=None)
    delta = after.price - before.price
    return PriceChange(
        before=before.price,
        after=after.price,
        amount=abs(delta),
        direction="up" if delta > 0 else "down",
    )


def compare_runs(
    conn: sqlite3.Connection,
    *,
    search_name: str,
    target: RunRecord,
    baseline: RunRecord | None,
) -> Comparison:
    """Produce exactly one difference event per listing.

    With no baseline, everything observed is new, which is what a first-ever run means.
    """
    target_rows = conn.execute(_OBSERVED_IN_RUN, {"run": target.id}).fetchall()
    observed_now = {row["listing_id"]: _fields_from(row) for row in target_rows}

    if baseline is None:
        events = tuple(
            DifferenceEvent(kind="new", listing_id=listing_id)
            for listing_id in sorted(observed_now)
        )
        return Comparison(
            search_name=search_name,
            baseline_run_id=None,
            target_run_id=target.id,
            events=events,
        )

    params = {"search": search_name, "cutoff": baseline.seq}
    previous = {
        row["listing_id"]: _fields_from(row)
        for row in conn.execute(_LATEST_SNAPSHOT_AT_OR_BEFORE, params).fetchall()
    }
    presence_then = {
        row["listing_id"]: row["kind"]
        for row in conn.execute(_PRESENCE_AT_OR_BEFORE, params).fetchall()
    }

    events: list[DifferenceEvent] = []

    for listing_id in sorted(observed_now):
        after = observed_now[listing_id]
        before = previous.get(listing_id)
        if before is None:
            events.append(DifferenceEvent(kind="new", listing_id=listing_id))
            continue
        if presence_then.get(listing_id) == "disappeared":
            events.append(DifferenceEvent(kind="returned", listing_id=listing_id))
            continue
        changes = _compare_fields(before, after)
        if changes:
            events.append(
                DifferenceEvent(
                    kind="changed",
                    listing_id=listing_id,
                    changes=changes,
                    price_change=_price_change(before, after),
                )
            )
        else:
            events.append(DifferenceEvent(kind="unchanged", listing_id=listing_id))

    # A listing is only gone on positive evidence. If any source failed or was unavailable, its
    # absence tells us nothing at all, so nothing is reported.
    if target.all_sources_succeeded:
        for listing_id in sorted(previous):
            if listing_id in observed_now:
                continue
            if presence_then.get(listing_id) == "disappeared":
                continue  # already gone before the baseline; not news again
            events.append(DifferenceEvent(kind="gone", listing_id=listing_id))

    return Comparison(
        search_name=search_name,
        baseline_run_id=baseline.id,
        target_run_id=target.id,
        events=tuple(events),
    )
