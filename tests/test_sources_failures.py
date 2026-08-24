"""One source having a bad afternoon, and what it is allowed to cost.

The rule this file protects is the reason the adapter layer exists at all: a site that is down,
throttling, or has quietly changed its response shape costs that site's listings for that run, and
nothing else. Not the run, not another source's rows, not the history.
"""

from __future__ import annotations

import pytest

from homescout.sources import (
    BaseSource,
    Capabilities,
    City,
    PolitenessConfig,
    Polygon,
    SearchQuery,
    SearchResult,
    SourceFailed,
    SourceUnavailable,
)
from sources_fakes import FakeResponse, FakeTransport, StubSource, listing, session_with


def query(area: object | None = None) -> SearchQuery:
    return SearchQuery(area=area or City("Portales", "NM"))


class Exploding(BaseSource):
    """A source whose adapter has a bug. The worst case, and the one that must stay contained."""

    name = "exploding"

    def capabilities(self) -> Capabilities:
        return Capabilities(applies=frozenset({"price_min"}))

    def run_search(self, q: SearchQuery) -> SearchResult:
        raise RuntimeError("an unforeseen mess")


class Refusing(BaseSource):
    name = "refusing"

    def capabilities(self) -> Capabilities:
        return Capabilities()

    def run_search(self, q: SearchQuery) -> SearchResult:
        raise SourceFailed("the site answered 503 on every attempt")


class Incapable(BaseSource):
    name = "incapable"

    def capabilities(self) -> Capabilities:
        return Capabilities()

    def run_search(self, q: SearchQuery) -> SearchResult:
        raise SourceUnavailable("this site has no concept of a school district")


def test_a_failing_source_reports_a_failure_with_a_readable_reason() -> None:
    """feat-002/AC-12: an outcome and a sentence, not a stack trace."""
    result = Refusing(session_with(FakeTransport())).search(query())

    assert result.outcome == "failed"
    assert result.rows == ()
    assert result.detail is not None
    assert "503" in result.detail


def test_an_adapter_bug_is_still_only_that_sources_problem() -> None:
    """feat-002/AC-12: nothing escapes, including the things nobody anticipated."""
    result = Exploding(session_with(FakeTransport())).search(query())

    assert result.outcome == "failed"
    assert "an unforeseen mess" in (result.detail or "")


def test_a_failure_still_reports_what_the_caller_must_filter() -> None:
    """feat-002/AC-3: a failed source still says which filters it would have applied.

    Which matters: a caller that got no rows and no report cannot tell "this source pushed your
    price filter" from "this source never touches price", and both change what it does next.
    """
    asked = SearchQuery(area=City("Portales", "NM"), price_min=100, sqft_min=1000)

    result = Exploding(session_with(FakeTransport())).search(asked)

    assert result.outcome == "failed"
    assert result.applied["price_min"] is True
    assert result.applied["sqft_min"] is False


def test_unavailable_is_distinguishable_from_failed() -> None:
    """feat-002/AC-13: one might work tomorrow; the other never will."""
    unavailable = Incapable(session_with(FakeTransport())).search(query())
    failed = Refusing(session_with(FakeTransport())).search(query())

    assert unavailable.outcome == "unavailable"
    assert failed.outcome == "failed"
    assert "school district" in (unavailable.detail or "")


def test_an_area_a_source_cannot_express_is_unavailable_not_substituted() -> None:
    """feat-002/AC-13: answering a different question quietly is worse than not answering."""

    class OnlyCities(BaseSource):
        name = "only-cities"

        def capabilities(self) -> Capabilities:
            return Capabilities(accepts_areas=(City,))

        def run_search(self, q: SearchQuery) -> SearchResult:  # pragma: no cover - never reached
            raise AssertionError("the area check should have stopped this")

    shape = Polygon(points=((34.1, -103.3), (34.2, -103.3), (34.2, -103.4)))
    result = OnlyCities(session_with(FakeTransport())).search(query(shape))

    assert result.outcome == "unavailable"
    assert result.rows == ()
    assert "no way to express" in (result.detail or "")


def test_one_source_failing_leaves_another_untouched() -> None:
    """feat-002/AC-12: the whole point. One bad afternoon costs one source's rows."""
    session = session_with(FakeTransport())
    working = StubSource(session, population=["a", "b"])

    broken = Refusing(session).search(query())
    good = working.search(query())

    assert broken.outcome == "failed"
    assert good.outcome == "ok"
    assert [row.source_listing_id for row in good.rows] == ["a", "b"]


def test_a_dead_network_is_every_source_failing_not_an_empty_market() -> None:
    """feat-002/AC-12: 'nothing succeeded' and 'nothing matched' must be tellable apart."""
    config = PolitenessConfig.from_mapping({"max_retries": 0})
    session = session_with(FakeTransport(default=OSError("network unreachable")), config=config)

    outcomes = [
        StubSource(session, population=["a"]).search(query()),
        StubSource(session, population=["b"]).search(query()),
    ]

    assert [r.outcome for r in outcomes] == ["failed", "failed"]
    assert all("network unreachable" in (r.detail or "") for r in outcomes)


def test_a_changed_response_shape_fails_rather_than_returning_half_read_rows() -> None:
    """feat-002/AC-12: loud and empty beats quiet and wrong."""
    from homescout.sources.realtor import normalize

    with pytest.raises(SourceFailed, match="description"):
        normalize.to_fields({"description": "not an object at all"})


def test_a_preview_failure_never_touches_the_query() -> None:
    """feat-002/AC-23: an image is the least important thing a run retrieves."""
    from homescout.sources.realtor import RealtorSource

    config = PolitenessConfig.from_mapping({"max_retries": 0})
    session = session_with(FakeTransport(default=FakeResponse(status=500)), config=config)
    source = RealtorSource(session)
    row = listing("a")
    row = type(row)(
        source="realtor",
        fields=row.fields,
        payload={"primary_photo": {"href": "https://ap.rdcpix.com/x-m1s.jpg"}},
        source_listing_id="a",
        fetched_at=row.fetched_at,
    )

    assert source.fetch_preview(row) is None


def test_a_non_image_response_is_not_stored_as_a_preview() -> None:
    """feat-002/AC-23: a content type that is not an image is not an image."""
    from homescout.sources.realtor import RealtorSource

    session = session_with(
        FakeTransport(default=FakeResponse(body=b"<html>", content_type="text/html"))
    )
    source = RealtorSource(session)
    row = listing("a")
    row = type(row)(
        source="realtor",
        fields=row.fields,
        payload={"primary_photo": {"href": "https://ap.rdcpix.com/x-m1s.jpg"}},
        source_listing_id="a",
    )

    assert source.fetch_preview(row) is None


def test_a_preview_url_with_an_unexpected_scheme_is_never_fetched() -> None:
    """feat-002/AC-23: no value from a response is followed anywhere but over http."""
    from homescout.sources.realtor import RealtorSource

    transport = FakeTransport()
    source = RealtorSource(session_with(transport))
    row = listing("a")
    row = type(row)(
        source="realtor",
        fields=row.fields,
        payload={"primary_photo": {"href": "file:///c:/windows/system32/config/sam"}},
        source_listing_id="a",
    )

    assert source.fetch_preview(row) is None
    assert transport.requests == []
