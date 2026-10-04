"""Cover a large circle with smaller circles a listing source will accept."""

from __future__ import annotations

import math
from collections.abc import Iterator

from .base import PointRadius

EARTH_MILES = 3958.7613


def cover(circle: PointRadius, maximum: float) -> Iterator[PointRadius]:
    """Yield a containing cover lazily, so the request budget also bounds huge areas.

    Four centers, one in each bearing quadrant, cover the original disk. Within a quadrant,
    the farthest point is either the original center or one of its outer corners. Compute both
    distances on the sphere, with a margin for coordinate and request rounding. Repeating the
    construction shrinks every piece without dropping the original perimeter, even at a pole
    or across the date line. Extra market is removed by the caller's exact geography test.
    """
    if circle.miles <= maximum:
        yield circle
        return

    angle = min(circle.miles / EARTH_MILES, math.pi)
    offset = angle / math.sqrt(2)
    corner = math.acos(max(-1, min(1,
        math.cos(angle) * math.cos(offset)
        + math.sin(angle) * math.sin(offset) / math.sqrt(2))))
    radius = max(offset, corner) * EARTH_MILES * 1.01
    lat, lon = math.radians(circle.latitude), math.radians(circle.longitude)
    for bearing in (45, 135, 225, 315):
        heading = math.radians(bearing)
        end_lat = math.asin(max(-1, min(1,
            math.sin(lat) * math.cos(offset)
            + math.cos(lat) * math.sin(offset) * math.cos(heading))))
        end_lon = lon + math.atan2(
            math.sin(heading) * math.sin(offset) * math.cos(lat),
            math.cos(offset) - math.sin(lat) * math.sin(end_lat))
        piece = PointRadius(math.degrees(end_lat),
                            (math.degrees(end_lon) + 180) % 360 - 180, radius)
        yield from cover(piece, maximum)
