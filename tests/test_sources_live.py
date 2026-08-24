"""The two questions only the real source can answer.

Everything else in this feature is proved offline, which is what keeps the suite fast and keeps the
tool from pointing traffic at a site purely to check itself. These two are here because no fixture
can answer them: does the endpoint still accept a client that identifies itself honestly, and is the
result cap still where we think it is.

Marked slow and excluded from the default run. They are deliberately cheap: the second one reads the
counts the source reports for the ranges the split produces, and never fetches the rows behind them.
Proving the split's completeness by actually pulling tens of thousands of listings would test the
expensive thing rather than the breakable one, and would aim a great deal of traffic at a source
this whole feature exists to be gentle with.
"""

from __future__ import annotations

import json

import pytest

from homescout.sources import City, PolitenessConfig, SearchQuery, State, default_session
from homescout.sources.realtor import (
    RESULT_CEILING,
    RealtorSource,
    _split_by_listing_date,
    queries,
)

pytestmark = pytest.mark.slow


def live_source() -> RealtorSource:
    #: The floor, not the default: these make a handful of requests and there is no reason to be
    #: quicker about it than the tool ever is.
    config = PolitenessConfig.from_mapping({"delay": 3.0})
    return RealtorSource(default_session(config=config))


def test_the_real_source_answers_a_client_that_names_itself_honestly() -> None:
    """feat-002/AC-11, AC-17, AC-22: the honest client still works, with no token of any kind.

    If this ever fails, the answer is not to start impersonating a browser. It is to report the
    source unavailable and say why.
    """
    result = live_source().search(SearchQuery(area=City("Portales", "NM")))

    assert result.outcome == "ok", result.detail
    assert len(result.rows) > 0
    assert all(row.source == "realtor" for row in result.rows)
    assert all(row.fields.city for row in result.rows)


def test_a_query_over_the_cap_is_detected_and_split_into_pieces_that_fit() -> None:
    """feat-002/AC-24: the cap is where we think it is, and our ranges land under it.

    Counts only. Each request here asks the source how many match a date range and ignores the rows,
    so establishing this costs a handful of requests rather than fifty thousand listings.
    """
    source = live_source()
    query = SearchQuery(area=State("Texas"))
    #: Resolved once and reused. Re-resolving per probe would double the traffic to prove nothing,
    #: and the place does not change between probes.
    place = source._resolve(query.area)

    whole = _reported_total(source, place, query)
    assert whole > RESULT_CEILING, (
        f"Texas reported {whole} listings, at or under the cap of {RESULT_CEILING}. "
        "This test needs a market above it; pick a larger one rather than lowering the bar."
    )

    #: Split until every piece reports a count the source will actually serve, exactly as the walk
    #: does, and check that it converges.
    pending = [query]
    fitted = []
    while pending and len(fitted) < 4:
        piece = pending.pop()
        total = _reported_total(source, place, piece)
        if total <= RESULT_CEILING:
            fitted.append((piece, total))
            continue
        halves = _split_by_listing_date(piece)
        assert halves is not None, "the query stopped being divisible while still over the cap"
        pending.extend(halves)

    assert fitted, "splitting produced no piece the source would serve"
    assert all(total <= RESULT_CEILING for _, total in fitted)


def _reported_total(source: RealtorSource, place: object, query: SearchQuery) -> int:
    """Ask the source how many match, and read nothing else."""
    document, variables = source._build(place, query, 0)
    #: One result instead of two hundred: this is a count, not a fetch.
    document = document.replace(f"limit: {200}", "limit: 1")
    body = json.dumps(
        {
            "operationName": "GetHomeSearch",
            "query": queries.minified(document),
            "variables": variables,
        },
        separators=(",", ":"),
    ).encode()
    from homescout.sources.politeness import Request

    fetched = source.session.request(
        source.name,
        Request(url=queries.ENDPOINT, method="POST", body=body, headers=source._headers),
    )
    return int(json.loads(fetched.body)["data"]["homeSearch"]["total"])
