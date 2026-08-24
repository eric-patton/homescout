"""Zillow.

The source that takes a box and refuses to hand over more than about five hundred results for it,
whatever you do. That refusal is the whole shape of this adapter: the query planner hands it a
bounding box, it asks once, and if the site says more properties match than it will return, the box
is cut in half and each half is asked separately, until every piece is small enough to answer
completely.

Two things measured on the day this was built are worth knowing before reading further.

**One request is a whole box.** The response carries both a paginated list of results and a set of
map results, and the map results are every property in the box, each with the same detail. So this
adapter reads the map results and never pages, which is fewer requests than the obvious
implementation and therefore politer as well as simpler.

**The endpoint every write-up names is gone.** `GetSearchPageState.htm` answers 404 with Zillow's
own error page. The one that answers is a `PUT` with a JSON body, and like every other external
address in this project it is configuration.

No credential, no cookie, no login. Both were checked: the site answers this tool's own user agent
with nothing else attached, which is why there is no authentication code here rather than careful
authentication code.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from ...records import SourceRow
from ..base import (
    BaseSource,
    BoundingBox,
    Capabilities,
    Preview,
    SearchQuery,
    SearchResult,
)
from ..boxes import halve
from ..ceiling import Page, collect
from ..errors import SourceFailed, SourceUnavailable
from ..politeness import PacedSession, Request
from . import normalize, queries

_ACCEPTED_AREAS = (BoundingBox,)


def _utc_text() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class ZillowSource(BaseSource):
    name = "zillow"

    def __init__(self, session: PacedSession) -> None:
        super().__init__(session)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            applies=queries.APPLIES,
            accepts_areas=_ACCEPTED_AREAS,
            ceiling=queries.RESULT_CEILING,
            page_size=queries.PAGE_SIZE,
        )

    # -- the search ---------------------------------------------------------

    def run_search(self, query: SearchQuery) -> SearchResult:
        if not isinstance(query.area, BoundingBox):
            raise SourceUnavailable(
                f"zillow cannot express {query.area.as_term()}; it takes a bounding box. "
                "No substitute area was searched."
            )

        harvest = collect(
            query,
            fetch_page=lambda q, offset: self._page(q, offset),
            split=_split_by_box,
            ceiling=queries.RESULT_CEILING,
            page_size=queries.PAGE_SIZE,
        )
        return SearchResult(
            source=self.name,
            outcome="ok",
            rows=harvest.rows,
            applied=self.capabilities().application(query),
            truncation=harvest.truncation,
            request_count=harvest.request_count,
        )

    def _page(self, query: SearchQuery, offset: int) -> Page:
        """One box, in one request.

        The offset is ignored on purpose and the fact is worth stating rather than hiding: the map
        results are the whole box, so there is no second page to ask for. The walk knows this
        because the declared page size is the ceiling, so it never asks.
        """
        area = query.area
        if not isinstance(area, BoundingBox):  # pragma: no cover - guarded by run_search
            raise SourceUnavailable("zillow was handed something that is not a box")

        payload = self._put(queries.body(query, area, self.capabilities().applies))
        cat1 = payload.get("cat1")
        if not isinstance(cat1, Mapping):
            raise SourceFailed(
                "zillow: the response carried no cat1 block. "
                "The source's response shape has probably changed."
            )
        results = cat1.get("searchResults")
        if not isinstance(results, Mapping):
            raise SourceFailed("zillow: expected a searchResults block; the shape has changed.")

        homes = results.get("mapResults")
        if homes is None:
            homes = results.get("listResults")
        if not isinstance(homes, list):
            raise SourceFailed("zillow: expected map results to be a list; the shape has changed.")

        fetched_at = _utc_text()
        return Page(
            rows=tuple(normalize.to_row(home, fetched_at=fetched_at) for home in homes),
            total=_total(cat1, len(homes)),
        )

    # -- preview images -----------------------------------------------------

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        """One small image for one row, or nothing at all.

        Nothing here can fail a query: the caller runs this after the search has already reported
        its outcome, and a failure returns None.
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

    def _put(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        fetched = self.session.request(
            self.name,
            Request(
                url=queries.endpoint(),
                method="PUT",
                body=json.dumps(body, separators=(",", ":")).encode(),
                headers=queries.headers(),
            ),
        )
        try:
            payload = json.loads(fetched.body)
        except ValueError as exc:
            raise SourceFailed(
                f"zillow returned something that is not JSON: {exc}. "
                "That is what its block page and its 404 page both look like."
            ) from None
        if not isinstance(payload, Mapping):
            raise SourceFailed("zillow returned JSON that is not an object")
        return payload


def _total(cat1: Mapping[str, Any], fallback: int) -> int:
    """How many properties the site says match, which is what decides whether to split.

    The count is the true one even when the rows are capped: twenty thousand reported, five hundred
    delivered. That asymmetry is the only reason splitting can work at all, so a response without a
    count is a response this adapter cannot reason about.
    """
    listing = cat1.get("searchList")
    if isinstance(listing, Mapping):
        total = listing.get("totalResultCount")
        if isinstance(total, int):
            return total
    return fallback


def _split_by_box(query: SearchQuery) -> tuple[SearchQuery, SearchQuery] | None:
    """Cut a query in two along the longer side of its box.

    The only dimension this source will divide on, and the one the query planner already speaks.
    Returns None once the box is too small to cut usefully, which is where an oversized query stops
    being divisible and becomes an honest truncation.
    """
    from dataclasses import replace

    if not isinstance(query.area, BoundingBox):
        return None
    halves = halve(query.area)
    if halves is None:
        return None
    return replace(query, area=halves[0]), replace(query, area=halves[1])


def factory(session: PacedSession) -> ZillowSource:
    return ZillowSource(session)
