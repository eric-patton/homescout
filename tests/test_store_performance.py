"""The stated bounds, measured rather than assumed.

Marked slow and excluded from the default run, because a suite that takes a minute stops being run
and a suite that never runs protects nothing.

    uv run pytest -m slow tests/test_store_performance.py
"""

from __future__ import annotations

import time

import pytest

from conftest import do_run, prop
from homescout.store import Store

PROPERTIES = 5_000
WRITE_BUDGET_SECONDS = 10.0
COMPARE_BUDGET_SECONDS = 5.0


def _market(count: int, *, price: int = 300_000) -> list:
    return [
        prop(
            f"p{index:05d}",
            price=price + index,
            address_line=f"{index} Example Road",
            postal_code=f"88{index % 1000:03d}",
        )
        for index in range(count)
    ]


@pytest.mark.slow
def test_writing_a_full_run_stays_within_budget(store: Store) -> None:
    """feat-001: one run's observations for 5,000 properties, written in under ten seconds."""
    started = time.perf_counter()
    do_run(store, sources={"realtor": _market(PROPERTIES)})
    elapsed = time.perf_counter() - started

    assert len(store.listings()) == PROPERTIES
    assert elapsed < WRITE_BUDGET_SECONDS, f"took {elapsed:.1f}s"


@pytest.mark.slow
def test_comparing_two_full_runs_stays_within_budget(store: Store) -> None:
    """feat-001: the comparison over 5,000 properties, in under five seconds.

    Half the market moves, a tenth of it vanishes and a tenth of it is new, so this is not the easy
    case where almost everything is unchanged.
    """
    do_run(store, sources={"realtor": _market(PROPERTIES)})

    moved = _market(PROPERTIES // 2, price=290_000)
    still = _market(PROPERTIES)[PROPERTIES // 2 : PROPERTIES - PROPERTIES // 10]
    fresh = [prop(f"n{index:05d}") for index in range(PROPERTIES // 10)]
    second = do_run(store, sources={"realtor": moved + still + fresh})

    started = time.perf_counter()
    comparison = store.compare("test-search", target_run_id=second.id)
    elapsed = time.perf_counter() - started

    counts = comparison.counts
    assert counts["changed"] == PROPERTIES // 2
    assert counts["new"] == PROPERTIES // 10
    assert counts["gone"] == PROPERTIES // 10
    assert elapsed < COMPARE_BUDGET_SECONDS, f"took {elapsed:.1f}s"


@pytest.mark.slow
def test_a_year_of_runs_does_not_degrade_the_comparison(store: Store) -> None:
    """feat-001: the bound holds against accumulated history, not just against an empty file.

    Fewer properties than the other two, over many runs, because what is being measured here is
    whether a comparison slows down as history piles up underneath it.
    """
    market = _market(200)
    for _ in range(60):
        do_run(store, sources={"realtor": market})

    last = do_run(store, sources={"realtor": market})
    started = time.perf_counter()
    store.compare("test-search", target_run_id=last.id)
    elapsed = time.perf_counter() - started

    assert elapsed < COMPARE_BUDGET_SECONDS, f"took {elapsed:.1f}s"
