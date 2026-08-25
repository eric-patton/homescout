"""The six public services, one small class each.

Every one of them answers the same shape of question (what is true at this point) and every one
answers it differently, which is why they are plugins rather than branches in a pass.

Two things they all share and neither is incidental:

**No feature found is an answer.** A point outside every mapped flood zone, or over no principal
aquifer, gets a value: `X` for the first, `false` for the second. That is different from a point
nobody asked about, which gets nothing at all and reads as unknown everywhere downstream. The spec
makes the distinction its first edge case and the rule engine's three-valued logic depends on it.

**A shape that changed is a failure, not an empty answer.** If a service starts returning something
this code cannot read, it raises rather than caching a blank, so the previously cached value stays
and reads as stale. Silently overwriting a real answer with nothing is the one outcome worse than an
outage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..sources.politeness import PacedSession
from . import settings
from .provider import ProviderFailed, ask_json, attributes_of, features_of, point_query

#: The classified wildfire hazard raster answers with a number. These are its classes, from the
#: layer's own legend, mapped to words a criterion can compare against.
WILDFIRE_CLASSES = {
    1: "very low",
    2: "low",
    3: "moderate",
    4: "high",
    5: "very high",
    6: "non-burnable",
    7: "water",
}


class Flood:
    """FEMA's National Flood Hazard Layer, at a point.

    `FLD_ZONE` is the letter everybody means by "flood zone": `A` and `V` zones are the special
    flood hazard areas that carry an insurance requirement, `X` is outside them. `ZONE_SUBTY` is the
    qualifier that distinguishes a 0.2 percent annual chance area from ordinary `X`, which is the
    difference between "not in a flood zone" and "not in a flood zone, but".
    """

    name = "flood"

    def values(self) -> tuple[str, ...]:
        return ("flood_zone",)

    def precision(self) -> int:
        return 4

    def ttl_days(self) -> int | None:
        return 365

    def configured(self) -> bool:
        return True

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        where = settings.endpoint(self.name)
        answer = ask_json(
            session, self.name, where.url, point_query(where.url, latitude, longitude,
                                                       "FLD_ZONE,ZONE_SUBTY")
        )
        found = features_of(answer, self.name)
        if not found:
            # Not a gap. The National Flood Hazard Layer maps the whole country, and a point in no
            # mapped zone is a point in no mapped zone.
            return {"flood_zone": None}
        attributes = attributes_of(found[0])
        zone = attributes.get("FLD_ZONE")
        subtype = attributes.get("ZONE_SUBTY")
        if not zone:
            raise ProviderFailed("flood: a feature came back with no FLD_ZONE")
        return {"flood_zone": f"{zone} ({subtype})" if subtype else str(zone)}


class Elevation:
    """The National Map's elevation point query, in feet, which is how land is described here."""

    name = "elevation"

    def values(self) -> tuple[str, ...]:
        return ("elevation_ft",)

    def precision(self) -> int:
        return 3

    def ttl_days(self) -> int | None:
        return None  # the ground does not move on any schedule this tool cares about

    def configured(self) -> bool:
        return True

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        where = settings.endpoint(self.name)
        answer = ask_json(
            session,
            self.name,
            where.url,
            {"x": longitude, "y": latitude, "units": "Feet", "wkid": 4326,
             "includeDate": "false"},
        )
        raw = answer.get("value")
        if raw is None:
            return {"elevation_ft": None}
        try:
            return {"elevation_ft": round(float(raw), 1)}
        except (TypeError, ValueError):
            raise ProviderFailed(f"elevation: {raw!r} is not a height") from None


class Aquifer:
    """The USGS principal aquifers layer.

    Fetched from Nevada's water agency, which is not a mistake. The dataset is the national USGS
    one; the copies on federal hosts either need a token or no longer answer, and this one serves
    the whole country. The address is configuration like every other, so a better host is a settings
    change.
    """

    name = "aquifer"

    def values(self) -> tuple[str, ...]:
        return ("over_principal_aquifer",)

    def precision(self) -> int:
        return 2

    def ttl_days(self) -> int | None:
        return None

    def configured(self) -> bool:
        return True

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        where = settings.endpoint(self.name)
        answer = ask_json(
            session, self.name, where.url,
            point_query(where.url, latitude, longitude, "AQ_NAME,ROCK_TYPE"),
        )
        found = features_of(answer, self.name)
        # False, not missing. The layer covers the country, so no intersecting polygon means the
        # point is over no principal aquifer, which is a thing worth knowing rather than a gap.
        return {"over_principal_aquifer": bool(found)}


class Wildfire:
    """The USFS classified wildfire hazard potential raster, as a word rather than a pixel."""

    name = "wildfire"

    def values(self) -> tuple[str, ...]:
        return ("wildfire_hazard",)

    def precision(self) -> int:
        return 3

    def ttl_days(self) -> int | None:
        return 1_825  # five years: the model is re-published every few

    def configured(self) -> bool:
        return True

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        where = settings.endpoint(self.name)
        answer = ask_json(
            session,
            self.name,
            where.url,
            {
                "geometry": json.dumps(
                    {"x": longitude, "y": latitude, "spatialReference": {"wkid": 4326}}
                ),
                "geometryType": "esriGeometryPoint",
                "returnGeometry": "false",
                "f": "json",
            },
        )
        raw = answer.get("value")
        if raw in (None, "", "NoData"):
            return {"wildfire_hazard": None}
        try:
            found = int(float(raw))
        except (TypeError, ValueError):
            raise ProviderFailed(f"wildfire: {raw!r} is not a hazard class") from None
        word = WILDFIRE_CLASSES.get(found)
        if word is None:
            raise ProviderFailed(
                f"wildfire: class {found} is not one this build knows. The layer's legend has "
                "probably changed, and guessing at a hazard rating is worse than not having one."
            )
        return {"wildfire_hazard": word}


class Broadband:
    """What internet a place can get, out of the FCC's own files rather than out of a service.

    The only provider here with anything behind it, and the reason is that no service will answer
    this question. The address the first build asked answers 405 and is not an endpoint; the map's
    own point endpoint is closed; the coordinates that would let anybody build a point query are
    licensed. Measured on 2026-08-24, with a real token in hand (feat-007 M-7).

    So the shape is different, and deliberately so (D-12). A state's published files are downloaded
    once, by somebody who asked for that, and reduced to one row per census block. A point on a
    property
    becomes a census block through the FCC's keyless block service, which is one paced request like
    every other provider makes, and the block is answered locally.

    Absent by default and honest about which kind of absent it is. No credentials at all is not
    configured. Credentials and no index is a state nobody has loaded, which names the state and the
    command rather than reading as a failure or as a gap in the data.
    """

    name = "broadband"

    def __init__(self) -> None:
        #: Set by the pass, which holds the store. Nothing else here needs one, so the protocol
        #: stays what it was for the other five and this one gets a hook rather than a parameter.
        self._store: Any = None

    def attach(self, store: Any) -> None:
        self._store = store

    def values(self) -> tuple[str, ...]:
        return ("upload_mbps", "download_mbps", "broadband_provider")

    def precision(self) -> int:
        # Four decimal places is about eleven metres, which is finer than a census block and is the
        # right key: two properties on the same street are usually the same block and one lookup.
        return 4

    def ttl_days(self) -> int | None:
        return 180  # the FCC publishes quarterly, and service changes, unlike the ground

    def configured(self) -> bool:
        return bool(self._account()) and bool(self._loaded())

    def why_not(self) -> str:
        if not self._account():
            return (
                f"the FCC's file API needs an account name and a token. Set "
                f"{settings.BROADBAND_USERNAME} and {settings.BROADBAND_TOKEN} in your environment "
                "or .env file to enable it; without both this provider is skipped and its values "
                "stay missing rather than being reported as a failure."
            )
        return (
            "no state's broadband data has been downloaded yet. There is no per-property service "
            "to ask, so this reads the FCC's own published files, one state at a time: run "
            "`homescout broadband --state NM` for the state you are searching. It is about fifty "
            "megabytes and half a minute."
        )

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        from . import broadband as fcc
        from . import states

        if self._store is None:
            raise ProviderFailed(
                "broadband was asked without a store to read the downloaded data from, which is a "
                "wiring mistake rather than anything about this property."
            )
        try:
            block, state = fcc.block_for(session, latitude, longitude)
        except fcc.BroadbandUnavailable as exc:
            raise ProviderFailed(f"broadband: {exc}") from None

        loaded = self._loaded()
        if state not in loaded:
            where = states.name_of(state) or state
            raise ProviderFailed(
                f"broadband: this property is in {where}, and no data for {state} has been "
                f"downloaded. Run `homescout broadband --state {state}`. "
                + (f"Loaded: {', '.join(sorted(loaded))}." if loaded else "")
            )

        found = self._store.broadband_for(block)
        if found is None:
            # The state is loaded and this block is not in it, which is an answer: the FCC has no
            # filed residential service here. A known negative, not a gap, which is the same
            # distinction the flood provider makes for a point outside a mapped hazard area.
            return {"download_mbps": None, "upload_mbps": None, "broadband_provider": None}

        return {
            "download_mbps": found.get("download_mbps"),
            "upload_mbps": found.get("upload_mbps"),
            "broadband_provider": found.get("providers") or None,
        }

    def _account(self) -> tuple[str, str] | None:
        from . import broadband as fcc

        return fcc.credentials(None)

    def _loaded(self) -> dict[str, Any]:
        if self._store is None:
            return {}
        try:
            return self._store.broadband_states()
        except Exception:  # noqa: BLE001 - an old database has no such table, which is "none"
            return {}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
