"""The two-stage geography: what gets asked for, and what gets kept.

The rule that has to hold, and that every test here checks a way of, is that whatever is sent to a
source contains the area. Coarse resolution may fetch too much, because the exact test afterwards
removes the extra. It may never fetch too little, because nothing afterwards can put a house back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homescout.records import ListingFields
from homescout.search import Placement
from homescout.search.geometry import miles_between, positions, to_geometry
from homescout.sources.base import (
    AddressRadius,
    BoundingBox,
    Capabilities,
    City,
    County,
    PointRadius,
    PostalCode,
    State,
)
from searches_fakes import (
    INSIDE,
    OUTSIDE,
    SQUARE,
    CountingBoundaries,
    boundaries,
    catalog,
    polygon,
    sourced,
    write,
)

#: What each kind of source will take. Realtor's list, Zillow's box, and a source that takes
#: everything, which is what the fakes do.
TAKES_PLACES = Capabilities(accepts_areas=(PostalCode, City, County, State, AddressRadius,
                                           PointRadius))
TAKES_BOXES = Capabilities(accepts_areas=(BoundingBox,))
TAKES_ANYTHING = Capabilities()


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake"):
        yield


def load(tmp_path: Path, name: str, body: str):
    write(tmp_path / "searches", name, text=body)
    return catalog(tmp_path / "searches").load(name)


def at(latitude: float | None, longitude: float | None, **fields) -> ListingFields:
    return ListingFields(latitude=latitude, longitude=longitude, **fields)


def holds(area, point: tuple[float, float]) -> bool:
    """Is this point inside this coarse form? Only asked of forms that are geometry."""
    latitude, longitude = point
    if isinstance(area, BoundingBox):
        return area.south <= latitude <= area.north and area.west <= longitude <= area.east
    if isinstance(area, PointRadius):
        return miles_between((area.latitude, area.longitude), point) <= area.miles
    raise AssertionError(f"{area!r} is a name, not a shape")


def drawn(name: str, geometry=SQUARE, **extra) -> str:
    keys = "".join(f", {k}: {v}" for k, v in extra.items())
    return (
        f"name: {name}\nareas:\n"
        f"  - {{type: polygon, name: shape, geometry: {str(geometry).replace(chr(39), chr(34))}"
        f"{keys}}}\nsources: [fake]\n"
    )


# -- coarse resolution -------------------------------------------------------


def test_a_drawn_shape_is_asked_for_as_a_box_by_a_source_that_takes_one(tmp_path: Path) -> None:
    """feat-004/AC-4: the coarse form contains every vertex of the shape."""
    definition = load(tmp_path, "boxed", drawn("boxed"))

    queries = definition.queries_for(TAKES_BOXES)

    assert len(queries) == 1
    box = queries[0].area
    assert isinstance(box, BoundingBox)
    for vertex in positions(to_geometry(SQUARE)):
        assert holds(box, vertex), f"{vertex} fell outside the box that was asked for"


def test_a_drawn_shape_is_asked_for_as_a_circle_by_a_source_that_takes_no_box(
    tmp_path: Path,
) -> None:
    """feat-004/AC-4: a site that takes named places and a radius can still be asked for a shape.

    This is what makes a drawn polygon work today, with no boundary lookups registered at all: a
    circle through the farthest vertex contains the whole shape, and the extra market it drags in is
    removed by the exact test afterwards.
    """
    definition = load(tmp_path, "circled", drawn("circled"))

    queries = definition.queries_for(TAKES_PLACES)

    assert len(queries) == 1
    circle = queries[0].area
    assert isinstance(circle, PointRadius)
    for vertex in positions(to_geometry(SQUARE)):
        assert holds(circle, vertex), f"{vertex} fell outside the circle that was asked for"


def test_a_shape_crossing_a_county_line_is_still_covered(tmp_path: Path) -> None:
    """feat-004/AC-4: the spec's edge case, with nothing registered to name the counties.

    The union of what is asked for contains the shape, which is the requirement. That it takes one
    query rather than several is a detail of how, not of whether.
    """
    wide = polygon(-104.5, 34.0, -102.5, 35.0)
    definition = load(tmp_path, "wide", drawn("wide", geometry=wide))

    for capabilities in (TAKES_BOXES, TAKES_PLACES):
        queries = definition.queries_for(capabilities)
        assert queries
        for vertex in positions(to_geometry(wide)):
            assert any(holds(q.area, vertex) for q in queries), f"{vertex} was not covered"


def test_a_named_place_is_asked_for_as_itself(tmp_path: Path) -> None:
    """feat-004/AC-4: the coarse form of a city is that city, which contains it exactly."""
    definition = load(
        tmp_path,
        "named",
        "name: named\nareas:\n"
        '  - {type: city, value: "Portales, NM"}\n'
        '  - {type: county, value: "Roosevelt County, NM"}\n'
        '  - {type: zip, value: "88130"}\n'
        "sources: [fake]\n",
    )

    asked = [q.area for q in definition.queries_for(TAKES_PLACES)]

    assert asked == [City("Portales", "NM"), County("Roosevelt", "NM"), PostalCode("88130")]


def test_a_radius_around_a_point_needs_no_lookup(tmp_path: Path) -> None:
    """feat-004/AC-2: a centre given as coordinates goes straight to the source as a circle."""
    definition = load(
        tmp_path,
        "point",
        "name: point\nareas:\n  - {type: radius, center: [34.18, -103.35], miles: 25}\n"
        "sources: [fake]\n",
    )

    asked = definition.queries_for(TAKES_PLACES)[0].area

    assert asked == PointRadius(34.18, -103.35, 25.0)


def test_a_source_that_can_express_none_of_the_areas_is_asked_nothing(tmp_path: Path) -> None:
    """feat-004/AC-4: not asked, rather than asked for somewhere else."""
    definition = load(
        tmp_path, "places", 'name: places\nareas:\n  - {type: city, value: "Portales, NM"}\n'
        "sources: [fake]\n"
    )

    assert definition.queries_for(TAKES_BOXES) == ()


def test_every_listing_status_asked_for_becomes_its_own_query(tmp_path: Path) -> None:
    """feat-004/AC-4: a source takes one status at a time, and status is never applied here."""
    definition = load(
        tmp_path,
        "statuses",
        'name: statuses\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  listing_type: [for_sale, pending]\nsources: [fake]\n",
    )

    queries = definition.queries_for(TAKES_PLACES)

    assert [q.listing_status for q in queries] == ["for_sale", "pending"]
    assert {q.area for q in queries} == {PostalCode("88130")}


# -- the exact test ----------------------------------------------------------


def test_a_property_inside_the_shape_stays_and_one_outside_does_not(tmp_path: Path) -> None:
    """feat-004/AC-5: whatever the source filtered, the shape decides."""
    definition = load(tmp_path, "exact", drawn("exact"))

    assert definition.place(at(*INSIDE)) is Placement.inside
    assert definition.place(at(*OUTSIDE)) is Placement.outside


def test_inside_any_area_qualifies(tmp_path: Path) -> None:
    """feat-004/AC-3: several areas are a union, including where two of them overlap."""
    left = polygon(-103.5, 34.1, -103.3, 34.3)
    right = polygon(-103.4, 34.1, -103.2, 34.3)
    definition = load(
        tmp_path,
        "union",
        "name: union\nareas:\n"
        f"  - {{type: polygon, geometry: {str(left).replace(chr(39), chr(34))}}}\n"
        f"  - {{type: polygon, geometry: {str(right).replace(chr(39), chr(34))}}}\n"
        "sources: [fake]\n",
    )

    assert definition.place(at(34.2, -103.45)) is Placement.inside, "in the first only"
    assert definition.place(at(34.2, -103.25)) is Placement.inside, "in the second only"
    assert definition.place(at(34.2, -103.35)) is Placement.inside, "in both"
    assert definition.place(at(34.2, -103.10)) is Placement.outside, "in neither"


def test_an_exclusion_removes_what_an_area_would_have_kept(tmp_path: Path) -> None:
    """feat-004/AC-3: not the east side of town, as geometry rather than as a mental note."""
    town = polygon(-103.5, 34.1, -103.3, 34.3)
    east = polygon(-103.35, 34.1, -103.3, 34.3)
    definition = load(
        tmp_path,
        "excluded",
        "name: excluded\nareas:\n"
        f"  - {{type: polygon, geometry: {str(town).replace(chr(39), chr(34))}}}\n"
        "exclude_areas:\n"
        f"  - {{type: polygon, name: east-side, geometry: "
        f"{str(east).replace(chr(39), chr(34))}}}\n"
        "sources: [fake]\n",
    )

    assert definition.place(at(34.2, -103.45)) is Placement.inside
    assert definition.place(at(34.2, -103.32)) is Placement.outside
    assert definition.exclusions[0].name == "east-side"


def test_a_property_with_no_coordinates_is_not_placed_and_not_dropped(tmp_path: Path) -> None:
    """feat-004/AC-6: a third answer, because both of the other two would be a lie."""
    definition = load(tmp_path, "nocoords", drawn("nocoords"))

    assert definition.place(at(None, None)) is Placement.unlocatable
    assert definition.place(at(34.20, None)) is Placement.unlocatable


def test_a_named_area_reads_the_place_the_source_reported(tmp_path: Path) -> None:
    """feat-004/AC-5: with no boundary lookups, a source's own place fields are the evidence.

    Not a guess: a source that says a house is in Portales is saying where the house is. It is only
    ever consulted when there is no boundary and no coordinate to test instead.
    """
    definition = load(
        tmp_path, "city", 'name: city\nareas:\n  - {type: city, value: "Portales, NM"}\n'
        "sources: [fake]\n"
    )

    assert definition.place(at(None, None, city="Portales", state="NM")) is Placement.inside
    assert definition.place(at(None, None, city="Clovis", state="NM")) is Placement.outside
    assert definition.place(at(None, None, city="Portales", state="TX")) is Placement.outside
    assert definition.place(at(None, None)) is Placement.unlocatable


def test_a_state_written_either_way_is_the_same_state(tmp_path: Path) -> None:
    """feat-004/AC-5: "New Mexico" and "NM" are one place, and treating them as two loses houses."""
    definition = load(
        tmp_path, "state", 'name: state\nareas:\n  - {type: state, value: "New Mexico"}\n'
        "sources: [fake]\n"
    )

    assert definition.place(at(None, None, state="NM")) is Placement.inside
    assert definition.place(at(None, None, state="TX")) is Placement.outside


def test_an_exclusion_that_cannot_be_tested_never_excludes(tmp_path: Path) -> None:
    """feat-004/AC-3: an exclusion removes a property on evidence, never on the absence of it."""
    definition = load(
        tmp_path,
        "guarded",
        'name: guarded\nareas:\n  - {type: city, value: "Portales, NM"}\n'
        "exclude_areas:\n"
        f"  - {{type: polygon, geometry: {str(SQUARE).replace(chr(39), chr(34))}}}\n"
        "sources: [fake]\n",
    )

    assert definition.place(at(None, None, city="Portales", state="NM")) is Placement.inside


# -- with a boundary provider registered -------------------------------------


def test_a_registered_provider_makes_a_named_area_exact(tmp_path: Path) -> None:
    """feat-004/AC-13: the boundary comes from enrichment, and this feature only asks for it."""
    definition = load(
        tmp_path, "bounded", 'name: bounded\nareas:\n  - {type: city, value: "Portales, NM"}\n'
        "sources: [fake]\n"
    )
    provider = CountingBoundaries(shapes={("city", "Portales, NM"): SQUARE})

    with boundaries(provider):
        assert definition.place(at(*INSIDE, city="Elsewhere")) is Placement.inside
        assert definition.place(at(*OUTSIDE, city="Portales")) is Placement.outside

    assert provider.lookups == ["city:Portales, NM"], "asked once, not once per property"


def test_a_provider_that_names_the_places_a_shape_touches_is_preferred_to_a_circle(
    tmp_path: Path,
) -> None:
    """feat-004/AC-4: named places are cheaper to search than a circle around everything."""
    definition = load(tmp_path, "touching", drawn("touching"))
    provider = CountingBoundaries(containing=[("county", "Roosevelt County, NM")])

    with boundaries(provider):
        asked = [q.area for q in definition.queries_for(TAKES_PLACES)]

    assert asked == [County("Roosevelt", "NM")]


def test_a_provider_locates_the_centre_of_a_named_radius(tmp_path: Path) -> None:
    """feat-004/AC-13: with a provider, the circle around a place name becomes exact."""
    definition = load(
        tmp_path,
        "located",
        'name: located\nareas:\n  - {type: radius, center: "Portales, NM", miles: 5}\n'
        "sources: [fake]\n",
    )
    provider = CountingBoundaries(points={"Portales, NM": (34.18, -103.35)})

    with boundaries(provider):
        assert definition.place(at(34.19, -103.35)) is Placement.inside
        assert definition.place(at(35.50, -103.35)) is Placement.outside
        assert definition.queries_for(TAKES_PLACES)[0].area == PointRadius(34.18, -103.35, 5.0)

    assert provider.lookups == ["locate:Portales, NM"]
