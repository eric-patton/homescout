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


def test_a_passed_property_is_marked_hidden_by_the_core_not_by_the_page(opened) -> None:
    """feat-010/AC-35, feat-010/AC-36: the rule lives in one place.

    The page filters rows it already holds, which is what keeps the toggle instant, but it filters
    on an answer the core gave rather than on a predicate of its own. The pre-build check held this
    change until that was true: the command line was about to grow its own copy of "passed means
    hidden", in another language, free to drift.
    """
    browser, held = opened
    rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]
    first = rows[0]["listing_id"]

    browser.post(
        f"/api/listings/{first}/annotation", json={"judgment": "pass"}, headers=ours()
    )

    default = browser.get("/api/results/portales", headers=reading()).json()
    marked = {row["listing_id"]: row for row in default["rows"]}
    assert marked[first]["judgment"] == "pass"
    assert marked[first]["hidden_by_default"] is True
    assert default["passed"] == 1, "the count comes from the core, not from counting rows"
    assert all(
        not row["hidden_by_default"] for row in default["rows"] if row["listing_id"] != first
    )

    asked = browser.get(
        "/api/results/portales", params={"include_passed": True}, headers=reading()
    ).json()
    shown = {row["listing_id"]: row for row in asked["rows"]}
    assert shown[first]["judgment"] == "pass", "still passed"
    assert shown[first]["hidden_by_default"] is False, "no longer hidden, because it was asked for"

    # Every row is still sent either way. That is what lets the checkbox cost nothing.
    assert len(asked["rows"]) == len(default["rows"])


def test_the_control_that_passes_a_house_is_the_one_that_brings_it_back(opened) -> None:
    """feat-010/AC-34: one control, no separate undo, nothing to go looking for."""
    browser, held = opened
    first = browser.get("/api/results/portales", headers=reading()).json()["rows"][0]["listing_id"]

    browser.post(f"/api/listings/{first}/annotation", json={"judgment": "pass"}, headers=ours())
    assert held.store.judgment_of(first) == "pass"

    browser.post(f"/api/listings/{first}/annotation", json={"judgment": None}, headers=ours())
    assert held.store.judgment_of(first) is None

    back = browser.get("/api/results/portales", headers=reading()).json()
    assert back["passed"] == 0
    assert all(not row["hidden_by_default"] for row in back["rows"])


def test_both_surfaces_answer_the_same_question_the_same_way(opened) -> None:
    """feat-010/AC-39, product invariant 5: the capability exists on both, and agrees.

    This is the assertion that catches the predicate drifting back into a surface later: if either
    side starts deciding for itself what passing means, these two sets stop matching.
    """
    browser, held = opened
    first = browser.get("/api/results/portales", headers=reading()).json()["rows"][0]["listing_id"]
    browser.post(f"/api/listings/{first}/annotation", json={"judgment": "pass"}, headers=ours())

    over_http = browser.get("/api/passed", headers=reading()).json()
    through_core, count = api.passed(held)

    assert count == 1
    assert over_http["count"] == count
    assert [row["listing_id"] for row in over_http["passed"]] == [
        row["listing_id"] for row in through_core
    ]

    hidden_http = {
        row["listing_id"]
        for row in browser.get("/api/results/portales", headers=reading()).json()["rows"]
        if row["hidden_by_default"]
    }
    from_core = api.results(held, "portales")["rows"]
    hidden_core = {row["listing_id"] for row in from_core if row["hidden_by_default"]}
    assert hidden_http == hidden_core == {first}


def test_a_record_merged_into_another_still_has_a_page(store: Store, db_path: Path) -> None:
    """feat-010/AC-9, product invariant 2: a merged constituent is not a missing listing.

    Found in use, while reviewing the merge queue: every link to a record that had been merged into
    another returned a 500. The page assembles a listing from its own history, which a merged
    constituent still has, and then asked for its extracted fields through a helper that consults
    only the listings currently representing a property. The two disagreed about what "this listing
    exists" means, and the disagreement took the page down.

    That is the wrong record to lose. Invariant 2 says every canonical listing stays traceable to
    the rows it was built from and that the provenance is visible, which is the whole basis for
    being able to inspect a merge and undo it. A person reviewing merges is exactly who follows
    these links.
    """
    loaded = load(store, [listing("a"), listing("b", price=90_000)])
    merged_id = store.supersede([loaded["a"], loaded["b"]], join_signal="same address")

    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        for constituent in (loaded["a"], loaded["b"]):
            response = browser.get(f"/api/listings/{constituent}", headers=reading())
            assert response.status_code == 200, f"{constituent}: {response.text[:200]}"
            assert response.json()["listing"]["superseded_by"] == merged_id, (
                "and it says what became of it, rather than pretending it is still its own property"
            )

        assert browser.get(f"/api/listings/{merged_id}", headers=reading()).status_code == 200


def test_the_spreadsheet_can_be_downloaded_from_the_page(opened) -> None:
    """feat-010/AC-50: a sheet you have to go and find on disk is a sheet you asked for twice.

    The same core operation the terminal calls, so the file that arrives in a browser and the file
    `homescout export` writes are one file made one way. It is still written into the workspace,
    which is what keeps it findable afterwards without exporting again.
    """
    browser, held = opened

    answered = browser.get("/api/export/portales?format=csv", headers=reading())

    assert answered.status_code == 200, answered.text
    assert answered.headers["content-type"].startswith("text/csv")
    assert "portales.csv" in answered.headers.get("content-disposition", "")
    body = answered.content.decode("utf-8-sig")
    assert "Property" in body.splitlines()[0], "the sheet has no header row"
    assert (held.root / "exports" / "portales.csv").exists(), "the copy in the workspace is gone"


def test_a_sheet_can_only_be_asked_for_in_a_format_that_exists(opened) -> None:
    """feat-010/AC-50: and says so, rather than writing something nobody can open."""
    browser, _held = opened

    answered = browser.get("/api/export/portales?format=pdf", headers=reading())

    assert answered.status_code == 400
    assert "xlsx or csv" in answered.json()["error"]


def test_asking_for_the_templates_is_not_asking_for_a_search_called_templates(opened) -> None:
    """The two paths overlap, and the order they are declared in is what tells them apart."""
    browser, _held = opened

    answered = browser.get("/api/export/templates", headers=reading())

    assert answered.status_code == 200
    assert "templates" in answered.json()


def test_two_requests_that_read_the_database_do_not_run_at_once(store: Store, db_path: Path):
    """feat-010/AC-64: one connection, so one question at a time, and it has to be true.

    The server always said it served one request at a time. It did not. The lock was reentrant and
    was held across an `await` in an async middleware, which runs on the event loop's own thread:
    a second request arriving while the first was suspended took the same lock and both went
    through. Nothing failed for months because nothing asked the database two things at once.

    The fire map does. Switching on the county names and the wind together fires two requests that
    both read the run's properties, their cursors interleave on the one connection, and sqlite
    refuses both with "bad parameter or other API misuse": two five hundreds, and an overlay that
    silently never appears.

    Checked by counting overlap rather than by racing and hoping. A test that fires two requests
    and asserts they both succeeded passes on a fast machine with the bug still in place.
    """
    import threading

    from homescout.web.app import build

    load(store, [listing("a"), listing("b")])
    held = held_workspace(shared_store(db_path))
    app = build(held)

    inside = 0
    together = 0
    counting = threading.Lock()

    original = api.results

    def watched(*args, **kwargs):
        nonlocal inside, together
        with counting:
            inside += 1
            together = max(together, inside)
        try:
            return original(*args, **kwargs)
        finally:
            with counting:
                inside -= 1

    from fastapi.testclient import TestClient

    with pytest.MonkeyPatch.context() as patching:
        patching.setattr(api, "results", watched)
        with TestClient(app) as browser:
            answers: list[int] = []

            def go() -> None:
                answers.append(
                    browser.get("/api/results/portales", headers=reading()).status_code
                )

            threads = [threading.Thread(target=go) for _ in range(4)]
            for one in threads:
                one.start()
            for one in threads:
                one.join()

    assert answers == [200, 200, 200, 200], answers
    assert together == 1, (
        f"{together} requests were reading the database at the same time over one connection, "
        "which is what the one-request-at-a-time lock exists to stop"
    )


def test_a_tile_and_a_rose_do_not_wait_behind_the_database(store: Store, db_path: Path) -> None:
    """feat-010/AC-64: the two answers that never open the store must not queue behind it.

    Both are somebody else's network with a disk cache in front: a wind rose is a ten-second query
    on a public archive. Held behind the one-request-at-a-time lock, forty of those would stop the
    interface answering anything at all, and would turn the wind overlay from three at a time into
    one at a time for no reason, because neither of them touches the database.
    """
    from homescout.web.app import WITHOUT_THE_DATABASE, _needs_the_database

    assert not _needs_the_database("/api/wind/rose/NM_ASOS/SKX")
    assert not _needs_the_database("/api/hazard/wildfire")
    #: Everything else waits its turn. Named as a list rather than as a flag on each route, so that
    #: adding a route is not also a chance to opt out of the store's only protection by accident.
    for path in ("/api/results/portales", "/api/ground/portales", "/api/rain/portales",
                 "/api/wind/stations/portales", "/api/tags", "/api/listings/x"):
        assert _needs_the_database(path), path
    assert len(WITHOUT_THE_DATABASE) == 2, WITHOUT_THE_DATABASE
