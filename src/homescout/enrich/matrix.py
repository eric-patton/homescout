"""Validated ORS driving matrix batches shared by church and results routing."""

from __future__ import annotations

import json
import math

from ..sources.errors import SourceError, SourceFailed
from ..sources.politeness import Request
from .provider import ProviderFailed

BATCH_SIZE = 100
PACING_KEY = "church_drive"


def durations(session, entries, destination, direction, endpoint, credential):
    if not endpoint.startswith("https://"):
        raise ProviderFailed("Routing endpoint must use HTTPS.")
    locations = [[lon, lat] for _, (lat, lon) in entries]
    locations.append([destination[1], destination[0]])
    many, one = list(range(len(entries))), [len(entries)]
    request = Request(
        endpoint, method="POST", allow_redirects=False, max_bytes=1_000_000,
        headers={"Authorization": credential, "Content-Type": "application/json",
                 "Accept": "application/json"},
        body=json.dumps({"locations": locations,
                         "sources": many if direction == "to" else one,
                         "destinations": one if direction == "to" else many,
                         "metrics": ["duration"], "resolve_locations": False}).encode(),
    )
    try:
        fetched = session.request(PACING_KEY, request)
    except SourceError as exc:
        if unsnappable(exc):
            if len(entries) == 1:
                yield entries[0][0], None
            else:
                middle = len(entries) // 2
                yield from durations(session, entries[:middle], destination, direction,
                                     endpoint, credential)
                yield from durations(session, entries[middle:], destination, direction,
                                     endpoint, credential)
            return
        raise ProviderFailed(
            "Routing request failed. Check service availability, key and quota; "
            "saved estimates are retained."
        ) from None
    try:
        rows = json.loads(fetched.body)["durations"]
        width, height = (1, len(entries)) if direction == "to" else (len(entries), 1)
        if (not isinstance(rows, list) or len(rows) != height
                or any(not isinstance(row, list) or len(row) != width for row in rows)):
            raise ValueError
        seconds = [row[0] for row in rows] if direction == "to" else rows[0]
        if any(value is not None and (type(value) not in (int, float)
               or not math.isfinite(value) or value < 0) for value in seconds):
            raise ValueError
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise ProviderFailed("Routing service returned invalid durations.") from None
    for (key, _), value in zip(entries, seconds, strict=True):
        yield key, None if value is None else value / 60


def unsnappable(exc):
    if not isinstance(exc, SourceFailed) or exc.status not in (400, 404):
        return False
    try:
        return json.loads(exc.detail).get("error", {}).get("code") == 6010
    except (ValueError, TypeError, AttributeError, RecursionError):
        return False
