"""Cutting a box, which is how two of the three sources divide an oversized query.

The properties that matter are the ones a wrong cut would violate quietly: the halves must cover the
original exactly (a gap loses properties nobody will ever know were missed), and repeated cutting
must terminate (a source that reports the same oversized count forever must not be able to make this
recurse without end).
"""

from __future__ import annotations

import pytest

from homescout.sources.base import BoundingBox
from homescout.sources.boxes import MIN_SPAN_DEGREES, halve, ring, spans

PORTALES = BoundingBox(south=34.10, west=-103.45, north=34.30, east=-103.25)


def area(box: BoundingBox) -> float:
    return (box.north - box.south) * (box.east - box.west)


def test_the_halves_cover_the_original_and_nothing_more() -> None:
    """feat-005/AC-3: a gap between the halves loses properties silently.

    Which is the worst failure available here: nobody can miss what they were never shown, and the
    counts would look perfectly reasonable.
    """
    halves = halve(PORTALES)

    assert halves is not None
    first, second = halves
    assert abs(area(first) + area(second) - area(PORTALES)) < 1e-12
    assert min(first.south, second.south) == PORTALES.south
    assert max(first.north, second.north) == PORTALES.north
    assert min(first.west, second.west) == PORTALES.west
    assert max(first.east, second.east) == PORTALES.east


def test_the_cut_is_along_the_longer_side_in_real_distance() -> None:
    """feat-005/AC-3: degrees of longitude are shorter than degrees of latitude.

    A box that is square in degrees is wider than it is tall nowhere, and taller than it is wide
    everywhere but the equator. Cutting by degrees alone makes every piece more elongated than the
    last, and an elongated piece covers more market per query, which is what splitting is against.
    """
    square_in_degrees = BoundingBox(south=34.0, west=-103.5, north=34.5, east=-103.0)
    tall, wide = spans(square_in_degrees)

    assert tall > wide, "in New Mexico, half a degree of latitude is the longer side"

    halves = halve(square_in_degrees)
    assert halves is not None
    first, second = halves
    assert first.west == second.west, "so it was cut horizontally"
    assert first.north == second.south


def test_a_wide_box_is_cut_the_other_way() -> None:
    """feat-005/AC-3: the choice is made per box, not once."""
    wide = BoundingBox(south=34.0, west=-104.0, north=34.1, east=-103.0)

    halves = halve(wide)

    assert halves is not None
    first, second = halves
    assert first.south == second.south, "cut vertically"
    assert first.east == second.west


def test_repeated_halving_stays_roughly_square() -> None:
    """feat-005/AC-3: which is the whole reason the cosine is in there.

    Ten cuts of a state-sized box, each one on whichever side is longer. If the ratio drifted, the
    pieces would be strips rather than tiles.
    """
    box = BoundingBox(south=31.3, west=-109.1, north=37.0, east=-103.0)
    for _ in range(10):
        halves = halve(box)
        assert halves is not None
        box = halves[0]

    tall, wide = spans(box)
    assert 0.5 < (wide / tall) < 2.0, f"drifted to {wide / tall:.2f}"


def test_a_box_at_the_floor_cannot_be_cut() -> None:
    """feat-005/AC-5: this is what turns "still too big" into an honest truncation.

    Without it, a source that reports the same oversized count for every piece it is handed, which
    is exactly what a broken or hostile source looks like, would be able to recurse until something
    ran out.
    """
    tiny = MIN_SPAN_DEGREES / 2
    speck = BoundingBox(south=34.0, west=-103.0, north=34.0 + tiny, east=-103.0 + tiny)

    assert halve(speck) is None


def test_a_box_at_the_floor_in_one_direction_is_cut_in_the_other() -> None:
    """feat-005/AC-3: a sliver still has one useful cut in it."""
    sliver = BoundingBox(
        south=34.0, west=-103.2, north=34.0 + MIN_SPAN_DEGREES / 2, east=-103.0
    )

    halves = halve(sliver)

    assert halves is not None
    assert halves[0].south == halves[1].south, "cut vertically, the only way left"


@pytest.mark.parametrize(
    "box",
    [
        BoundingBox(south=34.0, west=-103.0, north=34.0, east=-103.5),
        BoundingBox(south=34.5, west=-103.5, north=34.0, east=-103.0),
        BoundingBox(south=34.0, west=103.0, north=34.5, east=-103.0),
    ],
    ids=["no height", "inverted", "wraps the antimeridian"],
)
def test_a_box_that_is_not_a_box_is_refused(box: BoundingBox) -> None:
    """feat-005/AC-5: rather than becoming an enormous one through arithmetic nobody checked."""
    assert halve(box) is None


def test_a_ring_is_closed_and_longitude_first() -> None:
    """feat-005/AC-2: the order every geographic format uses, and the one source that takes a shape.

    Longitude first is the convention people get wrong most often, and getting it wrong here would
    search a box in the Indian Ocean while reporting perfect health.
    """
    points = ring(PORTALES)

    assert len(points) == 5
    assert points[0] == points[-1], "a ring is closed"
    assert all(-180 <= longitude <= -60 for longitude, _ in points), "longitudes are first"
    assert all(20 <= latitude <= 60 for _, latitude in points), "latitudes are second"
