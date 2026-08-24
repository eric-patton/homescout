"""The compact summary of what moved.

A run over a county holds thousands of properties, and all of them are already in the store. What a
scheduled agent needs is the part that changed, small enough to read in full and reason about. So
this document carries counts for everything and rows only for what moved: over N properties of which
K changed, its size is a function of K and not of N.

One shape covers a run, a run of everything, and a comparison, and every key is always present, so
a reader never branches on shape. For a comparison there are no sources, and the list is empty
rather than missing.

Scheduling and digests (feat-012) consumes this unchanged: it writes the document to a path and
renders the email from these per-property summaries and their stored image paths.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from .records import ListingFields
from .runner import RunOutcome
from .store import Comparison, DifferenceEvent, Store, utc_now

DIGEST_VERSION = 1

#: What one property looks like in a digest. Enough for an email to show it and a person to decide
#: whether to look, and no more: the record itself is in the store.
SUMMARY_FIELDS: tuple[str, ...] = (
    "address_line",
    "unit",
    "city",
    "state",
    "postal_code",
    "price",
    "beds",
    "baths",
    "sqft",
    "property_type",
    "listing_status",
    "listing_url",
)


def _summary(store: Store, listing_id: str, *run_ids: str | None) -> dict[str, Any]:
    """One property, as small as it can be while still being worth reading.

    Days on market comes from the store's own history, computed from this tool's first observation.
    The record also carries whatever the site claimed about days on market; that field is never read
    here, because freshness is computed from local history (product invariant 7) and the source's
    own claim exists only so it stays visible as evidence.
    """
    fields: ListingFields | None = None
    for run_id in run_ids:
        if run_id is None:
            continue
        snapshot = store.snapshot_at(listing_id, run_id)
        if snapshot is not None:
            fields = snapshot.fields
            break

    history = store.history(listing_id)
    image = store.get_preview_image(listing_id)
    summary: dict[str, Any] = {"listing_id": listing_id}
    for name in SUMMARY_FIELDS:
        summary[name] = getattr(fields, name, None) if fields is not None else None
    summary["image"] = image.path if image else None
    summary["first_observed_at"] = history.first_observed_at
    summary["days_on_market"] = history.days_on_market
    return summary


def _price_change(event: DifferenceEvent) -> dict[str, Any] | None:
    change = event.price_change
    if change is None:
        return None
    return {
        "before": change.before,
        "after": change.after,
        "amount": change.amount,
        "direction": change.direction,
    }


def _status_change(event: DifferenceEvent) -> dict[str, Any] | None:
    for field in event.changes:
        if field.field == "listing_status":
            return {"before": field.before, "after": field.after}
    return None


def _other_changes(event: DifferenceEvent) -> list[dict[str, Any]]:
    return [
        {"field": f.field, "before": f.before, "after": f.after}
        for f in event.changes
        if f.field not in ("price", "listing_status")
    ]


def entry(
    store: Store,
    *,
    search_name: str,
    comparison: Comparison,
    outcome: RunOutcome | None = None,
) -> dict[str, Any]:
    """One saved search's part of a digest."""
    target = comparison.target_run_id
    baseline = comparison.baseline_run_id
    counts = comparison.counts

    def summarize(event: DifferenceEvent) -> dict[str, Any]:
        # A property that is gone was not observed by the target run, so its last known state comes
        # from the baseline. Everything else is described by the run that just happened.
        order = (baseline, target) if event.kind == "gone" else (target, baseline)
        return _summary(store, event.listing_id, *order)

    new: list[dict[str, Any]] = []
    price_changes: list[dict[str, Any]] = []
    status_changes: list[dict[str, Any]] = []
    other_changes: list[dict[str, Any]] = []
    gone: list[dict[str, Any]] = []
    returned: list[dict[str, Any]] = []

    for event in comparison.events:
        if event.kind == "new":
            new.append(summarize(event))
        elif event.kind == "gone":
            gone.append(summarize(event))
        elif event.kind == "returned":
            returned.append(summarize(event))
        elif event.kind == "changed":
            price = _price_change(event)
            status = _status_change(event)
            others = _other_changes(event)
            if price is not None:
                price_changes.append({**summarize(event), "price_change": price})
            if status is not None:
                status_changes.append({**summarize(event), "status_change": status})
            if others:
                other_changes.append({**summarize(event), "fields": others})

    matched = counts["new"] + counts["changed"] + counts["unchanged"] + counts["returned"]
    sources = [
        {
            "source": report.source,
            "outcome": report.outcome,
            "rows": report.rows,
            "truncated": report.truncated,
            "detail": report.detail,
            "applied_by_source": list(report.applied_by_source),
            "applied_locally": list(report.applied_locally),
            "not_locatable": report.not_locatable,
        }
        for report in (outcome.sources if outcome else ())
    ]

    return {
        "name": search_name,
        "run_id": target,
        "baseline_run_id": baseline,
        "started_at": outcome.run.started_at if outcome else None,
        "finished_at": outcome.run.finished_at if outcome else None,
        "outcome": (("degraded" if outcome.degraded else "ok") if outcome else None),
        "sources": sources,
        "counts": {
            "matched": matched,
            "new": counts["new"],
            "changed": counts["changed"],
            "gone": counts["gone"],
            "returned": counts["returned"],
            # Always present and always empty until the rule engine exists, so that the shape of
            # this document never depends on whether that feature has been built.
            "flagged": 0,
        },
        "new": new,
        "price_changes": price_changes,
        "status_changes": status_changes,
        "other_changes": other_changes,
        "gone": gone,
        "returned": returned,
        "flagged": [],
    }


def envelope(kind: str, *, generated_at: str | None = None, **payload: Any) -> dict[str, Any]:
    """What every structured answer this tool gives is wrapped in.

    One shape for every command, so a reader parses the outside once and then looks at `kind`.
    `generated_at` is the envelope rather than the answer: it is the only part that differs between
    two identical requests, which is what lets a comparison be reproducible while still being
    stamped.
    """
    return {
        "homescout": {
            "digest_version": DIGEST_VERSION,
            "generated_at": generated_at or utc_now(),
        },
        "kind": kind,
        **payload,
    }


def build(
    entries: Iterable[dict[str, Any]],
    *,
    kind: str,
    skipped: Sequence[dict[str, Any]] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """The whole digest: one entry per saved search, and what could not be run."""
    return envelope(
        kind,
        generated_at=generated_at,
        searches=list(entries),
        skipped=list(skipped),
    )
