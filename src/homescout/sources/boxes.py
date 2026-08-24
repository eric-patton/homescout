"""Cutting a bounding box in half, which is how two of the three sources divide a query.

The ceiling walk in `ceiling.py` handles the whole procedure of getting everything out of a source
that caps one query: ask, read the count, and if it is over the cap, cut and recurse. It takes the
cutting as a parameter, because each source divides along whatever dimension it will divide along.
Realtor.com cuts by listing date. Zillow and Redfin both take a box, so they cut by geography, and
this is the one copy of that.

The cut is along the longer side **in real distance**, not in degrees. A degree of longitude is
shorter than a degree of latitude everywhere but the equator, and in the United States it is roughly
three quarters as long, so cutting by degrees alone would produce pieces that grow steadily more
elongated with every split. Elongated pieces cover more market per query, which is the opposite of
what splitting is for.
"""

from __future__ import annotations

from math import cos, radians

from .base import BoundingBox

#: A box narrower than this in either direction is not cut again. About two hundred metres of
#: latitude, which is a city block. A block with more properties than a source's cap is a single
#: tower, and the honest answer there is a truncation naming the ceiling rather than a descent that
#: never ends.
MIN_SPAN_DEGREES = 0.002


def spans(box: BoundingBox) -> tuple[float, float]:
    """How tall and how wide, in degrees and then in comparable distance.

    Returns the latitude span unchanged and the longitude span scaled by the cosine of the box's
    middle latitude, which is what makes the two numbers comparable.
    """
    tall = box.north - box.south
    middle = (box.north + box.south) / 2.0
    wide = (box.east - box.west) * cos(radians(middle))
    return tall, wide


def halve(box: BoundingBox) -> tuple[BoundingBox, BoundingBox] | None:
    """Two boxes that together cover this one exactly, or nothing.

    Nothing means the box can no longer usefully be divided, which is what turns "still too big"
    into an honest truncation rather than an infinite descent.

    The halves share their dividing edge. A property exactly on it would be returned by both, and
    the walk's own deduplication removes the repeat: overlap costs a duplicate, a gap would cost a
    property, and only one of those is recoverable.
    """
    tall_degrees = box.north - box.south
    wide_degrees = box.east - box.west
    if tall_degrees <= 0 or wide_degrees <= 0:
        # Includes a box that wraps the antimeridian, which no market this tool covers does, and
        # which would silently become an enormous box if the arithmetic were allowed to proceed.
        return None
    if tall_degrees < MIN_SPAN_DEGREES and wide_degrees < MIN_SPAN_DEGREES:
        return None

    tall, wide = spans(box)
    cut_vertically = wide > tall and wide_degrees >= MIN_SPAN_DEGREES
    if not cut_vertically and tall_degrees < MIN_SPAN_DEGREES:
        # The taller side is already at the floor, so the only cut left is the other one.
        cut_vertically = wide_degrees >= MIN_SPAN_DEGREES
        if not cut_vertically:
            return None

    if cut_vertically:
        middle = (box.west + box.east) / 2.0
        return (
            BoundingBox(south=box.south, west=box.west, north=box.north, east=middle),
            BoundingBox(south=box.south, west=middle, north=box.north, east=box.east),
        )
    middle = (box.south + box.north) / 2.0
    return (
        BoundingBox(south=box.south, west=box.west, north=middle, east=box.east),
        BoundingBox(south=middle, west=box.west, north=box.north, east=box.east),
    )


def ring(box: BoundingBox) -> tuple[tuple[float, float], ...]:
    """The box as a closed ring of longitude-latitude pairs, counter-clockwise.

    Longitude first, because that is the order every geographic interchange format uses and the
    order the one source that takes a shape expects. The first point is repeated at the end, which
    is what closes a ring.
    """
    return (
        (box.west, box.south),
        (box.east, box.south),
        (box.east, box.north),
        (box.west, box.north),
        (box.west, box.south),
    )
