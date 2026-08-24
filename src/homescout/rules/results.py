"""What a run's verdicts mean for what a person sees.

Read from the recorded verdicts rather than re-evaluated, so that what a surface shows and what the
database says can never differ, and so that a rule edited this morning does not change what last
night's run reported.

The four things a surface needs, and the rules that decide them:

- **What to show.** Everything the run kept, minus what a `drop` rule fired on. Excluded, never
  deleted: the property keeps its full history and can be asked for by name.
- **What to badge.** Every `flag` rule that fired, by identifier, so a badge means something
  specific.
- **What order.** Boosts up, demotes down, ties settled by the store's own stable order. A sort the
  caller asks for replaces this rather than being blended with it.
- **What was removed, and by what.** Per property and per rule, because an empty results table with
  no explanation is indistinguishable from a market that emptied out.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..records import ListingFields
from ..store import RuleVerdict, Store


@dataclass(frozen=True, slots=True)
class Result:
    """One property, as a run's criteria left it."""

    listing_id: str
    fields: ListingFields
    flags: tuple[str, ...] = ()
    #: Rule identifier to the names that were missing, for criteria nobody could answer.
    undetermined: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    boosted: tuple[str, ...] = ()
    demoted: tuple[str, ...] = ()

    @property
    def score(self) -> int:
        """Up for each boost that fired, down for each demote. The default order, as a number."""
        return len(self.boosted) - len(self.demoted)


@dataclass(frozen=True, slots=True)
class Excluded:
    """One property a criterion removed, and which criteria did it."""

    listing_id: str
    fields: ListingFields
    rules: tuple[str, ...]


def _fired(verdicts: Sequence[RuleVerdict], severity: str) -> tuple[str, ...]:
    return tuple(
        sorted(v.rule_id for v in verdicts if v.verdict == "fired" and v.severity == severity)
    )


def _snapshots(store: Store, run_id: str) -> dict[str, ListingFields]:
    return {s.listing_id: s.fields for s in store.snapshots_for_run(run_id)}


def results(
    store: Store,
    run_id: str,
    *,
    sort: str | None = None,
    descending: bool = False,
) -> tuple[Result, ...]:
    """What this run found, with its criteria applied.

    `sort` names a field to order by instead of the default. It is a field name rather than a
    function because ordering is a decision, and the constitution keeps decisions out of the
    surfaces that will offer this. A property with no value for that field sorts last whichever
    direction is asked for, because a missing price is not the cheapest house.
    """
    grouped = _by_listing(store.verdicts(run_id))
    fields = _snapshots(store, run_id)
    kept: list[Result] = []

    for listing_id, listing_fields in fields.items():
        verdicts = grouped.get(listing_id, [])
        if _fired(verdicts, "drop"):
            continue
        kept.append(
            Result(
                listing_id=listing_id,
                fields=listing_fields,
                flags=_fired(verdicts, "flag"),
                undetermined={
                    v.rule_id: v.missing for v in verdicts if v.verdict == "undetermined"
                },
                boosted=_fired(verdicts, "boost"),
                demoted=_fired(verdicts, "demote"),
            )
        )

    order = _stable_order(store, run_id)
    kept.sort(key=lambda r: order.get(r.listing_id, ("", r.listing_id)))

    if sort is None:
        # Stable order first, then score: Python's sort keeps the previous order among equals, so
        # two properties with the same score come out in the store's order rather than whichever
        # the dictionary happened to yield first.
        kept.sort(key=lambda r: -r.score)
        return tuple(kept)

    values = {r.listing_id: _sort_value(store, r, sort, run_id) for r in kept}
    present = [r for r in kept if values[r.listing_id] is not None]
    absent = [r for r in kept if values[r.listing_id] is None]
    present.sort(key=lambda r: values[r.listing_id], reverse=descending)
    # A property with no value for the chosen field sorts last whichever direction was asked for. A
    # missing price is not the cheapest house.
    return tuple([*present, *absent])


def excluded(store: Store, run_id: str) -> tuple[Excluded, ...]:
    """Everything a criterion removed from this run, with the criteria that removed it."""
    grouped = _by_listing(store.verdicts(run_id))
    fields = _snapshots(store, run_id)
    found = [
        Excluded(listing_id=listing_id, fields=fields[listing_id], rules=dropped)
        for listing_id, verdicts in sorted(grouped.items())
        if (dropped := _fired(verdicts, "drop")) and listing_id in fields
    ]
    return tuple(found)


def exclusion_counts(store: Store, run_id: str) -> dict[str, int]:
    """How many properties each criterion removed.

    The number that turns an empty results table from a mystery into a sentence. A search that
    dropped everything and a market with nothing in it look identical without it.
    """
    counts: dict[str, int] = {}
    for verdict_row in store.verdicts(run_id):
        if verdict_row.verdict == "fired" and verdict_row.severity == "drop":
            counts[verdict_row.rule_id] = counts.get(verdict_row.rule_id, 0) + 1
    return dict(sorted(counts.items()))


def newly_fired(
    store: Store,
    run_id: str,
    since_run_id: str | None,
    *,
    severities: Sequence[str] = ("flag",),
) -> dict[str, tuple[str, ...]]:
    """Which properties fired which criteria in this run and did not in the earlier one.

    Flags by default, because that is what a digest reports: a property that has been failing the
    same drop rule for a month is not news, and a badge appearing for the first time is.

    With no earlier run, everything that fired is new, which is the honest answer for a first run
    rather than a suspicious silence.
    """
    now = store.fired(run_id, severities=severities)
    before = store.fired(since_run_id, severities=severities) if since_run_id else {}
    fresh: dict[str, tuple[str, ...]] = {}
    for rule_id, listing_ids in sorted(now.items()):
        new = tuple(sorted(listing_ids - before.get(rule_id, set())))
        if new:
            fresh[rule_id] = new
    return fresh


def _by_listing(verdicts: Sequence[RuleVerdict]) -> dict[str, list[RuleVerdict]]:
    grouped: dict[str, list[RuleVerdict]] = {}
    for found in verdicts:
        grouped.setdefault(found.listing_id, []).append(found)
    return grouped


def _stable_order(store: Store, run_id: str) -> dict[str, tuple[str, str]]:
    """The tiebreak: first observation, then identifier. Total, and the same on every machine."""
    listings = {listing.id: listing for listing in store.listings()}
    return {
        listing_id: (listings[listing_id].first_observed_at, listing_id)
        for listing_id in (s.listing_id for s in store.snapshots_for_run(run_id))
        if listing_id in listings
    }


def _sort_value(store: Store, result: Result, sort: str, run_id: str) -> Any:
    """The value this property has for the field being sorted by, or nothing.

    A listing field comes off the snapshot already in hand. A derived one costs a look at that
    property's history, which is why it is asked for once per property rather than once per
    comparison.
    """
    from . import namespace as ns
    from .verdicts import values_for

    field_declared = ns.find(sort)
    if field_declared is None:
        return None
    if field_declared.origin == "listing":
        return getattr(result.fields, sort, None)
    if field_declared.origin == "derived":
        return values_for(store, result.listing_id, run_id=run_id).get(sort)
    return None
