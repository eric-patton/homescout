"""Specific houses named in a saved search, driven through the real file, loop and command line.

The case these tests are built from is real. On 2026-09-30 eight Louisiana houses were run by hand
as a throwaway search, with a half-mile circle drawn around each. Every house came back, along with
eighteen neighbours for sale inside the circles, and the three on numbered highways came back as
three records apiece. Named addresses are that run done properly: the circle decides what is asked
for, and the address decides what is kept.

What is faked is what reaches outside the machine: a source that answers with whatever lies inside
the area it was asked about, and either a scripted placer or the real Census provider over a
counting transport, which is how "looked up once" is proved rather than asserted.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from cli_fakes import FakeSource, invoke, row
from enrich_fakes import CountingTransport, session
from homescout import api
from homescout.search import addresses as named
from homescout.search import geometry as geo
from homescout.search.boundaries import PlacedAddress
from homescout.sources.base import BoundingBox, Capabilities, PointRadius, SearchResult
from homescout.store import Store
from searches_fakes import (
    CountingBoundaries,
    Hostile,
    boundaries,
    catalog,
    polygon,
    sourced,
    workspace,
    write,
)

#: Two of the eight, 0.14 miles apart, and one 27 miles away. Points are where the listing sites put
#: each house; the Census put them a few hundredths of a mile off, as it does.
TAYLOR = "52150 Taylor Dr, Loranger, LA 70446"
DITTA = "52149 Ditta Dr, Loranger, LA 70446"
HIGHWAY = "33063 Hwy 43, Independence, LA 70443"
TAYLOR_AT = (30.611282, -90.369808)
DITTA_AT = (30.610603, -90.372070)
HIGHWAY_AT = (30.586997, -90.597642)


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake", "other"):
        yield


class Around(FakeSource):
    """A source that answers each query with the rows that lie inside the area it was asked about.

    With `listing_status` among what it applies, it answers only the rows in the status asked for,
    which is what a real site does and what makes "asked for pending too" observable. Statuses in
    `refuse` fail, which is what Realtor does today with `pending` and `contingent`.
    """

    def __init__(
        self,
        name: str = "fake",
        *,
        rows: Sequence[Any] = (),
        applies: Sequence[str] = (),
        refuse: Sequence[str] = (),
    ) -> None:
        super().__init__(name, rows=rows, applies=applies)
        self.refuse = set(refuse)

    def run_search(self, query: Any) -> SearchResult:
        self.queries.append(query)
        status_pushed = "listing_status" in self._applies
        if status_pushed and query.listing_status in self.refuse:
            return SearchResult(
                source=self.name, outcome="failed", rows=(), applied={},
                detail=f"{self.name} answered 400",
            )
        served = [
            found for found in self.rows
            if _inside(query.area, found)
            and (not status_pushed or found.fields.listing_status == query.listing_status)
        ]
        return SearchResult(
            source=self.name,
            outcome="ok",
            rows=tuple(served),
            applied=self.capabilities().application(query),
        )


def _inside(area: Any, found: Any) -> bool:
    latitude, longitude = found.fields.latitude, found.fields.longitude
    if isinstance(area, PointRadius):
        if latitude is None or longitude is None:
            return False
        away = geo.miles_between((area.latitude, area.longitude), (latitude, longitude))
        return away <= area.miles
    if isinstance(area, BoundingBox):
        if latitude is None or longitude is None:
            return False
        return area.south <= latitude <= area.north and area.west <= longitude <= area.east
    return True


def house(
    identifier: str,
    line: str,
    point: tuple[float, float],
    *,
    source: str = "fake",
    postal: str = "70446",
    **fields: Any,
) -> Any:
    found = row(
        identifier,
        address_line=line,
        postal_code=postal,
        city="Loranger",
        state="LA",
        latitude=point[0],
        longitude=point[1],
        **fields,
    )
    if source == "fake":
        return found
    from dataclasses import replace

    return replace(found, source=source)


class Placing(CountingBoundaries):
    """The scripted provider, able to place addresses too, and counting what it was asked."""

    def __init__(self, placed: dict[str, PlacedAddress] | None = None) -> None:
        super().__init__()
        self.placed = dict(placed or {})
        self.prepared: list[str] = []

    def place_address(self, text: str) -> PlacedAddress | None:
        self.lookups.append(f"address:{text}")
        return self.placed.get(text)

    def prepare_addresses(self, texts: Sequence[str]) -> None:
        self.prepared.extend(texts)


def placed_at(point: tuple[float, float], matched: str | None = None, postal: str | None = None):
    return PlacedAddress(point[0], point[1], matched=matched, postal=postal)


def searching(name: str, *, addresses: str, areas: str = "", extra: str = "") -> str:
    return f"name: {name}\n{areas}addresses:\n{addresses}sources: [fake]\n{extra}"


def run(tmp_path: Path, name: str, sources: dict[str, Any]):
    with (
        Store.open(tmp_path / "homescout.db") as store,
        workspace(store, sources=sources) as space,
    ):
        return api.run_search(space, name)


def recorded(tmp_path: Path, run_id: str) -> list[str]:
    with Store.open(tmp_path / "homescout.db") as store:
        return sorted(s.fields.address_line or "" for s in store.snapshots_for_run(run_id))


# -- the file ------------------------------------------------------------------------------------


def test_a_search_names_addresses_as_text_or_as_entries(tmp_path: Path) -> None:
    """feat-004/AC-15: a line of text, or an entry with an address, a reason and a place."""
    write(tmp_path, "named", text=(
        "name: named\n"
        "addresses:\n"
        f"  - {TAYLOR}\n"
        f"  - address: {HIGHWAY}\n"
        "    reason: Sent by the agent.\n"
        "    at: [30.586997, -90.597642]\n"
        "sources: [fake]\n"
    ))

    definition = catalog(tmp_path).load("named")

    assert definition.problems() == (), "addresses and no areas is a whole search"
    assert [a.text for a in definition.addresses] == [TAYLOR, HIGHWAY]
    assert definition.addresses[1].reason == "Sent by the agent."
    assert definition.addresses[1].at == HIGHWAY_AT
    assert definition.addresses[0].at is None and definition.addresses[0].reason is None


def test_the_list_survives_a_load_and_a_save_and_an_edit_from_the_command_line(
    tmp_path: Path,
) -> None:
    """feat-004/AC-15: round trip under AC-8, and the command line's edit reaches the list.

    The edit goes through `searches edit --set`, the same operation the browser's editor uses, and
    the comment and the area it never touched are still there afterwards.
    """
    directory = tmp_path / "searches"
    path = write(directory, "named", text=(
        "# Louisiana, by hand.\n"
        "name: named\n"
        "areas:\n"
        '  - {type: city, value: "Portales, NM"}\n'
        "addresses:\n"
        f"  - {TAYLOR}  # the first one\n"
        "sources: [fake]\n"
    ))
    before = path.read_bytes()
    catalog(directory).edit("named", {"addresses": [TAYLOR]})
    assert path.read_bytes() == before, "assigning what is there changed the file"

    code, out, err = invoke(
        ["searches", "edit", "named", "--set", f'addresses=["{TAYLOR}", "{DITTA}"]', "--json"],
        db=tmp_path / "homescout.db",
    )

    assert code == 0, err
    text = path.read_text(encoding="utf-8")
    assert "# Louisiana, by hand." in text and "Portales, NM" in text
    assert [a.text for a in catalog(directory).load("named").addresses] == [TAYLOR, DITTA]


def test_naming_a_house_changes_the_scope_and_naming_none_changes_nothing(tmp_path: Path) -> None:
    """feat-004/AC-15, feat-001/AC-32: named houses are part of what a run observes.

    So adding one starts a new comparison series, as adding an area does. What must not happen is
    every existing search on the machine starting a new series the day this shipped: a search that
    names no house keeps the fingerprint it had before named houses existed. The literal below was
    computed by the code as it stood before this change, over this exact file.
    """
    plain = (
        "name: plain\nareas:\n  - {type: city, value: \"Portales, NM\"}\n"
        "filters:\n  price: {max: 500000}\nsources: [fake]\n"
    )
    write(tmp_path, "plain", text=plain)
    write(tmp_path, "empty", text=plain.replace("name: plain", "name: empty") + "addresses: []\n")
    write(tmp_path, "named", text=plain.replace("name: plain", "name: named")
          + f"addresses:\n  - {TAYLOR}\n")
    found = catalog(tmp_path)

    before = "sha256:a2c9234922bf4f039654245cfdabff61826443f6578ab2f30615f15f0120a3fa"
    assert found.load("plain").observation_revision == before
    assert found.load("empty").observation_revision == before
    assert found.load("named").observation_revision != before


def test_validation_reports_every_bad_entry_where_it_is_and_asks_nobody(tmp_path: Path) -> None:
    """feat-004/AC-17: located, collected in one pass, and nothing contacted.

    A source that fails the test if touched, and a placer that records every question, prove that
    validating a list of addresses looks nothing up.
    """
    long_one = "1 " + "Very Long Road " * 20
    write(tmp_path, "bad", text=(
        "name: bad\n"
        "addresses:\n"
        "  - 12345\n"                                   # 3: not text
        "  - {reason: no address}\n"                     # 4: no address
        "  - '   '\n"                                    # 5: empty
        f"  - {long_one}\n"                              # 6: too long
        "  - {address: 1 Main St, at: [-90.37, 30.61]}\n"  # 7: swapped
        "  - {address: 2 Main St, at: [30.61]}\n"          # 8: not a pair
        "  - {address: 3 Main St, at: [north, west]}\n"    # 9: not numbers
        "  - {address: 4 Main St, colour: blue}\n"         # 10: unknown key
        f"  - {TAYLOR}\n"
        f"  - '{TAYLOR.upper()}'\n"                      # 12: the same house again
        "sources: [fake]\n"
    ))
    placer = Placing()

    with Store.open(tmp_path / "homescout.db") as store, boundaries(placer):
        space = workspace(store, sources={"fake": Hostile()})
        space.catalog = catalog(tmp_path)
        found = api.validate_search(space, "bad")
    definition = catalog(tmp_path).load("bad")

    problems = [p for p in definition.problems() if p.severity == "problem"]
    notices = [p for p in definition.problems() if p.severity == "notice"]
    lines = sorted(int(p.location.split(":")[1]) for p in problems)
    assert lines == [3, 4, 5, 6, 7, 8, 9, 10], [(p.location, p.message) for p in problems]
    assert any("200" in p.message for p in problems)
    assert any("latitude first" in p.message for p in problems)
    assert [int(n.location.split(":")[1]) for n in notices] == [12]
    assert placer.lookups == [] and placer.prepared == []
    assert found == definition.problems()


def test_more_than_fifty_addresses_is_said_out_loud_and_is_still_valid() -> None:
    """feat-004/AC-17: any number is allowed, and what a long list costs per run is stated."""
    many = [f"{n} Main St, Loranger, LA 70446" for n in range(1, 52)]

    made, found = named.read(many)

    assert len(made) == 51
    assert [(where, severity) for where, _message, severity in found] == [((), "notice")]
    assert "153" in found[0][1], "the cost, in queries per source per run"


# -- placing ---------------------------------------------------------------------------------------


def test_an_address_is_looked_up_once_and_a_repeat_run_asks_nobody(tmp_path: Path) -> None:
    """feat-004/AC-16: placed by the Census, cached, and never asked again on the next run.

    The real provider over a counting transport: the count is the proof. An `at` in the file is used
    as written, so the second address is never asked about at all.
    """
    from homescout.enrich.boundaries import CensusBoundaries

    transport = CountingTransport({
        "onelineaddress": {"result": {"addressMatches": [{
            "coordinates": {"x": TAYLOR_AT[1], "y": TAYLOR_AT[0]},
            "addressComponents": {"zip": "70446"},
            "matchedAddress": "52150 TAYLOR DR, LORANGER, LA, 70446",
        }]}},
    })
    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=f"  - {TAYLOR}\n  - {{address: '{HIGHWAY}', at: [30.586997, -90.597642]}}\n",
    ))
    source = Around(rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)])

    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, session(transport), fetch=False)
        with boundaries(provider), workspace(store, sources={"fake": source}) as space:
            first = api.run_search(space, "named")
            asked_first = transport.count
            second = api.run_search(space, "named")

    assert asked_first == 1, transport.requests
    assert "onelineaddress" in transport.requests[0] and "Taylor" in transport.requests[0]
    assert transport.count == 1, "the second run looked the address up again"
    assert first.addresses[0].found_by == ("fake",) and second.addresses[0].found_by == ("fake",)
    assert first.addresses[0].matched == "52150 TAYLOR DR, LORANGER, LA, 70446"


def test_an_answer_lasts_a_year_and_no_answer_lasts_thirty_days() -> None:
    """feat-004/AC-16: new construction is asked about again; an address that was found is not."""
    from datetime import UTC, datetime, timedelta

    from homescout.enrich.boundaries import _expired

    now = datetime(2026, 9, 30, tzinfo=UTC)
    ago = lambda days: (now - timedelta(days=days)).isoformat()  # noqa: E731

    assert not _expired({"latitude": 1}, ago(300), now=now)
    assert _expired({"latitude": 1}, ago(400), now=now)
    assert not _expired(None, ago(20), now=now)
    assert _expired(None, ago(40), now=now)


# -- asking ----------------------------------------------------------------------------------------


def test_each_source_is_asked_with_no_filters_in_three_statuses_or_once() -> None:
    """feat-004/AC-18: no filter is ever sent, and the status fan-out follows what a source takes.

    Two houses 0.14 miles apart share one circle; a third, far away, gets its own. Every circle
    contains the half mile around each of its members, so sharing never asks for less.
    """
    addresses = (
        named.NamedAddress(TAYLOR, at=TAYLOR_AT),
        named.NamedAddress(DITTA, at=DITTA_AT),
        named.NamedAddress(HIGHWAY, at=HIGHWAY_AT),
    )
    plan = named.plan(addresses)

    assert len(plan.circles) == 2
    for circle in plan.circles:
        for member in circle.members:
            reach = geo.miles_between((circle.latitude, circle.longitude), member.at)
            assert reach + named.RADIUS_MILES <= circle.miles + 1e-9

    with_status = plan.queries_for(Capabilities(applies=frozenset({"listing_status", "price_min"})))
    without = plan.queries_for(Capabilities(applies=frozenset({"price_min"})))

    assert sorted(ask.query.listing_status for ask in with_status) == sorted(
        ["for_sale", "pending", "contingent"] * 2
    )
    assert len(without) == 2
    for ask in (*with_status, *without):
        assert set(ask.query.populated_fields()) <= {"listing_status"}, "a filter was sent"


def test_a_search_with_addresses_and_no_areas_asks_every_source(tmp_path: Path) -> None:
    """feat-004/AC-18: a source is unavailable only when it can express neither."""
    write(tmp_path / "searches", "named", text=searching(
        "named", addresses=f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n",
    ))
    source = Around(rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)])

    outcome = run(tmp_path, "named", {"fake": source})

    assert outcome.sources[0].outcome == "ok" and outcome.sources[0].rows == 1
    assert source.queries, "the source was never asked"


def test_a_house_under_contract_is_still_seen(tmp_path: Path) -> None:
    """feat-004/AC-18: pending is asked for whatever the search's own listing types say."""
    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n",
        extra="filters:\n  listing_type: [for_sale]\n",
    ))
    source = Around(
        rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT, listing_status="pending")],
        applies=["listing_status"],
    )

    outcome = run(tmp_path, "named", {"fake": source})

    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]


# -- keeping ---------------------------------------------------------------------------------------


def test_only_the_named_house_is_kept_and_its_neighbours_are_not(tmp_path: Path) -> None:
    """feat-004/AC-19: the circle returns the street; the address keeps one house.

    The by-hand run kept eighteen neighbours this way. Here two: one next door on the same street,
    and one with the same house number on another street.
    """
    write(tmp_path / "searches", "named", text=searching(
        "named", addresses=f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n",
    ))
    source = Around(rows=[
        house("taylor", "52150 Taylor Dr", TAYLOR_AT),
        house("next-door", "52160 Taylor Dr", (30.6115, -90.3700)),
        house("same-number", "52150 Ditta Dr", (30.6108, -90.3718)),
    ])

    outcome = run(tmp_path, "named", {"fake": source})

    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]


def test_three_spellings_of_one_highway_house_are_all_that_house(tmp_path: Path) -> None:
    """feat-004/AC-19: `Highway 43` from two sites and `Hwy 43 Hwy` from a third, all kept.

    Exactly what the three sites wrote for 33063 Highway 43 on 2026-09-30, and what the address
    matcher could not key at all until numbered highways were fixed.
    """
    write(tmp_path / "searches", "named", text=(
        "name: named\naddresses:\n"
        f"  - {{address: '{HIGHWAY}', at: [30.586997, -90.597642]}}\n"
        "sources: [fake, other]\n"
    ))
    fake = Around(rows=[house("a", "33063 Highway 43", (30.585764, -90.600606), postal="70443")])
    other = Around("other", rows=[
        house("b", "33063 Hwy 43 Hwy", (30.5853446, -90.6004883), postal="70443", source="other"),
        house("c", "33063 Highway 43", (30.58577, -90.60061), postal="70443", source="other"),
    ])

    outcome = run(tmp_path, "named", {"fake": fake, "other": other})

    assert recorded(tmp_path, outcome.run.id) == [
        "33063 Highway 43", "33063 Highway 43", "33063 Hwy 43 Hwy",
    ]
    assert outcome.addresses[0].found_by == ("fake", "other")


def test_a_unit_only_one_side_carries_does_not_separate_them(tmp_path: Path) -> None:
    """feat-004/AC-19: feat-006's rule on units, applied to a named house.

    A lot designation one site adds is the same house. Two different units are two homes.
    """
    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=(
            "  - {address: '103 Vail Loop, Loranger, LA 70446', at: [30.6, -90.4]}\n"
            "  - {address: '7 Oak Ct Apt 2, Loranger, LA 70446', at: [30.61, -90.41]}\n"
        ),
    ))
    source = Around(rows=[
        house("vail", "103 Vail Loop", (30.6001, -90.4001), unit="Lot 21"),
        house("oak-2", "7 Oak Ct", (30.6101, -90.4101), unit="Apt 2"),
        house("oak-3", "7 Oak Ct", (30.6102, -90.4102), unit="Apt 3"),
    ])

    outcome = run(tmp_path, "named", {"fake": source})

    with Store.open(tmp_path / "homescout.db") as store:
        kept = sorted(
            (s.fields.address_line, s.fields.unit) for s in store.snapshots_for_run(outcome.run.id)
        )
    assert kept == [("103 Vail Loop", "Lot 21"), ("7 Oak Ct", "Apt 2")]


def test_a_zip_code_nobody_gave_is_not_compared_and_one_that_differs_is(tmp_path: Path) -> None:
    """feat-004/AC-19: `at` with no ZIP still finds the house; a wrong ZIP is a different house."""
    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=(
            "  - {address: '52150 Taylor Dr', at: [30.611282, -90.369808]}\n"
            "  - {address: '52149 Ditta Dr, Loranger, LA 70401', at: [30.610603, -90.372070]}\n"
        ),
    ))
    source = Around(rows=[
        house("taylor", "52150 Taylor Dr", TAYLOR_AT),
        house("ditta", "52149 Ditta Dr", DITTA_AT),
    ])

    outcome = run(tmp_path, "named", {"fake": source})

    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]


def test_the_lookup_supplies_the_zip_code_when_the_person_left_it_out(tmp_path: Path) -> None:
    """feat-004/AC-19: the ZIP the lookup matched is the one compared."""
    write(tmp_path / "searches", "named", text=searching(
        "named", addresses="  - 52150 Taylor Dr\n  - 52149 Ditta Dr\n",
    ))
    placer = Placing({
        "52150 Taylor Dr": placed_at(TAYLOR_AT, "52150 TAYLOR DR, LORANGER, LA, 70446", "70446"),
        "52149 Ditta Dr": placed_at(DITTA_AT, "52149 DITTA DR, HAMMOND, LA, 70401", "70401"),
    })
    source = Around(rows=[
        house("taylor", "52150 Taylor Dr", TAYLOR_AT),
        house("ditta", "52149 Ditta Dr", DITTA_AT),
    ])

    with boundaries(placer):
        outcome = run(tmp_path, "named", {"fake": source})

    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]
    assert placer.prepared == ["52150 Taylor Dr", "52149 Ditta Dr"], "looked up before the run"


# -- exempt, and still judged ------------------------------------------------------------------


def test_a_named_house_skips_filters_and_exclusions_and_is_still_judged(tmp_path: Path) -> None:
    """feat-004/AC-20, feat-004/AC-3: in the run whatever the filters and exclusions say.

    The filters would hide it twice over (too dear, too old) and an exclusion covers it. It is in
    the run anyway, and the criteria still decide about it: a drop rule fires and is recorded, so
    it is set aside with its reason rather than vanishing. The neighbour inside the same exclusion,
    which nobody named, is excluded as before.
    """
    covering = json.dumps(polygon(-90.38, 30.60, -90.36, 30.62))
    write(tmp_path / "searches", "named", text=(
        "name: named\n"
        "areas:\n"
        "  - {type: radius, center: [30.611282, -90.369808], miles: 2}\n"
        "addresses:\n"
        f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n"
        "exclude_areas:\n"
        f"  - {{type: polygon, name: covered, geometry: {covering}}}\n"
        "filters:\n"
        "  price: {max: 300000}\n"
        "  year_built: {min: 2010}\n"
        "sources: [fake]\n"
        "rules:\n"
        "  - {id: too-dear, when: 'price > 400000', severity: drop}\n"
    ))
    source = Around(rows=[
        house("taylor", "52150 Taylor Dr", TAYLOR_AT, price=445_000, year_built=2003),
        house("cheap-neighbour", "52170 Taylor Dr", (30.6117, -90.3690), price=200_000,
              year_built=2015),
    ])

    outcome = run(tmp_path, "named", {"fake": source})

    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]
    with Store.open(tmp_path / "homescout.db") as store:
        fired = [v for v in store.verdicts(outcome.run.id) if v.verdict == "fired"]
    assert [v.rule_id for v in fired] == ["too-dear"]


def test_freshness_never_hides_a_named_house(tmp_path: Path) -> None:
    """feat-004/AC-20: the freshness filter is a filter, so it does not apply to a named house."""
    write(tmp_path, "named", text=searching(
        "named",
        addresses=f"  - {TAYLOR}\n",
        extra="filters:\n  listed_within_days: 7\n",
    ))
    definition = catalog(tmp_path).load("named")

    assert not definition.fresh_enough("2026-01-01T00:00:00Z")
    assert definition.fresh_enough("2026-01-01T00:00:00Z", named=True)


# -- the report ------------------------------------------------------------------------------------


def test_every_named_address_is_reported_found_not_found_or_not_looked_for(
    tmp_path: Path,
) -> None:
    """feat-004/AC-21: three ordinary answers, and the run is not a failure for any of them."""
    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=(
            f"  - {TAYLOR}\n"
            "  - 1 Nowhere Ln, Loranger, LA 70446\n"
            "  - 99999 Unplaceable Rd, Loranger, LA 70446\n"
        ),
    ))
    placer = Placing({
        TAYLOR: placed_at(TAYLOR_AT, "52150 TAYLOR DR, LORANGER, LA, 70446", "70446"),
        "1 Nowhere Ln, Loranger, LA 70446": placed_at((30.62, -90.38), "1 NOWHERE LN"),
    })
    source = Around(rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)])

    with boundaries(placer):
        outcome = run(tmp_path, "named", {"fake": source})

    assert outcome.run.status == "completed"
    reports = {r.address: r for r in outcome.addresses}
    assert reports[TAYLOR].found_by == ("fake",)
    assert reports[TAYLOR].matched == "52150 TAYLOR DR, LORANGER, LA, 70446"
    nowhere = reports["1 Nowhere Ln, Loranger, LA 70446"]
    assert nowhere.placed and nowhere.found_by == () and nowhere.missed_by == ("fake",)
    lost = reports["99999 Unplaceable Rd, Loranger, LA 70446"]
    assert not lost.placed and lost.missed_by == ()
    assert "found 1 of 2 named addresses" in (outcome.sources[0].detail or "")


def test_a_search_of_only_houses_none_of_them_placed_says_so(tmp_path: Path) -> None:
    """feat-004/AC-21, feat-004/AC-18: nothing to ask is said as that, not as an area problem.

    Found by the code-against-spec audit: each source used to be reported as having "no way to
    express any of this search's areas ()", which names areas the search does not have.
    """
    write(tmp_path / "searches", "named", text=searching(
        "named", addresses="  - 99999 Unplaceable Rd, Loranger, LA 70446\n",
    ))
    source = Around(rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)])

    with boundaries(Placing()):
        outcome = run(tmp_path, "named", {"fake": source})

    assert outcome.sources[0].outcome == "unavailable"
    assert "none of its named addresses could be placed" in (outcome.sources[0].detail or "")
    assert "areas ()" not in (outcome.sources[0].detail or "")
    assert not outcome.addresses[0].placed
    assert source.queries == []


def test_the_command_line_reports_each_address_in_both_forms(tmp_path: Path) -> None:
    """feat-004/AC-21: in `run --json`, and said out loud without it."""
    from homescout.sources import register

    write(tmp_path / "searches", "named", text=searching(
        "named",
        addresses=(
            f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n"
            "  - {address: '1 Nowhere Ln, Loranger, LA 70446', at: [30.62, -90.38]}\n"
        ),
    ))
    source = Around(rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)])
    register("fake", lambda _session: source, replace=True)

    code, out, err = invoke(["run", "named", "--json"], db=tmp_path / "homescout.db")
    assert code in (0, 2), err
    document = json.loads(out)
    reported = {r["address"]: r for r in document["searches"][0]["addresses"]}
    assert reported[TAYLOR]["found_by"] == ["fake"]
    assert reported["1 Nowhere Ln, Loranger, LA 70446"]["missed_by"] == ["fake"]

    code, out, err = invoke(["run", "named"], db=tmp_path / "homescout.db")
    assert f"{TAYLOR}: found by fake" in out
    assert "1 Nowhere Ln, Loranger, LA 70446: not found by any source" in out


def test_a_source_that_refuses_a_status_degrades_and_still_finds_the_house(tmp_path: Path) -> None:
    """feat-004/AC-18: a refused status is a failed query, as Realtor's are today, and no more."""
    write(tmp_path / "searches", "named", text=searching(
        "named", addresses=f"  - {{address: '{TAYLOR}', at: [30.611282, -90.369808]}}\n",
    ))
    source = Around(
        rows=[house("taylor", "52150 Taylor Dr", TAYLOR_AT)],
        applies=["listing_status"],
        refuse=["pending", "contingent"],
    )

    outcome = run(tmp_path, "named", {"fake": source})

    assert outcome.sources[0].outcome == "failed"
    assert outcome.addresses[0].found_by == ("fake",)
    assert recorded(tmp_path, outcome.run.id) == ["52150 Taylor Dr"]
