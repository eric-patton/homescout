"""Calculate only requested saved-area route estimates, never collect listings."""

from __future__ import annotations

from datetime import UTC, datetime

from .. import result_filters as filters
from ..deliver.settings import environment
from . import cache
from .matrix import BATCH_SIZE, durations
from .provider import ProviderFailed
from .travel import KEY, paced_session


def credential(store):
    return environment(store.path.parent).get(KEY, "").strip()


def calculate(store, rows, areas, active, *, retry=False, session=None, progress=None):
    owned = session is None
    routing_session = session or paced_session()
    try:
        return _calculate(store, rows, areas, active, retry=retry, session=routing_session,
                          progress=progress)
    finally:
        if owned and (close := getattr(routing_session, "close", None)) is not None:
            close()


def _failed(store, rows, areas, selected):
    now = datetime.now(UTC)
    keys = {filters.route_key(row, area) for area in areas if area["ref"] in selected
            for row in rows if filters.place(row) is not None}
    held = store.cached_values(filters.PROVIDER, list(keys))
    for route_key in keys:
        route = held.get(route_key, {}).get("route")
        if (route and isinstance(route.value, dict)
                and cache._age_days(route.fetched_at, now) <= filters.TTL_DAYS
                and (route.value.get("status") == "unavailable" or (
                    route.value.get("status") == "estimated"
                    and filters.numeric(route.value.get("minutes"))))):
            continue
        store.cache_values(filters.PROVIDER, route_key, {"failure": True})


def _calculate(store, rows, areas, active, *, retry=False, session=None, progress=None):
    say = progress or (lambda _: None)
    key = credential(store)
    if not key:
        return {"degraded": True, "summary": "Routing is unavailable: configure the ORS key."}
    selected = {entry["ref"] for entry in active}
    saved = 0
    for area in areas:
        if area["ref"] not in selected:
            continue
        routing = area["routing"]
        if (routing["provider"] != "openrouteservice" or routing["profile"] != "driving-car"
                or routing["options"] or routing["direction"] not in ("to", "from")):
            raise ProviderFailed("This saved area's routing configuration is unsupported.")
        wanted = {filters.route_key(row, area): filters.place(row) for row in rows
                  if filters.place(row) is not None}
        held = store.cached_values(filters.PROVIDER, list(wanted))
        now = datetime.now(UTC)
        for route_key, values in held.items():
            value, failure = values.get("route"), values.get("failure")
            cooling = not retry and failure and cache._age_days(failure.fetched_at, now) < 1 / 288
            valid = (value and isinstance(value.value, dict) and (
                value.value.get("status") == "unavailable" or (
                    value.value.get("status") == "estimated"
                    and filters.numeric(value.value.get("minutes")))))
            fresh = (valid
                     and cache._age_days(value.fetched_at, now) <= filters.TTL_DAYS
                     and (not retry or value.value.get("status") == "estimated"))
            if cooling or fresh:
                wanted.pop(route_key, None)
        entries = list(wanted.items())
        for start in range(0, len(entries), BATCH_SIZE):
            batch = entries[start:start + BATCH_SIZE]
            try:
                for route_key, minutes in durations(
                    session, batch, routing["center"], routing["direction"],
                    routing["endpoint"], key,
                ):
                    store.cache_values(filters.PROVIDER, route_key, {"route": {
                        "minutes": minutes,
                        "status": "estimated" if minutes is not None else "unavailable",
                    }})
                    saved += 1
                say(f"Driving estimates: {saved} saved; calculating {area['name']}.")
            except ProviderFailed as exc:
                # Keep successful/stale route records and timestamps. A separate short cooldown
                # prevents bound edits from repeatedly retrying an unavailable service.
                _failed(store, rows, areas, selected)
                say(str(exc))
                return {"degraded": True, "summary": str(exc), "saved": saved}
    return {"degraded": False, "saved": saved, "summary": f"{saved} driving estimates saved."}
