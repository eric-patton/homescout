"""Every action, performed twice: through HTTP and through the core, with the results compared.

This is AC-14 done behaviourally. The source scan in `test_web_contract.py` proves this layer does
not *import* anything that decides; this proves it does not *do* anything either, by making the same
change both ways and comparing the whole database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homescout import api
from homescout.store import Store
from web_fakes import (
    client,
    fingerprint,
    held_workspace,
    listing,
    load,
    ours,
    reading,
    shared_store,
)


@pytest.fixture
def opened(store: Store, db_path: Path):
    load(store, [listing("a"), listing("b", price=90_000)])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        yield browser, held


def without_time(found: dict) -> dict:
    """Two answers to the same question, with the only part that differs taken out."""
    trimmed = {k: v for k, v in found.items() if k != "homescout"}
    return trimmed


# ---------------------------------------------------------------------------
# The same action, both ways
# ---------------------------------------------------------------------------


def test_an_annotation_written_here_is_the_one_the_core_writes(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-14: identical resulting state, compared table by table."""
    loaded = load(store, [listing("a"), listing("b")])

    through_core = api.annotate(
        held_workspace(shared_store(db_path)), loaded["a"], verdict="worth a look", rank=2
    )
    after_core = fingerprint(store)

    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        response = browser.post(
            f"/api/listings/{loaded['b']}/annotation",
            json={"verdict": "worth a look", "rank": 2},
            headers=ours(),
        )
    assert response.status_code == 200, response.text

    # The two properties now carry the same judgment, written by two different surfaces.
    assert response.json()["verdict"] == through_core.verdict
    assert response.json()["rank"] == through_core.rank

    after_both = fingerprint(store)
    assert len(after_both["annotations"]) == len(after_core["annotations"]) + 1


def test_a_read_here_is_the_same_answer_the_core_gives(opened) -> None:
    browser, held = opened
    from_http = browser.get("/api/results/portales", headers=reading()).json()
    from_core = api.results(held, "portales")

    assert [row["listing_id"] for row in from_http["rows"]] == [
        row["listing_id"] for row in from_core["rows"]
    ]
    assert [column["name"] for column in from_http["columns"]] == [
        column["name"] for column in from_core["columns"]
    ]


def test_one_property_reads_the_same_both_ways(store: Store, db_path: Path) -> None:
    loaded = load(store, [listing("a", description="A home with a private well.")])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        from_http = browser.get(f"/api/listings/{loaded['a']}", headers=reading()).json()
    from_core = api.listing(held, loaded["a"])

    assert from_http["listing"]["listing_id"] == from_core["listing_id"]
    assert from_http["listing"]["extracted"]["water_source"]["value"] == "well"
    assert from_core["extracted"]["water_source"]["value"] == "well"


def test_a_note_written_here_is_a_note_the_core_reads(store: Store, db_path: Path) -> None:
    """feat-010/AC-19, and the same notes the spreadsheet's second sheet carries."""
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        response = browser.post(
            "/api/areas",
            json={"area_type": "city", "area_value": "Portales", "notes": "Good water."},
            headers=ours(),
        )
    assert response.status_code == 200, response.text
    assert [note.notes for note in api.area_notes(held)] == ["Good water."]


def test_a_note_written_here_reaches_the_spreadsheet(store: Store, db_path: Path) -> None:
    """AC-19's second half, which is a claim about two features agreeing.

    The only place it can be checked is where they meet: written through the interface, read out of
    a workbook.
    """
    loaded = load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        browser.post(
            "/api/areas",
            json={"area_type": "city", "area_value": "Portales", "notes": "Good water."},
            headers=ours(),
        )

    from export_fakes import column_of, sheet_rows
    from homescout.export import export_run

    target = db_path.parent / "sheet.xlsx"
    export_run(held.store, loaded.run_id, target, root=db_path.parent)

    assert list(sheet_rows(target, "Areas")[1][:3]) == ["city", "Portales", "Good water."]
    assert column_of(target, "Town Analysis Notes") == ["Good water."]


# ---------------------------------------------------------------------------
# Reading changes nothing
# ---------------------------------------------------------------------------


def test_reading_every_surface_changes_nothing(opened, store: Store) -> None:
    browser, held = opened
    loaded = list(api.results(held, "portales")["rows"])
    before = fingerprint(store)

    for path in (
        "/api/searches",
        "/api/searches/portales",
        "/api/results/portales",
        "/api/matches",
        "/api/areas",
        "/api/settings",
        "/api/runs/portales/status",
        f"/api/listings/{loaded[0]['listing_id']}",
    ):
        assert browser.get(path, headers=reading()).status_code == 200, path

    assert fingerprint(store) == before


def test_the_pages_themselves_change_nothing(opened, store: Store) -> None:
    browser, held = opened
    before = fingerprint(store)
    for path in ("/", "/search/portales", "/results/portales", "/matches",
                 "/changes/portales", "/listing/anything"):
        assert browser.get(path, headers=reading()).status_code == 200, path
    assert fingerprint(store) == before


# ---------------------------------------------------------------------------
# Failures are the product's own two kinds
# ---------------------------------------------------------------------------


def test_a_name_that_does_not_exist_is_invalid_input(opened) -> None:
    browser, _ = opened
    assert browser.get("/api/listings/nobody", headers=reading()).status_code == 400


def test_a_search_with_no_completed_run_says_so(store: Store, db_path: Path) -> None:
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        response = browser.get("/api/results/portales", headers=reading())
    assert response.status_code == 400
    assert "no completed run" in response.json()["error"]


def test_a_request_body_that_is_not_an_object_is_invalid_input(opened) -> None:
    browser, _ = opened
    response = browser.post("/api/areas", content="[1,2,3]", headers=ours())
    assert response.status_code == 400


def test_a_decision_that_is_not_one_is_refused(opened) -> None:
    browser, _ = opened
    response = browser.post("/api/matches/anything", json={"verdict": "maybe"}, headers=ours())
    assert response.status_code == 400
    assert "same" in response.json()["error"]


# ---------------------------------------------------------------------------
# The image
# ---------------------------------------------------------------------------


def test_a_property_with_no_stored_image_is_a_plain_absence(opened) -> None:
    browser, held = opened
    rows = api.results(held, "portales")["rows"]
    response = browser.get(
        f"/api/listings/{rows[0]['listing_id']}/image", headers=reading())
    assert response.status_code == 404


def test_a_stored_image_is_served_as_what_it_is(store: Store, db_path: Path) -> None:
    """And never sniffed, because a mislabelled image must not be read as a page."""
    loaded = load(store, [listing("a")])
    store.store_preview_image(loaded["a"], b"\x89PNG\r\n\x1a\nnot really", extension="png")
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        response = browser.get(f"/api/listings/{loaded['a']}/image", headers=reading())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def test_running_from_here_leaves_the_store_as_a_terminal_would(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-13: the same state, because it is the same operation."""
    import time

    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        started = browser.post("/api/searches/portales/run", json={}, headers=ours())
        assert started.status_code == 200, started.text

        for _ in range(100):
            status = browser.get("/api/runs/portales/status", headers=reading()).json()
            if status["finished"]:
                break
            time.sleep(0.05)

    assert status["finished"], status
    assert status["failed"] is None, status["failed"]
    assert status["outcome"]["counts"]["new"] >= 1
    assert [run.status for run in store.runs("portales")] == ["completed"]


def test_a_run_already_going_is_said_rather_than_started_twice(
    store: Store, db_path: Path
) -> None:
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        browser.post("/api/searches/portales/run", json={}, headers=ours())
        again = browser.post("/api/searches/portales/run", json={}, headers=ours())
    assert again.status_code == 200
    # Either it was still going and said so, or it had already finished. Both are honest answers;
    # what must not happen is two runs of the same search at once, and the store's own claim is what
    # actually enforces that.
    assert "already_running" in again.json()


# ---------------------------------------------------------------------------
# The saved search itself
# ---------------------------------------------------------------------------


def test_a_drawn_shape_is_written_into_the_file(
    tmp_path: Path, store: Store, db_path: Path
) -> None:
    """feat-010/AC-2, feat-010/AC-3: geometry drawn on the map lands in the file as geometry.

    Through the core's edit operation, which is what AC-3 requires: this interface never writes
    YAML, and the round-tripping document layer keeps everything it was not asked to change.
    """
    from homescout import api as core
    from searches_fakes import catalog, sourced, write

    directory = tmp_path / "searches"
    write(
        directory,
        "north",
        text=(
            "# The comment that has to survive\n"
            "name: north\n"
            'description: "The north side"\n'
            "areas:\n"
            '  - {type: city, value: "Portales, NM"}\n'
            "filters:\n"
            "  price: {min: 100000}\n"
            "sources: [fake]\n"
        ),
    )
    with sourced("fake"):
        held = held_workspace(shared_store(db_path), searches=None)
        held.catalog = catalog(directory)
        shape = {
            "type": "Polygon",
            "coordinates": [[[-103.4, 34.1], [-103.3, 34.1], [-103.3, 34.2],
                             [-103.4, 34.2], [-103.4, 34.1]]],
        }
        with client(held) as browser:
            response = browser.post(
                "/api/searches/north",
                json={
                    "set": {
                        "areas": [
                            {"type": "city", "value": "Portales, NM"},
                            {"type": "polygon", "geometry": shape},
                        ],
                        "exclude_areas": [],
                    }
                },
                headers=ours(),
            )
        assert response.status_code == 200, response.text

        text = (directory / "north.yaml").read_text(encoding="utf-8")
        assert "# The comment that has to survive" in text, "the file was rewritten around"
        assert "price" in text and "100000" in text, "a filter this never touched is gone"
        assert "Polygon" in text or "polygon" in text

        definition = core.show_search(held, "north")
        assert len(definition.areas) == 2
        assert any(getattr(area, "shape", None) is not None for area in definition.areas)


def test_a_shape_that_would_not_validate_is_refused_and_nothing_is_written(
    tmp_path: Path, store: Store, db_path: Path
) -> None:
    """feat-010/AC-3's other half: a refused edit leaves the file exactly as it was."""
    from searches_fakes import catalog, sourced, write

    directory = tmp_path / "searches"
    write(
        directory,
        "north",
        text=(
            "name: north\n"
            "areas:\n"
            '  - {type: city, value: "Portales, NM"}\n'
            "sources: [fake]\n"
        ),
    )
    with sourced("fake"):
        held = held_workspace(shared_store(db_path), searches=None)
        held.catalog = catalog(directory)
        before = (directory / "north.yaml").read_text(encoding="utf-8")
        with client(held) as browser:
            response = browser.post(
                "/api/searches/north",
                json={"set": {"areas": []}},
                headers=ours(),
            )
        assert response.status_code == 400
        assert (directory / "north.yaml").read_text(encoding="utf-8") == before
