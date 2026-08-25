"""The enrichment pass: which places, which providers, and what happened.

Its own pass, not part of a run. A listing run asks sources for listings and stops; this walks what
the store already holds and fills in what the public record says about where those properties are.
Separate because the two have nothing to do with each other's pacing: a backfill over a county is
thousands of points at a second each, and no nightly run should wait for it.

The rule the whole thing is built around is that one dead service costs one column. Every provider
is asked independently, a failure is recorded against that provider and nothing else, and a cached
value is never removed by a failure: it simply stops being fresh.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..store import Store
from . import cache, settings
from .provider import Provider, ProviderFailed


@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    """How one provider did, in the same shape a run reports a source.

    `skipped` is not a failure: a provider that needs a token nobody supplied has not been asked and
    has not broken. Telling those apart is the difference between "go and get a key" and "the
    government is down".
    """

    provider: str
    outcome: str  # ok | failed | skipped
    looked_up: int = 0
    cached: int = 0
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class PassOutcome:
    properties: int = 0
    without_location: int = 0
    providers: tuple[ProviderOutcome, ...] = ()
    #: Listing identifiers that carried no usable coordinates, so nothing was asked about them. A
    #: recorded reason distinct from any provider failure (AC-10).
    unlocatable: tuple[str, ...] = field(default_factory=tuple)

    @property
    def degraded(self) -> bool:
        return any(found.outcome == "failed" for found in self.providers)


def places_in(
    store: Store, *, search: str | None = None
) -> tuple[list[tuple[str, tuple[float, float]]], list[str]]:
    """Every property worth asking about, and the ones with nowhere to ask about.

    A property with no coordinates is not an error and not a failure. It is a property nobody can
    look up, recorded as that and skipped without a request.
    """
    if search is None:
        listings = [listing.id for listing in store.listings()]
    else:
        runs = store.runs(search, only_completed=True)
        seen: dict[str, None] = {}
        for run in runs:
            for snapshot in store.snapshots_for_run(run.id):
                seen[snapshot.listing_id] = None
        listings = list(seen)

    located: list[tuple[str, tuple[float, float]]] = []
    unlocatable: list[str] = []
    for listing_id in listings:
        fields = _latest_fields(store, listing_id)
        if fields is None or fields.latitude is None or fields.longitude is None:
            unlocatable.append(listing_id)
            continue
        located.append((listing_id, (fields.latitude, fields.longitude)))
    return located, unlocatable


def _latest_fields(store: Store, listing_id: str) -> Any:
    history = store.history(listing_id)
    if not history.prices:
        return None
    latest = history.prices[-1].run_id
    snapshot = store.snapshot_at(listing_id, latest)
    return snapshot.fields if snapshot is not None else None


def run_pass(
    store: Store,
    providers: Sequence[Provider],
    *,
    search: str | None = None,
    stale_only: bool = False,
    session: Any = None,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome:
    """Ask every provider about every place that needs it, once each."""
    say = progress or (lambda _message: None)
    # One provider holds a dataset rather than only asking a service, and the store is where that
    # dataset lives. A hook rather than a parameter, so the other five keep the protocol they have
    # and the pass still never names a provider (feat-007 D-12).
    for provider in providers:
        attach = getattr(provider, "attach", None)
        if attach is not None:
            attach(store)

    located, unlocatable = places_in(store, search=search)
    places = [place for _, place in located]
    held = cache.read(store, providers, places) if places else {}

    outcomes: list[ProviderOutcome] = []
    paced = session or _session(providers)

    for provider in providers:
        if not provider.configured():
            reason = getattr(provider, "why_not", lambda: "not configured")()
            outcomes.append(ProviderOutcome(provider.name, "skipped", detail=reason))
            say(f"{provider.name}: skipped, {reason}")
            continue

        wanted = _keys_to_ask(provider, places, held, stale_only=stale_only)
        looked_up = 0
        failure: str | None = None
        for key, place in wanted.items():
            try:
                found = provider.fetch(paced, place[0], place[1])
            except ProviderFailed as exc:
                # One column, not a run. Whatever was cached stays exactly as it was, and reads as
                # stale rather than disappearing.
                failure = str(exc)
                break
            except Exception as exc:  # noqa: BLE001 - deliberately the end of the line
                failure = f"{provider.name} failed unexpectedly: {exc}"
                break
            store.cache_values(provider.name, key, dict(found))
            looked_up += 1

        outcomes.append(
            ProviderOutcome(
                provider=provider.name,
                outcome="failed" if failure else "ok",
                looked_up=looked_up,
                cached=len(places) - len(wanted),
                detail=failure,
            )
        )
        say(f"{provider.name}: {'failed' if failure else 'ok'}, {looked_up} looked up")

    return PassOutcome(
        properties=len(located),
        without_location=len(unlocatable),
        providers=tuple(outcomes),
        unlocatable=tuple(unlocatable),
    )


def _keys_to_ask(
    provider: Provider,
    places: Sequence[tuple[float, float]],
    held: dict[tuple[float, float], dict[str, cache.Value]],
    *,
    stale_only: bool,
) -> dict[str, tuple[float, float]]:
    """One entry per distinct rounded place this provider still needs.

    Distinct is where the saving is: two properties on one street round to one key and are one
    lookup (AC-3). A key whose values are all fresh is not asked at all, which is what makes a
    second pass cost nothing (AC-2).

    `stale_only` narrows it further, to places that were asked about before and have aged. The two
    passes are for two different days: filling in a county nobody has enriched is thousands of
    requests at a second each, and topping up what has gone out of date is a handful. A pass that
    could not tell them apart would make the cheap one impossible to ask for.
    """
    wanted: dict[str, tuple[float, float]] = {}
    for place in places:
        key = cache.key_for(*place, provider.precision())
        if key in wanted:
            continue
        states = [held.get(place, {}).get(name) for name in provider.values()]
        if all(value is not None and value.status == "fresh" for value in states):
            continue
        aged = any(value is not None and value.status == "stale" for value in states)
        if stale_only and not aged:
            continue
        wanted[key] = place
    return wanted


def _session(providers: Sequence[Provider]) -> Any:
    from ..sources import default_session

    names = tuple(provider.name for provider in providers)
    return default_session(config=settings.pacing(names))
