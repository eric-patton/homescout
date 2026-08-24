"""Redfin, against a recorded download and a transport that counts.

The download was captured from the real endpoint on the day this adapter was built. Two things in it
are load-bearing: it carries the site's standing notice about withheld listings in every region, and
it carries no count at all, so the adapter has to infer that exactly the cap means there are more.
Both are asserted here rather than assumed.
"""

from __future__ import annotations

import csv
import io
import pathlib
from urllib.parse import parse_qs, urlsplit

import pytest

from homescout.sources import BoundingBox, County, SearchQuery
from homescout.sources.errors import SourceFailed, SourceUnavailable
from homescout.sources.redfin import STANDING_CAVEAT, RedfinSource, normalize, queries
from sources_fakes import FakeResponse, FakeTransport, code_of, session_with

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "redfin"
BOX = BoundingBox(south=34.10, west=-103.45, north=34.30, east=-103.25)


def recorded() -> str:
    return (FIXTURES / "search_box.csv").read_text(encoding="utf-8")


def answering(text: str) -> tuple[RedfinSource, FakeTransport]:
    transport = FakeTransport(
        default=FakeResponse(body=text.encode(), content_type="text/csv;charset=UTF-8")
    )
    return RedfinSource(session_with(transport)), transport


def parameters(transport: FakeTransport) -> dict[str, list[str]]:
    return parse_qs(urlsplit(transport.requests[0].url).query)


def a_download(count: int, *, start: int = 0) -> str:
    """A download of exactly `count` properties, in the real file's own columns."""
    header = recorded().splitlines()[0]
    notice = recorded().splitlines()[1]
    columns = next(csv.reader(io.StringIO(header)))
    rows = []
    for i in range(start, start + count):
        values = {name: "" for name in columns}
        values.update(
            {
                "SALE TYPE": "MLS Listing",
                "PROPERTY TYPE": "Single Family Residential",
                "ADDRESS": f"{i} Example Road",
                "CITY": "Portales",
                "STATE OR PROVINCE": "NM",
                "ZIP OR POSTAL CODE": "88130",
                "PRICE": "250000",
                "BEDS": "3",
                "BATHS": "2",
                "SQUARE FEET": "1800",
                "LOT SIZE": "43560",
                "YEAR BUILT": "1995",
                "DAYS ON MARKET": "10",
                "STATUS": "Active",
                "SOURCE": "NMMLS",
                "MLS#": str(1_000_000 + i),
                "LATITUDE": "34.2",
                "LONGITUDE": "-103.3",
            }
        )
        out = io.StringIO()
        csv.writer(out, lineterminator="").writerow([values[name] for name in columns])
        rows.append(out.getvalue())
    return "\n".join([header, notice, *rows]) + "\n"


def test_a_box_is_issued_as_a_ring_with_no_region_lookup() -> None:
    """feat-005/AC-2: which is what makes the blocked place-lookup paths irrelevant.

    Longitude first, and the whole thing built from formatting floats, so there is nothing in it
    that came out of a response.
    """
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX))

    assert len(transport.requests) == 1, "one download is a whole box, and no lookup precedes it"
    poly = parameters(transport)["poly"][0]
    points = [pair.split(" ") for pair in poly.split(",")]
    assert len(points) == 5 and points[0] == points[-1], "a closed ring"
    assert all(-104 < float(longitude) < -103 for longitude, _ in points), "longitude first"
    assert all(34 < float(latitude) < 35 for _, latitude in points)
    assert parameters(transport)["num_homes"] == ["350"], "asked for, not left to a default"


def test_an_area_that_is_not_a_box_is_refused_rather_than_swapped() -> None:
    """feat-005/AC-6: the query planner hands over a containing box, or this source is not asked."""
    source, transport = answering(recorded())

    with pytest.raises(SourceUnavailable, match="bounding box"):
        source.run_search(SearchQuery(area=County("Roosevelt", "NM")))
    assert transport.requests == []


def test_the_recorded_download_becomes_properties() -> None:
    """feat-005/AC-10: tagged with the source, the time, and the download's own cells."""
    source, _ = answering(recorded())

    result = source.run_search(SearchQuery(area=BOX))

    assert result.outcome == "ok"
    assert len(result.rows) == 5, "the notice line is not a property"
    row = result.rows[0]
    assert row.source == "redfin"
    assert row.fetched_at and row.payload
    # Qualified by the listing service, because two of them can issue the same number.
    assert row.source_listing_id == "NMMLS:20264246"
    assert row.fields.address_line == "317 E 17th St"
    assert row.fields.city == "Portales"
    assert row.fields.price == 450_000
    assert row.fields.property_type == "single_family", "in the tool's vocabulary, not the site's"
    assert row.fields.listing_status == "for_sale"
    assert row.fields.listing_url and row.fields.listing_url.startswith("https://www.redfin.com/")


def test_an_empty_cell_is_absent_and_never_zero() -> None:
    """feat-005/AC-10: this is a spreadsheet, so every value is a string and the two look alike.

    Getting it backwards records every property with no year built as having been built in the year
    nothing, which then compares as a change the first time the site fills the value in.
    """
    source, _ = answering(recorded())

    rows = source.run_search(SearchQuery(area=BOX)).rows
    no_year = [row for row in rows if row.fields.address_line == "217 W 14th St"]
    no_lot = [row for row in rows if row.fields.address_line == "320 E 11th St"]

    assert no_year and no_year[0].fields.year_built is None
    assert no_lot and no_lot[0].fields.lot_sqft is None
    assert no_year[0].fields.price == 75_000, "and the cells that are filled in are still read"


def test_only_declared_filters_reach_the_request() -> None:
    """feat-005/AC-1: and lot size is the one that is deliberately not declared.

    Three parameter names for it were tried against the real endpoint and none changed the result,
    while every other filter here does work. So the caller filters lot size locally and is told so,
    rather than the adapter claiming a narrowing that does not happen.
    """
    source, transport = answering(recorded())
    query = SearchQuery(
        area=BOX, price_min=200_000, beds_min=3, sqft_min=1_500, lot_sqft_min=43_560
    )

    result = source.run_search(query)

    sent = parameters(transport)
    assert sent["min_price"] == ["200000"]
    assert sent["num_beds"] == ["3"]
    assert sent["min_listing_approx_size"] == ["1500"]
    assert not any("lot" in key for key in sent), "nothing about lot size was sent"
    assert result.applied["lot_sqft_min"] is False, "and the caller is told it must filter it"
    assert result.applied["price_min"] is True


def test_asking_for_one_kind_of_property_narrows_the_codes() -> None:
    """feat-005/AC-1: the site takes a list of its own codes."""
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX, property_types=("single_family", "land")))

    assert parameters(transport)["uipt"] == ["1,5"]


def test_a_property_type_nobody_recognizes_widens_rather_than_empties() -> None:
    """feat-005/AC-1: an unfamiliar name must not silently return nothing."""
    source, transport = answering(recorded())

    source.run_search(SearchQuery(area=BOX, property_types=("houseboat",)))

    assert parameters(transport)["uipt"] == [queries.ALL_PROPERTY_CODES]


def test_exactly_the_cap_is_read_as_there_being_more() -> None:
    """feat-005/AC-9: the download reports no count, so this is the only honest reading.

    A market with exactly three hundred and fifty properties in it costs one unnecessary split.
    That is the right way round: the other error presents a capped result as a complete one.
    """
    capped = a_download(queries.ROW_CAP)
    smaller = a_download(12)
    answers = iter([capped, smaller, smaller])
    transport = FakeTransport(
        default=lambda request: FakeResponse(
            body=next(answers, smaller).encode(), content_type="text/csv"
        )
    )
    source = RedfinSource(session_with(transport))

    result = source.run_search(SearchQuery(area=BOX))

    assert len(transport.requests) == 3, "it split rather than presenting 350 as everything"
    assert result.truncation is None, "and the halves came back under the cap"
    assert len(result.rows) >= 12


def test_under_the_cap_is_taken_as_the_whole_answer() -> None:
    """feat-005/AC-9: and costs exactly one request, because there is nothing to work around."""
    source, transport = answering(a_download(11))

    result = source.run_search(SearchQuery(area=BOX))

    assert len(transport.requests) == 1
    assert len(result.rows) == 11
    assert result.truncation is None


def test_a_box_at_the_cap_that_cannot_be_cut_is_truncated() -> None:
    """feat-005/AC-9: what was retrieved is returned, flagged, rather than presented as complete."""
    source, transport = answering(a_download(queries.ROW_CAP))
    speck = BoundingBox(south=34.0, west=-103.0, north=34.0005, east=-103.0005)

    result = source.run_search(SearchQuery(area=speck))

    assert result.truncation is not None
    assert result.truncation.ceiling == queries.ROW_CAP
    assert len(result.rows) == queries.ROW_CAP, "and what was retrieved is kept"
    assert len(transport.requests) == 1


def test_every_result_carries_the_sites_own_caveat() -> None:
    """feat-005/AC-7: because the site cannot say when a region's rules are actually restricting it.

    Every response in every region carries the same notice, so it is a standing caveat rather than a
    signal. Saying it every time is what keeps a coverage gap from reading as a quiet market, which
    is the promise the criterion was protecting.
    """
    source, _ = answering(recorded())

    result = source.run_search(SearchQuery(area=BOX))

    assert result.detail == STANDING_CAVEAT
    assert "incomplete" in result.detail
    assert result.outcome == "ok", "a caveat is not a failure"
    assert result.truncation is None, "and not a truncation either; that one is the row cap"


def test_the_notice_line_is_never_mistaken_for_a_property() -> None:
    """feat-005/AC-10: it is the second line of every download and it has no address."""
    rows, notice = normalize.read(recorded())

    assert notice is True
    assert len(rows) == 5
    assert all(row["ADDRESS"] for row in rows)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{}&&{"errorMessage":"Endpoint not found.","resultCode":122}', "refused"),
        ("<!DOCTYPE HTML><HTML><HEAD><TITLE>ERROR</TITLE>", "web page"),
        ("", "empty body"),
    ],
    ids=["error envelope", "block page", "nothing at all"],
)
def test_a_response_that_is_not_a_download_is_unavailable_and_says_what_came_back(
    body: str, expected: str
) -> None:
    """feat-005/AC-7: the refusals that are unambiguous, distinct from a failure.

    These are what "Redfin will not give you this" looks like when it is machine-readable, which is
    the part of the criterion the endpoint can actually support.
    """
    source, _ = answering(body)

    with pytest.raises(SourceUnavailable, match=expected):
        source.run_search(SearchQuery(area=BOX))


def test_a_download_whose_columns_changed_fails_and_names_them() -> None:
    """feat-005, the changed-columns edge case: a parse failure, not silently missing values."""
    source, _ = answering("SALE TYPE,ADDRESS,CITY\nMLS Listing,1 Example Road,Portales\n")

    with pytest.raises(SourceFailed, match="PROPERTY TYPE"):
        source.run_search(SearchQuery(area=BOX))


def test_a_cell_that_cannot_be_read_names_the_column() -> None:
    """feat-005, the changed-columns edge case: loud and empty beats quiet and wrong."""
    broken = a_download(1).replace(",250000,", ",about $250k,")

    with pytest.raises(SourceFailed, match="PRICE"):
        normalize.to_fields(normalize.read(broken)[0][0])


def test_the_endpoint_can_be_moved_without_touching_the_code(monkeypatch) -> None:
    """feat-005/AC-2: as with every other external address in this project."""
    assert "redfin.com" in queries.endpoint()

    monkeypatch.setenv(queries.ENDPOINT_VARIABLE, "https://elsewhere.example/csv")
    source, transport = answering(recorded())
    source.run_search(SearchQuery(area=BOX))

    assert transport.requests[0].url.startswith("https://elsewhere.example/csv?")


def test_no_credential_appears_anywhere_in_this_adapter() -> None:
    """feat-005/AC-11: checked against the code rather than the prose that explains its absence."""
    import homescout.sources.redfin as package

    for module in (package, package.queries, package.normalize):
        body = code_of(module).lower()
        for forbidden in ("authorization", "api_key", "apikey", "password", "bearer"):
            assert forbidden not in body, f"{module.__name__} mentions {forbidden}"
