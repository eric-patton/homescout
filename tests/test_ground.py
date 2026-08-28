"""County lines, town names and how much rain falls: the parsing, not the servers.

Nothing here talks to the Census or to NOAA. The fetching is replaced and what is tested is
everything around it, which is where the decisions worth getting wrong live: which way round a
coordinate goes, which towns count as towns, what an average is an average of, and what happens
when a county will not answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homescout import api
from homescout.enrich import ground
from homescout.enrich.provider import ProviderFailed
from homescout.errors import InvalidInput
from homescout.store import Store
from web_fakes import held_workspace, listing, load, shared_store

COUNTIES = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "properties": {
                    "BASENAME": "Taos",
                    "COUNTY": "055",
                    "CENTLAT": "+36.5776",
                    "CENTLON": "-105.6367",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-105.9, 36.2], [-105.2, 36.2], [-105.2, 36.9],
                                     [-105.9, 36.9], [-105.9, 36.2]]],
                },
            },
            {
                "properties": {
                    "BASENAME": "Mora",
                    "COUNTY": "033",
                    "CENTLAT": "+35.9752",
                    "CENTLON": "-104.9464",
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[-105.2, 35.7], [-104.6, 35.7], [-104.6, 36.2],
                                      [-105.2, 36.2], [-105.2, 35.7]]]],
                },
            },
        ],
    }
)

TOWNS = json.dumps(
    {
        "features": [
            {"attributes": {"BASENAME": "Albuquerque, NM", "AREALAND": "681343624",
                            "CENTLAT": "+35.1", "CENTLON": "-106.6"}},
            {"attributes": {"BASENAME": "Taos, NM", "AREALAND": "48837334",
                            "CENTLAT": "+36.4", "CENTLON": "-105.6"}},
            {"attributes": {"BASENAME": "El Paso, TX--NM", "AREALAND": "663244525",
                            "CENTLAT": "+31.8", "CENTLON": "-106.4"}},
        ]
    }
)

RAIN = json.dumps(
    {
        "description": {"title": "Taos County, New Mexico January-December Precipitation",
                        "units": "Inches"},
        "data": {f"{year}12": {"value": 10.0 + (year % 5)} for year in range(1990, 2026)},
    }
)


def answering(monkeypatch, asked: list | None = None, **overrides: str):
    """The federal record, replaced. Records every address it was asked for."""
    answers = {"query?": COUNTIES, "88/query": TOWNS, "pcp/ann": RAIN}
    answers.update(overrides)

    def fetched(url: str, what: str) -> bytes:
        if asked is not None:
            asked.append(url)
        if "/88/query" in url:
            return answers["88/query"].encode()
        if "pcp/ann" in url:
            return answers["pcp/ann"].encode()
        return answers["query?"].encode()

    monkeypatch.setattr(ground, "_fetch", fetched)


def test_a_county_outline_comes_back_the_way_a_map_reads_it(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-60: GeoJSON says longitude first and every map in this tool says latitude first.

    Turned round once, here, rather than at the point of drawing. A coordinate order converted
    where it is used is a coordinate order that eventually gets converted twice, and the result is
    a map of New Mexico somewhere off the coast of Somalia: obviously wrong, and obvious only if
    somebody happens to look.
    """
    answering(monkeypatch)

    found = ground.counties(tmp_path, "https://example.invalid", "NM")

    assert [one["name"] for one in found] == ["Taos", "Mora"]
    first = found[0]
    assert first["fips"] == "055"
    assert first["latitude"] == pytest.approx(36.5776)
    assert first["longitude"] == pytest.approx(-105.6367)
    #: Latitude first, and in New Mexico rather than in the Indian Ocean.
    assert first["outline"][0][0] == [pytest.approx(36.2), pytest.approx(-105.9)]

    #: A multipolygon is flattened to its rings, so a county in two pieces draws as two pieces
    #: rather than as one line joining them across whatever is in between.
    assert len(found[1]["outline"]) == 1
    assert found[1]["outline"][0][0] == [pytest.approx(35.7), pytest.approx(-105.2)]


def test_the_record_is_asked_for_once_and_kept(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-60: a county line moves roughly never, so it is fetched once, ever.

    The same rule the wind rose follows and for the same reason: this is somebody else's public
    server being asked a favour by a tool one household runs.
    """
    asked: list[str] = []
    answering(monkeypatch, asked)

    ground.counties(tmp_path, "https://example.invalid", "NM")
    ground.counties(tmp_path, "https://example.invalid", "NM")
    ground.towns(tmp_path, "https://example.invalid", "NM")
    ground.towns(tmp_path, "https://example.invalid", "NM")

    assert len(asked) == 2, f"the same permanent answer was fetched more than once: {asked}"


def test_a_town_is_named_the_way_somebody_says_it(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-60: "Albuquerque, NM" forty times on a map of New Mexico says nothing.

    The state comes off, because on a map of that state it is a word repeated at every label. It
    stays on an area that spans two states, because there the second half is the fact: "El Paso,
    TX--NM" is not El Paso, and somebody reading the bottom of this map needs to know that.

    Biggest first, because that is what decides which names survive at which zoom.
    """
    answering(monkeypatch)

    found = ground.towns(tmp_path, "https://example.invalid", "NM")

    assert [one["name"] for one in found] == ["Albuquerque", "El Paso, TX--NM", "Taos"]
    assert found[0]["latitude"] == pytest.approx(35.1)


def test_rainfall_is_an_average_of_thirty_years_and_says_which(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-61: any single year here is a story about one monsoon.

    What somebody buying land is asking is what the place is normally like, and the answer to that
    is a normal: thirty years, which is the length the meteorological world uses. The years travel
    with the number because eleven inches means nothing without them.
    """
    answering(monkeypatch)

    found = ground.rainfall(tmp_path, "https://example.invalid", "NM", "055")

    assert found["name"] == "Taos"
    assert found["years"] == ground.YEARS == 30
    assert found["to"] - found["from"] == 29, (found["from"], found["to"])
    #: The fixture cycles 10..14 by year, so the average of any thirty consecutive years is 12.
    assert found["inches"] == pytest.approx(12.0, abs=0.2)


def test_a_missing_year_is_dropped_rather_than_averaged_in(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-61: the record marks a gap with a large negative number, not with nothing.

    Averaged in, one of those drags a county from twelve inches to minus one, and minus one inch
    of rain is the sort of wrong that is obvious on the page and invisible in the code.
    """
    holed = json.loads(RAIN)
    for year in ("200012", "200112"):
        holed["data"][year]["value"] = -99.0
    answering(monkeypatch, **{"pcp/ann": json.dumps(holed)})

    found = ground.rainfall(tmp_path, "https://example.invalid", "NM", "055")

    assert found["years"] == 28, "the gaps were counted as readings"
    assert found["inches"] > 9, f"a missing year was averaged in as rain: {found['inches']}"


def test_a_state_or_county_that_is_not_one_is_refused_before_it_is_asked_for(
    tmp_path: Path, monkeypatch
) -> None:
    """feat-010/AC-60: both go straight into somebody else's query string."""
    answering(monkeypatch)

    with pytest.raises(InvalidInput):
        ground.counties(tmp_path, "https://example.invalid", "XX")
    with pytest.raises(InvalidInput):
        ground.rainfall(tmp_path, "https://example.invalid", "NM", "55")
    with pytest.raises(InvalidInput):
        ground.rainfall(tmp_path, "https://example.invalid", "NM", "../etc")


def test_one_county_that_will_not_answer_does_not_stop_the_others(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-61: the rule every layer on this map follows, applied to thirty-three of them.

    A single record being down must cost that county's number and nothing else. The one that
    failed is named, because a county silently missing its number looks like a county with no
    rainfall record at all, and that is a different and much more interesting fact.
    """
    load(store, [listing("a", state="NM")])
    held = held_workspace(shared_store(db_path))

    def fetched(url: str, what: str) -> bytes:
        if "/88/query" in url:
            return TOWNS.encode()
        if "pcp/ann" in url:
            if "NM-033" in url:
                raise ProviderFailed("Mora rainfall: the public record did not answer")
            return RAIN.encode()
        return COUNTIES.encode()

    monkeypatch.setattr(ground, "_fetch", fetched)

    found = api.rainfall(held, "portales")

    assert [one["fips"] for one in found["counties"]] == ["055"]
    assert any("Mora" in said for said in found["unreachable"]), found["unreachable"]
    #: And the county is still on the map, with lines and a name, just without a number.
    assert len(api.ground(held, "portales")["counties"]) == 2


def test_the_map_is_told_what_states_the_run_actually_found(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-60: read off the properties, not off the search's name.

    A search called "nm-statewide" that turned something up over the Colorado line should get
    Colorado's counties, and a search named after nothing at all should still get the right ones.
    """
    load(store, [listing("a", state="NM"), listing("b", state="CO", city="Trinidad")])
    held = held_workspace(shared_store(db_path))

    asked: list[str] = []

    def fetched(url: str, what: str) -> bytes:
        asked.append(url)
        return (TOWNS if "/88/query" in url else COUNTIES).encode()

    monkeypatch.setattr(ground, "_fetch", fetched)
    api.ground(held, "portales")

    #: The state FIPS codes go into the query, so this is the check that both were asked about.
    joined = " ".join(asked)
    assert "STATE%3D%2735%27" in joined or "STATE='35'" in joined, joined
    assert "STATE%3D%2708%27" in joined or "STATE='08'" in joined, joined
