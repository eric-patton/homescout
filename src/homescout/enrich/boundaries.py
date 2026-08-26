"""Turning a place name into a shape, which is the thing saved searches has been waiting for.

Saved searches (feat-004) declared a port for this and left it unregistered, because resolving a
name to a boundary is public geospatial data with a cache and a lifetime, which is this feature's
job. Its drift ledger records the consequence: with nothing registered, a radius around a place name
is applied by the source and cannot be re-checked here, and a named area falls back to comparing the
place text a listing carries. Registering this closes that.

Everything here comes from the Census: TIGERweb for the shapes, the geocoder for what contains a
point. Both are keyless and national, and both are cached like every other provider, because a
county boundary is the most permanent fact in this product.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ..store import Store
from . import settings
from .provider import ProviderFailed, ask_json
from .states import STATES as _STATE_NAMES

#: TIGERweb's layer numbers for the shapes a saved search can name. Two for a city, because a place
#: that is not incorporated is a census designated place and lives in a different layer.
LAYERS: dict[str, tuple[int, ...]] = {
    "city": (28, 30),
    "county": (82,),
    "zip": (2,),
    "state": (80,),
}

#: The Census speaks in FIPS codes and a saved search speaks in postal abbreviations.
FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56", "PR": "72",
}

STATES = {code: postal for postal, code in FIPS.items()}

#: The same states by their written-out names, because a saved search may name one either way and
#: the rest of this product already treats the two as the same state (`search/areas.py` normalises
#: `New Mexico` and `NM` to one code before comparing them).
#:
#: Without this, a state written in full resolved to no boundary at all, and the failure was close
#: to invisible: the source that takes a state by name still worked, the two that need a bounding
#: box reported only that they had no way to express the area, and the empty answer was cached, so
#: it outlived the bug. Read from the table that already holds all three federal spellings rather
#: than typed out a second time here.
BY_NAME: dict[str, str] = {
    name.upper(): fips for fips, name in _STATE_NAMES.values()
}

#: A boundary that has been fetched is kept under this provider name, in the same table as every
#: other cached value.
PROVIDER = "boundaries"


def _split(value: str) -> tuple[str, str | None]:
    place, _, state = value.partition(",")
    return place.strip(), (state.strip().upper() or None)


def _quote(text: str) -> str:
    """A value for a `where` clause, with the one character that could break out of it removed.

    A place name is data. It reaches a query string, so the apostrophe in `O'Fallon` has to be
    doubled the way SQL wants, and nothing else about the name is interpreted at all.
    """
    return text.replace("'", "''")


class CensusBoundaries:
    """The boundary provider saved searches asks for, backed by the Census and by the cache."""

    name = PROVIDER

    def __init__(self, store: Store, session: Any = None, *, fetch: bool = True) -> None:
        self._store = store
        self._session = session
        #: Whether this instance may go and ask, or may only answer from what is already cached.
        #:
        #: Cache-only is what a saved search gets. Its geography test runs once per property in
        #: the filtering loop, and a lookup there would put a paced network request in the middle
        #: of a loop that is meant to be local, arithmetic and instant. Boundaries are fetched by
        #: the enrichment pass, which is where going and asking belongs, and read from the cache
        #: everywhere else.
        self._fetch = fetch

    # -- the port saved searches declared ------------------------------------

    def boundary(self, kind: str, value: str) -> Any | None:
        """The shape of a named place, as GeoJSON, or None when nobody can say."""
        if kind not in LAYERS:
            return None
        return self._cached(f"{kind}:{value}", "shape", lambda: self._shape(kind, value))

    def locate(self, place: str) -> tuple[float, float] | None:
        """A place's interior point, which is what a radius around a name needs."""
        found = self._cached(f"locate:{place}", "point", lambda: self._point(place))
        if isinstance(found, list) and len(found) == 2:
            return (float(found[0]), float(found[1]))
        return None

    def candidates(self, kind: str, value: str) -> tuple[str, ...]:
        """Every place this name could mean, for reporting an ambiguity rather than picking one."""
        place, state = _split(value)
        if state is not None:
            return ()
        layer = LAYERS.get(kind, (28,))[0]
        rows = self._query(layer, f"BASENAME='{_quote(place)}'", geometry=False)
        return tuple(
            sorted(
                f"{place}, {STATES[code]}"
                for row in rows
                if (code := str(row.get("attributes", {}).get("STATE", ""))) in STATES
            )
        )

    def containing(self, shape: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
        """The named places a shape falls in, coarsest first.

        Asked of the shape's own middle rather than of every vertex: a coarse query has to *contain*
        the shape, and the county a shape's middle is in is the one a search for it would name. A
        shape spanning two counties is the spec's edge case, and the honest answer for it is the
        several places its own geometry touches, which is what the caller falls back to a covering
        circle for when nothing here can say.
        """
        middle = _middle(shape)
        if middle is None:
            return ()
        latitude, longitude = middle
        answer = self._ask(
            "geocode",
            settings.endpoint("geocode").url,
            {
                "x": longitude,
                "y": latitude,
                "benchmark": "Public_AR_Current",
                "vintage": "Current_Current",
                "layers": "Counties,Incorporated Places,2020 Census ZIP Code Tabulation Areas",
                "format": "json",
            },
        )
        geographies = ((answer.get("result") or {}).get("geographies") or {})
        found: list[tuple[str, str]] = []
        for layer, kind in (
            ("Counties", "county"),
            ("Incorporated Places", "city"),
            ("2020 Census ZIP Code Tabulation Areas", "zip"),
        ):
            rows = geographies.get(layer) or []
            if not rows:
                continue
            row = rows[0]
            state = STATES.get(str(row.get("STATE", "")))
            base = str(row.get("BASENAME") or row.get("NAME") or "").strip()
            if not base:
                continue
            found.append((kind, f"{base}, {state}" if state and kind != "zip" else base))
        return tuple(found)

    # -- asking, and remembering the answer ----------------------------------

    def _shape(self, kind: str, value: str) -> Any | None:
        place, state = _split(value)
        code = FIPS.get(state or "")
        for layer in LAYERS[kind]:
            where = self._where(kind, place, code)
            rows = self._query(layer, where, geometry=True)
            if rows:
                return rows[0].get("geometry")
        return None

    def _where(self, kind: str, place: str, code: str | None) -> str:
        if kind == "zip":
            return f"GEOID='{_quote(place)}'"
        if kind == "state":
            found = FIPS.get(place.upper()) or BY_NAME.get(place.upper()) or code
            return f"STATE='{_quote(found or place)}'"
        clause = f"BASENAME='{_quote(place)}'"
        return f"{clause} AND STATE='{_quote(code)}'" if code else clause

    def _point(self, place: str) -> list[float] | None:
        name, state = _split(place)
        code = FIPS.get(state or "")
        for kind in ("city", "county"):
            for layer in LAYERS[kind]:
                rows = self._query(layer, self._where(kind, name, code), geometry=False)
                for row in rows:
                    attributes = row.get("attributes", {})
                    latitude = attributes.get("INTPTLAT")
                    longitude = attributes.get("INTPTLON")
                    if latitude and longitude:
                        return [float(latitude), float(longitude)]
        return None

    def _query(self, layer: int, where: str, *, geometry: bool) -> list[Mapping[str, Any]]:
        url = f"{settings.endpoint('boundaries').url}/{layer}/query"
        answer = self._ask(
            PROVIDER,
            url,
            {
                "where": where,
                "outFields": "NAME,BASENAME,STATE,GEOID,INTPTLAT,INTPTLON",
                "returnGeometry": "true" if geometry else "false",
                "outSR": "4326",
                "f": "geojson" if geometry else "json",
            },
        )
        rows = answer.get("features") or []
        if not isinstance(rows, list):
            raise ProviderFailed("boundaries: the response shape has changed")
        return [row for row in rows if isinstance(row, Mapping)]

    def _ask(self, name: str, url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return ask_json(self._paced(), name, url, params)

    def _paced(self) -> Any:
        if self._session is None:
            from ..sources import default_session

            self._session = default_session(config=settings.pacing((PROVIDER, "geocode")))
        return self._session

    def _cached(self, key: str, name: str, ask) -> Any | None:
        """Answer from the cache, or ask once and remember, including when the answer is nothing.

        A name nobody can resolve is worth remembering too. Without that, a saved search naming a
        place that does not exist would ask the Census about it on every single run, forever.
        """
        held = self._store.cached_values(PROVIDER, (key,))
        if key in held and name in held[key]:
            return held[key][name].value
        if not self._fetch:
            return None
        try:
            found = ask()
        except ProviderFailed:
            return None
        self._store.cache_values(PROVIDER, key, {name: found})
        return found


def _middle(shape: Mapping[str, Any]) -> tuple[float, float] | None:
    """The middle of a GeoJSON shape's extent, without needing a geometry library here."""
    try:
        text = json.dumps(shape)
    except (TypeError, ValueError):
        return None
    if len(text) > 5_000_000:
        return None
    points: list[tuple[float, float]] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) == 2
            and all(isinstance(part, int | float) for part in value)
        ):
            points.append((float(value[1]), float(value[0])))
            return
        if isinstance(value, list):
            for part in value:
                walk(part)

    walk(shape.get("coordinates"))
    if not points:
        return None
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)


def register(store: Store, session: Any = None, *, fetch: bool = False) -> CensusBoundaries:
    """Register this as the boundary provider saved searches asks for.

    Cache-only by default. A saved search asks about geography once per property, and a boundary
    that had to be fetched at that moment would turn a local test into a paced network request
    inside a loop.
    """
    from ..search.boundaries import register_boundaries

    provider = CensusBoundaries(store, session, fetch=fetch)
    register_boundaries(provider)
    return provider


def resolve(store: Store, areas: Sequence[tuple[str, str]], session: Any = None) -> int:
    """Fetch and cache the shapes for these named places. Returns how many were looked up.

    Called by the enrichment pass, so that the boundaries a saved search names are in the cache
    before anything needs them, and never fetched from inside a filtering loop.
    """
    provider = CensusBoundaries(store, session, fetch=True)
    found = 0
    for kind, value in areas:
        before = store.cached_values(PROVIDER, (f"{kind}:{value}",))
        provider.boundary(kind, value)
        if not before:
            found += 1
    return found
