"""The exact test, against the size of market it will actually meet.

Marked slow and excluded from the default run: it builds a shape with thousands of vertices and
tests five thousand properties against it, which is the shape of a real county search with a
hand-drawn boundary.

The budget matters because this runs inside the loop, once per property per source. A test that only
proved a hundred points would prove nothing about the case that hurts: a detailed shape, asked the
same question thousands of times.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest

from homescout.records import ListingFields
from homescout.search import Placement
from searches_fakes import catalog, sourced, write

pytestmark = pytest.mark.slow

#: The spec's non-functional requirement, in seconds.
BUDGET = 2.0

VERTICES = 3_000
PROPERTIES = 5_000


def many_sided(centre: tuple[float, float], radius: float, sides: int) -> list[list[float]]:
    """A shape with as many corners as a hand-drawn county boundary, and then some."""
    latitude, longitude = centre
    ring = [
        [
            longitude + radius * math.cos(2 * math.pi * i / sides),
            latitude + radius * math.sin(2 * math.pi * i / sides),
        ]
        for i in range(sides)
    ]
    return [*ring, ring[0]]


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake"):
        yield


def test_five_thousand_properties_against_a_detailed_shape_stay_inside_the_budget(
    tmp_path: Path,
) -> None:
    """feat-004/NFR-performance: under two seconds, including a many-vertex polygon."""
    ring = many_sided((34.2, -103.35), 0.25, VERTICES)
    write(
        tmp_path / "searches",
        "big",
        text=(
            "name: big\nareas:\n"
            f"  - {{type: polygon, geometry: {{type: Polygon, coordinates: [{ring}]}}}}\n"
            "sources: [fake]\n"
        ),
    )
    definition = catalog(tmp_path / "searches").load("big")

    # Half inside, half outside, so neither answer is reached by luck.
    properties = [
        ListingFields(
            latitude=34.2 + (0.001 * (i % 100)) * (1 if i % 2 else 4),
            longitude=-103.35 + 0.001 * (i % 50),
        )
        for i in range(PROPERTIES)
    ]

    started = time.perf_counter()
    verdicts = [definition.place(fields) for fields in properties]
    took = time.perf_counter() - started

    assert len(verdicts) == PROPERTIES
    assert Placement.inside in verdicts and Placement.outside in verdicts, "not a real mix"
    assert took < BUDGET, f"{PROPERTIES} properties took {took:.2f}s against {VERTICES} vertices"
