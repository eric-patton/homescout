"""Five thousand rows, and the claim that they are not compared against each other.

Marked slow and excluded from the default run. The requirement is that a run of five thousand rows
does not require comparing every row against every other, and the reason it is a requirement is
arithmetic: five thousand rows is twelve and a half million pairs, and a merge pass that did that
would take longer than the throttled fetching it follows.

What is measured is the number of comparisons rather than the wall clock, because the wall clock on
somebody else's machine is not the property being claimed.
"""

from __future__ import annotations

import time

import pytest

from homescout.merge.pass_ import run_pass
from homescout.store import Store
from merge_fakes import load

pytestmark = pytest.mark.slow

ROWS = 5_000
#: A run over a county: a few thousand properties, most of them on one source, a good share on two
#: or three. Three sources of the same market is what makes the pairs worth comparing at all.
SOURCES = ("realtor", "zillow", "redfin")


def a_county(count: int = ROWS) -> list[dict]:
    """A market laid out as a grid of streets, with each property on one, two or three sources."""
    rows: list[dict] = []
    index = 0
    while len(rows) < count:
        street = index % 60
        number = 100 + (index // 60) * 2
        latitude = 34.0 + street * 0.004
        longitude = -103.5 + (index // 60) * 0.0009
        # Every third property is on all three sources, every second on two, the rest on one.
        on = SOURCES[: 3 if index % 3 == 0 else (2 if index % 2 == 0 else 1)]
        for offset, source in enumerate(on):
            rows.append(
                {
                    "source": source,
                    # The formatting disagreements the real corpus has, at scale.
                    "address_line": (
                        f"{number} Street{street} {'Ave' if offset else 'Avenue'}"
                        if offset < 2
                        else f"{number} Street{street}"
                    ),
                    "unit": None,
                    "city": "Everton",
                    "state": "NM",
                    "postal_code": "88888",
                    "latitude": round(latitude + offset * 0.00002, 7),
                    "longitude": round(longitude + offset * 0.00002, 7),
                    "price": 200_000 + index * 10,
                    "beds": 3,
                    "baths": 2,
                    "sqft": 1800,
                    "lot_sqft": 43_560,
                    "parcel_number": None,
                    "property_type": "single_family",
                }
            )
            if len(rows) >= count:
                break
        index += 1
    return rows


def test_five_thousand_rows_are_not_compared_against_each_other(store: Store) -> None:
    """feat-006 performance: bounded by how many rows share a bucket, not by the size of the run.

    The number to beat is not "fast": it is "not quadratic". A hundredth of every possible pair is
    the assertion, and the real figure is far under it, because the buckets hold two or three rows.
    """
    rows = a_county()
    load(store, rows)
    assert len(store.listings()) == len(rows)

    started = time.perf_counter()
    outcome = run_pass(store)
    took = time.perf_counter() - started

    every_pair = len(rows) * (len(rows) - 1) // 2
    assert outcome.compared < every_pair // 100, (
        f"{outcome.compared} comparisons out of a possible {every_pair}"
    )
    assert outcome.compared < len(rows) * 4, "and near-linear rather than merely sub-quadratic"
    assert took < 60, f"the pass took {took:.1f}s"


def test_the_pass_over_a_county_actually_merges_it(store: Store) -> None:
    """feat-006/AC-1: because a pass that compared nothing would pass the test above easily.

    Two thirds of this market is on more than one source, so two thirds of the rows must come out as
    somebody else's duplicate.
    """
    rows = a_county(2_000)
    load(store, rows)

    outcome = run_pass(store)

    assert len(store.listings()) < len(rows) * 0.6
    assert len(outcome.merged) > 400
    assert all(len(group) in (2, 3) for group in outcome.merged)


def test_the_queue_stays_usable_when_a_first_run_fills_it(store: Store) -> None:
    """feat-006, the spec's own edge case: a large queue is expected and must not be capped.

    Every pair here is genuinely ambiguous, because every property sits a hundred and fifty metres
    from its own other listing. The queue must hold all of them and count them, rather than
    truncating and reporting a number that is not the number.
    """
    rows = []
    for index in range(600):
        for offset, source in enumerate(SOURCES[:2]):
            rows.append(
                {
                    "source": source,
                    "address_line": f"{100 + index} Ambiguous Way",
                    "unit": None,
                    "city": "Everton",
                    "state": "NM",
                    "postal_code": "88888",
                    "latitude": round(34.0 + index * 0.004 + offset * 0.0015, 7),
                    "longitude": -103.5,
                    "price": 200_000,
                    "beds": 3, "baths": 2, "sqft": 1800, "lot_sqft": 43_560,
                    "parcel_number": None, "property_type": "single_family",
                }
            )
    load(store, rows)

    outcome = run_pass(store)

    assert outcome.merged == [], "a hundred and fifty metres apart is not a match"
    assert len(outcome.queued) == 600, "every one of them is asked about"
    assert len(store.listings()) == len(rows), "and nothing was merged provisionally"
