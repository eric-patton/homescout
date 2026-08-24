"""Shapes, and the only place in this product that talks to shapely.

Two jobs, pulling in opposite directions.

**Exact, locally.** A drawn shape is the truth about where someone will live, and a point is either
inside it or it is not. That is what shapely is for, and it is why a polygon read from a file is
prepared once and then asked about thousands of times.

**Coarse, for a source.** No listing site accepts a drawn shape, so a shape also has to be able to
name something bigger that a site does accept. Bigger is the whole requirement: whatever is sent
must contain the shape, so that testing locally afterwards can only ever remove properties. A
covering form that is slightly too large costs requests. One that is slightly too small loses houses
nobody will ever know were missed, which is why the circle below is deliberately generous.

GeoJSON positions are longitude first. shapely's x is longitude and its y is latitude. Every
conversion in this module goes through `_point`, so that ordering is stated once instead of being
re-derived by whoever is reading.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import PreparedGeometry, prep
from shapely.validation import explain_validity

#: The earth, in miles, as a sphere. Good to a few parts in a thousand at these distances, which is
#: far inside the margin the covering circle already adds.
EARTH_MILES = 3958.7613

#: How much slack the covering circle adds beyond the farthest vertex: a proportion, and a floor.
#: The proportion covers the difference between a straight edge in degrees and the great-circle arc
#: a site measures along; the floor keeps a tiny shape from being covered by a circle the site
#: rounds down to nothing.
CIRCLE_MARGIN = 0.02
CIRCLE_FLOOR_MILES = 0.5


class GeometryError(ValueError):
    """A shape that cannot be read. Always reported against the file, never guessed at."""


def _point(longitude: float, latitude: float) -> Point:
    return Point(longitude, latitude)


def to_geometry(value: Any) -> BaseGeometry:
    """A GeoJSON geometry, a Feature, or a FeatureCollection of one, as shapely.

    All three are accepted because all three are what a map library hands out depending on how it
    was called, and which one arrives should never decide whether a saved search survives a round
    trip.
    """
    if not isinstance(value, Mapping):
        raise GeometryError("expected a GeoJSON object with a type and coordinates")

    kind = value.get("type")
    if kind == "Feature":
        return to_geometry(value.get("geometry"))
    if kind == "FeatureCollection":
        features = value.get("features")
        if not isinstance(features, Sequence) or len(features) != 1:
            raise GeometryError(
                "a FeatureCollection is only accepted when it holds exactly one shape; "
                "give each area its own entry"
            )
        return to_geometry(features[0])
    if kind not in ("Polygon", "MultiPolygon"):
        raise GeometryError(
            f"expected a Polygon or a MultiPolygon, got {kind!r}. "
            "An area is a region, so a point or a line cannot be one."
        )

    try:
        geometry = shape(dict(value))
    except Exception as exc:  # noqa: BLE001 - every shapely refusal is the same answer here
        raise GeometryError(f"could not read the geometry: {exc}") from None
    if geometry.is_empty:
        raise GeometryError("the geometry is empty, so it contains nothing")
    return geometry


def invalidity(geometry: BaseGeometry) -> str | None:
    """Why this shape is not a valid region, or None when it is.

    A self-intersecting ring is the case that matters: a shape drawn as a figure of eight has no
    honest inside, and shapely's answer to `contains` for one is arbitrary rather than wrong. Better
    refused at validation with the coordinates named.
    """
    if geometry.is_valid:
        return None
    return explain_validity(geometry)


def out_of_range(geometry: BaseGeometry) -> str | None:
    """A coordinate that cannot be a place on earth, or None.

    Almost always a hand-edited file with latitude and longitude the wrong way round, which is worth
    saying in those words rather than as a number out of range.
    """
    west, south, east, north = geometry.bounds
    if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
        return f"longitude {west:g} to {east:g} is outside -180 to 180"
    if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
        return (
            f"latitude {south:g} to {north:g} is outside -90 to 90. "
            "GeoJSON positions are longitude first, so this is usually a swapped pair."
        )
    return None


def prepare(geometry: BaseGeometry) -> PreparedGeometry:
    """Build the index that makes containment cheap.

    Done once per shape when a definition is loaded, never per property. A many-vertex shape asked
    about five thousand times is the whole performance budget of a run, and preparing inside the
    loop is how that budget gets spent twice.
    """
    return prep(geometry)


def contains(prepared: PreparedGeometry, latitude: float, longitude: float) -> bool:
    return bool(prepared.contains(_point(longitude, latitude)))


def union(shapes: Sequence[BaseGeometry]) -> BaseGeometry:
    """Every shape as one, which is what a search's areas mean together."""
    return unary_union(list(shapes))


def covers(outer: BaseGeometry, inner: BaseGeometry) -> bool:
    """Is every part of `inner` inside `outer`? Used to notice a search that excludes itself."""
    return bool(outer.covers(inner))


def box_of(geometry: BaseGeometry) -> tuple[float, float, float, float]:
    """South, west, north, east: the bounding box, in the order the source layer's box wants."""
    west, south, east, north = geometry.bounds
    return (south, west, north, east)


def miles_between(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    """Great-circle miles between two (latitude, longitude) pairs."""
    lat1, lon1 = math.radians(first[0]), math.radians(first[1])
    lat2, lon2 = math.radians(second[0]), math.radians(second[1])
    half = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_MILES * math.asin(min(1.0, math.sqrt(half)))


def positions(geometry: BaseGeometry) -> tuple[tuple[float, float], ...]:
    """Every vertex, as (latitude, longitude)."""
    found: list[tuple[float, float]] = []
    for part in getattr(geometry, "geoms", (geometry,)):
        rings = [part.exterior, *part.interiors]
        for ring in rings:
            found.extend((y, x) for x, y in ring.coords)
    return tuple(found)


def covering_circle(geometry: BaseGeometry) -> tuple[float, float, float]:
    """A centre and a radius in miles that contain the whole shape.

    The centre is the shape's centroid and the radius reaches its farthest vertex, plus a margin. A
    circle through the farthest vertex contains every vertex by construction; the margin covers the
    difference between an edge drawn straight in degrees and the arc a listing site measures along,
    and it is cheap: a fraction of a mile of extra market, filtered out locally the moment it comes
    back.
    """
    centroid = geometry.centroid
    centre = (centroid.y, centroid.x)
    farthest = max(
        (miles_between(centre, position) for position in positions(geometry)), default=0.0
    )
    return (centre[0], centre[1], max(farthest * (1 + CIRCLE_MARGIN), CIRCLE_FLOOR_MILES))
