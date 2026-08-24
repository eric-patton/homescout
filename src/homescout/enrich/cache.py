"""Reading what has already been asked, and telling three states apart.

**Fresh** is cached and within its lifetime. **Stale** is cached and past it: still the best answer
anyone has, still used, and labelled. **Missing** was never obtained, and is not a value at all.

Keeping the third distinct from the second is the point of the module. A property whose aquifer was
never looked up must not read as "not over an aquifer", because that is good news nobody has earned.
Downstream, missing simply does not appear in the mapping a criterion sees, which the rule engine's
three-valued logic already reads as unknown.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from ..store import Store
from .provider import Provider

Status = Literal["fresh", "stale", "missing"]


@dataclass(frozen=True, slots=True)
class Value:
    """One enriched value, and how much to trust its age."""

    value: Any
    status: Status
    fetched_at: str | None = None

    @property
    def known(self) -> bool:
        """Was this ever asked? A known value may still be `None`, which is a real answer."""
        return self.status != "missing"


def key_for(latitude: float, longitude: float, precision: int) -> str:
    """The cache key for a place, at one provider's precision.

    Rounding is what makes a street of houses one lookup rather than forty. It is per provider
    because the right precision differs: a flood boundary can run down the middle of a road, and
    elevation over a hundred metres is the same number.
    """
    return f"{round(latitude, precision):.{precision}f},{round(longitude, precision):.{precision}f}"


def _age_days(fetched_at: str, now: datetime) -> float:
    try:
        when = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return (now - when).total_seconds() / 86_400


def status_of(provider: Provider, fetched_at: str, *, now: datetime | None = None) -> Status:
    ttl = provider.ttl_days()
    if ttl is None:
        return "fresh"
    return "fresh" if _age_days(fetched_at, now or datetime.now(UTC)) <= ttl else "stale"


def read(
    store: Store,
    providers: Sequence[Provider],
    places: Sequence[tuple[float, float]],
    *,
    now: datetime | None = None,
) -> dict[tuple[float, float], dict[str, Value]]:
    """Every cached value for these places, in one query per provider.

    In bulk deliberately. Five providers against five thousand properties is twenty-five thousand
    lookups, and a query each would spend the whole performance budget on round trips to a file on
    the same disk.
    """
    moment = now or datetime.now(UTC)
    answer: dict[tuple[float, float], dict[str, Value]] = {place: {} for place in places}

    for provider in providers:
        precision = provider.precision()
        keys = {place: key_for(*place, precision) for place in places}
        held = store.cached_values(provider.name, tuple(keys.values()))
        for place, key in keys.items():
            found = held.get(key, {})
            for name in provider.values():
                cached = found.get(name)
                if cached is None:
                    answer[place][name] = Value(None, "missing")
                    continue
                answer[place][name] = Value(
                    cached.value,
                    status_of(provider, cached.fetched_at, now=moment),
                    cached.fetched_at,
                )
    return answer


def values_for(
    store: Store,
    providers: Sequence[Provider],
    latitude: float | None,
    longitude: float | None,
    *,
    now: datetime | None = None,
) -> dict[str, Value]:
    """What is known about one place. Everything is missing when there is no place."""
    if latitude is None or longitude is None:
        return {
            name: Value(None, "missing") for provider in providers for name in provider.values()
        }
    return read(store, providers, [(latitude, longitude)], now=now)[(latitude, longitude)]


def known_values(found: Mapping[str, Value]) -> dict[str, Any]:
    """Just the values that were actually obtained, for handing to something that evaluates.

    A missing value is left out rather than passed as `None`, because the thing on the other side
    treats absent as unknown, and unknown is exactly what it is. A value that was obtained and came
    back empty *is* passed, as `None`, and reads as unknown too: this tool does not distinguish an
    empty value from an undeterminable one anywhere else either (product invariant 10).
    """
    return {name: value.value for name, value in found.items() if value.known}
