"""Criteria against the size of market they will actually meet.

Marked slow and excluded from the default run. Five thousand properties by ten criteria is fifty
thousand verdicts, which is a county-sized search with a well-tuned set of rules, and the spec says
it has to be a small fraction of a run rather than a second pass over the market.
"""

from __future__ import annotations

import time

import pytest

from homescout.rules.definition import read
from homescout.rules.evaluate import verdict

pytestmark = pytest.mark.slow

PROPERTIES = 5_000
BUDGET = 2.0

SECTION = [
    {"id": "stale", "when": "dom > 180", "severity": "flag"},
    {"id": "very-stale", "when": "dom > 365", "severity": "demote"},
    {"id": "cheap", "when": "price < 300000", "severity": "boost"},
    {"id": "dear", "when": "price > 800000", "severity": "drop"},
    {"id": "small", "when": "sqft < 1200", "severity": "demote"},
    {"id": "acreage", "when": "lot_sqft > 200000", "severity": "boost"},
    {"id": "old", "when": "year_built < 1970", "severity": "flag"},
    {"id": "kind", "when": "property_type in ['single_family', 'farm']", "severity": "boost"},
    {"id": "per-foot", "when": "price / sqft < 150", "severity": "boost"},
    {"id": "no-fiber", "when": "upload_mbps < 100", "severity": "flag"},
]


def test_fifty_thousand_verdicts_are_a_small_fraction_of_a_run() -> None:
    """feat-008/NFR-performance: linear in properties and rules, and quick at both.

    The last criterion names a value nothing fills yet, so a tenth of this measurement is the
    undetermined path, which is the one that also has to be fast: a search whose enrichment has not
    run yet is the normal state of a new installation.
    """
    rules, problems = read(SECTION)
    assert not [p for p in problems if p.severity == "problem"], problems

    properties = [
        {
            "dom": index % 400,
            "price": 100_000 + (index % 900) * 1_000,
            "sqft": 800 + (index % 30) * 100,
            "lot_sqft": 5_000 + (index % 50) * 10_000,
            "year_built": 1950 + (index % 70),
            "property_type": "single_family" if index % 3 else "condo",
        }
        for index in range(PROPERTIES)
    ]

    started = time.perf_counter()
    answers = [
        verdict(rule.expression, values) for values in properties for rule in rules
    ]
    took = time.perf_counter() - started

    assert len(answers) == PROPERTIES * len(SECTION)
    assert {answer for answer, _ in answers} == {"fired", "not-fired", "undetermined"}
    assert took < BUDGET, f"{len(answers):,} verdicts took {took:.2f}s"
