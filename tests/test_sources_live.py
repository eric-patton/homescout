"""The questions only the real source can answer.

Everything else in this feature is proved offline, which is what keeps the suite fast and keeps the
tool from pointing traffic at a site purely to check itself. These are here because no fixture can
answer them: does the endpoint still accept a client that identifies itself honestly, is the result
cap still where we think it is, and does an image address the source gives out actually yield a
picture.

Marked slow and excluded from the default run. They are deliberately cheap: the second one reads the
counts the source reports for the ranges the split produces, and never fetches the rows behind them.
Proving the split's completeness by actually pulling tens of thousands of listings would test the
expensive thing rather than the breakable one, and would aim a great deal of traffic at a source
this whole feature exists to be gentle with.
"""

from __future__ import annotations

import json

import pytest

from homescout.sources import (
    BoundingBox,
    City,
    PolitenessConfig,
    SearchQuery,
    State,
    create,
    default_session,
)
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


def test_the_real_source_still_counts_bathrooms_the_way_the_mapping_reads_them() -> None:
    """feat-002/AC-5: the one check a recorded response cannot make.

    A fixture is recorded by the same request the adapter sends, so a field the request never asks
    for is absent from the recording too, and every offline test agrees with the mistake. That is
    exactly how the bath count stayed a whole bathroom short of the description for months. This
    test asks the live source and reads what comes back, so leaving a kind of bathroom out of the
    selection set fails here instead of quietly.
    """
    source = create("realtor", default_session())
    result = source.search(SearchQuery(area=City("Santa Fe", "NM"), listing_status="for_sale"))
    assert result.outcome == "ok" and result.rows

    counted = [row.payload.get("description") or {} for row in result.rows]
    #: Not every market has one, which is why the market is named rather than left to the search.
    with_shower = [d for d in counted if d.get("baths_3qtr")]
    assert with_shower, (
        "no property in this market reported a three-quarter bath. Either the source renamed the "
        "field or this market changed; check the response before assuming the mapping is fine."
    )

    for row, description in zip(result.rows, counted, strict=True):
        parts = {
            "baths_full": 1.0, "baths_3qtr": 1.0, "baths_half": 0.5, "baths_1qtr": 0.25,
        }
        assert set(description) >= set(parts), (
            f"the source stopped answering with {set(parts) - set(description)}"
        )
        expected = sum(
            worth * float(description[kind])
            for kind, worth in parts.items()
            if description.get(kind) is not None
        )
        assert row.fields.baths == (expected if any(
            description.get(kind) is not None for kind in parts
        ) else None)


def test_a_real_preview_image_comes_back_as_a_picture() -> None:
    """feat-002/AC-23: the obligation this feature put on the interface, against the real site.

    The offline tests could only prove that an image the transport returns is stored. They could not
    catch the source handing out addresses that redirect, which is what it does, and which made
    preview retrieval a no-op for every property until the first live run of a command found it.
    """
    source = create("realtor", default_session())
    result = source.search(SearchQuery(area=City("Portales", "NM"), price_max=200_000))
    assert result.outcome == "ok" and result.rows

    previews = []
    for row in result.rows[:2]:
        preview = source.preview(row)
        if preview is not None:
            previews.append(preview)

    assert previews, "the source offered no usable image for any of the first rows"
    for preview in previews:
        assert preview.content_type.startswith("image/")
        assert len(preview.data) > 1_000, "a redirect page rather than a picture"


# -- the two sources added by feat-005 ---------------------------------------

#: A box around Portales, New Mexico. Small enough that both sources answer it completely, so these
#: cost one request each and pull a few dozen rows.
PORTALES_BOX = BoundingBox(south=34.10, west=-103.45, north=34.30, east=-103.25)


def test_zillow_still_answers_a_client_that_identifies_itself() -> None:
    """feat-005/AC-2: the endpoint, the method, and the shape, against the real site.

    This is the test that catches the failure the whole plan was built around. The address every
    write-up names was already dead when this adapter was written; the one here answers today. When
    this starts failing, read it as news about the site rather than about the code, and remember
    that the address is configuration.
    """
    source = create("zillow", default_session())

    result = source.search(SearchQuery(area=PORTALES_BOX))

    assert result.outcome == "ok", result.detail
    assert result.rows, "a town of twelve thousand has properties for sale in it"
    row = result.rows[0]
    assert row.fields.latitude and 34.0 < row.fields.latitude < 34.4
    assert row.fields.city
    assert row.fields.price and row.fields.price > 1_000
    assert row.source_listing_id


def test_zillow_still_caps_a_query_where_we_think_it_does() -> None:
    """feat-005/AC-3: the count is the true one even when the rows are capped.

    That asymmetry is the only reason splitting can work at all, so it is worth checking against the
    real site rather than only against a fake. One request, and the rows behind the count are never
    fetched.
    """
    from homescout.sources.zillow import queries as zillow_queries

    source = create("zillow", default_session())
    state_sized = BoundingBox(south=31.3, west=-109.1, north=37.0, east=-103.0)

    page = source._page(SearchQuery(area=state_sized), 0)

    assert page.total > zillow_queries.RESULT_CEILING * 4, page.total
    assert len(page.rows) <= zillow_queries.RESULT_CEILING + 10, "the cap moved"
    assert len(page.rows) < page.total, "the site still reports more than it hands over"


def test_redfin_still_takes_a_polygon_and_still_says_nothing_about_its_cap() -> None:
    """feat-005/AC-9: both halves of what makes this adapter's arithmetic necessary.

    A ring is accepted with no region id, and the download carries no count, which is why exactly
    the cap has to be read as "there are more".
    """
    from homescout.sources.redfin import normalize as redfin_normalize

    source = create("redfin", default_session())

    result = source.search(SearchQuery(area=PORTALES_BOX))

    assert result.outcome == "ok", result.detail
    assert result.rows, "a town of twelve thousand has properties for sale in it"
    assert result.detail and "incomplete" in result.detail, "the standing caveat rides along"
    row = result.rows[0]
    assert row.fields.address_line and row.fields.city
    assert row.fields.latitude and 34.0 < row.fields.latitude < 34.4
    assert row.source_listing_id and ":" in row.source_listing_id
    assert redfin_normalize.MLS_NOTICE, "still the line the adapter knows to skip"


def test_redfin_still_refuses_to_narrow_by_lot_size() -> None:
    """feat-005/AC-1: the declaration says it does not, and this is why.

    If this test ever fails, that is good news and the fix is to declare the filter. Until then, an
    acreage search over this source spends its cap on properties the local test will discard, and
    the capability declaration says so honestly.
    """
    from homescout.sources.redfin import queries as redfin_queries

    assert "lot_sqft_min" not in redfin_queries.APPLIES

    source = create("redfin", default_session())
    metro = BoundingBox(south=35.0, west=-106.8, north=35.25, east=-106.4)

    unfiltered = source._page(SearchQuery(area=metro), 0)
    asked = source._page(SearchQuery(area=metro, lot_sqft_min=43_560), 0)

    smallest = [
        row.fields.lot_sqft for row in asked.rows if row.fields.lot_sqft is not None
    ]
    assert smallest and min(smallest) < 43_560, (
        "the site started honouring a lot-size filter; declare it and delete this test"
    )
    assert len(asked.rows) == len(unfiltered.rows)
