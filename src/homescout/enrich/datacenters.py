"""Where the data centers are, what is coming, and what somebody has only asked for.

This exists because of a sentence: "would be good to have a layer on the map for current data
centers, future known, guaranteed data center sites, and proposed possible future data center
sites (like awaiting approval, etc). just read about a large data center that's going to be built
in dona ana county."

Three categories and one axis, which is how real the thing is. A building that is running, a build
that is approved and going up, and a proposal somebody has applied for are three different facts
about a piece of ground, and a person deciding where to live treats them very differently.

**Why this is a value and not only a picture.** The fire map exists because the hazard layer is
served as tiles, so nothing here can measure how far a house is from the nearest red, and the eye
had to do what no column could. Data centers are not tiles. They are points and building outlines,
so the distance is computable, and what the fire map had to hand to a person's eye can here be
handed to a column and to a rule.

**Two sources, because the gap between them runs along the line she drew.**

The tracker is FracTracker Alliance's, keyless and query-enabled, and it is the only free national
source that carries a *status*. Its interest is contested projects, which is its strength and its
flaw: what it records well is what somebody objected to. Virginia has 463 records and New Mexico
has 9, and Meta's campus at Los Lunas, running since 2018, is not in it at all.

The mapped buildings are OpenStreetMap's, which has no concept of a building that does not exist
yet and is therefore no use at all for the second and third categories, and is the better source
for the first. They are outlines rather than announcements, so the distance is to the edge of the
thing rather than to a guess at its middle.

So OpenStreetMap knows what is built and the tracker knows what is coming. Neither needs a key.

**The sharp edge is that the tracker rates how well it knows where each site is, and the bottom
rating is not a small imprecision.** The seven-thousand-megawatt New Era proposal is recorded at a
city of "Lea County", which is 4,400 square miles, so its stored point is a county centroid. A
distance measured to that is a number about nothing.

The answer is that the precision of the number carries the caveat, which needs no second column and
cannot be skipped the way a footnote can. A pinned site or a surveyed outline gives a tenth of a
mile. A site known to the right town gives a whole number of miles, because five miles is a claim
the source can support and 5.3 is not. A site known only to a county gives no distance at all, and
becomes `data_center_in_county` instead, because dropping it would make a house beside a
seven-thousand-megawatt proposal read exactly like a house nobody asked about, and an empty cell in
this feature means nobody asked.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .provider import ProviderFailed

AGENT = "HomeScout (a personal house-search tool; one household)"
TIMEOUT_SECONDS = 180.0

#: How long each index stays good, and the two are deliberately different.
#:
#: A mapped building does not move. A project's status is the most perishable value this feature
#: holds, because it changes when somebody decides something and the decision is exactly what a
#: person watching this wants to hear about: proposed became approved is the event.
BUILT_DAYS = 90
TRACKED_DAYS = 7

#: The tracker answers a thousand records at a time and holds fewer than two thousand.
PAGE = 1000

#: What the source's seven statuses mean in the three this tool reports, plus the two that are
#: carried and measured against nothing.
#:
#: Read rather than inferred, and a status that is not in here is a failure that names it. Guessing
#: which bucket an unrecognised status belongs in is the same mistake as guessing a fire rating.
KIND_BY_STATUS = {
    "operating": "operating",
    "expanding": "operating",
    "approved/permitted/under construction": "approved",
    "proposed": "proposed",
    "pre-proposal": "proposed",
    "suspended": "suspended",
    "cancelled": "cancelled",
}

#: The three a distance is measured to. A cancelled project is not a thing near a house, and a
#: suspended one is not a thing near a house today.
MEASURED = ("operating", "approved", "proposed")

#: How many decimal places of a mile each siting confidence can support.
#:
#: Absent from this table means no distance at all: the site is known to a county, and a county here
#: can be four thousand square miles. A blank confidence is treated as the coarsest rather than the
#: finest, because the cost of being wrong falls entirely one way.
PLACES_BY_CONFIDENCE = {"high": 1, "medium": 0}

#: The tags OpenStreetMap uses. `telecom` is the current one; the other two are older and still in
#: use, and leaving them out loses real buildings.
TAGS = (("telecom", "data_center"), ("building", "data_center"), ("man_made", "data_center"))

MERCATOR_R = 6_378_137.0
EARTH_MILES = 3958.8


# -- keeping what has been fetched -----------------------------------------


def _kept(root: Path, name: str) -> Path:
    return Path(root) / "datacenters" / f"{name}.json"


def _remember(where: Path, what: object) -> None:
    where.parent.mkdir(parents=True, exist_ok=True)
    beside = where.with_suffix(".part")
    beside.write_text(
        json.dumps({"fetched_at": datetime.now(UTC).isoformat(), "held": what}),
        encoding="utf-8",
    )
    beside.replace(where)


def _held(where: Path, days: int) -> tuple[Any, bool] | None:
    """What is on disk and whether it is still fresh, or None when there is nothing.

    Stale is returned rather than discarded, because last week's answer about a data center is worth
    more than no answer, and because a source that has gone down should cost a refresh rather than
    a column (AC-4).
    """
    if not where.is_file():
        return None
    try:
        found = json.loads(where.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(str(found["fetched_at"]))
    except (ValueError, KeyError, TypeError, OSError):
        return None
    age = (datetime.now(UTC) - when).total_seconds() / 86_400
    return found.get("held"), age <= days


def _fetch(url: str, what: str, body: bytes | None = None) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - the address is this tool's own configuration
        url,
        data=body,
        headers={"User-Agent": AGENT, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
            return answer.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderFailed(f"{what}: the public record did not answer ({exc})") from None


def _number(value: Any) -> float | None:
    try:
        found = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(found) or math.isinf(found) else found


# -- the tracker: what is coming -------------------------------------------


def tracked(root: Path, service: str, *, refresh: bool = True) -> list[dict[str, Any]]:
    """Every site the tracker holds, nationally, with its status already collapsed to a kind.

    Fetched whole rather than per state. The whole country is fewer than two thousand records over
    two paged requests, which is a different order of magnitude from the FCC's per-state gigabytes
    and is why this index is a side effect of a pass rather than something a person has to ask for
    (D-15).
    """
    where = _kept(root, "tracked")
    found = _held(where, TRACKED_DAYS)
    if found is not None and (found[1] or not refresh):
        return list(found[0])

    try:
        rows = _all_tracked(service)
    except ProviderFailed:
        if found is not None:
            return list(found[0])  # stale, and stale beats nothing
        raise
    _remember(where, rows)
    return rows


def _all_tracked(service: str) -> list[dict[str, Any]]:
    fields = (
        "facility_name,city,county,state,status,location_confidence,operator_name,tenant,"
        "mw,property_size_acres,facility_size_sqft,expected_date_online,purpose,"
        "information_source,lat,long"
    )
    held: list[dict[str, Any]] = []
    offset = 0
    while True:
        asked = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": fields,
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": str(offset),
                "resultRecordCount": str(PAGE),
                "f": "geojson",
            }
        )
        body = _fetch(f"{service}?{asked}", "the data center tracker")
        try:
            answer = json.loads(body)
        except ValueError:
            raise ProviderFailed("the data center tracker: the answer was not readable.") from None
        features = answer.get("features") or []
        for feature in features:
            site = _one_tracked(feature)
            if site is not None:
                held.append(site)
        if len(features) < PAGE:
            return held
        offset += PAGE
        if offset > 100_000:  # a runaway pager is a bug, not a big dataset
            return held


def _one_tracked(feature: Mapping[str, Any]) -> dict[str, Any] | None:
    held = feature.get("properties") or {}
    status = str(held.get("status") or "").strip().lower()
    if not status:
        return None
    kind = KIND_BY_STATUS.get(status)
    if kind is None:
        raise ProviderFailed(
            f"the data center tracker: {status!r} is not a status this build knows. The tracker's "
            "vocabulary has probably changed, and guessing which of operating, approved or "
            "proposed it belongs in is worse than not drawing it."
        )

    shape = feature.get("geometry") or {}
    where = shape.get("coordinates") if shape.get("type") == "Point" else None
    longitude = _number(where[0]) if where else _number(held.get("long"))
    latitude = _number(where[1]) if where else _number(held.get("lat"))
    if latitude is None or longitude is None:
        return None

    return {
        "name": str(held.get("facility_name") or "").strip() or "an unnamed data center",
        "kind": kind,
        "status": status,
        "confidence": str(held.get("location_confidence") or "").strip().lower(),
        "latitude": latitude,
        "longitude": longitude,
        "state": str(held.get("state") or "").strip().upper(),
        "county": str(held.get("county") or "").strip(),
        "city": str(held.get("city") or "").strip(),
        "operator": str(held.get("operator_name") or held.get("tenant") or "").strip(),
        "megawatts": str(held.get("mw") or "").strip(),
        "acres": str(held.get("property_size_acres") or "").strip(),
        "expected": str(held.get("expected_date_online") or "").strip(),
        "source": str(held.get("information_source") or "").strip(),
    }


# -- OpenStreetMap: what is built ------------------------------------------

#: One query, for the whole country, interpolating nothing.
#:
#: A constant on purpose and worth saying so. This is a query language; a per-state version would
#: build it by concatenating a state's name, and the nearest place a state name comes from is a
#: hand-edited saved search (D-15).
BUILT_QUERY = """[out:json][timeout:180];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
{clauses}
);
out geom;
""".format(clauses="\n".join(f'  nwr(area.us)["{k}"="{v}"];' for k, v in TAGS))


def built(root: Path, service: str, *, refresh: bool = True) -> list[dict[str, Any]]:
    """Every data center OpenStreetMap has mapped in the country, as outlines where it has them.

    Kept for three months. A building does not move, and this is a volunteer service being asked a
    favour: it answers 429 and 504 when it is busy, its published usage policy is stricter than this
    feature's one-second floor, and it is the first source here where retrying briskly is impolite
    rather than merely wasteful. So a failure falls back to what is already held.
    """
    where = _kept(root, "built")
    found = _held(where, BUILT_DAYS)
    if found is not None and (found[1] or not refresh):
        return list(found[0])

    try:
        body = _fetch(
            service,
            "the mapped data centers",
            urllib.parse.urlencode({"data": BUILT_QUERY}).encode(),
        )
        try:
            answer = json.loads(body)
        except ValueError:
            raise ProviderFailed("the mapped data centers: the answer was not readable.") from None
        rows = [one for one in map(_one_built, answer.get("elements") or []) if one is not None]
        if not rows:
            raise ProviderFailed("the mapped data centers: the answer held none.")
    except ProviderFailed:
        if found is not None:
            return list(found[0])
        raise
    _remember(where, rows)
    return rows


def _one_built(element: Mapping[str, Any]) -> dict[str, Any] | None:
    tags = element.get("tags") or {}
    outline = _outline_of(element)
    if outline:
        # The middle is still carried, because a footprint too small to see at the zoom being drawn
        # becomes a mark and a mark needs somewhere to be (feat-010/AC-91).
        longitude = sum(point[0] for point in outline) / len(outline)
        latitude = sum(point[1] for point in outline) / len(outline)
    else:
        latitude = _number(element.get("lat"))
        longitude = _number(element.get("lon"))
    if latitude is None or longitude is None:
        return None
    return {
        "outline": outline,
        "name": str(tags.get("name") or "").strip() or "an unnamed data center",
        "kind": "operating",
        "status": "mapped",
        #: A surveyed building. This is what the tracker's "high" means, arrived at by somebody
        #: drawing the outline rather than by somebody reading an address off a map.
        "confidence": "high",
        "latitude": latitude,
        "longitude": longitude,
        "operator": str(tags.get("operator") or "").strip(),
        "source": "OpenStreetMap contributors",
    }


def _outline_of(element: Mapping[str, Any]) -> list[list[float]]:
    """A way's own geometry, or a relation's outer rings run together, as [longitude, latitude].

    Longitude first, because that is what GeoJSON and `shapely` both want and turning it round in
    two places is how the two ends of this stop agreeing.
    """
    held: list[list[float]] = []
    for point in element.get("geometry") or []:
        longitude, latitude = _number(point.get("lon")), _number(point.get("lat"))
        if longitude is not None and latitude is not None:
            held.append([longitude, latitude])
    if held:
        return held
    for member in element.get("members") or []:
        if member.get("role") not in (None, "", "outer"):
            continue
        for point in member.get("geometry") or []:
            longitude, latitude = _number(point.get("lon")), _number(point.get("lat"))
            if longitude is not None and latitude is not None:
                held.append([longitude, latitude])
    return held


# -- the counties a coarse site is somewhere inside ------------------------


def bare_county(name: str) -> str:
    """A county name with the word "county" off the end of it, folded for comparing.

    The tracker is not consistent with itself: one New Mexico row says "Lea County" and the next
    says "Dona Ana". The boundary service says "Lea" and "Dona Ana". Comparing the two raw is how
    the county-grain answer silently never fires, which would be the quietest possible way for this
    provider to be wrong, because the value it fails to produce reads as a value nobody asked for.
    """
    held = " ".join(str(name or "").split()).casefold()
    for tail in (" county", " parish", " borough", " census area", " municipality"):
        if held.endswith(tail):
            return held[: -len(tail)].strip()
    return held


def coarse_counties(sites: Iterable[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Which counties hold a site too coarsely located to measure, as (state, county) pairs.

    Fewer than sixty nationally, which is what makes `data_center_in_county` affordable: the
    outlines of those counties are fetched once with the index and asked locally afterwards, so
    nothing about this costs a request per property.
    """
    held = {
        (site["state"], bare_county(site["county"]))
        for site in sites
        if site.get("kind") in MEASURED
        and str(site.get("confidence") or "") not in PLACES_BY_CONFIDENCE
        and site.get("state")
        and site.get("county")
    }
    return sorted(held)


# -- how far ---------------------------------------------------------------


def to_mercator(latitude: float, longitude: float) -> tuple[float, float]:
    """Degrees to Web Mercator metres.

    The tree is built in this rather than in degrees, and the reason is that a degree of longitude
    is not a degree of latitude anywhere but the equator: in New Mexico it is five-sixths of one, so
    a nearest computed in raw degrees picks the wrong winner about as often as the distances are
    close. Mercator scales both axes by the same factor at any given place, so the nearest in
    Mercator metres is the nearest on the ground. The scale itself is wrong, which is why nothing
    below reports a Mercator distance: the winner is chosen here and then measured properly.
    """
    x = MERCATOR_R * math.radians(longitude)
    y = MERCATOR_R * math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))
    return x, y


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle miles. Plain haversine, and the only distance this module reports."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    d = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_MILES * math.asin(math.sqrt(d))


def rounded(miles: float, confidence: str) -> float | None:
    """The distance at the precision its source can support, or None when it can support none.

    The whole of the honesty of this provider is in this function. A tenth of a mile is 161 metres
    and a site known only to the right town is not known to 161 metres, so reporting 5.3 there is a
    claim the source cannot support. Five is one it can.
    """
    places = PLACES_BY_CONFIDENCE.get(str(confidence or "").strip().lower())
    if places is None:
        return None
    return round(miles, places) if places else float(round(miles))


class Nearby:
    """The two indexes, arranged so that asking "what is nearest" costs no request and no scan.

    Built once per pass and asked once per distinct location. A straightforward walk over roughly
    three and a half thousand sites, for every cache key in an area of five thousand properties, is
    on the order of ten million comparisons, which is tens of seconds rather than the five the
    performance requirement allows. `shapely`'s own spatial index answers exactly this question, so
    this costs a constructor rather than a design (AC-37).

    Every geometry is held twice, and the reason is that the two jobs want different things. The
    tree is built in Web Mercator, because a degree of longitude is not a degree of latitude
    anywhere but the equator and a nearest computed in raw degrees picks the wrong winner whenever
    two candidates are close. The measuring is done in degrees against the real outline, because
    Mercator metres are not miles. So: choose in one, measure in the other.
    """

    def __init__(
        self,
        sites: Sequence[Mapping[str, Any]],
        counties: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        from shapely.geometry import shape
        from shapely.strtree import STRtree

        self.sites = [site for site in sites if site.get("kind") in MEASURED]
        self.by_kind: dict[str, tuple[list[Mapping[str, Any]], list[Any], Any]] = {}
        for kind in MEASURED:
            held = [
                site
                for site in self.sites
                if site["kind"] == kind
                and str(site.get("confidence") or "").strip().lower() in PLACES_BY_CONFIDENCE
            ]
            if not held:
                continue
            degrees = [_geometry_of(site) for site in held]
            self.by_kind[kind] = (held, degrees, STRtree([_project(one) for one in degrees]))

        #: The counties holding a site nobody could place inside them, with what kind it is.
        self.counties = [
            (shape(one["outline"]), tuple(one["kinds"])) for one in counties if one.get("outline")
        ]

    def nearest(self, kind: str, latitude: float, longitude: float) -> tuple[Any, float] | None:
        """The nearest site of one kind and how far it is, in real miles.

        A mapped building is measured to its outline rather than to a point inside it, so a house
        beside a hundred-acre campus is told how far it is from the campus rather than from the
        middle of it (AC-34). A property standing on one reads zero, which is the right answer and
        not an error.
        """
        held = self.by_kind.get(kind)
        if held is None:
            return None
        from shapely.geometry import Point
        from shapely.ops import nearest_points

        sites, degrees, tree = held
        which = tree.nearest(Point(*to_mercator(latitude, longitude)))
        if which is None:
            return None
        at = int(which)
        site, outline = sites[at], degrees[at]
        where = Point(longitude, latitude)
        if outline.covers(where):
            return site, 0.0
        edge = nearest_points(outline, where)[0]
        return site, miles_between((latitude, longitude), (edge.y, edge.x))

    def counties_holding(self, latitude: float, longitude: float) -> tuple[str, ...]:
        """Which kinds have a site somewhere in the county this point is in."""
        if not self.counties:
            return ()
        from shapely.geometry import Point

        where = Point(longitude, latitude)
        held: set[str] = set()
        for outline, kinds in self.counties:
            if outline.covers(where):
                held.update(kinds)
        return tuple(sorted(held))


def _geometry_of(site: Mapping[str, Any]) -> Any:
    """One site as `shapely` sees it, in degrees: its outline where it has one, else its point."""
    from shapely.geometry import Point, Polygon

    outline = site.get("outline") or []
    if len(outline) >= 4 and outline[0] == outline[-1]:
        try:
            return Polygon(outline)
        except (ValueError, TypeError):
            pass
    if len(outline) >= 3:
        try:
            return Polygon([*outline, outline[0]])
        except (ValueError, TypeError):
            pass
    return Point(site["longitude"], site["latitude"])


def _project(geometry: Any) -> Any:
    """The same geometry in Web Mercator metres, which is what the tree is built in."""
    from shapely.geometry import Point, Polygon
    from shapely.geometry.base import BaseGeometry

    if isinstance(geometry, Point):
        return Point(*to_mercator(geometry.y, geometry.x))
    if isinstance(geometry, Polygon):
        return Polygon([to_mercator(y, x) for x, y in geometry.exterior.coords])
    assert isinstance(geometry, BaseGeometry)
    return geometry
