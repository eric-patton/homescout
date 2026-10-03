"""The high-hazard dams near a property.

This exists because of McLeod Dam. It is a 25-foot earthen flood-control dam above Garfield and
Salem, built in 1951, and on the afternoon of 29 September 2026 the Weather Service declared a Flash
Flood Emergency for its imminent failure. None of that was news to the federal inventory: it already
had the dam as high hazard, condition poor (assessed March 2023), with no emergency action plan.
New Mexico has 145 high-hazard dams rated poor or unsatisfactory, most of them flood-control dams
built in the fifties and sixties to protect the very towns that have since grown up below them.

**Near, never downstream (AC-54).** The inventory gives each dam as one point, on a structure that
can run more than a mile, and the maps of what a failure would flood are public for nine of New
Mexico's dams, none of them local. Nothing here knows which way a dam drains. So what this says is
how far, how many, and how bad, and it says "near".

**Held a state at a time, and the neighbours too (AC-53).** The inventory's own application asks a
query service for one state's dams; 420 New Mexico dams are 138 kilobytes. A dam ten miles from a
house in Raton is in Colorado, so the states fetched are the store's states and every state that
borders one. Ninety days, because a condition assessment is a thing that happens every few years.

**Codes are read from a table written down here.** The service answers in numbers. Which number is
which condition was read off the national file, where all 411 shared dams agree, and a number not in
the table is a failure that names it, because guessing that an unknown condition is satisfactory is
exactly the false comfort this exists to remove.
"""

from __future__ import annotations

import json
import math
import urllib.parse
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import kept
from .provider import ProviderFailed
from .states import STATES, neighbours

HELD_DAYS = 90

#: How far "nearby" is, for the count and the worst condition.
NEARBY_MILES = 10.0

#: The inventory's hazard potential code for high: a failure would probably cost a life.
HIGH_HAZARD = "4"

#: Hazard codes this build knows, so an unknown one is noticed rather than dropped.
HAZARDS = {"1": "undetermined", "2": "low", "3": "significant", "4": "high"}

#: Condition assessment, by the inventory's code. "Not available" and "not rated" are both unknown,
#: and both read `not rated`, which nothing here ever reads as satisfactory.
CONDITIONS = {
    "1": "satisfactory",
    "2": "fair",
    "3": "poor",
    "4": "unsatisfactory",
    "5": "not rated",
    "6": "not rated",
}

#: Worst first. Unknown sits below every condition that is known to be a problem and above the one
#: that is known to be fine, because "nobody has rated it" is not good news.
WORST_FIRST = ("unsatisfactory", "poor", "fair", "not rated", "satisfactory")

#: Emergency action plan, by the inventory's code.
PLANS = {
    "1": "has an emergency action plan",
    "2": "no emergency action plan",
    "3": "no emergency action plan required",
}

#: Primary purpose, by the inventory's code, for the ones the national file pins down. A purpose
#: is said in a dam's description and decides nothing, so an unknown one is left unsaid rather than
#: failed on.
PURPOSES = {
    "1": "tailings",
    "2": "irrigation",
    "4": "fish and wildlife pond",
    "5": "recreation",
    "7": "debris control",
    "8": "water supply",
    "9": "flood control",
    "10": "fire protection or stock pond",
    "12": "other",
}

NONE_NEARBY = f"none within {NEARBY_MILES:g} miles"

FIELDS = "conditionAssessId,conditionAssessDate,yearCompleted,primaryPurposeId,ownerNames"
EARTH_MILES = 3958.8


def _file(root: Path, state: str) -> Path:
    return Path(root) / "dams" / f"{state}.json"


def states_for(states: Iterable[str]) -> tuple[str, ...]:
    """The states to hold: these, and every state bordering one of them."""
    wanted = set()
    for state in states:
        wanted.add(state)
        wanted.update(neighbours(state))
    return tuple(sorted(code for code in wanted if code in STATES))


def inventory(
    root: Path,
    service: str,
    state: str,
    *,
    now: datetime | None = None,
    fetch: kept.Fetcher | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """One state's high-hazard dams, and whether the copy is stale."""
    now = now or datetime.now(UTC)
    fetch = fetch or kept.fetch
    where = _file(root, state)
    held = kept.read(where, now=now)
    if held is not None and held[1] <= HELD_DAYS:
        return list(held[0]), False
    asked = urllib.parse.urlencode({"sy": f"@stateKey:{state}", "addProps": FIELDS})
    try:
        fresh = parse(fetch(f"{service}?{asked}", f"dams in {state}"), f"dams in {state}")
    except ProviderFailed:
        if held is None:
            raise
        return list(held[0]), True
    kept.write(where, fresh, now=now)
    return fresh, False


def parse(body: bytes, what: str) -> list[dict[str, Any]]:
    try:
        rows = json.loads(body)
    except (ValueError, RecursionError):
        raise ProviderFailed(f"{what}: the answer was not readable") from None
    if not isinstance(rows, list):
        raise ProviderFailed(f"{what}: the answer was not a list; the inventory has changed")
    found = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        hazard = str(row.get("publicHazardId") or "").strip()
        if hazard and hazard not in HAZARDS:
            raise ProviderFailed(f"{what}: hazard code {hazard!r} is not one this build knows")
        if hazard != HIGH_HAZARD:
            continue
        try:
            latitude, longitude = float(row["latitude"]), float(row["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue
        condition = str(row.get("conditionAssessId") or "").strip()
        if condition and condition not in CONDITIONS:
            raise ProviderFailed(
                f"{what}: condition code {condition!r} is not one this build knows, and guessing "
                "that a dam is in good condition is the one guess this must never make"
            )
        plan = str(row.get("eapId") or "").strip()
        if plan and plan not in PLANS:
            raise ProviderFailed(
                f"{what}: emergency plan code {plan!r} is not one this build knows"
            )
        found.append(
            {
                "id": _text(row.get("federalId"), 12),
                "name": _text(row.get("name"), 100) or "an unnamed dam",
                "latitude": round(latitude, 5),
                "longitude": round(longitude, 5),
                "condition": CONDITIONS.get(condition, "not rated"),
                "assessed": _date(row.get("conditionAssessDate")),
                "plan": PLANS.get(plan),
                "built": _year(row.get("yearCompleted")),
                "purpose": PURPOSES.get(str(row.get("primaryPurposeId") or "").strip()),
                "owner": _text(row.get("ownerNames"), 100),
            }
        )
    return found


def _text(value: Any, longest: int) -> str:
    return kept.plain(value, longest)


def _date(value: Any) -> str | None:
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _year(value: Any) -> int | None:
    try:
        found = int(str(value).strip())
    except ValueError:
        return None
    return found if 1600 <= found <= 2100 else None


def describe(dam: Mapping[str, Any], miles: float | None = None) -> str:
    """One dam in a sentence, which is what `dam_nearest` holds."""
    parts = [f"{dam['name']} ({dam['id']})" if dam.get("id") else str(dam["name"])]
    if dam.get("built"):
        parts.append(f"built {dam['built']}")
    condition = str(dam.get("condition") or "not rated")
    assessed = f" ({dam['assessed']})" if dam.get("assessed") else ""
    parts.append(f"condition {condition}{assessed}")
    if dam.get("plan"):
        parts.append(str(dam["plan"]))
    if miles is not None:
        parts.append(f"{miles:.1f} mi")
    return ", ".join(parts)


class Inventory:
    """The held high-hazard dams, arranged for asking which are near a point."""

    def __init__(
        self,
        dams: Sequence[Mapping[str, Any]],
        outlines: Any,
        *,
        stale: bool = False,
        failures: Sequence[str] = (),
    ) -> None:
        from shapely.geometry import Point
        from shapely.strtree import STRtree

        self.failures = list(failures)

        seen: set[str] = set()
        self.dams: list[Mapping[str, Any]] = []
        for dam in dams:
            if not isinstance(dam, Mapping) or not all(
                isinstance(dam.get(name), (int, float)) for name in ("latitude", "longitude")
            ) or not dam.get("name"):
                continue  # a record in a shape this build did not write is not a dam
            key = str(dam.get("id") or f"{dam['latitude']},{dam['longitude']}")
            if key in seen:
                continue
            seen.add(key)
            self.dams.append(dam)
        self.outlines = outlines
        self.stale = stale
        self._points = [Point(d["longitude"], d["latitude"]) for d in self.dams]
        self._tree = STRtree(self._points) if self._points else None

    def answer(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """The four values for a point, or None when its state's inventory is not held."""
        from shapely.geometry import Point, box

        if self.outlines.state_of(latitude, longitude) is None:
            return None
        if self._tree is None:
            return {"dam_miles": None, "dam_nearest": None, "dams_nearby": 0,
                    "dam_worst_nearby": NONE_NEARBY}

        here = Point(longitude, latitude)
        # The tree measures in degrees, and a degree of longitude here is shorter than a degree of
        # latitude, so its nearest is a first guess. The true nearest is no further than that guess
        # really is, so every dam inside a box that size is a candidate, and real distance decides.
        guess = self.dams[int(self._tree.nearest(here))]
        reach = max(
            _miles(latitude, longitude, guess["latitude"], guess["longitude"]), NEARBY_MILES
        )
        dlat = math.degrees(reach / EARTH_MILES)
        dlon = dlat / max(math.cos(math.radians(latitude)), 0.01)
        close = [
            self.dams[i]
            for i in self._tree.query(
                box(longitude - dlon, latitude - dlat, longitude + dlon, latitude + dlat)
            )
        ] or [guess]
        distances = {
            id(dam): _miles(latitude, longitude, dam["latitude"], dam["longitude"]) for dam in close
        }
        best = min(close, key=lambda dam: distances[id(dam)])
        within = [dam for dam in close if distances[id(dam)] <= NEARBY_MILES]
        worst = min(
            (WORST_FIRST.index(str(dam.get("condition") or "not rated")) for dam in within),
            default=None,
        )
        miles = round(distances[id(best)], 1)
        return {
            "dam_miles": miles,
            "dam_nearest": describe(best, miles),
            "dams_nearby": len(within),
            "dam_worst_nearby": WORST_FIRST[worst] if worst is not None else NONE_NEARBY,
        }


def _miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_MILES * math.asin(min(1.0, math.sqrt(a)))


def build(
    root: Path,
    states: Iterable[str],
    *,
    service: str,
    boundaries_service: str,
    now: datetime | None = None,
    fetch: kept.Fetcher | None = None,
    outlines: Any = None,
) -> Inventory:
    """The inventory for these states and their neighbours, refreshed where stale.

    A point is answered only when its own state and every neighbour of it are held, because a
    nearest dam worked out with one side of a border missing is a nearest dam that may be wrong in
    the direction that costs somebody something (AC-53).
    """
    states = tuple(sorted(set(states)))
    held: list[dict[str, Any]] = []
    have: set[str] = set()
    stale = False
    failures: list[str] = []
    for state in states_for(states):
        try:
            found, old = inventory(root, service, state, now=now, fetch=fetch)
        except ProviderFailed as exc:
            failures.append(str(exc))
            continue
        have.add(state)
        held.extend(found)
        stale = stale or old
    answerable = [s for s in states if s in have and all(n in have for n in neighbours(s))]
    if states and not answerable:
        raise ProviderFailed("; ".join(failures) or "dams: nothing could be fetched")
    if outlines is None:
        outlines = kept.Outlines.of(root, boundaries_service, answerable)
    return Inventory(held, outlines, stale=stale, failures=failures)
