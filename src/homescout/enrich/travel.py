"""Generated driving polygons, requested once and kept as saved-search geometry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..deliver.settings import environment
from ..errors import InvalidInput
from ..search.areas import AreaError, build
from ..sources import default_session
from ..sources.errors import SourceError
from ..sources.politeness import PolitenessConfig, Request, SourcePolicy
from ..store import Store

KEY = "HOMESCOUT_ORS_API_KEY"
ENDPOINT = "https://api.heigit.org/openrouteservice/v2/isochrones/driving-car"
PROVIDER = "drive_time"
ATTRIBUTION = "openrouteservice by HeiGIT | Data from OpenStreetMap | CC-BY-SA 4.0"


def paced_session():
    # Six seconds between requests stays below the free plan's twenty calls per minute.
    return default_session(config=PolitenessConfig(default=SourcePolicy(
        delay=6, timeout=60, max_retries=2, max_body_bytes=3_000_000,
    )))


class DriveTimes:
    def __init__(self, store: Store, session: Any = None) -> None:
        self.store = store
        self.session = session

    def polygon(self, center: list[float], minutes: float, direction: str,
                *, refresh: bool = False) -> dict:
        # Exact coordinates, rather than rounded cells: road access can change across a street.
        key = json.dumps(["v1", *center, minutes, direction], separators=(",", ":"))
        cached = self.store.cached_values(PROVIDER, (key,)).get(key, {}).get("area")
        if cached is not None and not refresh:
            return cached.value
        credential = environment(self.store.path.parent).get(KEY, "").strip()
        if not credential:
            raise InvalidInput(
                f"Set {KEY} in the .env beside the database to preview a driving area."
            )
        request = Request(
            ENDPOINT, method="POST", allow_redirects=False, max_bytes=3_000_000,
            headers={"Authorization": credential, "Content-Type": "application/json",
                     "Accept": "application/geo+json"},
            body=json.dumps({"locations": [[center[1], center[0]]], "range": [minutes * 60],
                             "range_type": "time", "location_type":
                             "destination" if direction == "to" else "start"}).encode(),
        )
        try:
            fetched = (self.session or paced_session()).request(PROVIDER, request)
        except SourceError:
            # Neither the response body nor transport error is trusted to omit the credential.
            raise InvalidInput(
                "The routing service could not generate that area. Check the key and quota, "
                "then try again. Existing saved areas are unchanged."
            ) from None
        try:
            answer = json.loads(fetched.body)
            features = answer["features"]
            if not isinstance(features, list) or len(features) != 1:
                raise ValueError
            area = {"type": "drive_time", "address": "Public destination", "center": center,
                    "minutes": minutes, "direction": direction, "provider": "openrouteservice",
                    "public_place": True, "generated_at": datetime.now(UTC).isoformat(),
                    "license": "CC-BY-SA 4.0", "attribution": ATTRIBUTION,
                    "geometry": features[0]["geometry"]}
            parsed = build(area)
            area["geometry"] = json.loads(json.dumps(parsed.shape.__geo_interface__))
        except (ValueError, TypeError, KeyError, RecursionError, AreaError):
            raise InvalidInput(
                "The routing service returned no valid driving polygon. Try again."
            ) from None
        # Only validated data enters the cache, so a failed refresh leaves the last answer intact.
        self.store.cache_values(PROVIDER, key, {"area": area})
        return area
