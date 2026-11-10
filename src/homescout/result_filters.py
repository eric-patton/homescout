"""Results-only drive-time constraints and cache-only evaluation over complete collected rows."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .enrich import cache, settings
from .errors import InvalidInput

PROVIDER = "results_drive_time_v1"
TTL_DAYS = 30


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(",", ":")).encode()).hexdigest()


def destinations(definition: Any) -> list[dict]:
    """Routing identity survives renames/reordering and collection-duration/geometry changes."""
    found = {}
    for area in (*getattr(definition, "areas", ()), *getattr(definition, "exclusions", ())):
        if getattr(area, "kind", None) != "drive_time":
            continue
        travel = area.travel or {}
        routing = {
            "center": list(area.centre), "direction": travel.get("direction"),
            "provider": travel.get("provider"),
            "endpoint": settings.endpoint("church_drive").url,
            "profile": travel.get("profile", "driving-car"),
            "options": travel.get("options", {}),
        }
        # Address changes invalidate a UI reference even when geocoding returns the same point.
        reference = digest([definition.name, area.address, routing])
        found[reference] = {
            "ref": reference, "name": area.name or area.address, "address": area.address,
            "excluded": bool(area.excluded), "routing": routing,
        }
    return list(found.values())


def bound(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = float(value) if not isinstance(value, bool) else float("nan")
    except (ValueError, TypeError, OverflowError):
        number = float("nan")
    if not math.isfinite(number) or number < 0:
        raise InvalidInput("Drive-time bounds must be finite, nonnegative minutes.")
    return number


def validate(raw: Any, areas: Sequence[dict]) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 100:
        raise InvalidInput("Drive-time filters must be a list of at most 100 areas.")
    known = {area["ref"] for area in areas}
    found = {}
    for entry in raw:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("ref"), str):
            raise InvalidInput("Each drive-time filter needs its saved area reference.")
        reference = entry["ref"]
        if reference not in known:
            raise InvalidInput("A drive-time location changed or was removed. Reload the results.")
        low, high = bound(entry.get("min")), bound(entry.get("max"))
        if low is not None and high is not None and low > high:
            raise InvalidInput("Minimum drive time cannot be greater than maximum drive time.")
        if low is not None or high is not None:
            found[reference] = {"ref": reference, "min": low, "max": high}
    return list(found.values())


def place(row: dict) -> tuple[float, float] | None:
    lat, lon = row.get("latitude"), row.get("longitude")
    if (type(lat) in (int, float) and type(lon) in (int, float)
            and math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        return float(lat), float(lon)
    return None


def route_key(row: dict, area: dict) -> str | None:
    point = place(row)
    return digest([list(point), area["routing"]]) if point is not None else None


def numeric(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read(store: Any, rows: Sequence[dict], areas: Sequence[dict], *, configured=True) -> None:
    """Attach estimates in bulk, without network traffic or snapshot changes."""
    for row in rows:
        row["drive_times"] = {}
    for area in areas:
        keys = [(row, route_key(row, area)) for row in rows]
        held = store.cached_values(PROVIDER, [key for _, key in keys if key])
        for row, key in keys:
            value = held.get(key, {}).get("route")
            status = "pending" if key and configured else "unavailable"
            minutes = None
            fresh = None
            failure = held.get(key, {}).get("failure")
            recent_failure = (failure and cache._age_days(
                failure.fetched_at, datetime.now(UTC)) < 1 / 288)
            if recent_failure:
                status = "unavailable"
            if value is not None:
                answer = value.value if isinstance(value.value, dict) else {}
                if answer.get("status") == "estimated" and numeric(answer.get("minutes")):
                    status, minutes = "estimated", answer["minutes"]
                else:
                    status = "unavailable"
                fresh = ("fresh" if cache._age_days(value.fetched_at, datetime.now(UTC))
                         <= TTL_DAYS else "stale")
            row["drive_times"][area["ref"]] = {
                "minutes": minutes, "status": status, "freshness": fresh,
                "fetched_at": value.fetched_at if value else None,
                "refresh_failed": bool(recent_failure and
                                       (value is None or failure.fetched_at > value.fetched_at)),
            }


def match(row: dict, filters: Sequence[dict]) -> str:
    """Definite failure wins over unknown, so counts refer only to undecidable candidates."""
    unknown = None
    for condition in filters:
        estimate = row.get("drive_times", {}).get(condition["ref"], {})
        minutes = estimate.get("minutes")
        if estimate.get("status") != "estimated" or not numeric(minutes):
            if estimate.get("status", "pending") == "pending":
                unknown = unknown or "pending"
            else:
                unknown = "unavailable"
        elif ((condition["min"] is not None and minutes < condition["min"])
              or (condition["max"] is not None and minutes > condition["max"])):
            return "excluded"
    return unknown or "match"


def evaluate(rows: Sequence[dict], filters: Sequence[dict]) -> dict:
    counts = dict.fromkeys(("match", "excluded", "pending", "unavailable"), 0)
    matches = []
    for row in rows:
        status = match(row, filters)
        counts[status] += 1
        if status == "match":
            matches.append(row)
    return {"rows": matches, **counts,
            "complete": not (counts["pending"] or counts["unavailable"])}
