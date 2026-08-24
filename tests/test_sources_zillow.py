"""Zillow, against a recorded response and a transport that counts.

The recorded response was captured from the real endpoint on the day this adapter was built, so a
change in the site's response shape shows up as a fixture that no longer matches reality rather than
as a test that quietly passes against a stale idea of the schema.

Everything about splitting is exercised without the network, because splitting is arithmetic over
counts the site reports, and the site reporting twenty thousand while handing over five hundred is
what a fake transport can reproduce exactly.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from homescout.sources import BoundingBox, PacedSession, SearchQuery, State
from homescout.sources.errors import SourceFailed, SourceUnavailable
from homescout.sources.zillow import ZillowSource, queries
from sources_fakes import FakeClock, FakeResponse, FakeTransport, code_of, session_with

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "zillow"
BOX = BoundingBox(south=34.10, west=-103.45, north=34.30, east=-103.25)


def recorded() -> dict:
    return json.loads((FIXTURES / "search_box.json").read_text(encoding="utf-8"))


def answering(payload: dict) -> tuple[ZillowSource, FakeTransport]:
    transport = FakeTransport(default=FakeResponse(body=json.dumps(payload).encode()))
    return ZillowSource(session_with(transport)), transport


def synthetic(total: int, per_box: int = 4) -> tuple[ZillowSource, FakeTransport]:
    """A site that reports `total` for every box it is handed until the box gets small.

    The rows are keyed to the box asked for, so the union across pieces is what deduplication has to
    survive, and the counts fall as the boxes shrink, which is what makes splitting terminate.
    """

    def answer(request):
        body = json.loads(request.body)
        bounds = body["searchQueryState"]["mapBounds"]
        # A count that falls with the box's *area*, which is how a market actually thins out.
        # Falling with one side alone would need twenty levels of splitting to clear the ceiling,
        # and twenty levels is a million branches.
        share = (
            abs(bounds["east"] - bounds["west"]) * abs(bounds["north"] - bounds["south"])
        )
        here = max(1, int(total * share))
        homes = [
            {
                "zpid": f"{bounds['west']:.4f}:{bounds['south']:.4f}:{i}",
                "detailUrl": "/homedetails/x/1_zpid/",
                "hdpData": {
                    "homeInfo": {
                        "zpid": f"{bounds['west']:.4f}:{bounds['south']:.4f}:{i}",
                        "price": 300_000,
                        "homeStatus": "FOR_SALE",
                        "streetAddress": f"{i} Example Road",
                        "city": "Portales",
                        "state": "NM",
                        "zipcode": "88130",
                        "latitude": bounds["south"],
                        "longitude": bounds["west"],
                    }
                },
            }
            for i in range(min(per_box, here))
        ]
        payload = {
            "cat1": {
                "searchResults": {"mapResults": homes},
                "searchList": {"totalResultCount": here},
            }
        }
        return FakeResponse(body=json.dumps(payload).encode())

    transport = FakeTransport(default=answer)
    return ZillowSource(session_with(transport)), transport


def test_a_box_is_issued_as_the_sites_own_map_bounds() -> None:
    """feat-005/AC-2: natively, in the source's own form, with no place lookup at all."""
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX))

    assert len(transport.requests) == 1, "one request is a whole box"
    request = transport.requests[0]
    assert request.method == "PUT", "the endpoint that answers takes a PUT with a body"
    body = json.loads(request.body)
    assert body["searchQueryState"]["mapBounds"] == {
        "west": -103.45,
        "east": -103.25,
        "south": 34.10,
        "north": 34.30,
    }
    assert body["wants"]["cat1"] == ["mapResults"], "the map results are the whole box"


def test_an_area_that_is_not_a_box_is_refused_rather_than_swapped() -> None:
    """feat-005/AC-6: the query planner hands over a containing box, or this source is not asked.

    Answering a different question quietly is worse than not answering, which is why this is an
    outcome rather than a nearby substitute.
    """
    source, transport = answering(recorded())

    with pytest.raises(SourceUnavailable, match="bounding box"):
        source.run_search(SearchQuery(area=State("New Mexico")))
    assert transport.requests == [], "and nothing was asked"


def test_the_recorded_response_becomes_properties() -> None:
    """feat-005/AC-10: tagged with the source, the time, and the site's own words."""
    source, _ = answering(recorded())

    result = source.run_search(SearchQuery(area=BOX))

    assert result.outcome == "ok"
    assert len(result.rows) == 4
    row = result.rows[0]
    assert row.source == "zillow"
    assert row.fetched_at, "every row says when it was fetched"
    assert row.payload, "and keeps what the site actually said"
    assert row.source_listing_id
    assert row.fields.city == "Portales"
    assert row.fields.state == "NM"
    assert row.fields.price and row.fields.price > 0
    assert row.fields.listing_status == "for_sale", "in the tool's vocabulary, not the site's"
    assert row.fields.latitude and 34.0 < row.fields.latitude < 34.5


def test_a_lot_size_is_converted_out_of_whatever_unit_it_arrived_in() -> None:
    """feat-005/AC-10: the filter takes square feet and the response answers in acres.

    Getting this backwards produces a number wrong by a factor of forty-three thousand that looks
    entirely plausible in a table.
    """
    from homescout.sources.zillow.normalize import to_fields

    acres = to_fields({"hdpData": {"homeInfo": {"lotAreaValue": 2.0, "lotAreaUnit": "acres"}}})
    feet = to_fields({"hdpData": {"homeInfo": {"lotAreaValue": 8000, "lotAreaUnit": "sqft"}}})
    absent = to_fields({"hdpData": {"homeInfo": {}}})

    assert acres.lot_sqft == 87_120
    assert feet.lot_sqft == 8_000
    assert absent.lot_sqft is None, "absent, not zero"


def test_a_unit_nobody_recognizes_fails_rather_than_guessing() -> None:
    """feat-005/AC-10: a lot size wrong by an unknown factor is worse than no lot size."""
    from homescout.sources.zillow.normalize import to_fields

    with pytest.raises(SourceFailed, match="convert"):
        to_fields({"hdpData": {"homeInfo": {"lotAreaValue": 3, "lotAreaUnit": "hectares"}}})


def test_only_declared_filters_reach_the_request() -> None:
    """feat-005/AC-1: the capability declaration is the whole contract.

    A field the adapter never claimed has no path to the site, and the caller is told it still has
    to filter for it. Both halves are checked, because either one alone is a promise nobody keeps.
    """
    source, transport = answering(recorded())
    query = SearchQuery(
        area=BOX,
        price_min=250_000,
        beds_min=3,
        sqft_min=1_800,
        lot_sqft_min=43_560,
        year_built_min=1990,
        listed_since="2026-01-01",
    )

    result = source.run_search(query)

    state = json.loads(transport.requests[0].body)["searchQueryState"]["filterState"]
    assert state["price"] == {"min": 250_000}
    assert state["beds"] == {"min": 3}
    assert state["sqft"] == {"min": 1_800}
    assert state["lotSize"] == {"min": 43_560}, "in square feet, which is what the filter takes"
    assert state["built"] == {"min": 1990}
    assert result.applied["price_min"] is True
    assert result.applied["listed_since"] is False, "not declared, so the caller still filters it"
    assert "doz" not in state, "and it was never sent"


def test_asking_for_one_kind_of_property_turns_the_others_off() -> None:
    """feat-005/AC-1: the site's home-type filter works by exclusion, so the adapter does too."""
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX, property_types=("single_family",)))

    state = json.loads(transport.requests[0].body)["searchQueryState"]["filterState"]
    assert state["isCondo"] == {"value": False}
    assert state["isLotLand"] == {"value": False}
    assert "isSingleFamily" not in state, "the one that was asked for is left alone"


def test_a_property_type_nobody_recognizes_widens_rather_than_empties() -> None:
    """feat-005/AC-1: an unfamiliar name must not silently return nothing.

    A filter nobody can express is a filter the caller applies locally, and the declaration already
    tells it so. Turning every type off would return an empty market and look like a quiet one.
    """
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX, property_types=("houseboat",)))

    state = json.loads(transport.requests[0].body)["searchQueryState"]["filterState"]
    assert not any(key.startswith("is") for key in state)


def test_a_box_over_the_ceiling_is_subdivided_and_the_union_returned() -> None:
    """feat-005/AC-3: more than five hundred distinct properties out of an area that caps at 500.

    The number in the criterion, asserted as a number. The counts here are synthetic on purpose:
    the property being tested is the arithmetic of splitting and merging, not any real market.
    """
    source, transport = synthetic(total=20_000, per_box=8)

    result = source.run_search(SearchQuery(area=BoundingBox(34.0, -104.0, 35.0, -103.0)))

    identifiers = [row.source_listing_id for row in result.rows]
    assert len(identifiers) > 500, f"only {len(identifiers)} came back"
    assert len(set(identifiers)) == len(identifiers), "the union kept a duplicate"
    assert len(transport.requests) > 1, "it split"
    assert result.truncation is None, "and it got everything"


def test_subdivision_is_paced_rather_than_burst() -> None:
    """feat-005/AC-4: every piece goes through the same politeness gate as everything else.

    Observed on the clock rather than assumed from the code: the pieces of one split are separated
    by the source's own delay, which is what stops adding coverage from increasing the odds of being
    blocked.
    """
    clock = FakeClock()

    def answer(request):
        body = json.loads(request.body)
        bounds = body["searchQueryState"]["mapBounds"]
        width = abs(bounds["east"] - bounds["west"])
        here = 4_000 if width > 0.3 else 3
        homes = [
            {
                "zpid": f"{bounds['west']:.4f}:{i}",
                "hdpData": {"homeInfo": {"zpid": f"{bounds['west']:.4f}:{i}"}},
            }
            for i in range(min(3, here))
        ]
        return FakeResponse(
            body=json.dumps(
                {"cat1": {"searchResults": {"mapResults": homes},
                          "searchList": {"totalResultCount": here}}}
            ).encode()
        )

    transport = FakeTransport(default=answer)
    session: PacedSession = session_with(transport, clock=clock)
    source = ZillowSource(session)

    source.run_search(SearchQuery(area=BoundingBox(34.0, -104.0, 34.5, -103.5)))

    assert len(transport.requests) >= 3, "it split"
    assert clock.slept, "and waited between the pieces rather than issuing them at once"
    assert sum(clock.slept) > 0


def test_a_box_that_cannot_be_cut_any_further_is_truncated_and_says_why() -> None:
    """feat-005/AC-5: what was retrieved is returned, flagged, naming the ceiling responsible.

    This is what a single tower with six hundred units looks like, and what a source that reports
    the same oversized count for every piece it is handed looks like too.
    """
    payload = {
        "cat1": {
            "searchResults": {
                "mapResults": [{"zpid": "1", "hdpData": {"homeInfo": {"zpid": "1"}}}]
            },
            "searchList": {"totalResultCount": 9_000},
        }
    }
    source, transport = answering(payload)
    speck = BoundingBox(south=34.0, west=-103.0, north=34.0005, east=-103.0005)

    result = source.run_search(SearchQuery(area=speck))

    assert result.truncation is not None
    assert result.truncation.ceiling == queries.RESULT_CEILING
    assert "9000" in result.truncation.reason.replace(",", "")
    assert result.rows, "and what was retrieved is kept"
    assert len(transport.requests) == 1, "it did not try to cut something it cannot cut"


def test_an_empty_half_stops_the_descent_rather_than_continuing_into_it() -> None:
    """feat-005, the coastline edge case: splitting stops where the properties stop.

    No rule about water is needed. The walk only recurses into a half whose own reported total is
    over the ceiling, and empty water reports zero.
    """
    seen: list[float] = []

    def answer(request):
        bounds = json.loads(request.body)["searchQueryState"]["mapBounds"]
        seen.append(bounds["west"])
        # The eastern half is ocean. The western half is a city.
        empty = bounds["west"] > -103.5
        here = 0 if empty else (2_000 if abs(bounds["east"] - bounds["west"]) > 0.3 else 5)
        return FakeResponse(
            body=json.dumps(
                {"cat1": {"searchResults": {"mapResults": []},
                          "searchList": {"totalResultCount": here}}}
            ).encode()
        )

    transport = FakeTransport(default=answer)
    source = ZillowSource(session_with(transport))

    source.run_search(SearchQuery(area=BoundingBox(34.0, -104.0, 34.5, -103.0)))

    eastern = [west for west in seen if west > -103.5]
    assert len(eastern) <= 2, f"it kept dividing empty water: {len(eastern)} requests"


def test_a_response_that_is_not_the_shape_it_has_always_been_fails_loudly() -> None:
    """feat-005/AC-1: a 404 page and a block page are both large and neither is a market.

    Half-read rows written as fact would poison every later comparison in a way no later run could
    detect, which is why this is a failure rather than an empty result.
    """
    source, _ = answering({"nothing": "recognizable"})

    with pytest.raises(SourceFailed, match="cat1"):
        source.run_search(SearchQuery(area=BOX))


def test_the_endpoint_can_be_moved_without_touching_the_code(monkeypatch) -> None:
    """feat-005/AC-2: the address every write-up names had already died before this was built."""
    assert "zillow.com" in queries.endpoint()

    monkeypatch.setenv(queries.ENDPOINT_VARIABLE, "https://elsewhere.example/state")
    source, transport = answering(recorded())
    source.run_search(SearchQuery(area=BOX))

    assert transport.requests[0].url == "https://elsewhere.example/state"


def test_no_credential_appears_anywhere_in_this_adapter() -> None:
    """feat-005/AC-11: and the check is on the source, so it stays true after somebody tries.

    The failure this catches is real and predictable: a site starts refusing, and the first instinct
    is to add a cookie or a key to make it stop.
    """
    import homescout.sources.zillow as package

    for module in (package, package.queries, package.normalize):
        body = code_of(module).lower()
        for forbidden in ("authorization", "api_key", "apikey", "password", "cookie", "bearer"):
            assert forbidden not in body, f"{module.__name__} mentions {forbidden}"


def test_the_union_of_the_pieces_is_every_property_the_ceiling_hid() -> None:
    """feat-005/AC-3: the criterion's first sentence, stated as set equality.

    A fixed universe of properties at known coordinates, and a site that answers any box with the
    ones inside it, capped at five hundred, while reporting the true count. The whole point of
    splitting is that what comes back at the end is the universe, not a sample of it: an assertion
    that merely counts past five hundred would pass on a walk that lost half the market and found
    the rest twice.
    """
    universe = {
        f"p{i:05d}": (34.0 + (i % 97) / 97 * 0.5, -104.0 + (i // 97) / 21 * 0.5)
        for i in range(2_000)
    }

    def answer(request):
        bounds = json.loads(request.body)["searchQueryState"]["mapBounds"]
        inside = [
            identifier
            for identifier, (latitude, longitude) in universe.items()
            if bounds["south"] <= latitude <= bounds["north"]
            and bounds["west"] <= longitude <= bounds["east"]
        ]
        homes = [
            {"zpid": identifier, "hdpData": {"homeInfo": {"zpid": identifier}}}
            for identifier in inside[: queries.RESULT_CEILING]
        ]
        return FakeResponse(
            body=json.dumps(
                {"cat1": {"searchResults": {"mapResults": homes},
                          "searchList": {"totalResultCount": len(inside)}}}
            ).encode()
        )

    transport = FakeTransport(default=answer)
    source = ZillowSource(session_with(transport))

    result = source.run_search(
        SearchQuery(area=BoundingBox(south=34.0, west=-104.0, north=34.5, east=-103.5))
    )

    returned = {row.source_listing_id for row in result.rows}
    assert returned == set(universe), (
        f"{len(set(universe) - returned)} properties were lost to the ceiling"
    )
    assert len(result.rows) == len(universe), "and none came back twice"
    assert result.truncation is None
