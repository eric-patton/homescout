"""Where the wind comes from: the rose behind the fire map's second overlay.

Nothing here talks to the archive. The fetching is replaced and what is tested is everything around
it, which is where every decision worth getting wrong lives: what a direction means, what is asked
for, what is kept, and what is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homescout import api
from homescout.enrich import wind
from homescout.errors import InvalidInput
from homescout.store import Store
from web_fakes import client, held_workspace, listing, load, reading, shared_store

#: The archive's answer, in its own shape, cut down to the parts that carry meaning. Sixteen
#: directions, a calm figure that belongs to none of them, and speed columns whose labels are what
#: says which of them count as hard wind.
TABLE = """\
# Windrose Data Table (Percent Frequency) for TAOS MUNI APT(AWOS) (SKX)
# Observations Used/Missing/Total: 22064/0/22064
# 16 Apr 1992 12:00 PM - 30 Apr 2025 11:56 PM America/Denver
#   constraints: Apr
# Wind Speed Units: miles per hour
# First value in table is CALM
Direction,Calm     , 2.0  4.9, 5.0  6.9, 7.0  9.9,10.0 14.9,15.0 19.9,20.0+
349-010  ,12.00    ,    4.000,    3.000,    2.000,    0.000,    0.000,    0.000
011-033  ,         ,    1.000,    1.000,    0.000,    0.000,    0.000,    0.000
034-055  ,         ,    1.000,    0.000,    0.000,    0.000,    0.000,    0.000
056-078  ,         ,    1.000,    0.000,    0.000,    0.000,    0.000,    0.000
079-100  ,         ,    1.000,    0.000,    0.000,    9.000,    0.000,    0.000
101-123  ,         ,    1.000,    0.000,    0.000,    0.000,    0.000,    0.000
124-145  ,         ,    1.000,    0.000,    0.000,    0.000,    0.000,    0.000
146-168  ,         ,    1.000,    0.000,    0.000,    0.000,    0.000,    0.000
169-190  ,         ,    2.000,    4.000,    4.000,    6.000,    0.000,    0.000
191-213  ,         ,    2.000,    0.000,    0.000,    0.000,    0.000,    0.000
214-235  ,         ,    5.000,    0.000,    0.000,    0.000,    2.000,    1.000
236-258  ,         ,    5.000,    0.000,    0.000,    0.000,    0.000,    0.000
259-280  ,         ,    8.000,    4.000,    0.000,    2.000,    4.000,    6.000
281-303  ,         ,    3.000,    0.000,    0.000,    0.000,    0.000,    0.000
304-325  ,         ,    2.000,    0.000,    0.000,    0.000,    0.000,    0.000
326-348  ,         ,    2.000,    0.000,    0.000,    0.000,    0.000,    0.000
"""

STATIONS = """\
{"type": "FeatureCollection", "features": [
  {"id": "SKX", "properties": {"sname": "TAOS MUNI APT(AWOS)"},
   "geometry": {"type": "Point", "coordinates": [-105.6724, 36.4582]}},
  {"id": "AXX", "properties": {"sname": "Angel Fire"},
   "geometry": {"type": "Point", "coordinates": [-105.29, 36.42]}}
]}
"""


def answering(monkeypatch, asked: list | None = None, table: str = TABLE):
    """The archive, replaced. Records what it was asked for."""

    def fetched(url: str, what: str) -> bytes:
        if asked is not None:
            asked.append(url)
        return (STATIONS if url.endswith(".geojson") else table).encode()

    monkeypatch.setattr(wind, "_fetch", fetched)


def test_north_is_north_and_west_is_west() -> None:
    """feat-010/AC-59: the one thing here that is worst to get backwards.

    A rose says where the wind comes FROM, and every conclusion drawn from this map inverts if the
    sixteen rows are read a quarter turn out. The archive labels them as ranges that wrap around
    north ("349-010"), which is exactly the sort of label somebody parses into a bearing and gets
    half a sector wrong. They are not parsed: sixteen equal slices starting at north is what was
    asked for, so that is what they are read as, and this pins it.
    """
    found = wind.read(TABLE, "NM_ASOS", "SKX", "april")

    assert len(found.sectors) == 16
    assert found.sectors[0].degrees == 0.0
    assert found.sectors[4].degrees == 90.0
    assert found.sectors[8].degrees == 180.0
    assert found.sectors[12].degrees == 270.0

    assert wind.compass(0) == "north"
    assert wind.compass(90) == "east"
    assert wind.compass(180) == "south"
    assert wind.compass(270) == "west"
    assert wind.compass(225) == "southwest"

    best = found.prevailing
    assert best is not None
    assert wind.compass(best.degrees) == "west", "the busiest row is not the one it says it is"


def test_a_rose_accounts_for_every_observation() -> None:
    """feat-010/AC-59: sixteen directions and the calm, and nothing else, is all of the time.

    Which is the whole check on the parse. A column skipped or a row read twice shows up here as a
    number that is not a hundred, and nowhere else at all: every other number in this answer looks
    perfectly reasonable while being wrong.
    """
    found = wind.read(TABLE, "NM_ASOS", "SKX", "april")

    total = sum(sector.percent for sector in found.sectors) + found.calm
    assert round(total, 2) == 100.0, f"the rose accounts for {total}% of the time"
    assert found.calm == 12.0
    assert found.observations == 22064
    assert "1992" in found.period and "2025" in found.period


def test_hard_wind_is_counted_separately_and_from_the_labels() -> None:
    """feat-010/AC-59: a rose of every breeze is not the question a fire map is asking.

    Which columns are hard wind is read off the archive's own labels rather than counted from the
    right, so a table that gains or loses a speed band stays right instead of quietly shifting.
    """
    found = wind.read(TABLE, "NM_ASOS", "SKX", "april")
    west = found.sectors[12]
    southwest = found.sectors[10]

    assert west.percent == 24.0
    assert west.strong == 10.0, "the two columns at and above 15 mph were not the ones counted"
    assert southwest.strong == 3.0
    assert found.sectors[0].strong == 0.0


def test_a_table_that_is_not_sixteen_directions_is_a_failure() -> None:
    """feat-010/AC-59: a rose of the wrong shape drawn anyway is a wrong answer nobody can see."""
    with pytest.raises(Exception, match="directions"):
        wind.read("\n".join(TABLE.splitlines()[:12]), "NM_ASOS", "SKX", "april")


def test_a_station_and_a_season_are_checked_before_they_reach_a_url() -> None:
    """feat-010/AC-59: both come from a page, and a page's values are never trusted."""
    assert wind.named("skx", "station") == "SKX"
    assert wind.network_for("nm") == "NM_ASOS"
    assert wind.when("april") == "april"

    for wrong in ("", "../etc", "a b", "SKX&f=json", "S", "x" * 40):
        with pytest.raises(InvalidInput):
            wind.named(wrong, "station")
    with pytest.raises(InvalidInput):
        wind.when("spring")


def test_a_rose_is_fetched_once_and_then_read_off_the_disk(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-59: it is a query across decades on somebody else's public archive.

    Ten seconds of theirs for an answer that summarises thirty years, so it is asked exactly once
    in the life of a workspace and read off the disk after. Nothing else in this tool is a strong
    enough reason to ask twice.
    """
    asked: list[str] = []
    answering(monkeypatch, asked=asked)

    first = wind.rose(tmp_path, "https://example.invalid/windrose", "NM_ASOS", "SKX", "april")
    second = wind.rose(tmp_path, "https://example.invalid/windrose", "NM_ASOS", "SKX", "april")

    assert first.sectors == second.sectors
    assert first.calm == second.calm
    assert len(asked) == 1, "the same station was asked about twice"
    assert "station=SKX" in asked[0] and "network=NM_ASOS" in asked[0]
    assert "monthlimit=1" in asked[0] and "month1=4" in asked[0]
    assert "nsector=16" in asked[0] and "units=mph" in asked[0]
    assert list((tmp_path / "wind").glob("*.json")), "nothing was kept"
    assert not list((tmp_path / "wind").glob("*.part")), "a half-written answer was left"

    # A different season is a different question, so it is fetched rather than served the first.
    wind.rose(tmp_path, "https://example.invalid/windrose", "NM_ASOS", "SKX", "year")
    assert len(asked) == 2
    assert "monthlimit" not in asked[1], "the whole year was asked for as one month"


def test_the_stations_come_from_where_the_properties_are(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-59: from the properties themselves, not from what the search is called.

    A search named "nm-statewide" that turned up a house over the Colorado line should get
    Colorado's weather stations too, and a search named after nothing at all should still get the
    right ones. The name of a search is a label somebody typed.
    """
    answering(monkeypatch)
    load(store, [listing("a"), listing("b", state="CO", city="Trinidad")])
    held = held_workspace(shared_store(db_path))

    found = api.wind_stations(held, "portales")

    assert found["states"] == ["CO", "NM"], found["states"]
    assert {one["station"] for one in found["stations"]} == {"SKX", "AXX"}
    assert found["unreachable"] == []
    assert sorted(found["seasons"]) == ["april", "year"]


def test_a_state_that_will_not_answer_does_not_take_the_others_with_it(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-59: reliability, which product invariant says no single outside failure decides.

    A state with no automated network, or an archive having a bad afternoon, is a map that says so
    and still draws every other state.
    """

    def fetched(url: str, what: str) -> bytes:
        if "CO_ASOS" in url:
            raise OSError("no")
        return STATIONS.encode()

    monkeypatch.setattr(wind, "_fetch", fetched)
    load(store, [listing("a"), listing("b", state="CO", city="Trinidad")])
    held = held_workspace(shared_store(db_path))

    found = api.wind_stations(held, "portales")

    assert len(found["stations"]) == 2, "New Mexico went missing because Colorado did"
    assert len(found["unreachable"]) == 1
    assert found["unreachable"][0].startswith("CO:")


def test_a_rose_is_served_with_the_place_it_belongs_to(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-59: the rose carries no coordinates and a map cannot draw one without them.

    So they are filled in here from the station list rather than by the page holding two answers
    and joining them itself, which is one more thing for a screen to get wrong.
    """
    answering(monkeypatch)
    load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))

    with client(held) as browser:
        answered = browser.get("/api/wind/rose/NM_ASOS/SKX?season=april", headers=reading())
        refused = browser.get("/api/wind/rose/NM_ASOS/SKX?season=whenever", headers=reading())

    assert answered.status_code == 200, answered.text
    found = answered.json()["rose"]
    assert found["latitude"] == 36.4582
    assert found["longitude"] == -105.6724
    assert found["name"] == "TAOS MUNI APT(AWOS)"
    assert found["when"] == "april"
    assert found["prevailing"]["compass"] == "west"
    assert len(found["sectors"]) == 16

    assert refused.status_code == 400, "a season nobody offers was accepted"


def test_the_page_says_which_way_a_direction_means() -> None:
    """feat-010/AC-59: the sentence that stops every conclusion from this overlay being inverted.

    "From the west" and "to the west" are opposite claims about which red matters, and a rose is
    drawn the way roses have always been drawn, which is the way somebody who has not seen one
    before will read backwards. So the page says it, in the legend and again in every bubble.
    """
    from web_fakes import STATIC

    page = (STATIC / "fire.js").read_text(encoding="utf-8")

    assert page.count("the wind comes ") >= 2, "the page says it once or not at all"
    assert 'el("strong", {}, "from")' in page, "the word that carries it is not emphasised"
    assert "pushes a fire east" in page, "the page never spells out what it means for a fire"
