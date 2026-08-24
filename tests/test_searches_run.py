"""A definition file, driven through the real run loop and the real command line.

Everything below the file is real here: the store, the loop, the argument parser, the digest. What
is supplied is the source, because the alternative is a network, and the boundary provider, because
that feature is not built yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli_fakes import FakeSource, invoke, row
from homescout import api
from homescout.search import Placement
from homescout.sources.base import Capabilities, City, PostalCode
from homescout.store import Store
from searches_fakes import (
    INSIDE,
    OUTSIDE,
    SQUARE,
    CountingBoundaries,
    boundaries,
    catalog,
    sourced,
    workspace,
    write,
)


def drawn(name: str) -> str:
    """A saved search whose only area is a shape somebody drew."""
    shape = str(SQUARE).replace(chr(39), chr(34))
    return (
        f"name: {name}\nareas:\n"
        f"  - {{type: polygon, name: shape, geometry: {shape}}}\n"
        "sources: [fake]\n"
    )


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake"):
        yield


def located(identifier: str, point: tuple[float | None, float | None], **fields):
    return row(identifier, latitude=point[0], longitude=point[1], **fields)


def run(tmp_path: Path, name: str, source: FakeSource, images: bool = False):
    with (
        Store.open(tmp_path / "homescout.db") as store,
        workspace(store, sources={"fake": source}, images=images) as space,
    ):
        return api.run_search(space, name)


def test_a_property_outside_the_shape_never_reaches_the_store(tmp_path: Path) -> None:
    """feat-004/AC-5: the source returned it, the coarse query was wider than the shape, it goes.

    This is the whole promise of two-stage geography: a coarse query is not the user's problem.
    """
    write(tmp_path / "searches", "drawn", text=drawn("drawn"))
    source = FakeSource(rows=[located("in", INSIDE), located("out", OUTSIDE)])

    outcome = run(tmp_path, "drawn", source)

    assert outcome.sources[0].rows == 1
    with Store.open(tmp_path / "homescout.db") as store:
        kept = store.snapshots_for_run(outcome.run.id)
    assert [snapshot.fields.address_line for snapshot in kept] == ["in Example Road"]


def test_a_property_with_no_coordinates_is_kept_and_counted(tmp_path: Path) -> None:
    """feat-004/AC-6: retained and marked, rather than dropped or assumed to qualify.

    Dropping it would be the worse of the two, because a property that stops being recorded is one
    the store can only later describe as having disappeared.
    """
    write(tmp_path / "searches", "drawn", text=drawn("drawn"))
    source = FakeSource(
        rows=[located("in", INSIDE), located("lost", (None, None)), located("out", OUTSIDE)]
    )

    outcome = run(tmp_path, "drawn", source)

    assert outcome.sources[0].rows == 2
    assert outcome.sources[0].not_locatable == 1
    with Store.open(tmp_path / "homescout.db") as store:
        assert len(store.listings()) == 2


def test_the_run_says_out_loud_how_many_it_could_not_place(tmp_path: Path) -> None:
    """feat-004/AC-6: visible as an unresolved case rather than as an absence."""
    write(tmp_path / "searches", "drawn", text=drawn("drawn"))
    with sourced("fake"):
        from homescout.sources import register

        register("fake", lambda _s: FakeSource(rows=[located("lost", (None, None))]), replace=True)
        code, out, err = invoke(
            ["run", "drawn", "--json", "--no-images"], db=tmp_path / "homescout.db"
        )

    assert code == 0, err
    entry = json.loads(out)["searches"][0]
    assert entry["sources"][0]["not_locatable"] == 1
    assert entry["counts"]["matched"] == 1


def test_a_source_that_cannot_express_the_areas_is_unavailable_rather_than_empty(
    tmp_path: Path,
) -> None:
    """feat-004/AC-4: not asked is a different fact from asked and found nothing.

    The store reads a source that found nothing as evidence about a market. It has to be told the
    difference, or a source that was never asked would start marking houses as gone.
    """
    write(
        tmp_path / "searches",
        "places",
        text='name: places\nareas:\n  - {type: city, value: "Portales, NM"}\nsources: [fake]\n',
    )

    class Boxes(FakeSource):
        def capabilities(self) -> Capabilities:
            from homescout.sources.base import BoundingBox

            return Capabilities(accepts_areas=(BoundingBox,))

    outcome = run(tmp_path, "places", Boxes(rows=[located("in", INSIDE)]))

    assert outcome.sources[0].outcome == "unavailable"
    assert "Portales, NM" in (outcome.sources[0].detail or "")
    assert outcome.sources[0].rows == 0
    with Store.open(tmp_path / "homescout.db") as store:
        assert not store.runs("places", only_completed=True)[0].all_sources_succeeded


def test_the_command_line_and_the_core_place_the_same_properties(tmp_path: Path) -> None:
    """feat-004/AC-7: one definition, two entry points, identical geometry and identical results.

    The browser interface is not built yet, so its half is represented by the facade it will call,
    which is the same seam the command line goes through. When that surface arrives it inherits this
    obligation rather than being trusted with it.
    """
    rows = [located("in", INSIDE), located("out", OUTSIDE), located("lost", (None, None))]
    through_core = tmp_path / "core"
    through_command = tmp_path / "command"
    for directory in (through_core, through_command):
        write(directory / "searches", "drawn", text=drawn("drawn"))

    with (
        Store.open(through_core / "homescout.db") as store,
        workspace(store, sources={"fake": FakeSource(rows=rows)}, images=False) as space,
    ):
        definition = space.catalog.load("drawn")
        core_queries = definition.queries_for(Capabilities())
        core = api.run_search(space, "drawn")

    from homescout.sources import register

    register("fake", lambda _s: FakeSource(rows=rows), replace=True)
    code, out, err = invoke(
        ["run", "drawn", "--json", "--no-images"], db=through_command / "homescout.db"
    )
    assert code == 0, err

    entry = json.loads(out)["searches"][0]
    assert entry["counts"]["matched"] == core.comparison.counts["new"]
    assert entry["sources"][0]["rows"] == core.sources[0].rows
    assert entry["sources"][0]["not_locatable"] == core.sources[0].not_locatable

    with Store.open(through_command / "homescout.db") as store:
        command_definition = catalog(through_command / "searches").load("drawn")
        assert command_definition.queries_for(Capabilities()) == core_queries
        assert len(store.listings()) == 2


def test_freshness_is_never_sent_to_a_source_and_never_drops_a_row(tmp_path: Path) -> None:
    """feat-004/AC-11: a local freshness window narrows what you are shown, never what is recorded.

    Both halves are the same defect one step apart. Pushed to a source, older properties stop coming
    back and the store reads the gap as houses that may have sold. Applied during a run, the row is
    dropped before it is recorded and the store reads exactly the same gap.
    """
    write(
        tmp_path / "searches",
        "fresh",
        text='name: fresh\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  listed_within_days: 30\nsources: [fake]\n",
    )
    source = FakeSource(rows=[located("a", INSIDE), located("b", OUTSIDE)])

    outcome = run(tmp_path, "fresh", source)

    assert [q.listed_since for q in source.queries] == [None]
    assert outcome.sources[0].rows == 2, "freshness removed nothing from the run"
    assert "listed_since" not in outcome.sources[0].applied_locally


def test_freshness_is_measured_from_our_own_first_sighting(tmp_path: Path) -> None:
    """feat-004/AC-11: never from a source's own days-on-market, which is about its records."""
    from datetime import UTC, datetime

    write(
        tmp_path / "searches",
        "fresh",
        text='name: fresh\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  listed_within_days: 30\nsources: [fake]\n",
    )
    definition = catalog(tmp_path / "searches").load("fresh")
    now = datetime(2026, 8, 23, tzinfo=UTC)

    assert definition.fresh_enough("2026-08-01T00:00:00Z", now=now)
    assert not definition.fresh_enough("2026-01-01T00:00:00Z", now=now)
    assert definition.fresh_enough(None, now=now), "unknown is not a reason to hide something"


def test_a_repeat_run_looks_no_place_up_twice(tmp_path: Path) -> None:
    """feat-004/AC-13: one lookup per area, however many properties or runs go past it.

    A run tests thousands of properties against a few areas. Asking the provider per property, or
    per run within one invocation, is the difference between one request and thousands.
    """
    write(
        tmp_path / "searches",
        "bounded",
        text='name: bounded\nareas:\n  - {type: city, value: "Portales, NM"}\nsources: [fake]\n',
    )
    provider = CountingBoundaries(shapes={("city", "Portales, NM"): SQUARE})
    rows = [located(str(i), INSIDE) for i in range(20)]

    with (
        boundaries(provider),
        Store.open(tmp_path / "homescout.db") as store,
        workspace(store, sources={"fake": FakeSource(rows=rows)}, images=False) as space,
    ):
        definition = space.catalog.load("bounded")
        api.run_search(space, "bounded")
        for _ in range(3):
            assert definition.place(rows[0].fields) is Placement.inside

    assert provider.lookups == ["city:Portales, NM"]


def test_the_areas_a_search_covers_are_what_the_surfaces_show(tmp_path: Path) -> None:
    """feat-004/AC-1: a saved search shows what it covers, without running anything."""
    write(
        tmp_path / "searches",
        "shown",
        text='name: shown\nareas:\n  - {type: city, value: "Portales, NM"}\n'
        '  - {type: zip, value: "88130"}\nsources: [fake]\n',
    )

    code, out, err = invoke(["searches", "show", "shown", "--json"], db=tmp_path / "homescout.db")

    assert code == 0, err
    assert json.loads(out)["search"] == {"name": "shown", "sources": ["fake"], "areas": 2}

    code, listed, err = invoke(["searches", "list", "--json"], db=tmp_path / "homescout.db")
    assert code == 0, err
    assert json.loads(listed)["searches"] == ["shown"]


def test_a_notice_is_reported_without_making_the_search_invalid(tmp_path: Path) -> None:
    """feat-004/AC-9: valid, and worth saying something about, are not the same answer."""
    write(
        tmp_path / "searches",
        "circle",
        text='name: circle\nareas:\n  - {type: radius, center: "Portales, NM", miles: 25}\n'
        "sources: [fake]\n",
    )

    code, out, err = invoke(
        ["searches", "validate", "circle", "--json"], db=tmp_path / "homescout.db"
    )

    assert code == 0, err
    answer = json.loads(out)
    assert answer["valid"] is True
    assert [p["severity"] for p in answer["problems"]] == ["notice"]


def test_a_definition_from_a_file_runs_from_the_command_line(tmp_path: Path) -> None:
    """feat-004/AC-1: the file is the whole configuration. Nothing else is registered."""
    write(
        tmp_path / "searches",
        "portales",
        text='name: portales\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  price: {max: 400000}\nsources: [fake]\n",
    )
    from homescout.sources import register

    register(
        "fake",
        lambda _s: FakeSource(rows=[located("a", INSIDE), located("b", INSIDE, price=900_000)]),
        replace=True,
    )

    code, out, err = invoke(
        ["run", "portales", "--json", "--no-images"], db=tmp_path / "homescout.db"
    )

    assert code == 0, err
    entry = json.loads(out)["searches"][0]
    assert entry["name"] == "portales"
    assert entry["counts"]["new"] == 1, "the price filter was applied, locally, by the tool"
    assert entry["sources"][0]["applied_locally"] == ["price_max"]


def test_the_query_a_definition_produces_carries_its_filters(tmp_path: Path) -> None:
    """feat-004/AC-1: what the file says becomes what the source is asked."""
    write(
        tmp_path / "searches",
        "filtered",
        text='name: filtered\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  price: {min: 100000, max: 500000}\n  beds: {min: 3}\n"
        "  lot_acres: {min: 1}\nsources: [fake]\n",
    )

    query = catalog(tmp_path / "searches").load("filtered").queries_for(Capabilities())[0]

    assert query.area == PostalCode("88130")
    assert (query.price_min, query.price_max) == (100_000, 500_000)
    assert query.beds_min == 3
    assert query.lot_sqft_min == 43_560
    assert query.listing_status == "for_sale"


def test_an_area_a_source_cannot_express_does_not_stop_the_others(tmp_path: Path) -> None:
    """feat-004/AC-4: a search with two areas, one of which this source cannot be asked for."""
    write(
        tmp_path / "searches",
        "mixed",
        text="name: mixed\nareas:\n"
        f"  - {{type: polygon, geometry: {str(SQUARE).replace(chr(39), chr(34))}}}\n"
        '  - {type: city, value: "Portales, NM"}\n'
        "sources: [fake]\n",
    )

    class OnlyPlaces(FakeSource):
        def capabilities(self) -> Capabilities:
            return Capabilities(accepts_areas=(City,))

    definition = catalog(tmp_path / "searches").load("mixed")
    asked = definition.queries_for(OnlyPlaces().capabilities())

    assert [q.area for q in asked] == [City("Portales", "NM")]
