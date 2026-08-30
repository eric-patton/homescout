"""What is around a property, as a picture and as a prevailing direction.

Two things the store cannot answer as data and can answer as context.

**The hazard map is a substitute for a computation this product cannot do.** The wildfire and
interface layers are served as tiles rather than as geometry, so nothing here can measure the
distance from a house to the nearest high-hazard block. The property's own rating is known and says
nothing about what is next to it: a parcel rated low, a hundred yards from a rated-high ridge, reads
identically to one in the middle of a hundred square miles of low. A picture of the hazard around
the point is what closes that, and a model looking at it can say which of the two this is.

**Wind is regional and has to say so.** A rose is one weather station's record over decades, the
nearest station can be forty miles away, and sending it without that distance invites a confident
sentence about prevailing smoke direction at a parcel the data has nothing to say about. So what
goes out carries the station, how far it is, and the caveat in words.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

#: How much ground the hazard picture covers, in degrees either side of the property. Roughly two
#: and a half miles across at this latitude, which is the scale the question is asked at: not the
#: parcel, which the photograph shows, and not the county, which the rating already summarises.
AROUND_DEGREES = 0.018

#: Big enough to see the shape of a hazard boundary, small enough that it costs a fraction of what
#: the photograph does.
TILE = "512,512"

#: Which season's rose. April is what matters for smoke and dust in eastern New Mexico, and it is
#: what the map already opens on, so a person comparing the two sees the same thing.
SEASON = "april"

#: Beyond this the station describes somewhere else. The rose is still worth sending, because a
#: regional prevailing wind is still a fact about the region, but the caveat gets louder.
FAR_MILES = 50.0

EARTH_MILES = 3958.8


def bbox_around(latitude: float, longitude: float, degrees: float = AROUND_DEGREES) -> str:
    """The rectangle to draw the hazard in, as `hazard_tile` wants it."""
    return ",".join(
        str(round(v, 6))
        for v in (
            longitude - degrees,
            latitude - degrees,
            longitude + degrees,
            latitude + degrees,
        )
    )


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle miles. Plain haversine, because this is a distance to a weather station."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        (lon2 - lon1) / 2
    ) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(d))


def nearest_station(
    latitude: float, longitude: float, stations: Sequence[Mapping[str, Any]]
) -> tuple[Mapping[str, Any], float] | None:
    """The closest station with coordinates, and how far away it is."""
    best: tuple[Mapping[str, Any], float] | None = None
    for station in stations:
        lat, lon = station.get("latitude"), station.get("longitude")
        if lat is None or lon is None:
            continue
        away = miles_between((latitude, longitude), (float(lat), float(lon)))
        if best is None or away < best[1]:
            best = (station, away)
    return best


def wind_from(rose: Mapping[str, Any], station: Mapping[str, Any], miles: float) -> dict[str, Any]:
    """One rose, said in a sentence, with what is uncertain about it attached.

    The summary is prose rather than sixteen percentages because that is what the question is: which
    way does the wind usually come from here, and how often. A model handed the full sector table
    would restate it; handed the sentence, it can reason about whether a worry is upwind.
    """
    best = rose.get("prevailing") or {}
    where = best.get("compass")
    percent = best.get("percent")

    said = "no prevailing direction was recorded"
    if where:
        said = f"most often from the {where}"
        if percent:
            said += f", about {round(float(percent))}% of the time"
    calm = rose.get("calm")
    if calm:
        said += f", calm {round(float(calm))}% of the time"

    return {
        "station": station.get("name") or station.get("station") or "an unnamed station",
        "miles": round(miles, 1),
        "season": rose.get("when") or SEASON,
        "summary": said + f" (recorded over {rose.get('period') or 'the station record'})",
        # Said in the dossier rather than left for the model to work out, because the failure this
        # prevents is a confident sentence about a parcel forty miles from the evidence.
        "far": miles > FAR_MILES,
    }
