"""Realtor.com.

The best-structured of the three free sources, and the one this feature ships to prove the interface
is worth having. It answers a public GraphQL endpoint that needs no token, no cookie, and no login,
which is why this adapter has no authentication code at all rather than careful authentication code.

Geography resolves in two steps because that is how the source thinks: a free-text term becomes the
site's own place object, and the search is then issued against that place. An area the site has no
way to express (a drawn polygon, a bounding box) is reported unavailable rather than swapped for
something nearby, because answering a different question quietly is worse than not answering.

The site caps one query at ten thousand results. The way around that is to cut the query by the date
a listing appeared, which is the only dimension it will divide on, and the cutting itself lives in
`ceiling.py` where every source shares it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from ...records import SourceRow
from ..base import (
    AddressRadius,
    BaseSource,
    Capabilities,
    City,
    County,
    DateRange,
    PostalCode,
    Preview,
    SearchQuery,
    SearchResult,
    State,
)
from ..ceiling import Page, collect
from ..errors import SourceFailed, SourceUnavailable
from ..politeness import PacedSession, Request
from . import normalize, queries

#: The site's own cap. Documented nowhere, observable everywhere.
RESULT_CEILING = 10_000
PAGE_SIZE = 200

#: How far back a split may reach when a query has no date bound of its own. Nothing on this site
#: was listed before it existed, so this is a bound on the arithmetic, not on the results.
EARLIEST_LISTING_DATE = "1990-01-01"

#: Only what the site actually narrows on its own side. Anything not named here is never sent, and
#: is reported back to the caller as still needing local filtering. Growing this list means proving
#: the request measurably changes, which is what the test for it does.
APPLIES = frozenset(
    {
        "price_min",
        "price_max",
        "beds_min",
        "beds_max",
        "baths_min",
        "baths_max",
        "sqft_min",
        "sqft_max",
        "lot_sqft_min",
        "lot_sqft_max",
        "year_built_min",
        "year_built_max",
        "property_types",
        "listing_status",
        "listed_since",
    }
)

#: Each declared filter, and the fragment that expresses it. The request is built by walking this
#: table, so a field absent from it has no path into a request even if someone adds it to a query.
_FILTER_FRAGMENTS: dict[str, tuple[str, str]] = {
    "price_min": ("list_price", "min"),
    "price_max": ("list_price", "max"),
    "beds_min": ("beds", "min"),
    "beds_max": ("beds", "max"),
    "baths_min": ("baths", "min"),
    "baths_max": ("baths", "max"),
    "sqft_min": ("sqft", "min"),
    "sqft_max": ("sqft", "max"),
    "lot_sqft_min": ("lot_sqft", "min"),
    "lot_sqft_max": ("lot_sqft", "max"),
    "year_built_min": ("year_built", "min"),
    "year_built_max": ("year_built", "max"),
}

_ACCEPTED_AREAS = (PostalCode, City, County, State, AddressRadius)


@dataclass(frozen=True, slots=True)
class Place:
    """A term as the source resolved it."""

    text: str
    area_type: str
    latitude: float | None = None
    longitude: float | None = None


class RealtorSource(BaseSource):
    name = "realtor"

    def __init__(self, session: PacedSession, *, version: str = "0.1.0") -> None:
        super().__init__(session)
        self._version = version
        self._headers = queries.headers(version)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            applies=APPLIES,
            accepts_areas=_ACCEPTED_AREAS,
            ceiling=RESULT_CEILING,
            page_size=PAGE_SIZE,
        )

    # -- the search ---------------------------------------------------------

    def run_search(self, query: SearchQuery) -> SearchResult:
        place = self._resolve(query.area)
        harvest = collect(
            query,
            fetch_page=lambda q, offset: self._page(place, q, offset),
            split=_split_by_listing_date,
            ceiling=RESULT_CEILING,
            page_size=PAGE_SIZE,
        )
        return SearchResult(
            source=self.name,
            outcome="ok",
            rows=harvest.rows,
            applied=self.capabilities().application(query),
            truncation=harvest.truncation,
            request_count=harvest.request_count,
        )

    def _resolve(self, area: Any) -> Place:
        """Turn an area into the site's own place object, or say it cannot be expressed."""
        if not isinstance(area, _ACCEPTED_AREAS):
            raise SourceUnavailable(
                f"realtor cannot express {area.as_term()}; it takes named places and a radius "
                "around an address, not arbitrary shapes"
            )

        data = self._post(
            queries.GEOGRAPHY_QUERY,
            {"searchInput": {"search_term": area.as_term()}},
            "Search_suggestions",
        )
        results = (data.get("search_suggestions") or {}).get("geo_results") or []
        if not results:
            raise SourceUnavailable(
                f"realtor does not recognize {area.as_term()!r} as a place. "
                "No substitute area was searched."
            )

        wanted = _expected_area_type(area)
        chosen = next(
            (r for r in results if ((r.get("geo") or {}).get("area_type")) == wanted),
            results[0],
        )
        geo = chosen.get("geo") or {}
        centroid = geo.get("centroid") or {}
        if isinstance(area, AddressRadius) and not centroid:
            raise SourceUnavailable(
                f"realtor resolved {area.address!r} but gave it no coordinates, "
                "so a radius around it cannot be searched"
            )
        return Place(
            text=str(chosen.get("text") or area.as_term()),
            area_type=str(geo.get("area_type") or ""),
            latitude=centroid.get("lat"),
            longitude=centroid.get("lon"),
        )

    def _page(self, place: Place, query: SearchQuery, offset: int) -> Page:
        document, variables = self._build(place, query, offset)
        data = self._post(document, variables, "GetHomeSearch")
        search = data.get("homeSearch")
        if not isinstance(search, Mapping):
            raise SourceFailed(
                "realtor: the response carried no homeSearch block. "
                "The source's response shape has probably changed."
            )
        results = search.get("results") or []
        if not isinstance(results, list):
            raise SourceFailed("realtor: expected results to be a list; the shape has changed.")
        fetched_at = _utc_text()
        return Page(
            rows=tuple(normalize.to_row(home, fetched_at=fetched_at) for home in results),
            total=int(search.get("total") or 0),
        )

    def _build(self, place: Place, query: SearchQuery, offset: int) -> tuple[str, dict[str, Any]]:
        """Assemble the request from the capability declaration, and only from it."""
        applies = self.capabilities().applies

        filters: list[str] = []
        grouped: dict[str, dict[str, Any]] = {}
        for name, (field_name, bound) in _FILTER_FRAGMENTS.items():
            if name not in applies:
                continue
            value = getattr(query, name, None)
            if value is None:
                continue
            grouped.setdefault(field_name, {})[bound] = value
        for field_name, bounds in grouped.items():
            parts = ", ".join(f"{bound}: {value}" for bound, value in sorted(bounds.items()))
            filters.append(f"{field_name}: {{ {parts} }}")

        types = ""
        if "property_types" in applies and query.property_types:
            types = f"type: {json.dumps(list(query.property_types))}"

        status = ""
        if "listing_status" in applies and query.listing_status:
            status = f"status: {query.listing_status}"

        dates = _date_fragment(query) if "listed_since" in applies else ""

        parts = {
            "status": status,
            "dates": dates,
            "types": types,
            "filters": "\n      ".join(filters),
            "limit": PAGE_SIZE,
            "fields": queries.HOME_FIELDS,
        }

        if place.area_type == "address":
            document = queries.RADIUS_SEARCH % parts
            #: The radius comes from what was asked for. Reading it off the resolved place would
            #: lose it: the place knows where it is, only the query knows how far around it to look.
            miles = query.area.miles if isinstance(query.area, AddressRadius) else 0
            variables = {
                "coordinates": [place.longitude, place.latitude],
                "radius": f"{miles:g}mi",
                "offset": offset,
            }
            return document, variables

        document = queries.AREA_SEARCH % parts
        return document, {"search_location": {"location": place.text}, "offset": offset}

    # -- preview images -----------------------------------------------------

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        """One small image for one row, or nothing at all.

        Nothing here can fail a query: the caller runs this after the search has already reported
        its outcome, and a failure returns None. A row without an image is a row without an image,
        which the store treats as leaving whatever image it already holds alone.
        """
        payload = row.payload if isinstance(row.payload, Mapping) else {}
        url = normalize.preview_url(payload)
        if not url or urlsplit(url).scheme not in ("http", "https"):
            return None
        try:
            fetched = self.session.fetch_image(self.name, url)
        except SourceFailed:
            return None
        content_type = (fetched.content_type or "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            return None
        return Preview(source_url=url, content_type=content_type, data=fetched.body)

    # -- transport ----------------------------------------------------------

    def _post(
        self, document: str, variables: Mapping[str, Any], operation: str
    ) -> Mapping[str, Any]:
        body = json.dumps(
            {
                "operationName": operation,
                "query": queries.minified(document),
                "variables": dict(variables),
            },
            separators=(",", ":"),
        ).encode()
        fetched = self.session.request(
            self.name,
            Request(
                url=queries.ENDPOINT,
                method="POST",
                body=body,
                headers=self._headers,
            ),
        )
        try:
            payload = json.loads(fetched.body)
        except ValueError as exc:
            raise SourceFailed(f"realtor returned something that is not JSON: {exc}") from None
        if not isinstance(payload, Mapping):
            raise SourceFailed("realtor returned JSON that is not an object")
        errors = payload.get("errors")
        if errors:
            first = errors[0].get("message") if isinstance(errors[0], Mapping) else errors[0]
            raise SourceFailed(f"realtor reported an error: {first}")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SourceFailed("realtor returned no data block")
        return data


def _expected_area_type(area: Any) -> str:
    return {
        PostalCode: "postal_code",
        City: "city",
        County: "county",
        State: "state",
        AddressRadius: "address",
    }[type(area)]


def _date_fragment(query: SearchQuery) -> str:
    span = query.listed_between
    if span is not None and (span.start or span.end):
        bounds = []
        if span.start:
            bounds.append(f'min: "{span.start}"')
        if span.end:
            bounds.append(f'max: "{span.end}"')
        return f"list_date: {{ {', '.join(bounds)} }}"
    if query.listed_since:
        return f'list_date: {{ min: "{query.listed_since}" }}'
    return ""


def _split_by_listing_date(query: SearchQuery) -> tuple[SearchQuery, SearchQuery] | None:
    """Cut a query in two along the date a listing appeared.

    The only dimension this source will divide on. Returns None once the two halves would cover the
    same day, which is where an oversized query stops being divisible and becomes an honest
    truncation.
    """
    span = query.listed_between or DateRange(
        start=query.listed_since or EARLIEST_LISTING_DATE,
        end=_today().isoformat(),
    )
    start = date.fromisoformat(span.start or EARLIEST_LISTING_DATE)
    end = date.fromisoformat(span.end or _today().isoformat())
    if (end - start).days < 2:
        return None
    middle = start + (end - start) / 2
    return (
        query.within(DateRange(start=start.isoformat(), end=middle.isoformat())),
        query.within(
            DateRange(start=(middle + timedelta(days=1)).isoformat(), end=end.isoformat())
        ),
    )


def _today() -> date:
    return datetime.now(UTC).date()


def _utc_text() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def factory(session: PacedSession) -> RealtorSource:
    return RealtorSource(session)
