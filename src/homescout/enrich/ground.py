"""Where you are looking: county lines, town names, and how much rain falls on each county.

This exists because of a sentence about the fire map: "if we could get the counties and major city
names on the map, and a number over each county for the annual precipitation."

Three separate things and one reason. The hazard layer is a wall of red and green with no words on
it. A basemap has town names, but they are underneath a raster whose whole point is to be opaque
enough to read, so the moment the map becomes useful it also becomes anonymous: a person looks at a
patch of red half an hour north of somewhere and cannot say where. County lines and town names put
the names back on top, drawn by this tool rather than borrowed from a tile.

Rainfall is the same question asked about the ground rather than the map. Fire hazard is modelled
from fuel and terrain and says nothing about how dry a place is year on year, and in this state
that is most of what somebody buying land wants to know: nine inches a year and twenty inches a
year are different countries. It is one number per county because that is the finest grain the
federal record actually publishes, and saying so is better than interpolating a number that looks
like it is about the property.

**All three are keyless, national, and effectively permanent.** County lines move roughly never,
urban areas are redrawn once a decade, and a thirty-year rainfall average changes by a hundredth of
an inch a year. Everything here is therefore fetched once per state and kept on disk for ever
after, exactly like a wind rose, and for the same reason: this is somebody else's public server
being asked a favour.
"""

from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from ..errors import InvalidInput
from .provider import ProviderFailed
from .states import STATES

AGENT = "HomeScout (a personal house-search tool; one household)"
TIMEOUT_SECONDS = 60.0

#: Three at a time. A county's rainfall is one small query, but thirty-three of them at once on a
#: public server is not how a personal tool behaves.
AT_ONCE = 3
_room = threading.Semaphore(AT_ONCE)

#: TIGERweb's layer numbers. Counties for the lines, urban areas for the names.
#:
#: Urban areas rather than incorporated places, and the choice is the whole reason there is a
#: readable number of labels. Places would give every incorporated village in the state, hundreds
#: of them, most of which are a name on a road; the Census defines an urban area by where people
#: actually are, so the list for New Mexico is thirty-seven and reads as "the towns". It is also
#: the only free national answer to "how big is this town" that does not need a key: the Census
#: population API asks for one now.
COUNTY_LAYER = 82
URBAN_LAYER = 88

#: About a kilometre, which at any zoom where a county fits on screen is finer than a line is wide.
#: The unsimplified outlines for one state are a megabyte; this is seventeen kilobytes.
DETAIL = 0.01

#: How many years of rainfall to average, ending at the last complete year the record has.
#:
#: Thirty is the length the meteorological world calls a normal, and it is long enough that one
#: monsoon does not move it. Shorter would be news rather than climate, which is the same mistake
#: the wind overlay refuses to make by reading decades rather than a forecast.
YEARS = 30

#: The earliest year worth asking about. The county record runs to 1895 and the last thirty years
#: is what a person buying now is buying into.
EARLIEST = 1895


def _kept(root: Path, *parts: str) -> Path:
    stamp = hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
    return Path(root) / "ground" / f"{stamp}.json"


def _remember(where: Path, what: object) -> None:
    where.parent.mkdir(parents=True, exist_ok=True)
    beside = where.with_suffix(".part")
    beside.write_text(json.dumps(what), encoding="utf-8")
    beside.replace(where)


def _fetch(url: str, what: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - the address is this tool's own configuration
        url, headers={"User-Agent": AGENT, "Accept": "*/*"}
    )
    with _room:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
                return answer.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderFailed(f"{what}: the public record did not answer ({exc})") from None


def postal(state: str) -> str:
    """A two-letter state code, checked, because it goes straight into a query."""
    held = str(state or "").strip().upper()
    if held not in STATES:
        raise InvalidInput(f"{state!r} is not a state this tool knows.")
    return held


def _json(body: bytes, what: str) -> dict:
    try:
        found = json.loads(body)
    except ValueError:
        raise ProviderFailed(f"{what}: the answer was not readable.") from None
    if not isinstance(found, dict):
        raise ProviderFailed(f"{what}: the answer was not the shape this expects.")
    if "error" in found:
        raise ProviderFailed(f"{what}: {found['error']}")
    return found


# -- county lines ----------------------------------------------------------


def counties(root: Path, service: str, state: str) -> list[dict[str, object]]:
    """Every county in one state: its name, its middle, and its outline.

    The outline is simplified on the server rather than here, which is both cheaper and the only
    version that is honest about what it is: a line drawn to about a kilometre. A county boundary
    at full precision is a survey document and this is a label on a map.
    """
    state = postal(state)
    kept = _kept(root, "counties", state)
    if kept.is_file():
        return json.loads(kept.read_text(encoding="utf-8"))

    asked = urllib.parse.urlencode(
        {
            "where": f"STATE='{STATES[state][0]}'",
            "outFields": "BASENAME,COUNTY,CENTLAT,CENTLON",
            "returnGeometry": "true",
            "geometryPrecision": "3",
            "maxAllowableOffset": str(DETAIL),
            "f": "geojson",
        }
    )
    body = _fetch(f"{service.rstrip('/')}/{COUNTY_LAYER}/query?{asked}", f"{state} counties")
    found = _json(body, f"{state} counties")

    held: list[dict[str, object]] = []
    for feature in found.get("features") or []:
        held_of = feature.get("properties") or {}
        name = str(held_of.get("BASENAME") or "").strip()
        shape = feature.get("geometry") or {}
        rings = _rings(shape)
        if not name or not rings:
            continue
        held.append(
            {
                "state": state,
                "fips": str(held_of.get("COUNTY") or "").strip(),
                "name": name,
                "latitude": _number(held_of.get("CENTLAT")),
                "longitude": _number(held_of.get("CENTLON")),
                "outline": rings,
            }
        )
    if not held:
        raise ProviderFailed(f"{state}: the boundary service listed no counties.")
    _remember(kept, held)
    return held


def _rings(shape: dict) -> list[list[list[float]]]:
    """A polygon or a multipolygon, flattened to a list of rings as [latitude, longitude].

    Turned round here rather than in the browser because GeoJSON says longitude first and every
    map library in this tool says latitude first, and a coordinate order that is converted at the
    point of drawing is a coordinate order that is eventually converted twice.
    """
    kind = shape.get("type")
    holds = shape.get("coordinates") or []
    if kind == "Polygon":
        parts = [holds]
    elif kind == "MultiPolygon":
        parts = list(holds)
    else:
        return []
    rings: list[list[list[float]]] = []
    for polygon in parts:
        for ring in polygon:
            turned = [
                [float(point[1]), float(point[0])]
                for point in ring
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            if len(turned) >= 3:
                rings.append(turned)
    return rings


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


# -- town names ------------------------------------------------------------


def towns(root: Path, service: str, state: str) -> list[dict[str, object]]:
    """The towns in one state, biggest first, as a name and a place to write it.

    `size` is the urban area's land area, and it is what decides which names are drawn at which
    zoom. Not a population, and the field says so: population from the Census now needs a key, and
    a tool that made somebody register for an account before it would label Santa Fe would be a
    worse tool. Across urban areas, which are drawn round where people actually live, land area
    ranks them close enough to put the right dozen names on a state-sized map.
    """
    state = postal(state)
    kept = _kept(root, "towns", state)
    if kept.is_file():
        return json.loads(kept.read_text(encoding="utf-8"))

    asked = urllib.parse.urlencode(
        {
            "where": "1=1",
            "geometry": _box(counties(root, service, state)),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "BASENAME,AREALAND,CENTLAT,CENTLON",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    body = _fetch(f"{service.rstrip('/')}/{URBAN_LAYER}/query?{asked}", f"{state} towns")
    found = _json(body, f"{state} towns")

    held: list[dict[str, object]] = []
    for feature in found.get("features") or []:
        held_of = feature.get("attributes") or {}
        name = str(held_of.get("BASENAME") or "").strip()
        latitude = _number(held_of.get("CENTLAT"))
        longitude = _number(held_of.get("CENTLON"))
        if not name or latitude is None or longitude is None:
            continue
        held.append(
            {
                "name": _shortened(name),
                "latitude": latitude,
                "longitude": longitude,
                "size": int(_number(held_of.get("AREALAND")) or 0),
            }
        )
    held.sort(key=lambda one: -int(one["size"]))
    _remember(kept, held)
    return held


def _shortened(name: str) -> str:
    """"Albuquerque, NM" is what the Census calls it and "Albuquerque" is what a person calls it.

    The state is on every one of them, which on a map of that state is a word repeated forty times
    saying nothing. An area spanning two states keeps both, because there the second half is the
    fact: "El Paso, TX--NM" is not El Paso.
    """
    head, _, tail = name.partition(",")
    return head.strip() if tail.strip().count("-") == 0 and len(tail.strip()) <= 2 else name


def _box(held: list[dict[str, object]]) -> str:
    """A rectangle round a state, worked out from its own county outlines.

    Derived rather than tabulated. Fifty-six hand-typed rectangles is fifty-six chances to put a
    number in wrong, and a wrong one is invisible: the map simply has no names in one corner and
    nothing anywhere says why.

    An urban area is kept if it touches the box, so a town just over the state line comes with it.
    That is right rather than sloppy: somebody looking at the edge of this state can see that town
    and wants it named.
    """
    latitudes = [point[0] for one in held for ring in one["outline"] for point in ring]
    longitudes = [point[1] for one in held for ring in one["outline"] for point in ring]
    if not latitudes:
        raise ProviderFailed("no county outlines to take a state's extent from")
    return (
        f"{min(longitudes):.4f},{min(latitudes):.4f},"
        f"{max(longitudes):.4f},{max(latitudes):.4f}"
    )


# -- how much rain ---------------------------------------------------------


def rainfall(root: Path, service: str, state: str, county_fips: str) -> dict[str, object]:
    """One county's average yearly precipitation, over the last thirty complete years on record.

    Precipitation and not rainfall, and the distinction is not pedantry here. The national record
    measures frozen precipitation by melting it, so this figure includes snow as the water it melts
    down to: roughly an inch of water for a foot of snow. A mountain county therefore reads as a
    modest number while having a real winter, and the pages that show it say so.

    An average and not a year. Any single year here is a story about a monsoon, and what somebody
    buying land is asking is what the place is normally like. The years it covers travel with the
    number, because "eleven inches" means nothing without them and because a reader who wants to
    know whether this is drying out can go and look at the record itself.
    """
    state = postal(state)
    county_fips = str(county_fips or "").strip()
    if not county_fips.isdigit() or len(county_fips) != 3:
        raise InvalidInput(f"{county_fips!r} is not a county code.")

    kept = _kept(root, "rain", state, county_fips, str(YEARS))
    if kept.is_file():
        return json.loads(kept.read_text(encoding="utf-8"))

    where = f"{state}-{county_fips}"
    #: The record refuses a range that ends in a year it does not have, so the end is last year
    #: and, if the record has not caught up yet, the year before that. Asked from 1895 and sliced
    #: here rather than asked for exactly thirty years: the whole series is four kilobytes, and
    #: one request that cannot be off by a year is worth more than three saved.
    last = datetime.now(UTC).year - 1
    found = None
    for ending in (last, last - 1):
        try:
            found = _json(
                _fetch(
                    f"{service.rstrip('/')}/{where}/pcp/ann/12/{EARLIEST}-{ending}.json",
                    f"{where} rainfall",
                ),
                f"{where} rainfall",
            )
            break
        except ProviderFailed:
            if ending == last - 1:
                raise
    assert found is not None
    read = found.get("data")
    if not isinstance(read, dict) or not read:
        raise ProviderFailed(f"{where}: the rainfall record is empty.")

    #: Keys are "YYYY12": the year, and the month the twelve-month window ends on. Sorted as text,
    #: which for a fixed-width year is the same as sorted by year and does not need parsing.
    years = sorted(read)[-YEARS:]
    values = [
        _number((read[year] or {}).get("value"))
        for year in years
        if isinstance(read.get(year), dict)
    ]
    values = [one for one in values if one is not None and one > -90]
    if not values:
        raise ProviderFailed(f"{where}: no readable rainfall in the last {YEARS} years.")

    held = {
        "state": state,
        "fips": county_fips,
        "name": str((found.get("description") or {}).get("title") or "").split(" County")[0],
        "inches": round(sum(values) / len(values), 1),
        "years": len(values),
        "from": int(years[0][:4]),
        "to": int(years[-1][:4]),
    }
    _remember(kept, held)
    return held
