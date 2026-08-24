"""Redfin.

Not a library and not an API: the download button behind the map, which hands back a CSV. It takes a
polygon, which a bounding box already is, so unlike the other two sources it needs no place lookup
at all.

Three measured facts shape everything here.

**The cap is 350 and the response does not mention it.** A query matching four thousand properties
and a query matching exactly three hundred and fifty come back identical in shape. So getting
exactly the cap is read as "there are more", which is the only honest conclusion available, and the
query is then cut in half and each half asked separately.

**It will not narrow by lot size.** Every parameter name for it was tried and none changed the
result, while every other filter measured does work. So lot size is not declared, and the caller
filters it locally and is told that it has to. For a search about acreage that matters: this
source's 350 rows will be mostly properties the local test is about to discard.

**It cannot say when a region's listing service forbids downloads.** Every response in every region
carries the same line about local rules, and a metropolitan box in one state returns two properties
where a town of twelve thousand in another returns sixty-one. The restriction is real and invisible.
So the site's own notice rides on every result rather than being read as a signal, and `unavailable`
is kept for the refusals that are unambiguous: a response that is not a download at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

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

#: What every result says, because the site says it on every response. Not a truncation: a
#: truncation that is always on stops meaning anything. A caveat that is always true is still worth
#: repeating, because the alternative is a person reading a short list as a quiet market.
STANDING_CAVEAT = (
    "Redfin's download excludes listings its local MLS does not permit, in every region, and does "
    "not say which or how many. Treat this source's contribution as incomplete."
)


def _utc_text() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class RedfinSource(BaseSource):
    name = "redfin"

    def __init__(self, session: PacedSession) -> None:
        super().__init__(session)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            applies=queries.APPLIES,
            accepts_areas=_ACCEPTED_AREAS,
            ceiling=queries.ROW_CAP,
            page_size=queries.PAGE_SIZE,
        )

    # -- the search ---------------------------------------------------------

    def run_search(self, query: SearchQuery) -> SearchResult:
        if not isinstance(query.area, BoundingBox):
            raise SourceUnavailable(
                f"redfin cannot express {query.area.as_term()}; it takes a bounding box. "
                "No substitute area was searched."
            )

        harvest = collect(
            query,
            fetch_page=lambda q, offset: self._page(q, offset),
            split=_split_by_box,
            ceiling=queries.ROW_CAP,
            page_size=queries.PAGE_SIZE,
        )
        return SearchResult(
            source=self.name,
            outcome="ok",
            rows=harvest.rows,
            applied=self.capabilities().application(query),
            truncation=harvest.truncation,
            detail=STANDING_CAVEAT,
            request_count=harvest.request_count,
        )

    def _page(self, query: SearchQuery, offset: int) -> Page:
        """One box, in one download.

        The offset is ignored, and deliberately: the download is not paginated in any way this
        adapter can rely on, so the walk is told the page size is the cap and therefore never asks
        for a second one. Getting everything out of an oversized box is done by cutting the box.
        """
        area = query.area
        if not isinstance(area, BoundingBox):  # pragma: no cover - guarded by run_search
            raise SourceUnavailable("redfin was handed something that is not a box")

        text = self._download(queries.parameters(query, area, self.capabilities().applies))
        rows, _notice = normalize.read(text)
        fetched_at = _utc_text()
        return Page(
            rows=normalize.to_rows(rows, fetched_at=fetched_at),
            total=_inferred_total(len(rows)),
        )

    # -- preview images -----------------------------------------------------

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        """None, always, because the download carries no images.

        The interface obliges every adapter to decide what preview retrieval means for it rather
        than letting one quietly inherit nothing, and this source's answer is that there is nothing
        to retrieve: the CSV has twenty-seven columns and not one of them is a photograph.

        Scraping the linked page for one would be a second request per property against a site this
        tool is trying to be light on, to get an image the digest can already do without. So a
        Redfin-only property appears in the email without a picture, which is the same thing that
        happens when an image fetch fails.
        """
        return None

    # -- transport ----------------------------------------------------------

    def _download(self, parameters: Mapping[str, str]) -> str:
        query = "&".join(f"{key}={_escaped(value)}" for key, value in sorted(parameters.items()))
        fetched = self.session.request(
            self.name,
            Request(
                url=f"{queries.endpoint()}?{query}",
                method="GET",
                headers={"Accept": "text/csv,text/plain"},
            ),
        )
        text = fetched.body.decode("utf-8", errors="replace")
        _refuse_if_not_a_download(text)
        return text


def _escaped(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value), safe=",.-")


def _refuse_if_not_a_download(text: str) -> None:
    """Everything the endpoint answers that is not a CSV, named rather than parsed hopefully.

    This is what AC-7's `unavailable` is actually for. The site cannot tell us that a region's
    listing service forbids downloads, but it can and does tell us when it will not serve one at
    all, and those answers are unambiguous.
    """
    head = text.lstrip()[:400]
    if head.startswith("{}&&"):
        raise SourceUnavailable(
            f"redfin refused the download: {head[4:200]}"
        )
    if head[:1] == "<":
        raise SourceUnavailable(
            "redfin answered with a web page rather than a download, which is what its block page "
            "looks like. No rows were taken from it."
        )
    if not head:
        raise SourceUnavailable("redfin answered with an empty body rather than a download.")
    if not head.upper().startswith("SALE TYPE"):
        raise SourceFailed(
            "redfin's download does not begin with the header it has always begun with. "
            f"It starts {head[:80]!r}. No rows are returned rather than rows read from a shape "
            "this adapter does not recognize."
        )


def _inferred_total(found: int) -> int:
    """How many properties match, as far as anything here can tell.

    The download reports no count at all, so exactly the cap is read as "there are more" and cut,
    and anything under the cap is read as the whole answer. A market with exactly 350 properties in
    it costs one unnecessary split. That is the right way round: the other error presents a capped
    result as a complete one, which is the failure this whole layer exists to prevent.
    """
    return found + 1 if found >= queries.ROW_CAP else found


def _split_by_box(query: SearchQuery) -> tuple[SearchQuery, SearchQuery] | None:
    """Cut a query in two along the longer side of its box."""
    if not isinstance(query.area, BoundingBox):
        return None
    halves = halve(query.area)
    if halves is None:
        return None
    return replace(query, area=halves[0]), replace(query, area=halves[1])


def factory(session: PacedSession) -> RedfinSource:
    return RedfinSource(session)
