"""What a provider is, and the one helper they all share.

A provider answers questions about a *place*, not about a listing: whether it floods, how high it
is, what is under it, how likely it is to burn. All of those are effectively permanent, which is why
they are cached hard and asked once, and all of them come from public services that move, go down,
and occasionally start refusing you.

So the shape here is deliberately small. A provider says what values it supplies, how precisely to
round a location before asking, how long an answer stays good, whether it can run at all, and how to
ask. The pass knows nothing else about any of them, which is what AC-1 means by adding one requiring
no change to the pass.

The distinction the whole feature turns on lives in `fetch`'s return: a value that is genuinely
absent for a location is `None` in the mapping, and a value nobody asked for is not in the mapping
at all. A point outside every mapped flood zone has an answer. A point nobody has asked about does
not, and rendering the second as the first is how a missing value becomes false good news.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ..sources.errors import SourceError
from ..sources.politeness import PacedSession
from ..sources.transport import Request


class ProviderFailed(Exception):
    """This provider could not answer. One column, not a run."""


@runtime_checkable
class Provider(Protocol):
    """Everything the enrichment pass may assume about a public data service."""

    name: str

    def values(self) -> tuple[str, ...]:
        """The names this provider fills, as the rule engine's namespace calls them."""
        ...

    def precision(self) -> int:
        """Decimal places to round a location to before asking, and therefore the cache key.

        A provider's own business: a flood boundary can run down the middle of a street and needs
        four, while elevation over a hundred metres is the same answer and does not.
        """
        ...

    def ttl_days(self) -> int | None:
        """How long an answer stays fresh. None for facts that do not change."""
        ...

    def configured(self) -> bool:
        """Can this provider run at all? False when it needs something nobody has supplied."""
        ...

    def fetch(self, session: PacedSession, latitude: float, longitude: float) -> Mapping[str, Any]:
        """Ask about one place. Raises `ProviderFailed`; never returns a partial guess."""
        ...


def ask_json(
    session: PacedSession, name: str, url: str, params: Mapping[str, Any]
) -> Mapping[str, Any]:
    """One request, one JSON object, or a failure naming this provider.

    Every provider goes through here, so pacing, backoff, the honest user agent and the body limit
    are the same ones the listing sources use rather than a second set with its own opinions.
    """
    from urllib.parse import urlencode

    query = urlencode({key: value for key, value in params.items() if value is not None})
    try:
        fetched = session.request(name, Request(url=f"{url}?{query}", method="GET"))
    except SourceError as exc:
        raise ProviderFailed(str(exc)) from None

    try:
        found = json.loads(fetched.body)
    except ValueError:
        raise ProviderFailed(
            f"{name} answered with something that is not JSON. The service has probably changed."
        ) from None
    if not isinstance(found, Mapping):
        raise ProviderFailed(f"{name} answered with a {type(found).__name__}, not an object")
    error = found.get("error")
    if isinstance(error, Mapping):
        # ArcGIS answers a refusal with HTTP 200 and an error object, so a caller that only checks
        # the status reads a refusal as data.
        raise ProviderFailed(f"{name} refused: {error.get('message', 'no reason given')}")
    return found


def features_of(answer: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    """The features in an ArcGIS query response, or a failure if the shape has changed.

    An empty list is a real answer and is returned as one: at this point, no feature intersects, and
    that is a fact about the place rather than a fact about the service.
    """
    found = answer.get("features")
    if found is None:
        raise ProviderFailed(f"{name} answered without a features list; the shape has changed")
    if not isinstance(found, list):
        raise ProviderFailed(f"{name} answered with a features list that is not a list")
    return [f for f in found if isinstance(f, Mapping)]


def attributes_of(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    found = feature.get("attributes")
    return found if isinstance(found, Mapping) else {}


def point_query(url: str, latitude: float, longitude: float, fields: str) -> dict[str, Any]:
    """The parameters every ArcGIS point-in-polygon question takes."""
    return {
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": fields,
        "returnGeometry": "false",
        "f": "json",
    }
