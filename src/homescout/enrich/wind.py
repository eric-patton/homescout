"""Where the wind comes from, over decades rather than today.

A house near a wall of red burns when the wind pushes the fire at it, so the useful question on a
fire map is not "how hard is the wind blowing" but "which way does the weather generally move
through here". Those are different questions with different answers, and only the second one keeps.
Today's forecast is a fact about Thursday; a house is a thirty-year decision.

So this reads a **wind rose**: how often, over every hourly observation a weather station has ever
recorded, the wind came from each of sixteen directions, and how often it did so hard. Iowa State's
environmental mesonet keeps the whole national archive of those observations and will compute the
rose for one station on request, which is the entire reason this is three hundred lines rather than
three thousand. Thirty years of hourly readings for Taos is one request.

TWO THINGS SHAPE EVERY DECISION BELOW.

**The request is expensive and the answer never changes.** It is a query over tens of thousands of
rows and it takes about ten seconds. The answer is a summary of decades, so a month from now it is
the same summary. Every rose is therefore kept on disk the first time it is fetched and read off
the disk for ever after, and this asks for a station's rose exactly once in the life of the
workspace. Three at a time, not four and not forty: unlike a map tile this is real work on somebody
else's database, done as a favour to the public.

**What it can honestly say is bounded, and the page says so.** These are anemometers ten metres up
at airports, in the open, tens of miles apart. A canyon has its own wind and this knows nothing
about it. What it does say, and says well, is which way weather moves through a region, which is the
direction a fire in the red would travel.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..errors import InvalidInput
from .provider import ProviderFailed

#: How many of these to ask for at once. Fewer than the map tiles, deliberately: a tile is a file on
#: a server and this is a query across decades of observations.
AT_ONCE = 3

#: One of these takes about ten seconds when the archive is busy.
TIMEOUT_SECONDS = 90.0

AGENT = "HomeScout (a personal house-search tool; one household)"

#: Sixteen points of the compass, which is how a wind rose has been drawn since before anybody
#: measured one. Thirty-six is available and is more than an eye reads off a glyph.
SECTORS = 16

#: The earliest year to ask about. Not "everything ever": the automated stations came in through the
#: nineties, and a rose that mixes a decade of hand-read observations with three of automatic ones
#: is two datasets in a trenchcoat.
FROM_YEAR = 1990
TO_YEAR = 2100

#: The wind that moves a fire. Below this a rose is mostly telling you about calm afternoons, which
#: is a true thing about a place and not the thing being asked.
STRONG_MPH = 15.0

#: Which months to count, by the name this tool uses for the choice.
#:
#: The whole year is the honest default and April is the one worth having beside it: in New Mexico
#: it is both the windiest month and the middle of fire season, which is not a coincidence. The
#: archive limits a request to one named month or to none, so these are the two questions that can
#: be asked in a single request, and asking four times for "spring" would be four times the work on
#: somebody else's machine for an answer April already gives.
WHEN: dict[str, int | None] = {"year": None, "april": 4}

_room = threading.Semaphore(AT_ONCE)

#: A station is a handful of letters and digits, and it reaches a URL. Anything else is not one.
NAMED = re.compile(r"^[A-Z0-9_]{2,20}$")

#: The first number in a speed-band label, which is the band's floor. "20.0+" has no second one.
FLOOR = re.compile(r"^(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class Sector:
    """One of the sixteen directions, and how often the wind came *from* it."""

    #: Degrees clockwise from north, at the middle of the sector.
    degrees: float
    #: Percent of all observations.
    percent: float
    #: Percent of all observations, counting only the ones at `STRONG_MPH` and above.
    strong: float


@dataclass(frozen=True)
class Rose:
    """One station's wind, summarised over its whole record."""

    station: str
    name: str
    latitude: float
    longitude: float
    when: str
    calm: float
    sectors: tuple[Sector, ...]
    observations: int
    period: str

    @property
    def prevailing(self) -> Sector | None:
        """The direction the wind most often comes from. Nothing, for a station that never blows."""
        real = [sector for sector in self.sectors if sector.percent > 0]
        return max(real, key=lambda sector: sector.percent) if real else None

    def document(self) -> dict[str, object]:
        best = self.prevailing
        return {
            "station": self.station,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "when": self.when,
            "calm": self.calm,
            "observations": self.observations,
            "period": self.period,
            "sectors": [
                {"degrees": one.degrees, "percent": one.percent, "strong": one.strong}
                for one in self.sectors
            ],
            "prevailing": (
                None
                if best is None
                else {
                    "degrees": best.degrees,
                    "compass": compass(best.degrees),
                    "percent": best.percent,
                    "strong": best.strong,
                }
            ),
        }


#: The sixteen points, in the order the sectors come out.
POINTS = (
    "north", "north-northeast", "northeast", "east-northeast",
    "east", "east-southeast", "southeast", "south-southeast",
    "south", "south-southwest", "southwest", "west-southwest",
    "west", "west-northwest", "northwest", "north-northwest",
)


def compass(degrees: float) -> str:
    """A bearing as the word for it. Spelled out, because "WSW" is a thing to decode and this
    product does not make anybody decode anything."""
    return POINTS[int(round(degrees / 22.5)) % 16]


def named(what: str, kind: str) -> str:
    """A station or a network, checked. Both arrive from a page and both reach a URL."""
    held = (what or "").strip().upper()
    if not NAMED.match(held):
        raise InvalidInput(f"{what!r} is not a {kind}.")
    return held


def when(what: str) -> str:
    """Which months, checked."""
    held = (what or "year").strip().lower()
    if held not in WHEN:
        raise InvalidInput(f"{what!r} is not a season. Known: {', '.join(sorted(WHEN))}.")
    return held


def network_for(state: str) -> str:
    """The archive's name for a state's automated airport weather network."""
    return f"{named(state, 'state')}_ASOS"


def _kept(root: Path, *parts: str) -> Path:
    stamp = hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
    return Path(root) / "wind" / f"{stamp}.json"


def _fetch(url: str, what: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - the address is this tool's own configuration
        url, headers={"User-Agent": AGENT, "Accept": "*/*"}
    )
    with _room:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
                return answer.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderFailed(f"{what}: the weather archive did not answer ({exc})") from None


def _remember(where: Path, what: object) -> None:
    where.parent.mkdir(parents=True, exist_ok=True)
    beside = where.with_suffix(".part")
    beside.write_text(json.dumps(what), encoding="utf-8")
    beside.replace(where)


def stations(root: Path, service: str, network: str) -> list[dict[str, object]]:
    """Every weather station in one state's network, and where each one is.

    One request, and the answer changes about as often as an airport opens.
    """
    network = named(network, "network")
    kept = _kept(root, "stations", network)
    if kept.is_file():
        return json.loads(kept.read_text(encoding="utf-8"))

    body = _fetch(f"{service.rstrip('/')}/{network}.geojson", network)
    try:
        found = json.loads(body)
        features = found["features"]
    except (ValueError, KeyError, TypeError):
        raise ProviderFailed(
            f"{network}: the weather archive answered with something "
            "that is not a list of stations."
        ) from None

    held = []
    for feature in features:
        where = (feature.get("geometry") or {}).get("coordinates") or []
        if len(where) < 2:
            continue
        held.append(
            {
                "station": feature.get("id"),
                "network": network,
                "name": (feature.get("properties") or {}).get("sname") or feature.get("id"),
                "longitude": float(where[0]),
                "latitude": float(where[1]),
            }
        )
    _remember(kept, held)
    return held


def rose(root: Path, service: str, network: str, station: str, season: str = "year") -> Rose:
    """One station's wind rose, from the disk if it is there and from the archive if not."""
    network = named(network, "network")
    station = named(station, "station")
    season = when(season)

    kept = _kept(root, "rose", network, station, season)
    if kept.is_file():
        return _rebuild(json.loads(kept.read_text(encoding="utf-8")))

    month = WHEN[season]
    asked = {
        "station": station,
        "network": network,
        "nsector": str(SECTORS),
        "units": "mph",
        "justdata": "true",
        "year1": str(FROM_YEAR),
        "year2": str(TO_YEAR),
        "month1": str(month or 1),
        "month2": str(month or 1),
        "day1": "1",
        "day2": "1",
        "hour1": "0",
        "hour2": "0",
        "minute1": "0",
        "minute2": "0",
    }
    if month is not None:
        # The archive counts one named month across every year, or none, and nothing in between.
        asked["monthlimit"] = "1"

    body = _fetch(f"{service}?{urllib.parse.urlencode(asked)}", station)
    found = read(body.decode("utf-8", "replace"), network, station, season)
    _remember(kept, _flatten(found))
    return found


def read(text: str, network: str, station: str, season: str) -> Rose:
    """The archive's table, as sixteen directions.

    Its shape, which is a comment block and then a plain table:

        # Windrose Data Table (Percent Frequency) for TAOS MUNI APT(AWOS) (SKX)
        # Observations Used/Missing/Total: 22064/0/22064
        # 16 Apr 1992 12:00 PM - 30 Apr 2025 11:56 PM America/Denver
        # First value in table is CALM
        Direction,Calm     , 2.0  4.9, 5.0  6.9, ... ,20.0+
        349-010  ,13.43    ,    2.050,    3.267, ... ,   0.074
        011-033  ,         ,    1.009,    1.191, ... ,   0.019

    A row is a direction the wind came *from* and the columns are speeds, so the frequency for a
    direction is its row added up, and the calm figure sits once in the first row because calm has
    no direction to belong to. The direction labels are ranges that wrap around north, so rather
    than parse "349-010" into a bearing, the sectors are read as what they are: sixteen equal
    slices, the first one centred on north. That is exactly what was asked for, so anything else
    would be reading a number back out of a label this code wrote the request for.
    """
    name = station
    observations = 0
    period = ""
    header: list[str] = []
    rows: list[list[str]] = []
    calm = 0.0

    for line in text.splitlines():
        if line.startswith("#"):
            said = line.lstrip("#").strip()
            if said.startswith("Windrose Data Table") and " for " in said:
                name = said.split(" for ", 1)[1].strip()
            elif said.startswith("Observations Used"):
                try:
                    observations = int(said.split(":", 1)[1].split("/")[0].strip())
                except (IndexError, ValueError):
                    observations = 0
            elif " - " in said and not period:
                period = said
            continue
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if not header:
            header = parts
            continue
        rows.append(parts)

    if not header or len(rows) != SECTORS:
        raise ProviderFailed(
            f"{station}: the weather archive answered with "
            f"{len(rows)} directions rather than {SECTORS}. It has probably changed its table."
        )

    # Which speed columns count as strong. A label is a range like "15.0 19.9" or an open top like
    # "20.0+", and the floor is the only part of either that this needs. Read off the label rather
    # than counted in from the right, so a table that gains or loses a band stays right: the last
    # one is the one with no upper number, and counting from the end would silently miss it.
    strong_columns = set()
    for at, label in enumerate(header[2:], start=2):
        floor = FLOOR.match(label.strip())
        if floor and float(floor.group(1)) >= STRONG_MPH:
            strong_columns.add(at)

    step = 360.0 / SECTORS
    sectors = []
    for at, parts in enumerate(rows):
        if at == 0 and len(parts) > 1 and parts[1]:
            calm = _number(parts[1])
        total = sum(_number(part) for part in parts[2:])
        strong = sum(_number(parts[where]) for where in strong_columns if where < len(parts))
        sectors.append(
            Sector(degrees=round(at * step, 2), percent=round(total, 3), strong=round(strong, 3))
        )

    return Rose(
        station=station,
        name=name,
        latitude=0.0,
        longitude=0.0,
        when=season,
        calm=round(calm, 3),
        sectors=tuple(sectors),
        observations=observations,
        period=period,
    )


def _number(text: str) -> float:
    try:
        return float(text.strip())
    except (AttributeError, ValueError):
        return 0.0


def _flatten(found: Rose) -> dict[str, object]:
    return {
        "station": found.station,
        "name": found.name,
        "latitude": found.latitude,
        "longitude": found.longitude,
        "when": found.when,
        "calm": found.calm,
        "observations": found.observations,
        "period": found.period,
        "sectors": [[one.degrees, one.percent, one.strong] for one in found.sectors],
    }


def _rebuild(held: dict) -> Rose:
    return Rose(
        station=held["station"],
        name=held["name"],
        latitude=held.get("latitude", 0.0),
        longitude=held.get("longitude", 0.0),
        when=held["when"],
        calm=held["calm"],
        sectors=tuple(Sector(*one) for one in held["sectors"]),
        observations=held["observations"],
        period=held["period"],
    )
