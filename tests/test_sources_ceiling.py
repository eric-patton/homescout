"""Getting everything out of a source that caps one query.

These run against a stub with a population of a known size and a ceiling of 50, deliberately. The
real cap is ten thousand, and proving completeness there would mean pulling tens of thousands of
real rows to check ourselves. A ceiling small enough to force several levels of splitting proves the
same arithmetic in milliseconds, and against a population we know exactly, so completeness is
demonstrated rather than inferred from a big number coming back.
"""

from __future__ import annotations

from homescout.sources import City, PolitenessConfig, SearchQuery
from sources_fakes import FakeClock, FakeTransport, StubSource, listing, session_with


def population(count: int) -> list[str]:
    return [f"p{i:04d}" for i in range(count)]


def query() -> SearchQuery:
    return SearchQuery(area=City("Portales", "NM"))


def test_a_query_under_the_ceiling_is_not_split() -> None:
    """feat-002/AC-14: splitting is a workaround, not something that happens for its own sake."""
    source = StubSource(session_with(FakeTransport()), population=population(30), ceiling=50)

    result = source.search(query())

    assert len(result.rows) == 30
    assert result.truncated is False


def test_an_oversized_query_returns_the_whole_population() -> None:
    """feat-002/AC-14: the union of the pieces is everything the ceiling was hiding."""
    whole = population(500)
    source = StubSource(session_with(FakeTransport()), population=whole, ceiling=50)

    result = source.search(query())

    assert [row.source_listing_id for row in result.rows] == whole
    assert result.truncated is False


def test_duplicates_the_split_created_are_removed() -> None:
    """feat-002/AC-14: overlapping pieces are our doing, so their repeats are ours to clean up."""
    whole = population(200)
    source = StubSource(session_with(FakeTransport()), population=whole, ceiling=50)

    result = source.search(query())
    identifiers = [row.source_listing_id for row in result.rows]

    assert len(identifiers) == len(set(identifiers)) == 200


def test_a_repeat_within_one_response_is_kept_but_a_repeat_across_pieces_is_not() -> None:
    """feat-002/AC-14: the deduplication boundary is the page, and that distinction is the point.

    A repeat across pieces is our own doing: two overlapping query pieces asking for the same
    property. A repeat inside one response is the source contradicting itself, and both halves of a
    contradiction are evidence the store is required to keep. Collapsing the second kind would
    destroy a source row, which is exactly the bug the listing store's audit found one layer down.
    """
    from homescout.sources.ceiling import Page, collect

    pages = [
        Page(rows=(listing("a", price=400_000), listing("a", price=350_000)), total=2),
        Page(rows=(listing("a", price=400_000), listing("b")), total=2),
    ]
    served = iter(pages)

    def fetch_page(query, offset):
        return next(served)

    harvest = collect(
        query(),
        fetch_page=fetch_page,
        #: Always divisible, so the walk asks a second time and the cross-piece repeat appears.
        split=lambda q: None,
        ceiling=None,
        page_size=2,
    )

    prices = [row.fields.price for row in harvest.rows]
    assert prices == [400_000, 350_000], "both halves of the source's own contradiction survive"


def test_a_repeat_across_two_pieces_is_dropped() -> None:
    """feat-002/AC-14: our own overlapping asks are ours to clean up."""
    from homescout.sources.ceiling import Page, collect

    served = iter(
        [
            Page(rows=(listing("a"),), total=100),
            Page(rows=(listing("a"), listing("b")), total=2),
            Page(rows=(listing("a"), listing("c")), total=2),
        ]
    )

    def fetch_page(q, offset):
        return next(served)

    from homescout.sources import DateRange

    harvest = collect(
        query(),
        fetch_page=fetch_page,
        split=lambda q: (q.within(DateRange("0", "1")), q.within(DateRange("1", "2"))),
        ceiling=50,
        page_size=10,
    )

    assert [row.source_listing_id for row in harvest.rows] == ["a", "b", "c"]


def test_a_query_that_cannot_be_divided_far_enough_is_flagged_truncated() -> None:
    """feat-002/AC-15: an incomplete result is never returned as though it were whole."""
    source = StubSource(
        session_with(FakeTransport()), population=population(500), ceiling=50, divisible=False
    )

    result = source.search(query())

    assert result.truncated is True
    assert result.truncation is not None
    assert result.truncation.ceiling == 50
    assert "500" in result.truncation.reason
    assert len(result.rows) == 50


def test_truncation_names_the_ceiling_that_caused_it() -> None:
    """feat-002/AC-15: 'incomplete' is not useful; 'incomplete because of this' is."""
    source = StubSource(
        session_with(FakeTransport()), population=population(120), ceiling=40, divisible=False
    )

    result = source.search(query())

    assert result.truncation is not None
    assert "limit of 40" in result.truncation.reason


def test_a_source_that_refuses_partway_keeps_what_was_retrieved() -> None:
    """feat-002/AC-15: the other route to the same flag, named differently."""
    source = StubSource(
        session_with(FakeTransport()),
        population=population(500),
        ceiling=50,
        page_size=10,
        fail_after=6,
    )

    result = source.search(query())

    assert result.truncated is True
    assert result.truncation is not None
    assert result.truncation.ceiling is None
    assert "stopped answering partway through" in result.truncation.reason
    assert len(result.rows) > 0


def test_every_request_a_split_makes_is_paced() -> None:
    """feat-002/AC-16: splitting a query never becomes a burst."""
    clock = FakeClock()
    session = session_with(FakeTransport(), clock=clock)
    source = StubSource(session, population=population(200), ceiling=50, page_size=10)

    result = source.search(query())

    #: Every request after the first waited its turn, and none of the waits was short.
    assert len(clock.slept) == result.request_count - 1
    assert all(wait >= 3.0 for wait in clock.slept)


def test_pacing_a_split_uses_the_configured_delay_not_a_smaller_one() -> None:
    """feat-002/AC-16: a split obeys the same delay a single request would."""
    clock = FakeClock()
    config = PolitenessConfig.from_mapping({"delay": 7})
    session = session_with(FakeTransport(), clock=clock, config=config)
    source = StubSource(session, population=population(120), ceiling=50, page_size=10)

    source.search(query())

    assert set(clock.slept) == {7.0}


def test_a_split_that_never_converges_is_bounded_by_a_request_budget() -> None:
    """feat-002/AC-16: a source misreporting its counts cannot become a request storm.

    Depth alone bounds nothing here, because the number of branches doubles at every level: a depth
    of twenty permits a million requests. The budget on total requests is the bound that holds, and
    it is what turns a pathological split into an honest truncation instead of a hang.
    """
    from homescout.sources.ceiling import MAX_REQUESTS_PER_QUERY

    source = StubSource(session_with(FakeTransport()), population=population(600), ceiling=1)

    result = source.search(query())

    assert result.request_count <= MAX_REQUESTS_PER_QUERY + 1
    assert result.outcome == "ok"


def test_an_empty_result_is_success_not_failure() -> None:
    """feat-002/AC-12: a market with nothing in it is a different fact from a source being down."""
    source = StubSource(session_with(FakeTransport()), population=[], ceiling=50)

    result = source.search(query())

    assert result.outcome == "ok"
    assert result.rows == ()
    assert result.truncated is False
