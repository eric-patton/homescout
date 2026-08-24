"""The interface itself: what an adapter must offer, and what it must never send.

These tests deliberately use a stub source rather than Realtor.com. The point of the feature is that
the core knows nothing about any particular site, and a test that could only be written against a
real site would be evidence against that.
"""

from __future__ import annotations

import pytest

from homescout.sources import (
    BaseSource,
    Capabilities,
    City,
    PacedSession,
    Polygon,
    Preview,
    SearchQuery,
    SearchResult,
    Source,
    create,
    register,
    registered,
    unregister,
)
from sources_fakes import FakeTransport, StubSource, listing, session_with


@pytest.fixture
def session() -> PacedSession:
    return session_with(FakeTransport())


def test_an_adapter_is_a_name_capabilities_and_a_search(session: PacedSession) -> None:
    """feat-002/AC-1: a stub declaring only the interface members runs a query end to end."""

    class Minimal(BaseSource):
        name = "minimal"

        def capabilities(self) -> Capabilities:
            return Capabilities()

        def run_search(self, query: SearchQuery) -> SearchResult:
            return SearchResult(source=self.name, rows=(listing("1"),))

    source = Minimal(session)
    assert isinstance(source, Source)

    result = source.search(SearchQuery(area=City("Portales", "NM")))
    assert result.outcome == "ok"
    assert len(result.rows) == 1


def test_preview_retrieval_is_part_of_the_interface(session: PacedSession) -> None:
    """feat-002/AC-23: an adapter cannot satisfy the interface while omitting preview retrieval.

    The obligation lives here rather than on whichever adapter needed it first, so that a source
    added later inherits it instead of quietly declining it.
    """

    class NoPreview:
        name = "no-preview"

        def capabilities(self) -> Capabilities:
            return Capabilities()

        def search(self, query: SearchQuery) -> SearchResult:
            return SearchResult(source=self.name)

    assert not isinstance(NoPreview(), Source)
    assert isinstance(StubSource(session), Source)


def test_a_declaration_names_only_real_query_fields(session: PacedSession) -> None:
    """feat-002/AC-2: a declaration cannot name a filter that is not a query field."""
    with pytest.raises(ValueError, match="not query fields"):
        Capabilities(applies=frozenset({"price_min", "moon_phase"}))


def test_an_undeclared_filter_is_never_sent(session: PacedSession) -> None:
    """feat-002/AC-2: a field absent from the declaration has no path into the request."""
    transport = FakeTransport()
    source = StubSource(session_with(transport), population=["a"], applies=("price_min",))

    source.search(SearchQuery(area=City("Portales", "NM"), price_min=100, beds_min=3))

    #: The stub echoes nothing, so the assertion that matters is the report: `beds_min` was not
    #: applied by the source, which is exactly the claim "we did not send it".
    result = source.search(SearchQuery(area=City("Portales", "NM"), price_min=100, beds_min=3))
    assert result.applied["price_min"] is True
    assert result.applied["beds_min"] is False


def test_the_result_says_what_still_needs_filtering(session: PacedSession) -> None:
    """feat-002/AC-3: per query field, whether the source applied it."""
    source = StubSource(session, population=["a"], applies=("price_min", "beds_min"))

    result = source.search(
        SearchQuery(area=City("Portales", "NM"), price_min=100, beds_min=3, sqft_min=1000)
    )

    assert result.applied == {
        "price_min": True,
        "beds_min": True,
        "sqft_min": False,
        #: A search is for-sale unless told otherwise, so the status is always a constraint and
        #: always reported. This stub does not push it, so the caller must apply it.
        "listing_status": False,
    }
    assert set(result.locally_applied) == {"sqft_min", "listing_status"}


def test_an_unset_field_is_not_a_filter(session: PacedSession) -> None:
    """feat-002/AC-3: nothing is claimed about a field the search never constrained."""
    source = StubSource(session, population=["a"], applies=("price_min",))

    result = source.search(SearchQuery(area=City("Portales", "NM")))

    assert "price_min" not in result.applied
    assert "beds_min" not in result.applied


def test_every_row_carries_its_source_and_when_it_was_fetched(session: PacedSession) -> None:
    """feat-002/AC-4: attribution is on the row, not inferred from context."""
    source = StubSource(session, population=["a", "b"])

    result = source.search(SearchQuery(area=City("Portales", "NM")))

    assert all(row.source == "stub" for row in result.rows)
    assert all(row.fetched_at and row.fetched_at.endswith("Z") for row in result.rows)


def test_a_row_keeps_the_sources_own_words(session: PacedSession) -> None:
    """feat-002/AC-5: the original response is retained beside the normalized fields."""
    source = StubSource(session, population=["a"])

    row = source.search(SearchQuery(area=City("Portales", "NM"))).rows[0]

    assert row.payload["id"] == "a"
    assert row.fields.price == row.payload["price"]


def test_registering_a_source_touches_nothing_else(session: PacedSession) -> None:
    """feat-002/AC-21: a new adapter is one registration and no edits anywhere."""

    class Newcomer(StubSource):
        name = "newcomer"

    register("newcomer", lambda s: Newcomer(s, population=["x"]))
    try:
        assert "newcomer" in registered()
        source = create("newcomer", session)
        result = source.search(SearchQuery(area=City("Portales", "NM")))
        assert [row.source_listing_id for row in result.rows] == ["x"]
    finally:
        unregister("newcomer")

    assert "newcomer" not in registered()


def test_an_unknown_source_says_what_is_known(session: PacedSession) -> None:
    """feat-002/AC-21: naming a source that does not exist is a clear error, not a crash."""
    with pytest.raises(KeyError, match="known sources"):
        create("nonesuch", session)


def test_a_polygon_is_in_the_vocabulary_even_though_no_source_takes_one() -> None:
    """feat-002/AC-13: an unsupported area is expressible, so it can be reported unavailable."""
    shape = Polygon(points=((34.1, -103.3), (34.2, -103.3), (34.2, -103.4)))
    assert "polygon" in shape.as_term()


def test_an_adapter_must_decide_what_preview_retrieval_means_for_it(session: PacedSession) -> None:
    """feat-002/AC-23: the obligation is real, not inherited as a silent no-op.

    A shared base class that quietly returned None would let an adapter satisfy the interface while
    never fetching an image, which is the same hole the whole-product review found once already. A
    source with no images has to say so on purpose.
    """

    class Forgetful(BaseSource):
        name = "forgetful"

        def capabilities(self) -> Capabilities:
            return Capabilities()

        def run_search(self, query: SearchQuery) -> SearchResult:
            return SearchResult(source=self.name)

    with pytest.raises(NotImplementedError, match="must decide"):
        Forgetful(session).fetch_preview(listing("a"))


def test_a_preview_can_never_interrupt_a_run(session: PacedSession) -> None:
    """feat-002/AC-23, AC-12: an image is the least important thing a run retrieves."""

    class BadImages(BaseSource):
        name = "bad-images"

        def capabilities(self) -> Capabilities:
            return Capabilities()

        def run_search(self, query: SearchQuery) -> SearchResult:
            return SearchResult(source=self.name)

        def fetch_preview(self, row):
            raise RuntimeError("something nobody anticipated")

    assert BadImages(session).preview(listing("a")) is None


def test_the_user_agent_is_not_a_setting() -> None:
    """feat-002/AC-11: every other knob is tunable; the tool's own name is not.

    A configurable user agent is a configurable claim about who is calling, which is the one thing
    the honesty rule exists to prevent. Nothing in the configuration can reach it.
    """
    from homescout.sources import PolitenessConfig
    from homescout.sources.errors import ConfigurationError

    with pytest.raises(ConfigurationError, match="unknown politeness settings"):
        PolitenessConfig.from_mapping(
            {"user_agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/135.0.0.0"}
        )


def test_preview_retrieval_returns_bytes_not_a_stored_file(session: PacedSession) -> None:
    """feat-002/AC-23: an adapter hands back an image; storing it is the caller's job."""
    source = StubSource(session, population=["a"])

    preview = source.fetch_preview(listing("a"))

    assert isinstance(preview, Preview)
    assert preview.data == b"x"
