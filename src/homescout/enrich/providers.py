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
    """The FCC's national broadband map, which now needs a token.

    Absent by default and honest about why. With no token it makes no request and its values stay
    missing, which is a different thing from a failure: nobody asked and nothing broke. That is
    product invariant 9, and it is the same shape the optional extraction model has.
    """

    name = "broadband"

    def values(self) -> tuple[str, ...]:
        return ("upload_mbps", "download_mbps", "broadband_provider")

    def precision(self) -> int:
        return 4

    def ttl_days(self) -> int | None:
        return 180  # service changes, unlike the ground

    def configured(self) -> bool:
        return settings.token(settings.BROADBAND_TOKEN) is not None

    def why_not(self) -> str:
        return (
            f"the FCC national broadband map requires an API token. Set {settings.BROADBAND_TOKEN} "
            "in your environment or .env file to enable it; without one this provider is skipped "
            "and its values stay missing rather than being reported as a failure."
        )

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        found = settings.token(settings.BROADBAND_TOKEN)
        if found is None:
            raise ProviderFailed(self.why_not())
        where = settings.endpoint(self.name)
        answer = ask_json(
            session,
            self.name,
            where.url,
            {"latitude": latitude, "longitude": longitude, "format": "json"},
        )
        return _broadband_values(answer)


def _broadband_values(answer: Mapping[str, Any]) -> dict[str, Any]:
    """The best fixed service reported at a location.

    Best rather than a list, because a criterion asks whether real internet is available here and
    not who sells it. The fastest available answers that.
    """
    rows = answer.get("results") or answer.get("data") or []
    if not isinstance(rows, list):
        raise ProviderFailed("broadband: the response shape has changed")
    best: dict[str, Any] = {"upload_mbps": None, "download_mbps": None, "broadband_provider": None}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        down = _number(row.get("maxAdvertisedDownloadSpeed") or row.get("max_advertised_download"))
        up = _number(row.get("maxAdvertisedUploadSpeed") or row.get("max_advertised_upload"))
        if down is None:
            continue
        if best["download_mbps"] is None or down > best["download_mbps"]:
            best = {
                "download_mbps": down,
                "upload_mbps": up,
                "broadband_provider": row.get("brandName") or row.get("provider_name"),
            }
    return best


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
