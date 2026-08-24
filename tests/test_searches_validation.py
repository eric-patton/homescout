"""Everything wrong with a definition, before a single request is made.

Validation is what stands between a typo and an hour of throttled requests. So it reports everything
it can find at once, each thing with a place in the file, and it contacts nothing at all while doing
it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homescout import api
from homescout.search import blocking, notices
from homescout.store import Store
from searches_fakes import Hostile, catalog, sourced, write


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake"):
        yield


def problems_of(tmp_path: Path, name: str, text: str) -> tuple:
    write(tmp_path / "searches", name, text=text)
    return catalog(tmp_path / "searches").load(name).problems()


def messages(found) -> str:
    return " | ".join(f"{p.location} {p.message}" for p in found)


def test_every_problem_is_reported_at_once_and_each_one_has_a_line(tmp_path: Path) -> None:
    """feat-004/AC-9: one pass, and enough location detail to fix the file by hand.

    Four separate mistakes in one file. A validator that stopped at the first would cost four
    attempts to learn what one pass can say.
    """
    found = problems_of(
        tmp_path,
        "messy",
        "name: messy\n"
        "areas:\n"
        '  - {type: city, value: "Las Cruces"}\n'
        '  - {type: parish, value: "Orleans, LA"}\n'
        "filters:\n"
        "  price: {min: 700000, max: 200000}\n"
        "sources: [nowhere]\n",
    )

    said = messages(found)
    assert len(blocking(found)) == 4, said
    assert "ambiguous" in said
    assert "parish" in said
    assert "above its max" in said
    assert "nowhere" in said
    assert all(":" in p.location for p in blocking(found)), said
    assert "messy.yaml:3" in said and "messy.yaml:6" in said, said


def test_the_four_named_refusals(tmp_path: Path) -> None:
    """feat-004/AC-10: an unknown source, a broken shape, a backwards range, an unknown type."""
    # Deliberately a name no adapter will ever have. This read `zillow` until that became a real
    # source (feat-005), at which point the test was checking nothing.
    unknown_source = problems_of(
        tmp_path, "s", 'name: s\nareas:\n  - {type: zip, value: "88130"}\nsources: [craigslist]\n'
    )
    assert "there is no source named 'craigslist'" in messages(unknown_source)

    figure_of_eight = problems_of(
        tmp_path,
        "g",
        "name: g\nareas:\n"
        '  - {type: polygon, geometry: {type: Polygon, coordinates: '
        "[[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]}}\n"
        "sources: [fake]\n",
    )
    assert "not a valid area" in messages(figure_of_eight)
    assert "crosses itself" in messages(figure_of_eight)

    inverted = problems_of(
        tmp_path,
        "r",
        'name: r\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  beds: {min: 5, max: 2}\nsources: [fake]\n",
    )
    assert "above its max" in messages(inverted)

    unknown_area = problems_of(
        tmp_path, "a", 'name: a\nareas:\n  - {type: neighborhood, value: "east"}\nsources: [fake]\n'
    )
    assert "unknown area type" in messages(unknown_area)


def test_a_shape_written_the_wrong_way_round_is_named_for_what_it_is(tmp_path: Path) -> None:
    """feat-004/AC-10: latitude and longitude swapped is the commonest hand-editing mistake."""
    found = problems_of(
        tmp_path,
        "swapped",
        "name: swapped\nareas:\n"
        "  - {type: polygon, geometry: {type: Polygon, coordinates: "
        "[[[34.15, -103.4], [34.25, -103.4], [34.25, -103.3], [34.15, -103.4]]]}}\n"
        "sources: [fake]\n",
    )
    assert "longitude first" in messages(found)


def test_a_typo_in_a_key_is_not_silent(tmp_path: Path) -> None:
    """feat-004/AC-9: a misspelled filter parses perfectly and then never applies."""
    found = problems_of(
        tmp_path,
        "typo",
        'name: typo\nareas:\n  - {type: zip, value: "88130"}\n'
        "filters:\n  prise: {min: 100}\nsources: [fake]\n",
    )
    assert "'prise' is not a filter" in messages(found)

    top = problems_of(
        tmp_path,
        "typo2",
        'name: typo2\nareas:\n  - {type: zip, value: "88130"}\nsources: [fake]\nexpirt: {}\n',
    )
    assert "'expirt' is not part of a saved search" in messages(top)


def test_a_name_that_disagrees_with_its_file_is_reported(tmp_path: Path) -> None:
    """feat-004/AC-9: a run is asked for by name, a directory is read by file name."""
    found = problems_of(
        tmp_path, "onedisk", 'name: another\nareas:\n  - {type: zip, value: "88130"}\n'
        "sources: [fake]\n"
    )
    assert "does not match the file name" in messages(found)


def test_a_file_that_is_not_yaml_at_all_still_loads_and_says_where(tmp_path: Path) -> None:
    """feat-004/AC-9: a broken file is reported with a line, not raised from somewhere nameless."""
    found = problems_of(tmp_path, "broken", "name: broken\nareas: [\n")

    assert len(blocking(found)) == 1
    assert "broken.yaml:" in blocking(found)[0].location


def test_a_definition_that_asks_for_an_object_to_be_built_is_refused(tmp_path: Path) -> None:
    """feat-004/NFR-security: a saved search is data. Nothing in one is ever executed.

    The file below is the shape of a YAML deserialization attack. The loader this feature uses does
    not construct objects at all, so the tag is reported against its line instead of imported and
    called, and the test asserts the report rather than the absence of an effect, because an absent
    effect is also what a silently ignored tag looks like.
    """
    found = problems_of(
        tmp_path,
        "tagged",
        "name: tagged\n"
        "areas: !!python/object/apply:os.system ['echo pwned > owned.txt']\n"
        "sources: [fake]\n",
    )

    said = messages(found)
    assert "asks for an object to be built" in said
    assert "tagged.yaml:2" in said
    assert not (tmp_path / "owned.txt").exists()
    assert not Path("owned.txt").exists()


def test_validating_a_definition_contacts_nothing(tmp_path: Path) -> None:
    """feat-004/AC-9: the point of validating is to spend no requests, so it may spend none."""
    write(tmp_path / "searches", "quiet")
    db = tmp_path / "homescout.db"

    with Store.open(db) as store:
        workspace = api.Workspace(
            store=store,
            catalog=catalog(tmp_path / "searches"),
            queue=None,
            sources={"fake": Hostile()},
        )
        found = api.validate_search(workspace, "quiet")

    assert blocking(found) == ()


def test_a_search_that_excludes_all_of_itself_is_valid_and_says_so(tmp_path: Path) -> None:
    """feat-004/AC-9: valid, matches nothing, and says which of those two it is.

    The edge case the spec names. Reported as a notice rather than a problem, because refusing to
    run it would be answering a different question from the one that was asked.
    """
    box = "[[[-103.4, 34.15], [-103.3, 34.15], [-103.3, 34.25], [-103.4, 34.25], [-103.4, 34.15]]]"
    bigger = "[[[-104, 34], [-103, 34], [-103, 35], [-104, 35], [-104, 34]]]"
    found = problems_of(
        tmp_path,
        "nothing",
        "name: nothing\nareas:\n"
        f"  - {{type: polygon, geometry: {{type: Polygon, coordinates: {box}}}}}\n"
        "exclude_areas:\n"
        f"  - {{type: polygon, geometry: {{type: Polygon, coordinates: {bigger}}}}}\n"
        "sources: [fake]\n",
    )

    assert blocking(found) == ()
    assert len(notices(found)) == 1
    assert "matches nothing" in notices(found)[0].message


def test_a_radius_around_a_name_says_it_is_the_sources_to_apply(tmp_path: Path) -> None:
    """feat-004/AC-9: a notice, because nothing here can measure from a place name yet."""
    found = problems_of(
        tmp_path,
        "circle",
        'name: circle\nareas:\n  - {type: radius, center: "Portales, NM", miles: 25}\n'
        "sources: [fake]\n",
    )

    assert blocking(found) == ()
    assert "applied by each source" in messages(notices(found))


def test_a_radius_around_a_point_needs_no_notice_and_no_provider(tmp_path: Path) -> None:
    """feat-004/AC-2: a centre given as coordinates is exact with nothing registered at all."""
    found = problems_of(
        tmp_path,
        "point",
        "name: point\nareas:\n  - {type: radius, center: [34.18, -103.35], miles: 25}\n"
        "sources: [fake]\n",
    )

    assert found == ()


def test_a_definition_that_fails_validation_is_never_run(tmp_path: Path) -> None:
    """feat-004/AC-9: the whole reason validation exists is that a run costs requests."""
    from homescout.search import InvalidSearch

    write(tmp_path / "searches", "bad", text="name: bad\nareas: []\nsources: [fake]\n")
    db = tmp_path / "homescout.db"

    with Store.open(db) as store:
        workspace = api.Workspace(
            store=store,
            catalog=catalog(tmp_path / "searches"),
            queue=None,
            sources={"fake": Hostile()},
        )
        with pytest.raises(InvalidSearch):
            api.run_search(workspace, "bad")

        assert not store.runs("bad"), "nothing was recorded for a search that never ran"
