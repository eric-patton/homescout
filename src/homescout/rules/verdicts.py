"""Evaluating a run's criteria, and writing down what they decided.

Two things here are worth reading before changing anything.

**The values come from one place per property, not one place per rule.** A criterion naming `dom`
and another naming `price_cut` both read the same history, and reading it twice per property per
rule is how an evaluation pass that should take milliseconds takes a minute.

**The verdicts are written down.** They could be recomputed on demand from the snapshot, and that
would be wrong: editing a criterion tomorrow would change what a run decided last week, and every
past digest would quietly disagree with the database it came from. A run's decisions are history,
and history here is append-only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ..records import FIELD_NAMES
from ..store import ListingHistory, RuleVerdict, Snapshot, Store
from . import namespace as ns
from .definition import Rule
from .evaluate import verdict

#: The listing fields a rule may name, read from the namespace rather than restated so the two
#: cannot drift apart.
_LISTING_NAMES = tuple(
    name for name in FIELD_NAMES if (found := ns.find(name)) and found.origin == "listing"
)


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def values_for(
    store: Store,
    listing_id: str,
    *,
    run_id: str | None = None,
    at: str | None = None,
    snapshot: Snapshot | None = None,
    enriched: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything a criterion may ask about one property, gathered once.

    A name absent from this mapping, or present with no value, is unknown to the evaluator, which is
    exactly right for an enriched value nobody has fetched: the rule is undetermined rather than
    false. Enriched and extracted names are absent entirely until the features that fill them exist,
    and absent and empty mean the same thing here on purpose.
    """
    values: dict[str, Any] = {}

    # A caller walking a run already holds every snapshot in it. Asking the store for each one again
    # is a query per property, on top of the one per property the history costs.
    if snapshot is None and run_id is not None:
        snapshot = store.snapshot_at(listing_id, run_id)
    if snapshot is not None:
        values.update({name: getattr(snapshot.fields, name, None) for name in _LISTING_NAMES})

    if enriched is None and snapshot is not None:
        enriched = _enriched(store, snapshot.fields.latitude, snapshot.fields.longitude)
    values.update(enriched or {})

    history = store.history(listing_id, as_of=at)
    prices = [entry.price for entry in history.prices if entry.price is not None]
    values["dom"] = history.days_on_market
    values["presence"] = history.presence
    values["price_cut"] = any(
        later < earlier for earlier, later in zip(prices, prices[1:], strict=False)
    )
    values["price_raised_after_days"] = _raised_after(history)
    if run_id is not None:
        values["is_new"] = store.get_listing(listing_id).created_in_run == run_id
    return values


def _enriched(store: Store, latitude: float | None, longitude: float | None) -> dict[str, Any]:
    """What the public record says about where this property is, if anybody has asked.

    Read from the cache and never fetched here. A criterion is evaluated inside a loop over every
    property a run saw, and a lookup in that loop would be a paced network request per property;
    enrichment is its own pass for exactly that reason. A value nobody has fetched is simply absent,
    which the evaluator already reads as unknown, which is what the spec asks for.
    """
    from ..enrich.cache import known_values
    from ..enrich.cache import values_for as enriched_values_for
    from ..enrich.registry import create

    return known_values(enriched_values_for(store, create(), latitude, longitude))


def _raised_after(history: ListingHistory) -> int | None:
    """Days from our first sighting to the first time the price went up, or nothing.

    A price rising late is worth flagging and is invisible in any single response: it exists only in
    a comparison between two of our own observations.
    """
    entries = [entry for entry in history.prices if entry.price is not None]
    for earlier, later in zip(entries, entries[1:], strict=False):
        if later.price is not None and earlier.price is not None and later.price > earlier.price:
            first = _moment(history.first_observed_at)
            return max(0, (_moment(later.observed_at) - first).days)
    return None


def evaluate_run(
    store: Store, rules: Sequence[Rule], run_id: str
) -> tuple[RuleVerdict, ...]:
    """Every criterion against every property this run saw, in a stable order.

    Ordered by property and then by the order the rules are written in the file, so that two
    evaluations of the same run produce the same rows in the same sequence. A recorded fact that
    depends on dictionary ordering is not a reproducible one.
    """
    if not rules:
        return ()
    run = store.get_run(run_id)
    at = run.finished_at or run.started_at
    snapshots = store.snapshots_for_run(run_id)
    enriched = _enriched_for_all(store, snapshots)
    found: list[RuleVerdict] = []
    for snapshot in snapshots:
        values = values_for(
            store,
            snapshot.listing_id,
            run_id=run_id,
            at=at,
            snapshot=snapshot,
            enriched=enriched.get(snapshot.listing_id, {}),
        )
        for rule in rules:
            answer, missing = verdict(rule.expression, values)
            found.append(
                RuleVerdict(
                    run_id=run_id,
                    listing_id=snapshot.listing_id,
                    rule_id=rule.id,
                    severity=rule.severity,
                    verdict=answer,
                    missing=missing,
                )
            )
    return tuple(found)


def _enriched_for_all(store: Store, snapshots: Sequence[Snapshot]) -> dict[str, dict[str, Any]]:
    """Every property's enriched values, in one query per provider rather than one per property."""
    from ..enrich.cache import known_values, read
    from ..enrich.registry import create

    providers = create()
    places = [
        (s.fields.latitude, s.fields.longitude)
        for s in snapshots
        if s.fields.latitude is not None and s.fields.longitude is not None
    ]
    held = read(store, providers, places) if places else {}
    found: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        place = (snapshot.fields.latitude, snapshot.fields.longitude)
        found[snapshot.listing_id] = known_values(held.get(place, {}))
    return found


def record(store: Store, rules: Sequence[Rule], run_id: str) -> tuple[RuleVerdict, ...]:
    """Evaluate this run's criteria and write the answers down."""
    found = evaluate_run(store, rules, run_id)
    store.record_verdicts(run_id, found)
    return found
