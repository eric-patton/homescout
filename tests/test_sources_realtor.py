"""The Realtor.com adapter, against responses recorded from the real source.

Recorded rather than live, so these run offline and deterministically, and so a change in the
source's response shape surfaces as a fixture that no longer matches reality instead of as a test
that quietly passes against a stale idea of the schema. See `fixtures/realtor/README.md`.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from homescout.records import SourceRow
from homescout.sources import (
    AddressRadius,
    BoundingBox,
    City,
    County,
    PolitenessConfig,
    PostalCode,
    SearchQuery,
    State,
)
from homescout.sources.realtor import RESULT_CEILING, RealtorSource, normalize, queries
from sources_fakes import FakeClock, FakeResponse, FakeTransport, session_with

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "realtor"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def homes() -> list[dict]:
    return fixture("search_city")["data"]["homeSearch"]["results"]


def responder(
    *,
    search: dict | None = None,
    geography: dict | None = None,
    total: int | None = None,
) -> FakeTransport:
    """Answer the geography lookup and the search from the recorded responses.

    `total` makes the fake behave the way a real source does under splitting: a narrower date range
    matches fewer properties. Without that, a fake reporting the same oversized count for every
    piece would never converge, which is a property of the fake rather than of the code.
    """
    geography = geography if geography is not None else fixture("geography_city")
    search = search if search is not None else fixture("search_city")

    def answer(request):
        body = json.loads(request.body)
        if body["operationName"] == "Search_suggestions":
            return FakeResponse(body=json.dumps(geography).encode())
        page = json.loads(json.dumps(search))
        if total is not None:
            page["data"]["homeSearch"]["total"] = _scaled(total, body["query"])
        return FakeResponse(body=json.dumps(page).encode())

    return FakeTransport(default=answer)


def _scaled(total: int, document: str) -> int:
    """How many a real source would report for the date range in this document.

    Each halving of the range roughly halves the matches, so the count shrinks the way the walk
    expects it to.
    """
    import re

    found = re.search(r'list_date: \{ min: "(\d{4}-\d{2}-\d{2})", max: "(\d{4}-\d{2}-\d{2})"',
                      document)
    if not found:
        return total
    from datetime import date

    start, end = (date.fromisoformat(g) for g in found.groups())
    whole = (date.today() - date(1990, 1, 1)).days or 1
    return max(1, round(total * ((end - start).days / whole)))


def source(transport: FakeTransport, **kwargs) -> RealtorSource:
    return RealtorSource(session_with(transport, **kwargs))


# -- geography ---------------------------------------------------------------


@pytest.mark.parametrize(
    "area",
    [
        PostalCode("88130"),
        City("Portales"),
        City("Portales", "NM"),
        County("Roosevelt", "NM"),
        State("New Mexico"),
    ],
    ids=["zip", "city", "city-with-state", "county", "state"],
)
def test_the_accepted_area_forms_are_issued_in_the_sources_own_form(area) -> None:
    """feat-002/AC-17: each form this source accepts is resolved and searched, not approximated."""
    transport = responder()

    result = source(transport).search(SearchQuery(area=area))

    assert result.outcome == "ok"
    lookup = json.loads(transport.bodies[0])
    assert lookup["operationName"] == "Search_suggestions"
    assert lookup["variables"]["searchInput"]["search_term"] == area.as_term()

    search = json.loads(transport.bodies[1])
    assert "search_location" in search["variables"]


def test_an_address_with_a_radius_is_searched_as_a_radius() -> None:
    """feat-002/AC-17: the sixth form is a different query shape, not a named place."""
    geography = {
        "data": {
            "search_suggestions": {
                "geo_results": [
                    {
                        "text": "1747 S Roosevelt Rd, Portales, NM",
                        "geo": {
                            "area_type": "address",
                            "centroid": {"lat": 34.15, "lon": -103.4},
                        },
                    }
                ]
            }
        }
    }
    transport = responder(geography=geography)

    result = source(transport).search(
        SearchQuery(area=AddressRadius("1747 S Roosevelt Rd, Portales, NM", miles=5))
    )

    assert result.outcome == "ok"
    search = json.loads(transport.bodies[1])
    assert search["variables"]["coordinates"] == [-103.4, 34.15]
    assert "nearby" in search["query"]
    #: The radius that was asked for, not a default. Searching five miles as zero would return one
    #: house and look like a market with nothing in it.
    assert search["variables"]["radius"] == "5mi"


def test_an_area_this_source_cannot_express_is_unavailable() -> None:
    """feat-002/AC-13: a bounding box is Zillow's language, not this one's."""
    transport = responder()

    result = source(transport).search(SearchQuery(area=BoundingBox(34.0, -103.5, 34.3, -103.2)))

    assert result.outcome == "unavailable"
    assert result.rows == ()
    assert "no way to express" in (result.detail or "")
    assert transport.requests == []


def test_a_place_the_source_does_not_recognize_is_unavailable_not_empty() -> None:
    """feat-002/AC-13: 'I do not know that place' is not 'nothing is for sale there'."""
    transport = responder(geography={"data": {"search_suggestions": {"geo_results": []}}})

    result = source(transport).search(SearchQuery(area=City("Nowhere", "ZZ")))

    assert result.outcome == "unavailable"
    assert "does not recognize" in (result.detail or "")
    assert "No substitute area was searched" in (result.detail or "")


# -- what is sent ------------------------------------------------------------


def test_every_request_identifies_this_tool_and_no_other_product() -> None:
    """feat-002/AC-11: the endpoint demands a client name; the value we give it is our own.

    This is the trap the plan exists to close. The endpoint answers `400 missing client
    identification headers` without the pair, and the obvious reference implementation supplies
    Realtor.com's own web application name. It accepts ours just as readily.
    """
    transport = responder()

    source(transport).search(SearchQuery(area=City("Portales", "NM")))

    for request in transport.requests:
        headers = {k.lower(): v for k, v in request.headers.items()}
        assert headers["rdc-client-name"] == "homescout"
        assert "homescout" in headers["user-agent"].lower()
        for absent in ("origin", "referer", "sec-ch-ua", "x-is-bot", "cookie", "authorization"):
            assert absent not in headers


def test_no_credential_is_read_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """feat-002/AC-22: the search path needs no token, so there is no code that could read one."""
    read: list[str] = []
    real_getenv = __import__("os").environ.get

    def watched(key, default=None):
        read.append(key)
        return real_getenv(key, default)

    monkeypatch.setattr(__import__("os").environ, "get", watched, raising=False)
    transport = responder()

    source(transport).search(SearchQuery(area=City("Portales", "NM")))

    assert read == []
    assert all("token" not in json.dumps(dict(r.headers)).lower() for r in transport.requests)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("price_min", 100_000, "list_price"),
        ("price_max", 400_000, "list_price"),
        ("beds_min", 3, "beds"),
        ("baths_min", 2, "baths"),
        ("sqft_min", 1500, "sqft"),
        ("lot_sqft_min", 20_000, "lot_sqft"),
        ("year_built_min", 1990, "year_built"),
    ],
)
def test_each_declared_filter_measurably_changes_the_request(field, value, expected) -> None:
    """feat-002/AC-18: a declaration that does not change the request is a lie."""
    without = responder()
    source(without).search(SearchQuery(area=City("Portales", "NM")))
    plain = json.loads(without.bodies[1])["query"]

    with_filter = responder()
    source(with_filter).search(SearchQuery(area=City("Portales", "NM"), **{field: value}))
    filtered = json.loads(with_filter.bodies[1])["query"]

    #: The bare name appears in the selection set too, so the fragment is what is checked: a
    #: constraint on the field, not a request for it.
    fragment = f"{expected}: {{"
    assert fragment not in plain
    assert fragment in filtered
    assert str(value) in filtered


def test_property_types_and_status_are_pushed_too() -> None:
    """feat-002/AC-18: the two non-numeric filters this source applies."""
    transport = responder()

    source(transport).search(
        SearchQuery(
            area=City("Portales", "NM"),
            property_types=("single_family", "land"),
            listing_status="for_sale",
        )
    )

    query = json.loads(transport.bodies[1])["query"]
    assert "single_family" in query
    assert "status: for_sale" in query


def test_a_field_the_adapter_does_not_declare_never_reaches_the_request() -> None:
    """feat-002/AC-2: the declaration is the only door, so an undeclared field has none."""
    transport = responder()

    #: A search asking for something this adapter does not push. The source must not be told about
    #: it, and the caller must be told that it still has to filter for it itself.
    asked = SearchQuery(area=City("Portales", "NM"), price_min=1, listed_since="2026-01-01")
    result = source(transport).search(asked)
    query = json.loads(transport.bodies[1])["query"]

    assert "list_price: {" in query
    #: Nothing this adapter never declared can appear, because the request is built by walking the
    #: declaration rather than by reading the query.
    for never in ("school", "hoa", "open_house", "foreclosure"):
        assert never not in query
    assert result.applied["price_min"] is True


def test_the_selection_set_asks_only_for_what_is_mapped() -> None:
    """feat-002/AC-18: every field requested is a field with a use, so there is less to break."""
    requested = set(queries.HOME_FIELDS.replace("{", " ").replace("}", " ").split())

    for absent in ("advertisers", "open_houses", "current_estimates", "pet_policy", "units"):
        assert absent not in requested


def test_no_per_property_request_is_made_for_a_page_of_properties() -> None:
    """feat-002/AC-20: with the extra detail off, request count does not track row count."""
    transport = responder()

    result = source(transport).search(SearchQuery(area=City("Portales", "NM")))

    #: One geography lookup, one search page. Twelve rows came back and cost nothing extra.
    assert len(transport.requests) == 2
    assert len(result.rows) == 12


# -- what comes back ---------------------------------------------------------


def test_the_recorded_response_maps_onto_the_stores_fields() -> None:
    """feat-002/AC-5: the mapping is transcribed from a real response, not imagined."""
    row = normalize.to_row(homes()[0], fetched_at="2026-08-23T00:00:00.000000Z")

    assert row.source == "realtor"
    assert row.source_listing_id == homes()[0]["property_id"]
    assert row.fields.price == homes()[0]["list_price"]
    assert row.fields.city == "Portales"
    assert row.fields.state == "NM"
    assert row.fields.county == "Roosevelt"
    assert row.fields.latitude is not None and row.fields.longitude is not None


def test_a_row_keeps_the_sources_own_object_beside_the_mapping() -> None:
    """feat-002/AC-5: a normalization bug found later is correctable against what arrived."""
    original = homes()[0]

    row = normalize.to_row(original, fetched_at="2026-08-23T00:00:00.000000Z")

    assert isinstance(row, SourceRow)
    assert row.payload == original
    assert row.fields.sqft == original["description"]["sqft"]


def test_half_baths_count_as_half() -> None:
    """feat-002/AC-5: two full and one half is two and a half, which is how everyone quotes it."""
    fields = normalize.to_fields({"description": {"baths_full": 2, "baths_half": 1}})

    assert fields.baths == 2.5


def test_a_field_the_response_omits_stays_empty() -> None:
    """feat-002/AC-5: an absent price is not a price of nothing."""
    fields = normalize.to_fields({"description": {}, "location": {}})

    assert fields.price is None
    assert fields.beds is None
    assert fields.photo_urls is None


def test_the_sources_own_days_listed_is_recorded_but_kept_out_of_the_compared_set() -> None:
    """feat-002/AC-4: what the source claims about age is kept for debugging, never believed.

    Freshness in this tool always comes from its own first observation. This value exists so that a
    disagreement is visible when someone goes looking, and it is deliberately outside the set of
    fields a change event may name.
    """
    from homescout.store import COMPARED_FIELDS

    row = normalize.to_row(homes()[0], fetched_at="2026-08-23T00:00:00.000000Z")

    assert row.fields.days_on_market_source is not None
    assert "days_on_market_source" not in COMPARED_FIELDS


def test_every_row_is_attributed_and_stamped() -> None:
    """feat-002/AC-4: source and fetch time on the row itself."""
    transport = responder()

    result = source(transport).search(SearchQuery(area=City("Portales", "NM")))

    assert all(row.source == "realtor" for row in result.rows)
    assert all((row.fetched_at or "").endswith("Z") for row in result.rows)


def test_the_search_reports_what_the_caller_must_still_filter() -> None:
    """feat-002/AC-3: this source pushes a lot, but not everything a saved search can ask."""
    transport = responder()

    result = source(transport).search(
        SearchQuery(area=City("Portales", "NM"), price_min=100_000, beds_min=3)
    )

    assert result.applied["price_min"] is True
    assert result.applied["beds_min"] is True
    assert result.locally_applied == ()


# -- the ceiling -------------------------------------------------------------


def test_the_ceiling_is_the_one_the_source_actually_enforces() -> None:
    """feat-002/AC-19: ten thousand, and the adapter declares it rather than discovering it."""
    assert RESULT_CEILING == 10_000
    assert source(responder()).capabilities().ceiling == 10_000


def test_an_oversized_query_is_split_by_the_date_a_listing_appeared() -> None:
    """feat-002/AC-19: the only dimension this source will divide on."""
    transport = responder(total=25_000)

    result = source(transport).search(SearchQuery(area=City("Portales", "NM")))

    search_bodies = [b for b in transport.bodies if "GetHomeSearch" in b]
    assert any("list_date" in body for body in search_bodies)
    assert len(search_bodies) > 1
    assert result.truncated is False


def test_a_source_that_never_narrows_is_stopped_by_the_budget_not_by_luck() -> None:
    """feat-002/AC-15, AC-16: the request budget is what makes a pathological split terminate.

    A source reporting the same oversized count for every piece it is handed is exactly what a
    broken one looks like. Depth alone does not save us there, because the number of branches
    doubles at each level, so the walk carries a budget for the whole query and truncates honestly
    when it runs out.
    """
    stuck = fixture("search_city")
    stuck["data"]["homeSearch"]["total"] = 25_000
    transport = responder(search=stuck)

    result = source(transport).search(SearchQuery(area=City("Portales", "NM")))

    assert result.truncated is True
    assert result.truncation is not None
    assert "more than" in result.truncation.reason
    assert result.request_count <= 2_001


def test_every_request_a_split_makes_is_paced() -> None:
    """feat-002/AC-16: forty pieces is forty paced requests, not a burst."""
    clock = FakeClock()
    transport = responder(total=25_000)

    source(transport, clock=clock).search(SearchQuery(area=City("Portales", "NM")))

    assert len(clock.slept) == len(transport.requests) - 1
    assert all(wait >= 3.0 for wait in clock.slept)


# -- preview images ----------------------------------------------------------


def test_one_preview_image_is_fetched_per_row_through_the_same_gate() -> None:
    """feat-002/AC-23: images are requests too, and obey every rule the others do."""
    clock = FakeClock()
    transport = FakeTransport(default=FakeResponse(body=b"jpegdata", content_type="image/jpeg"))
    adapter = RealtorSource(session_with(transport, clock=clock))
    rows = [normalize.to_row(h, fetched_at="2026-08-23T00:00:00.000000Z") for h in homes()[:3]]

    previews = [adapter.fetch_preview(row) for row in rows]

    assert all(p is not None and p.data == b"jpegdata" for p in previews)
    assert len(transport.requests) == 3
    assert clock.slept == [3.0, 3.0]


def test_a_row_the_source_gave_no_image_for_yields_no_preview() -> None:
    """feat-002/AC-23: no image is a fact, not a failure."""
    transport = FakeTransport()
    adapter = RealtorSource(session_with(transport))
    row = normalize.to_row({"property_id": "1", "primary_photo": None}, fetched_at="x")

    assert adapter.fetch_preview(row) is None
    assert transport.requests == []


def test_an_image_failure_is_confined_to_that_row() -> None:
    """feat-002/AC-23: one bad image never fails a query or changes an outcome."""
    config = PolitenessConfig.from_mapping({"max_retries": 0})
    transport = FakeTransport(
        responses=[FakeResponse(status=500)],
        default=FakeResponse(body=b"jpeg", content_type="image/jpeg"),
    )
    adapter = RealtorSource(session_with(transport, config=config))
    rows = [normalize.to_row(h, fetched_at="x") for h in homes()[:2]]

    first = adapter.fetch_preview(rows[0])
    second = adapter.fetch_preview(rows[1])

    assert first is None
    assert second is not None


def test_a_plaintext_image_address_is_asked_for_over_https() -> None:
    """feat-002/AC-23: the source's own image addresses are unusable exactly as given.

    Found by the first live run of the command line: the source hands out `http://` addresses, its
    image host answers each one with a 301 to the identical `https` address, and image fetches do
    not follow redirects. Taken literally, every preview in the product was a 167-byte redirect page
    and no property ever got a picture. Asking for `https` is not following the redirect; it is
    declining to make the plaintext request in the first place.
    """
    from homescout.sources.realtor import normalize

    plain = {"primary_photo": {"href": "http://ap.rdcpix.com/abc-m123s.jpg"}}
    secure = {"primary_photo": {"href": "https://ap.rdcpix.com/abc-m123s.jpg"}}

    assert normalize.preview_url(plain) == "https://ap.rdcpix.com/abc-m123s.jpg"
    assert normalize.preview_url(secure) == "https://ap.rdcpix.com/abc-m123s.jpg"
    assert normalize.preview_url({}) is None
