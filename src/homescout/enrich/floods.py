"""Where the Weather Service has warned of flash floods, and where floods were reported.

This exists because of a storm. The remnants of Hurricane Polo crossed New Mexico in the last days
of September 2026; McLeod Dam above Garfield went into a Flash Flood Emergency for imminent failure,
the Rincon Arroyo breached its levees, and Rincon, which FEMA maps as Zone X, minimal hazard, stayed
under water a day later. A mold-sensitive household asked to see where that storm went and where
it could happen again.

Nothing public says where the water went. USGS opened no high-water-mark event, Copernicus had no
activation, FEMA had no declaration, and NOAA's storm database runs three months behind. What does
exist, for every storm since 2008, is the Weather Service's own record: the polygon of every
flash-flood warning, whether it was raised to an emergency, and every flood report a spotter or an
emergency manager filed. Iowa State's Environmental Mesonet keeps that archive, keyless.

**What it is and is not.** A warning says where the Weather Service expected flooding, drawn wide: a
median of about 550 square kilometres in New Mexico. An emergency polygon is drawn over whole towns.
A report is positioned to about a kilometre, usually as an offset from a named place. So this counts
how often a place has been warned, and how many reports were filed within a mile, and the word for
all of it is "warned", never "flooded" (AC-48).

**How it is held.** A state at a time, a year at a time (D-18). A year that has ended is fetched
once and never again, because its warnings are final; New Mexico since 2008 is about 35 megabytes
once, and then one year and one reports file a week. Each warning is kept once, by its identity,
with the polygon it was issued with, which is its widest extent (AC-46). The archive's ready-made
HTML link is not kept at all (AC-49).
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import urllib.parse
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import kept
from .provider import ProviderFailed

#: The first year the archive holds storm-based warning polygons for, nationally.
WARNINGS_FROM = 2008

#: The first year storm reports are recorded consistently enough to count.
REPORTS_FROM = 2005

#: How long the current year's warnings and the reports are believed. A closed year is believed
#: for ever.
CURRENT_DAYS = 7

#: Which storm reports are about water reaching the ground. A debris flow is what a burn scar sends
#: down a canyon, and in this state it is the same question.
REPORT_KINDS = ("FLASH FLOOD", "FLOOD", "DEBRIS FLOW")

#: What a report is counted within. Reports are placed to a hundredth of a degree, about a
#: kilometre, so a mile is the honest grain.
NEARBY_METRES = 1609.344

#: The two damage threats the Weather Service attaches to a flash-flood warning. Anything else is
#: kept as nothing rather than as a word nobody chose.
DAMAGE = ("CONSIDERABLE", "CATASTROPHIC")

#: The most points one warning's outline may have. A real one has tens; a polygon of a million
#: points is an answer that would cost the pass its memory, and is dropped as unreadable.
MOST_POINTS = 50_000

_OFFICE = re.compile(r"^[A-Z]{3}$")
EARTH_METRES = 6_371_008.8


# -- dates -----------------------------------------------------------------


def local_date(issued: str, longitude: float) -> str:
    """The date a moment fell on where it happened, in local standard time (D-19).

    One hour per fifteen degrees of longitude, which is what a time zone approximates. Windows ships
    no time-zone database, and a dependency to say "the evening of the 29th" rather than "the small
    hours of the 30th" is not worth having: summer time puts the half hour after midnight on the
    previous day, and nothing else moves.
    """
    when = _moment(issued)
    return (when + timedelta(hours=round(longitude / 15.0))).date().isoformat()


def local_time(issued: str, longitude: float) -> str:
    """The hour and minute a moment fell at where it happened, in local standard time (D-19)."""
    when = _moment(issued) + timedelta(hours=round(longitude / 15.0))
    return when.strftime("%H:%M")


def _moment(text: str) -> datetime:
    found = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    return found if found.tzinfo else found.replace(tzinfo=UTC)


# -- the warnings ----------------------------------------------------------


def _warnings_file(root: Path, state: str, year: int) -> Path:
    return Path(root) / "floods" / f"warnings-{state}-{year}.json"


def warnings(
    root: Path,
    service: str,
    state: str,
    *,
    now: datetime | None = None,
    fetch: kept.Fetcher | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Every flash-flood warning that touched a state since 2008, and whether any of it is stale."""
    now = now or datetime.now(UTC)
    fetch = fetch or kept.fetch
    found: list[dict[str, Any]] = []
    stale = False
    for year in range(WARNINGS_FROM, now.year + 1):
        where = _warnings_file(root, state, year)
        held = kept.read(where, now=now)
        closed = year < now.year
        if held is not None and closed and not _fetched_before_it_closed(held[1], year, now):
            found.extend(held[0])
            continue
        if held is not None and not closed and held[1] <= CURRENT_DAYS:
            found.extend(held[0])
            continue
        try:
            fresh = _fetch_year(service, state, year, fetch)
        except ProviderFailed:
            if held is None:
                raise
            found.extend(held[0])  # stale, and stale beats nothing
            stale = True
            continue
        kept.write(where, fresh, now=now)
        found.extend(fresh)
    return found, stale


def _fetched_before_it_closed(age_days: float, year: int, now: datetime) -> bool:
    """Was this year's file fetched while the year was still running, or within a week of its end?

    Such a file is missing whatever came after it, so it is fetched once more and then believed for
    ever. A week, because a warning upgraded to an emergency in a follow-up statement on the last
    night of December is still being filed in January.
    """
    fetched = now - timedelta(days=age_days)
    return fetched < datetime(year + 1, 1, 8, tzinfo=UTC)


def _fetch_year(service: str, state: str, year: int, fetch: kept.Fetcher) -> list[dict[str, Any]]:
    asked = urllib.parse.urlencode(
        {"sts": f"{year}-01-01T00:00Z", "ets": f"{year + 1}-01-01T00:00Z", "states": state}
    )
    body = fetch(f"{service}?{asked}", f"flash-flood warnings for {state} in {year}")
    return parse_warnings(body, f"flash-flood warnings for {state} in {year}")


def parse_warnings(body: bytes, what: str) -> list[dict[str, Any]]:
    """The archive's GeoJSON reduced to one record per flash-flood warning (AC-46, AC-49)."""
    try:
        answer = json.loads(body)
    except (ValueError, RecursionError):
        raise ProviderFailed(f"{what}: the answer was not readable") from None
    features = answer.get("features") if isinstance(answer, Mapping) else None
    if not isinstance(features, list):
        raise ProviderFailed(f"{what}: the answer has no features list; the archive has changed")

    by_key: dict[tuple[str, int, int], dict[str, Any]] = {}
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        held = feature.get("properties") or {}
        if held.get("phenomena") != "FF" or held.get("significance") != "W":
            continue
        office = str(held.get("wfo") or "").strip().upper()
        try:
            event = int(held.get("eventid"))
            year = int(held.get("year"))
        except (TypeError, ValueError):
            continue
        if not _OFFICE.match(office):
            continue
        shape = _polygons(feature.get("geometry"))
        issued = str(held.get("issue") or held.get("polygon_begin") or "")
        try:
            _moment(issued)
        except ValueError:
            continue
        key = (office, event, year)
        emergency = bool(held.get("max_is_emergency") or held.get("is_emergency"))
        damage = _damage(held.get("max_floodtag_damage"), held.get("floodtag_damage"))
        first = by_key.get(key)
        if first is None:
            if shape is None:
                continue
            by_key[key] = {
                "office": office,
                "event": event,
                "year": year,
                "issued": issued,
                "emergency": emergency,
                "damage": damage,
                "polygon": shape,
                "status": str(held.get("status") or ""),
            }
            continue
        # The same warning again: an update, which can only shrink it. Keep the issued polygon,
        # and keep every sign that it got worse.
        first["emergency"] = first["emergency"] or emergency
        first["damage"] = _damage(first["damage"], damage)
        if held.get("status") == "NEW" and first.get("status") != "NEW" and shape is not None:
            first["polygon"] = shape
            first["issued"] = issued
            first["status"] = "NEW"
    for record in by_key.values():
        record.pop("status", None)
    return list(by_key.values())


def _damage(*tags: Any) -> str | None:
    found = [str(tag).strip().upper() for tag in tags if tag]
    if "CATASTROPHIC" in found:
        return "catastrophic"
    if "CONSIDERABLE" in found:
        return "considerable"
    return None


def _polygons(shape: Any) -> list[list[list[list[float]]]] | None:
    """A Polygon or MultiPolygon as a list of polygons of rings of [longitude, latitude], checked.

    Every number is made a float here and rounded to four places, about eleven metres, which is
    finer than any warning is drawn. Nothing that is not a number survives into the record.
    """
    if not isinstance(shape, Mapping):
        return None
    kind = shape.get("type")
    holds = shape.get("coordinates")
    if kind == "Polygon":
        parts = [holds]
    elif kind == "MultiPolygon":
        parts = holds
    else:
        return None
    if not isinstance(parts, list):
        return None
    polygons: list[list[list[list[float]]]] = []
    if sum(len(ring) for polygon in parts if isinstance(polygon, list)
           for ring in polygon if isinstance(ring, list)) > MOST_POINTS:
        return None
    for polygon in parts:
        if not isinstance(polygon, list):
            continue
        rings = []
        for ring in polygon:
            points = []
            for point in ring if isinstance(ring, list) else []:
                try:
                    x, y = float(point[0]), float(point[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if math.isfinite(x) and math.isfinite(y):
                    points.append([round(x, 4), round(y, 4)])
            if len(points) >= 4:
                rings.append(points)
        if rings:
            polygons.append(rings)
    return polygons or None


# -- the reports -----------------------------------------------------------


def _reports_file(root: Path, state: str) -> Path:
    return Path(root) / "floods" / f"reports-{state}.json"


def reports(
    root: Path,
    service: str,
    state: str,
    *,
    now: datetime | None = None,
    fetch: kept.Fetcher | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Every flood, flash-flood and debris-flow report filed in a state since 2005."""
    now = now or datetime.now(UTC)
    fetch = fetch or kept.fetch
    where = _reports_file(root, state)
    held = kept.read(where, now=now)
    if held is not None and held[1] <= CURRENT_DAYS:
        return list(held[0]), False
    tomorrow = (now + timedelta(days=1)).date().isoformat()
    asked = urllib.parse.urlencode(
        {
            "state": state,
            "type": ",".join(REPORT_KINDS),
            "fmt": "csv",
            "sts": f"{REPORTS_FROM}-01-01T00:00Z",
            "ets": f"{tomorrow}T00:00Z",
        }
    )
    try:
        fresh = parse_reports(
            fetch(f"{service}?{asked}", f"flood reports for {state}"), f"flood reports for {state}"
        )
    except ProviderFailed:
        if held is None:
            raise
        return list(held[0]), True
    kept.write(where, fresh, now=now)
    return fresh, False


#: The columns a report is read from. The archive's CSV carries more; a missing one of these means
#: the shape has changed, which is a failure rather than a quiet blank.
REPORT_COLUMNS = ("VALID", "LAT", "LON", "TYPETEXT", "CITY", "COUNTY", "SOURCE", "REMARK")


def parse_reports(body: bytes, what: str) -> list[dict[str, Any]]:
    try:
        return _read_reports(body, what)
    except csv.Error as exc:
        raise ProviderFailed(f"{what}: the answer was not readable ({exc})") from None


def _read_reports(body: bytes, what: str) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    rows = csv.DictReader(io.StringIO(text))
    header = set(rows.fieldnames or ())
    missing = [column for column in REPORT_COLUMNS if column not in header]
    if missing:
        raise ProviderFailed(
            f"{what}: the answer has no {', '.join(missing)}; the archive has changed"
        )
    found: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row.get("TYPETEXT") or "").strip().upper()
        if kind not in REPORT_KINDS:
            continue
        try:
            latitude, longitude = float(row["LAT"]), float(row["LON"])
            valid = datetime.strptime(str(row["VALID"]).strip(), "%Y%m%d%H%M").replace(tzinfo=UTC)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue
        found.append(
            {
                "at": valid.isoformat().replace("+00:00", "Z"),
                "latitude": round(latitude, 4),
                "longitude": round(longitude, 4),
                "kind": kind.lower(),
                "place": _text(row.get("CITY"), 80),
                "county": _text(row.get("COUNTY"), 60),
                "source": _text(row.get("SOURCE"), 60),
                "remark": _text(row.get("REMARK"), 800),
            }
        )
    return found


def _text(value: Any, longest: int) -> str:
    """A string, trimmed and bounded. It is shown as text and only ever as text (AC-49)."""
    return kept.plain(value, longest)


# -- asking ----------------------------------------------------------------


class Record:
    """The held warnings and reports for some states, arranged for asking about a point."""

    def __init__(
        self,
        warnings: Sequence[Mapping[str, Any]],
        reports: Sequence[Mapping[str, Any]],
        outlines: Any,
        *,
        stale: bool = False,
        reported: Iterable[str] | None = None,
        failures: Sequence[str] = (),
    ) -> None:
        from shapely.geometry import Point, Polygon
        from shapely.ops import unary_union
        from shapely.strtree import STRtree

        self.outlines = outlines
        self.stale = stale
        #: The states whose reports are held. None means every state the outlines hold. A state
        #: missing from here answers its warnings and leaves the report count missing (AC-47).
        self.reported = None if reported is None else set(reported)
        self.failures = list(failures)
        seen: set[tuple[str, int, int]] = set()
        self.warnings: list[Mapping[str, Any]] = []
        shapes = []
        for one in warnings:
            try:
                key = (str(one["office"]), int(one["event"]), int(one["year"]))
                str(one["issued"])
                polygons = []
                for rings in one["polygon"]:
                    polygon = Polygon(rings[0], rings[1:])
                    polygons.append(polygon if polygon.is_valid else polygon.buffer(0))
                shape = polygons[0] if len(polygons) == 1 else unary_union(polygons)
            except (KeyError, TypeError, ValueError, IndexError):
                continue  # a record in a shape this build did not write is not a warning
            if key in seen:
                continue  # the same warning held for two neighbouring states
            seen.add(key)
            self.warnings.append(one)
            shapes.append(shape)
        self._shapes = shapes
        self._tree = STRtree(shapes) if shapes else None

        self.reports = [
            report for report in reports
            if isinstance(report.get("latitude"), (int, float))
            and isinstance(report.get("longitude"), (int, float)) and report.get("at")
        ]
        self._report_points = [Point(r["longitude"], r["latitude"]) for r in self.reports]
        self._report_tree = STRtree(self._report_points) if self._report_points else None

    def answer(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """The five values for a point, or None when the point is in no state this record holds."""
        from shapely.geometry import Point, box

        state = self.outlines.state_of(latitude, longitude)
        if state is None:
            return None
        here = Point(longitude, latitude)
        covering = []
        if self._tree is not None:
            covering = [self.warnings[i] for i in self._tree.query(here, predicate="intersects")]
        latest = max(covering, key=lambda one: one["issued"], default=None)

        nearby = 0
        if self._report_tree is not None:
            dlat = math.degrees(NEARBY_METRES / EARTH_METRES)
            dlon = dlat / max(math.cos(math.radians(latitude)), 0.01)
            near = box(longitude - dlon, latitude - dlat, longitude + dlon, latitude + dlat)
            for i in self._report_tree.query(near):
                report = self.reports[i]
                if _metres(latitude, longitude, report["latitude"], report["longitude"]) <= (
                    NEARBY_METRES
                ):
                    nearby += 1

        day = local_date(latest["issued"], longitude) if latest else None
        found: dict[str, Any] = {
            "flash_flood_warnings": len(covering),
            "flash_flood_emergencies": sum(1 for one in covering if one["emergency"]),
            "flash_flood_latest": day,
            "flash_flood_latest_year": int(day[:4]) if day else None,
        }
        if self.reported is None or state in self.reported:
            found["flood_reports_nearby"] = nearby
        return found

    def within(
        self, start: date, end: date, *, bounds: tuple[float, float, float, float] | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The warnings issued and the reports filed between two local dates, inclusive."""
        warned = []
        for one, shape in zip(self.warnings, self._shapes, strict=True):
            centre = shape.representative_point()
            day = date.fromisoformat(local_date(one["issued"], centre.x))
            if start <= day <= end:
                warned.append({**one, "date": day.isoformat(),
                               "time": local_time(one["issued"], centre.x)})
        filed = []
        for report in self.reports:
            day = date.fromisoformat(local_date(report["at"], report["longitude"]))
            if start <= day <= end:
                filed.append({**report, "date": day.isoformat()})
        return warned, filed

    def latest_emergency(self) -> date | None:
        """The local date of the most recent emergency held, which is where the map opens."""
        found = None
        for one, shape in zip(self.warnings, self._shapes, strict=True):
            if not one["emergency"]:
                continue
            day = date.fromisoformat(local_date(one["issued"], shape.representative_point().x))
            if found is None or day > found:
                found = day
        return found


def _metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_METRES * math.asin(min(1.0, math.sqrt(a)))


def build(
    root: Path,
    states: Iterable[str],
    *,
    warnings_service: str,
    reports_service: str,
    boundaries_service: str,
    now: datetime | None = None,
    fetch: kept.Fetcher | None = None,
    outlines: Any = None,
) -> Record:
    """Everything held for these states, refreshed where stale, as one record to ask.

    A state whose warnings cannot be had at all is left out of the outlines, so its properties read
    as missing rather than as never warned (AC-47). Reports are a separate record: failing to get
    them costs the report count, not the warnings.
    """
    states = tuple(sorted(set(states)))
    held_warnings: list[dict[str, Any]] = []
    held_reports: list[dict[str, Any]] = []
    answered: list[str] = []
    reported: list[str] = []
    stale = False
    failures: list[str] = []
    for state in states:
        try:
            found, old = warnings(root, warnings_service, state, now=now, fetch=fetch)
        except ProviderFailed as exc:
            failures.append(str(exc))
            continue
        answered.append(state)
        held_warnings.extend(found)
        stale = stale or old
        try:
            filed, old = reports(root, reports_service, state, now=now, fetch=fetch)
        except ProviderFailed as exc:
            failures.append(str(exc))
            continue
        reported.append(state)
        held_reports.extend(filed)
        stale = stale or old
    if states and not answered:
        raise ProviderFailed("; ".join(failures) or "flash floods: nothing could be fetched")
    if outlines is None:
        outlines = kept.Outlines.of(root, boundaries_service, answered)
    return Record(
        held_warnings, held_reports, outlines, stale=stale, reported=reported, failures=failures
    )
