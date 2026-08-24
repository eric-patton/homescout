"""Fresh, stale, missing: three states, and the one that matters most is the third.

A value nobody fetched must never read as a negative answer. "We never looked" and "we looked and
there is no flood zone here" are different facts, and the second one is good news while the first
one is no news at all.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from enrich_fakes import FakeProvider
from homescout.enrich import cache
from homescout.store import Store

PLACE = (34.1848, -103.3452)
NEARBY = (34.18481, -103.34521)
FAR = (29.9511, -90.0715)


def test_a_value_never_fetched_is_missing_and_is_not_an_answer(store: Store) -> None:
    """feat-007/AC-7: missing is the absence of a value, not a value meaning no."""
    provider = FakeProvider()

    found = cache.values_for(store, [provider], *PLACE)

    assert found["flood_zone"].status == "missing"
    assert found["flood_zone"].value is None
    assert found["flood_zone"].known is False
    assert cache.known_values(found) == {}, "nothing is handed on as if it were an answer"


def test_a_value_fetched_and_empty_is_an_answer(store: Store) -> None:
    """feat-007/AC-7: the spec's first edge case, and the distinction the feature turns on.

    A point outside every mapped flood zone has been asked about. That is not the same as a point
    nobody asked about, and conflating them is how "nobody checked" becomes "no flood risk".
    """
    provider = FakeProvider()
    store.cache_values(provider.name, cache.key_for(*PLACE, provider.precision()),
                       {"flood_zone": None})

    found = cache.values_for(store, [provider], *PLACE)

    assert found["flood_zone"].status == "fresh"
    assert found["flood_zone"].value is None
    assert found["flood_zone"].known is True
    assert cache.known_values(found) == {"flood_zone": None}


def test_a_value_past_its_lifetime_is_stale_and_still_used(store: Store) -> None:
    """feat-007/AC-7: out of date beats absent, for facts that change on the scale of decades."""
    provider = FakeProvider(ttl=30)
    store.cache_values(provider.name, cache.key_for(*PLACE, provider.precision()),
                       {"flood_zone": "AE"})

    later = datetime.now(UTC) + timedelta(days=45)
    found = cache.values_for(store, [provider], *PLACE, now=later)

    assert found["flood_zone"].status == "stale"
    assert found["flood_zone"].value == "AE"
    assert cache.known_values(found) == {"flood_zone": "AE"}


def test_a_value_that_never_expires_is_always_fresh(store: Store) -> None:
    """feat-007/AC-1: a provider declares its own lifetime, and the ground has none."""
    provider = FakeProvider(name="elevation", supplies=("elevation_ft",), ttl=None)
    store.cache_values(provider.name, cache.key_for(*PLACE, provider.precision()),
                       {"elevation_ft": 4009.4})

    much_later = datetime.now(UTC) + timedelta(days=9_999)
    found = cache.values_for(store, [provider], *PLACE, now=much_later)

    assert found["elevation_ft"].status == "fresh"


def test_two_places_that_round_together_share_one_answer(store: Store) -> None:
    """feat-007/AC-3: which is most of the saving on a street of houses."""
    provider = FakeProvider(decimals=3)
    store.cache_values(provider.name, cache.key_for(*PLACE, 3), {"flood_zone": "X"})

    assert cache.key_for(*PLACE, 3) == cache.key_for(*NEARBY, 3)
    assert cache.values_for(store, [provider], *NEARBY)["flood_zone"].value == "X"
    assert cache.values_for(store, [provider], *FAR)["flood_zone"].status == "missing"


def test_precision_is_the_providers_own(store: Store) -> None:
    """feat-007/AC-3: a flood boundary can run down the middle of a street, and elevation cannot.

    Two points about forty metres apart. The coarse provider treats them as one place and asks once;
    the fine one treats them as two, because between them there could be a boundary that decides
    whether a house needs flood insurance.
    """
    here, there = (34.1848, -103.3452), (34.1846, -103.3455)

    assert cache.key_for(*here, 2) == cache.key_for(*there, 2)
    assert cache.key_for(*here, 4) != cache.key_for(*there, 4)
    assert FakeProvider(decimals=2).precision() < FakeProvider(decimals=4).precision()


def test_a_property_with_no_location_has_nothing_to_look_up(store: Store) -> None:
    """feat-007/AC-10: not a failure, and not a request either."""
    provider = FakeProvider()

    found = cache.values_for(store, [provider], None, None)

    assert found["flood_zone"].status == "missing"


def test_reading_many_places_is_one_query_per_provider(store: Store) -> None:
    """feat-007/NFR-performance: the shape that makes five thousand properties possible.

    Counted rather than timed: a query per property per provider is the implementation that misses
    the budget, and counting is how a test says so on any machine.
    """
    provider = FakeProvider()
    places = [(34.0 + i / 10_000, -103.0 - i / 10_000) for i in range(200)]
    for place in places:
        store.cache_values(provider.name, cache.key_for(*place, provider.precision()),
                           {"flood_zone": "X"})

    queries: list[str] = []
    store.connection.set_trace_callback(queries.append)
    try:
        found = cache.read(store, [provider], places)
    finally:
        store.connection.set_trace_callback(None)

    assert len(found) == len(places)
    selects = [q for q in queries if q.strip().upper().startswith("SELECT")]
    assert len(selects) == 1, f"{len(selects)} queries for one provider"
