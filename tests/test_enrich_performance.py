"""A fully cached area, at the size of a real county search.

Marked slow and excluded from the default run. The requirement is five thousand properties in under
five seconds with no network requests, and the reason it is a requirement is that this pass runs
before every export and every page of results: if reading what is already known costs a minute,
nobody will leave enrichment turned on.
"""

from __future__ import annotations

import time

import pytest

from conftest import do_run, prop
from enrich_fakes import CountingTransport, FakeProvider, session
from homescout.enrich.cache import key_for, read
from homescout.enrich.pass_ import run_pass
from homescout.store import Store

pytestmark = pytest.mark.slow

PROPERTIES = 5_000
BUDGET = 5.0


def test_a_fully_cached_area_is_read_in_seconds_and_asks_nobody(store: Store) -> None:
    """feat-007/NFR-performance: no requests, and the local work is bulk rather than a loop."""
    providers = [
        FakeProvider(name="flood", decimals=4),
        FakeProvider(name="elevation", supplies=("elevation_ft",),
                     answer={"elevation_ft": 4009.4}, decimals=3, ttl=None),
        FakeProvider(name="aquifer", supplies=("over_principal_aquifer",),
                     answer={"over_principal_aquifer": True}, decimals=2, ttl=None),
    ]
    places = [(34.0 + i / 5_000, -103.0 - i / 5_000) for i in range(PROPERTIES)]
    for provider in providers:
        for place in places:
            store.cache_values(
                provider.name,
                key_for(*place, provider.precision()),
                dict.fromkeys(provider.values(), "cached"),
            )

    started = time.perf_counter()
    found = read(store, providers, places)
    took = time.perf_counter() - started

    assert len(found) == PROPERTIES
    assert all(value.status == "fresh" for values in found.values() for value in values.values())
    assert took < BUDGET, f"{PROPERTIES} properties took {took:.2f}s to read"


def test_a_second_pass_over_a_cached_county_makes_no_requests(store: Store) -> None:
    """feat-007/AC-2: zero, counted rather than assumed, at a size where it would show."""
    rows = [
        prop(f"p{i}", latitude=34.0 + i / 2_000, longitude=-103.0 - i / 2_000) for i in range(300)
    ]
    do_run(store, sources={"realtor": rows})
    providers = [FakeProvider(decimals=3)]
    transport = CountingTransport()

    run_pass(store, providers, session=session(transport))
    asked = len(providers[0].asked)
    run_pass(store, providers, session=session(transport))

    assert 0 < asked < 300, "properties within a rounding step of each other shared a lookup"
    assert len(providers[0].asked) == asked, "the second pass asked again"


def test_the_nearest_data_centre_is_found_by_index_rather_than_by_walking_the_set() -> None:
    """feat-007/AC-37, feat-007/NFR-performance: the first pass over a new area, not the second.

    This provider is the one that makes the performance requirement's second sentence false. Every
    other one asks a service per location, so its cold pass is bounded by waiting; this one asks
    nobody, so its cold pass is bounded entirely by local work, and the requirement says that does
    not happen.

    The number is what makes it a real risk rather than a wording problem. Roughly three and a half
    thousand sites, asked once per cache key over an area of five thousand properties, is ten
    million comparisons, which a straightforward loop does in tens of seconds. The pre-build check
    caught this before any of it was written, and this test is what stops it coming back: a loop
    put back in place of the spatial index fails here rather than in six months on a real county.
    """
    import random

    from homescout.enrich import datacenters

    random.seed(11)
    # A stand-in for the two indexes at the size they actually are.
    sites = [
        {
            "name": f"site {n}",
            "kind": ("operating", "approved", "proposed")[n % 3],
            "confidence": "high",
            "latitude": random.uniform(25.0, 49.0),
            "longitude": random.uniform(-124.0, -67.0),
        }
        for n in range(3_400)
    ]
    nearby = datacenters.Nearby(sites)
    places = [
        (random.uniform(32.0, 36.9), random.uniform(-109.0, -103.0)) for _ in range(PROPERTIES)
    ]

    started = time.monotonic()
    for latitude, longitude in places:
        for kind in datacenters.MEASURED:
            nearby.nearest(kind, latitude, longitude)
        nearby.counties_holding(latitude, longitude)
    took = time.monotonic() - started

    assert took < BUDGET, (
        f"{PROPERTIES:,} properties against {len(sites):,} data centres took {took:.1f}s, over the "
        f"{BUDGET}s this feature allows. A walk over the set rather than a spatial index is the "
        "first thing to check."
    )


def _new_mexico_records():
    """Records the size of New Mexico's, over an outline that is a real shapely polygon, so the
    point-in-state lookup is timed along with everything else."""
    import random

    from shapely.geometry import box

    from homescout.enrich import dams, floods, kept

    rng = random.Random(7)

    def anywhere() -> tuple[float, float]:
        return 31.5 + rng.random() * 5.4, -109.0 + rng.random() * 6.0

    outlines = kept.Outlines({"NM": box(-109.05, 31.33, -103.0, 37.0),
                              "TX": box(-103.0, 25.8, -93.5, 36.5)})
    warned = []
    for event in range(3_500):
        lat, lon = anywhere()
        half = 0.05 + rng.random() * 0.2
        ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half],
                [lon - half, lat + half], [lon - half, lat - half]]
        warned.append({"office": "ABQ", "event": event, "year": 2008 + event % 19,
                       "issued": "2026-09-29T19:47:00Z", "emergency": event % 70 == 0,
                       "damage": None, "polygon": [[ring]]})
    reports = []
    for _ in range(2_000):
        lat, lon = anywhere()
        reports.append({"at": "2026-09-29T20:00:00Z", "latitude": lat, "longitude": lon,
                        "kind": "flash flood", "place": "", "county": "", "source": "",
                        "remark": ""})
    held = []
    for number in range(2_000):
        lat, lon = anywhere()
        held.append({"id": f"NM{number:05d}", "name": "a dam", "latitude": lat, "longitude": lon,
                     "condition": "poor", "assessed": None, "plan": None, "built": 1960,
                     "purpose": None, "owner": ""})
    places = [anywhere() for _ in range(PROPERTIES)]
    return (floods.Record(warned, reports, outlines), dams.Inventory(held, outlines), places)


def test_flash_floods_are_answered_by_index_for_five_thousand_properties() -> None:
    """feat-007/AC-55, feat-007/NFR-performance: three and a half thousand warning polygons and two
    thousand reports, asked about five thousand properties, through the real state lookup."""
    record, _inventory, places = _new_mexico_records()

    started = time.perf_counter()
    for place in places:
        record.answer(*place)
    took = time.perf_counter() - started

    assert took < BUDGET, f"{PROPERTIES} properties took {took:.2f}s against the warnings"


def test_dams_are_answered_by_index_for_five_thousand_properties() -> None:
    """feat-007/AC-55, feat-007/NFR-performance: two thousand dams, the nearest of them and the
    worst within ten miles, for five thousand properties, through the real state lookup."""
    _record, inventory, places = _new_mexico_records()

    started = time.perf_counter()
    for place in places:
        inventory.answer(*place)
    took = time.perf_counter() - started

    assert took < BUDGET, f"{PROPERTIES} properties took {took:.2f}s against the dams"
