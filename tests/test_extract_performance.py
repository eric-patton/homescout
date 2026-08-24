"""Five thousand descriptions through the deterministic patterns, and what that costs a run.

Marked slow and excluded from the default run. The requirement is that with the model off,
extraction over five thousand properties adds no more than a few seconds, and it is worth measuring
rather than asserting because this feature deliberately does not cache its deterministic answers:
they are recomputed every time a criterion is evaluated. That is only the right decision while it is
cheap, and this is what keeps it honest.

The prose is real. Five thousand copies of one sentence would measure the regular expression
engine's caching rather than the work, so the corpus is cycled and each one is made distinct.
"""

from __future__ import annotations

import time

import pytest

from extract_fakes import described, load, texts
from homescout.extract import known_values, values_for
from homescout.rules.definition import Rule
from homescout.rules.parse import parse
from homescout.rules.verdicts import record
from homescout.store import Store

pytestmark = pytest.mark.slow

ROWS = 5_000

#: What "a few seconds" is taken to mean, with a wide margin over what was measured, because the
#: wall clock on somebody else's machine is not the property being claimed.
BUDGET_SECONDS = 10.0


class Prop:
    def __init__(self, description: str) -> None:
        self.description = description


def a_county(count: int = ROWS) -> list[str]:
    """Five thousand distinct descriptions, built from real ones."""
    corpus = texts()
    return [
        f"{corpus[index % len(corpus)]} Listing number {index}."
        for index in range(count)
    ]


def test_five_thousand_descriptions_cost_a_few_seconds(store: Store) -> None:
    """feat-009 performance: the deterministic pass, at the size of a county."""
    prose = a_county()

    started = time.perf_counter()
    found = [values_for(Prop(text)) for text in prose]
    took = time.perf_counter() - started

    assert len(found) == ROWS
    assert took < BUDGET_SECONDS, f"reading {ROWS} descriptions took {took:.1f}s"
    determined = sum(1 for reading in found for entry in reading.values() if entry.determined)
    assert determined > ROWS // 10, "and it was actually doing the work"


def test_the_cost_is_in_the_reading_rather_than_in_a_query(store: Store) -> None:
    """Nothing about the deterministic pass touches the database, which is why it can be recomputed.

    If this ever needs a store, the decision not to cache pattern results has to be revisited, and
    the failure here is the notice.
    """
    prose = a_county(500)
    values_for(Prop(prose[0]))  # warm any lazy imports

    started = time.perf_counter()
    for text in prose:
        known_values(values_for(Prop(text)))
    per_description = (time.perf_counter() - started) / len(prose)

    assert per_description < BUDGET_SECONDS / ROWS, (
        f"{per_description * 1000:.2f}ms per description leaves no room for five thousand"
    )


def test_evaluating_a_runs_criteria_over_a_county_stays_within_the_budget(store: Store) -> None:
    """The path that actually runs it: extraction happens inside rule evaluation, once per property.

    Smaller than five thousand because this one also pays for the store, the history and the
    verdicts, which are not what is being measured. What it proves is that adding extraction to that
    loop did not change its shape.
    """
    prose = a_county(1_000)
    loaded = load(store, [described(f"p{index:05d}", text) for index, text in enumerate(prose)])
    criteria = [
        Rule(
            id="well-only",
            when='water_source == "well"',
            severity="flag",
            expression=parse('water_source == "well"'),
        ),
        Rule(
            id="no-septic",
            when='sewer != "septic"',
            severity="demote",
            expression=parse('sewer != "septic"'),
        ),
    ]

    started = time.perf_counter()
    verdicts = record(store, criteria, loaded.run_id)
    took = time.perf_counter() - started

    assert len(verdicts) == 2_000
    assert took < 30.0, f"evaluating a thousand properties took {took:.1f}s"
    assert any(v.verdict == "fired" for v in verdicts), "and the extracted values reached the rules"
