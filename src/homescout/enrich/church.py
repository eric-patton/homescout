"""Saved house-to-church driving estimates, with no live traffic."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from typing import Any

from ..deliver.settings import environment
from ..store import Store
from . import cache, settings
from .provider import ProviderFailed
from .travel import KEY

DESTINATION = (30.5771925204, -90.57493594311)
CHURCH = "Old Zion Hill Baptist Church"
ADDRESS = "25890 LA-442, Independence, LA 70443"
BATCH_SIZE = 100
Place = tuple[float, float]


class ChurchDrive:
    name = "church_drive"

    def __init__(self) -> None:
        self.store: Store | None = None
        self.louisiana: set[str] = set()
        self.locations: list[Place] = []

    def attach(self, store: Store) -> None:
        self.store = store
        snapshots = store.latest_snapshots()
        snapshots.update(store.merged_stand_ins())
        roots = [
            listing_id for listing_id, snapshot in snapshots.items()
            if ((fields := snapshot.fields).state
                and fields.state.strip().upper() in ("LA", "LOUISIANA")
                and fields.latitude is not None and fields.longitude is not None)
        ]
        self.locations = []
        # A saved result can carry older coordinates, or a constituent's coordinates just after
        # a merge. Enrich those exact places too, without rewriting any observed snapshot.
        for start in range(0, len(roots), 400):
            chunk = roots[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            rows = store.connection.execute(
                "WITH RECURSIVE members(id) AS ("
                f" SELECT id FROM listings WHERE id IN ({marks})"
                " UNION SELECT l.id FROM listings l JOIN members m ON l.superseded_by=m.id"
                " WHERE l.retracted=0)"
                " SELECT DISTINCT s.latitude,s.longitude FROM listing_snapshots s"
                " JOIN members m ON m.id=s.listing_id"
                " WHERE UPPER(TRIM(s.state)) IN ('LA','LOUISIANA')"
                " AND s.latitude IS NOT NULL AND s.longitude IS NOT NULL", chunk,
            )
            self.locations.extend((row[0], row[1]) for row in rows)
        self.locations = list(dict.fromkeys(self.locations))
        self.louisiana = {cache.key_for(*place, self.precision()) for place in self.locations}

    def additional_places(self) -> list[Place]:
        return self.locations

    def values(self) -> tuple[str, ...]:
        return ("church_drive_minutes", "church_drive_status")

    def precision(self) -> int:
        return 6

    def ttl_days(self) -> int:
        return 30

    def coverage(self) -> str:
        return "Louisiana houses driving to Old Zion Hill Baptist Church; no live traffic"

    def _credential(self) -> str:
        if self.store is not None:
            return environment(self.store.path.parent).get(KEY, "").strip()
        return settings.token(KEY) or ""

    def configured(self) -> bool:
        return bool(self._credential())

    def why_not(self) -> str:
        return f"Set {KEY} in the .env beside the database for church driving estimates."

    def fetch(self, session: Any, latitude: float, longitude: float) -> Mapping[str, Any]:
        key = cache.key_for(latitude, longitude, self.precision())
        return next(self.fetch_many(session, {key: (latitude, longitude)}))[1]

    def fetch_many(self, session: Any, wanted: Mapping[str, Place]) -> Iterator[tuple[str, dict]]:
        eligible = []
        for key, place in wanted.items():
            if key not in self.louisiana:
                yield key, self._answer(None, "outside coverage")
            elif (not all(math.isfinite(x) for x in place)
                  or not -90 <= place[0] <= 90 or not -180 <= place[1] <= 180):
                raise ProviderFailed("church_drive: invalid property coordinates")
            else:
                eligible.append((key, place))
        for start in range(0, len(eligible), BATCH_SIZE):
            yield from self._batch(session, eligible[start:start + BATCH_SIZE])

    @staticmethod
    def _answer(minutes: float | None, status: str) -> dict:
        return {"church_drive_minutes": minutes, "church_drive_status": status}

    def _batch(self, session: Any, entries: list[tuple[str, Place]]) -> Iterator[tuple[str, dict]]:
        from .matrix import durations

        credential = self._credential()
        if not credential:
            raise ProviderFailed(self.why_not())
        for key, minutes in durations(session, entries, DESTINATION, "to",
                                      settings.endpoint(self.name).url, credential):
            yield key, self._answer(None if minutes is None else round(minutes, 1),
                                   "route unavailable" if minutes is None else "estimated")
