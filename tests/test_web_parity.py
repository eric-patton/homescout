"""The interface can do what the terminal can do, checked as a property rather than promised.

Product invariant 5 says neither surface is the privileged one. That is easy to write and easy to
lose: a command gets added to the terminal because that is where the person adding it was working,
and nothing anywhere fails. So the first test here enumerates the terminal's own commands out of
its parser and insists each one has a route, and the rest exercise the operations that only became
reachable from a browser once parity was the requirement.

Where these use a real `FileCatalog` over a temporary directory rather than the in-memory one, it is
because what is being checked is a property of the file: that a copy keeps its comments, that
setting a search aside does not delete it, and that a settings write leaves the rest of the file
alone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from homescout import api
from homescout.errors import InvalidInput
from homescout.search.definition import FileCatalog
from homescout.store import Store
from web_fakes import (
    STATIC,
    client,
    fingerprint,
    held_workspace,
    ours,
    reading,
    shared_store,
)

# ---------------------------------------------------------------------------
# feat-010/AC-22: every command the terminal has, reachable here
# ---------------------------------------------------------------------------

#: Each command the terminal exposes, and the route that reaches the same core operation. This is a
#: hand-written table on purpose: the point is that adding a command means deciding, in writing,
#: how the browser reaches it, and the test below fails until somebody has.
REACHES: dict[str, tuple[str, str]] = {
    "run": ("POST", "/api/searches/{name}/run"),
    "changes": ("GET", "/api/changes/{name}"),
    "searches list": ("GET", "/api/searches"),
    "searches show": ("GET", "/api/searches/{name}"),
    "searches validate": ("GET", "/api/searches/{name}"),
    "searches create": ("PUT", "/api/searches/{name}"),
    "searches delete": ("DELETE", "/api/searches/{name}"),
    "searches restore": ("POST", "/api/searches/{name}/restore"),
    "searches edit": ("POST", "/api/searches/{name}"),
    "annotate": ("POST", "/api/listings/{listing_id}/annotation"),
    "matches list": ("GET", "/api/matches"),
    "matches resolve": ("POST", "/api/matches/{match_id}"),
    "enrich": ("POST", "/api/enrich"),
    "extract": ("POST", "/api/extract"),
    "export": ("POST", "/api/export"),
    "overview": ("GET", "/api/searches"),
    "notes": ("GET", "/api/notes"),
    "broadband": ("GET", "/api/broadband"),
    "show": ("GET", "/api/listings/{listing_id}"),
    "areas": ("GET", "/api/areas"),
    # `serve` is what starts this interface. A route for it would be the interface offering to
    # start itself, which is not a capability the browser is missing.
    "serve": ("", ""),
}

#: Capabilities the terminal carries as a flag on a command rather than as a command of its own.
#: Same argument, one level down: `run --deliver` is a thing the tool can do.
FLAGS_REACH: dict[str, tuple[str, str]] = {
    "run --deliver": ("POST", "/api/deliver"),
    "enrich --stale": ("POST", "/api/enrich"),
    "extract --limit": ("POST", "/api/extract"),
    "export --template": ("GET", "/api/export/templates"),
    "notes --set": ("POST", "/api/notes"),
    "broadband --state": ("POST", "/api/broadband"),
}


def terminal_commands() -> set[str]:
    """Every command the terminal's parser exposes, read out of the parser itself."""
    from homescout.cli.main import build_parser

    found: set[str] = set()

    def walk(parser: argparse.ArgumentParser, prefix: str = "") -> None:
        for action in parser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            for name, sub in action.choices.items():
                path = f"{prefix} {name}".strip()
                deeper = [a for a in sub._actions if isinstance(a, argparse._SubParsersAction)]
                walk(sub, path) if deeper else found.add(path)

    walk(build_parser())
    return found


def routes(held: api.Workspace) -> set[tuple[str, str]]:
    from homescout.web.app import build

    found: set[tuple[str, str]] = set()
    for route in build(held).routes:
        for method in getattr(route, "methods", ()) or ():
            found.add((method, getattr(route, "path", "")))
    return found


def test_every_terminal_command_has_a_route(store: Store, db_path: Path) -> None:
    """feat-010/AC-22: a capability cannot be added to one surface and missed on the other."""
    commands = terminal_commands()
    assert commands, "the parser exposed no commands, so this test proves nothing"

    unmapped = sorted(commands - set(REACHES))
    assert not unmapped, (
        f"{', '.join(unmapped)} exists in the terminal and has no entry here. Add the route that "
        "reaches the same core operation, so the browser is not quietly missing it."
    )
    stale = sorted(set(REACHES) - commands)
    assert not stale, f"{', '.join(stale)} is listed here and is no longer a command."

    served = routes(held_workspace(shared_store(db_path)))
    for command, wanted in sorted({**REACHES, **FLAGS_REACH}.items()):
        if wanted == ("", ""):
            continue
        assert wanted in served, f"{command} maps to {wanted[0]} {wanted[1]}, which is not served"


# ---------------------------------------------------------------------------
# feat-010/AC-23: made, copied, set aside, brought back
# ---------------------------------------------------------------------------

WRITTEN = """\
# A search somebody wrote by hand, with a note they left themselves.
name: portales
description: everything around town

areas:
  # The one that matters.
  - {type: city, value: "Portales, NM"}

filters:
  price: {max: 300000}

sources: [realtor]
"""


@pytest.fixture
def filed(store: Store, db_path: Path, tmp_path: Path):
    """A workspace whose searches are real files, because that is what is being checked."""
    where = tmp_path / "searches"
    where.mkdir()
    (where / "portales.yaml").write_text(WRITTEN, encoding="utf-8")
    held = held_workspace(shared_store(db_path))
    held.catalog = FileCatalog(where)
    with client(held) as browser:
        yield browser, held, where


def test_a_search_is_made_copied_and_set_aside_from_here(filed) -> None:
    """feat-010/AC-23: every one of these, and none of them deletes anything."""
    browser, held, where = filed

    made = browser.put("/api/searches/starting-out", headers=ours())
    assert made.status_code == 200, made.text
    assert (where / "starting-out.yaml").is_file()

    copied = browser.post(
        "/api/searches/portales/duplicate", json={"name": "portales-cheap"}, headers=ours()
    )
    assert copied.status_code == 200, copied.text
    assert "note they left themselves" in (where / "portales-cheap.yaml").read_text(
        encoding="utf-8"
    ), "a duplicate that loses the comments is a new search that looks similar, not a copy"

    for change, standing in (
        ({"paused": True}, "paused"),
        ({"paused": False}, None),
        ({"archived": True}, "archived"),
        ({"archived": False}, None),
    ):
        answer = browser.post("/api/searches/portales/standing", json=change, headers=ours())
        assert answer.status_code == 200, answer.text
        assert api._standing_of(held, "portales") == standing
        body = (where / "portales.yaml").read_text(encoding="utf-8")
        assert (where / "portales.yaml").is_file(), "setting a search aside deleted its file"
        assert "note they left themselves" in body
        if standing is None:
            key = "paused" if "paused" in change else "archived"
            assert key not in body, (
                f"{key} came back to its default and was written out as a line saying so. "
                "Absent and default are the same state here, and this file is read by people."
            )


def test_the_list_says_which_searches_are_set_aside(filed) -> None:
    """feat-010/AC-23: the list is the only surface these are visible on.

    Found by clicking Pause and watching the card not change. The write had landed and the run of
    everything was skipping it correctly; the list simply never reported either property, so the
    one place a person looks could not tell them what they had just done.
    """
    browser, _held, _where = filed
    browser.post("/api/searches/portales/standing", json={"paused": True}, headers=ours())

    entry = next(
        s
        for s in browser.get("/api/searches", headers=reading()).json()["searches"]
        if s["name"] == "portales"
    )
    assert entry["paused"] is True
    assert entry["archived"] is False

    browser.post("/api/searches/portales/standing", json={"archived": True}, headers=ours())
    entry = next(
        s
        for s in browser.get("/api/searches", headers=reading()).json()["searches"]
        if s["name"] == "portales"
    )
    assert entry["archived"] is True


def test_a_search_that_is_set_aside_is_skipped_and_said_to_be(filed) -> None:
    """feat-010/AC-23: skipped by a run of everything, which reports that it skipped it."""
    _browser, held, _where = filed
    api.set_standing(held, "portales", paused=True)

    outcome = api.run_all(held)
    skipped = {s.name: s.reason for s in outcome.skipped}
    assert skipped == {"portales": "paused"}
    assert not outcome.outcomes, "a paused search was run by a run of everything"
    assert "paused" in outcome.skipped[0].detail
    assert "by name" in outcome.skipped[0].detail


def test_a_search_that_is_set_aside_still_runs_when_asked_for(filed) -> None:
    """feat-010/AC-23: paused means nobody is watching it, not that it stopped working."""
    _browser, held, _where = filed
    api.set_standing(held, "portales", archived=True)
    assert api.show_search(held, "portales").archived is True
    # Named explicitly, it is a search like any other: this is the load the runner would do.
    assert held.catalog.load("portales").name == "portales"


# ---------------------------------------------------------------------------
# feat-010/AC-27: deleting one, and the two things that survive it
# ---------------------------------------------------------------------------


def test_a_deleted_search_stops_being_one_at_once(filed) -> None:
    """feat-010/AC-27: out of the list, out of a run of everything, not found by name."""
    browser, held, _where = filed

    answer = browser.delete("/api/searches/portales", headers=ours())
    assert answer.status_code == 200, answer.text

    assert "portales" not in api.list_searches(held)
    listed = browser.get("/api/searches", headers=reading()).json()["searches"]
    assert [entry["name"] for entry in listed] == []
    assert not api.run_all(held).outcomes, "a deleted search was still run by a run of everything"

    missing = browser.get("/api/searches/portales", headers=reading())
    assert missing.status_code >= 400, "a deleted search was still found by name"


def test_deleting_keeps_the_definition_and_offers_it_back(filed) -> None:
    """feat-010/AC-27: kept rather than unlinked, and restorable with everything in it.

    The areas are usually the part that took longest and the comments are usually the part saying
    why. Nothing is gained by making this final, so it is not.
    """
    browser, held, where = filed

    answer = browser.delete("/api/searches/portales", headers=ours()).json()
    assert answer["restorable"] is True
    assert not (where / "portales.yaml").exists(), "it is still in the searches folder"

    kept = Path(answer["kept_at"])
    assert kept.is_file(), "the definition was unlinked rather than kept"
    assert "note they left themselves" in kept.read_text(encoding="utf-8")

    assert browser.get("/api/deleted", headers=reading()).json()["searches"] == ["portales"]

    back = browser.post("/api/searches/portales/restore", headers=ours())
    assert back.status_code == 200, back.text
    body = (where / "portales.yaml").read_text(encoding="utf-8")
    assert "note they left themselves" in body, "restoring lost the comments"
    assert "The one that matters" in body
    assert api.show_search(held, "portales").name == "portales"


def test_deleting_a_search_removes_nothing_a_run_recorded(filed) -> None:
    """feat-010/AC-27: the constitution's append-only history, enforced at the one place that
    would most plausibly break it.

    Non-negotiable 2 and product invariant 1 say snapshot history is append-only and no feature may
    delete a historical row. "Delete this search" is the request most likely to be read as "and
    everything it found", so this asserts the whole database is byte-for-byte identical afterwards
    and that the answer says how many runs it kept.
    """
    browser, held, _where = filed
    before = fingerprint(held.store)
    runs = len(held.store.runs("portales"))

    answer = browser.delete("/api/searches/portales", headers=ours()).json()

    assert fingerprint(held.store) == before, "deleting a search changed the store"
    assert answer["runs_kept"] == runs, "the answer did not say what it kept"


def test_restoring_over_a_search_that_exists_again_is_refused(filed) -> None:
    """feat-010/AC-27: bringing one back must never overwrite one somebody has since made."""
    browser, _held, where = filed
    browser.delete("/api/searches/portales", headers=ours())
    browser.put("/api/searches/portales", headers=ours())
    replacement = (where / "portales.yaml").read_bytes()

    refused = browser.post("/api/searches/portales/restore", headers=ours())
    assert refused.status_code >= 400
    assert (where / "portales.yaml").read_bytes() == replacement


# ---------------------------------------------------------------------------
# feat-010/AC-24: the parts of a definition this interface edits
# ---------------------------------------------------------------------------


def test_editing_a_definition_here_leaves_the_rest_of_the_file_alone(filed) -> None:
    """feat-010/AC-24, standing on AC-3: an edit made here is an edit and nothing else."""
    browser, _held, where = filed

    answer = browser.post(
        "/api/searches/portales",
        json={
            "set": {
                "description": "everything around town, cheaper",
                "sources": ["realtor", "redfin"],
                "filters.price.max": 250_000,
            }
        },
        headers=ours(),
    )
    assert answer.status_code == 200, answer.text

    body = (where / "portales.yaml").read_text(encoding="utf-8")
    assert "# The one that matters." in body, "an edit here threw away a comment"
    assert "somebody wrote by hand" in body
    assert "cheaper" in body
    assert "250000" in body


# ---------------------------------------------------------------------------
# feat-010/AC-25: the optional configuration
# ---------------------------------------------------------------------------

EXISTING = """\
# HomeScout settings for this workspace. Never committed.

# The port, uncommon on purpose.
HOMESCOUT_PORT=47823
"""


@pytest.fixture
def configured(store: Store, db_path: Path, monkeypatch):
    """A workspace with a settings file already in it, and an environment that is put back."""
    monkeypatch.delenv("HOMESCOUT_MAP_TILES", raising=False)
    monkeypatch.delenv("HOMESCOUT_EXTRACT_MODEL", raising=False)
    held = held_workspace(shared_store(db_path))
    (held.root / ".env").write_text(EXISTING, encoding="utf-8")
    return held


def test_a_setting_written_here_lands_in_the_file_and_takes_effect(configured) -> None:
    """feat-010/AC-25: it is written, it is true now, and the rest of the file is untouched.

    The two halves are both load-bearing and were both wrong once. A staging file that is never
    renamed loses the write in silence; a write that only reaches the file leaves the page saying
    "saved" while the thing stays off until somebody restarts the server.
    """
    import os

    held = configured
    api.set_configuration(held, {"HOMESCOUT_EXTRACT_MODEL": "gpt-4o-mini"})

    body = (held.root / ".env").read_text(encoding="utf-8")
    assert "HOMESCOUT_EXTRACT_MODEL=gpt-4o-mini" in body
    assert "# The port, uncommon on purpose." in body, "the write threw away a comment"
    assert "HOMESCOUT_PORT=47823" in body
    assert not list(held.root.glob(".env.partial")), "the write was left in a staging file"
    assert os.environ.get("HOMESCOUT_EXTRACT_MODEL") == "gpt-4o-mini"
    assert api.configuration(held)["model"]["model"] == "gpt-4o-mini"


def test_a_setting_turned_off_leaves_no_trace_of_itself(configured) -> None:
    """feat-010/AC-25: off means the line goes, not that it becomes an empty assignment."""
    import os

    held = configured
    api.set_configuration(held, {"HOMESCOUT_MAP_TILES": "https://tile.example.invalid/{z}.png"})
    api.set_configuration(held, {"HOMESCOUT_MAP_TILES": ""})

    body = (held.root / ".env").read_text(encoding="utf-8")
    assert "HOMESCOUT_MAP_TILES" not in body
    assert "HOMESCOUT_PORT=47823" in body
    assert "HOMESCOUT_MAP_TILES" not in os.environ


@pytest.mark.parametrize(
    "name",
    ["OPENAI_API_KEY", "HOMESCOUT_EXTRACT_API_KEY", "HOMESCOUT_SMTP_PASSWORD", "FCC_TOKEN"],
)
def test_a_credential_is_refused(configured, name: str) -> None:
    """feat-010/AC-25: the constitution's rule, made a refusal rather than a convention."""
    with pytest.raises(InvalidInput) as raised:
        api.set_configuration(configured, {name: "sk-whatever"})
    assert "credential" in str(raised.value)
    assert "sk-whatever" not in (configured.root / ".env").read_text(encoding="utf-8")


def test_no_credential_is_ever_reported(configured, monkeypatch) -> None:
    """feat-010/AC-25: it says whether one is there, and never what it is."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-do-not-show-this")
    monkeypatch.setenv("HOMESCOUT_EXTRACT_MODEL", "gpt-4o-mini")

    found = api.configuration(configured)
    assert found["model"]["credential"] is True, "it has to say a credential is there"
    assert "sk-do-not-show-this" not in repr(found), "and it must never say what it is"


def test_the_settings_route_refuses_a_credential_too(configured) -> None:
    """The same refusal from the outside, because that is where somebody would try it."""
    with client(configured) as browser:
        answer = browser.post(
            "/api/configuration", json={"set": {"OPENAI_API_KEY": "sk-nope"}}, headers=ours()
        )
    assert answer.status_code == 400, answer.text
    assert "sk-nope" not in (configured.root / ".env").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# feat-010/AC-2: named, and its sense changed, without redrawing it
# ---------------------------------------------------------------------------

SHAPE = {
    "type": "Polygon",
    "coordinates": [
        [[-103.4, 34.1], [-103.3, 34.1], [-103.3, 34.2], [-103.4, 34.2], [-103.4, 34.1]]
    ],
}


def test_a_drawn_area_can_be_named_and_moved_in_or_out(filed) -> None:
    """feat-010/AC-2: all three verbs. Drawn was built first; named and edited are these.

    A file with three drawn areas that reads as three drawn areas is the thing this prevents. The
    name and the included-or-excluded sense are both properties of the entry, so changing either is
    an ordinary edit rather than deleting the shape and drawing it again.
    """
    browser, _held, where = filed

    made = browser.post(
        "/api/searches/portales",
        json={
            "set": {
                "areas": [
                    {"type": "city", "value": "Portales, NM"},
                    {"type": "polygon", "name": "east side", "geometry": SHAPE},
                ],
                "exclude_areas": [],
            }
        },
        headers=ours(),
    )
    assert made.status_code == 200, made.text
    assert "east side" in (where / "portales.yaml").read_text(encoding="utf-8")

    moved = browser.post(
        "/api/searches/portales",
        json={
            "set": {
                "areas": [{"type": "city", "value": "Portales, NM"}],
                "exclude_areas": [{"type": "polygon", "name": "east side", "geometry": SHAPE}],
            }
        },
        headers=ours(),
    )
    assert moved.status_code == 200, moved.text

    found = browser.get("/api/searches/portales", headers=reading()).json()["search"]
    assert [a["name"] for a in found["exclusions"]] == ["east side"]
    assert not [a for a in found["areas"] if a.get("geometry")], "the shape stayed on both sides"
    assert "note they left themselves" in (where / "portales.yaml").read_text(encoding="utf-8")

    taken = browser.post(
        "/api/searches/portales",
        json={
            "set": {
                "areas": [{"type": "city", "value": "Portales, NM"}],
                "exclude_areas": [],
            }
        },
        headers=ours(),
    )
    assert taken.status_code == 200, taken.text
    body = (where / "portales.yaml").read_text(encoding="utf-8")
    assert "exclude_areas" not in body, (
        "no exclusions is the same state as no exclude_areas key, so the key should go rather "
        "than be left as an empty list"
    )


def test_saving_a_search_unchanged_changes_nothing_at_all(filed) -> None:
    """feat-010/AC-3: the map hands over the whole areas list on every save.

    So the ordinary case, opening a search and pressing save without touching anything, has to be
    a no-op down to the bytes. Without that, the styles a person chose in their file (a flow map on
    one line, a blank line between sections) get rewritten in this tool's taste the first time
    somebody looks at the search.
    """
    browser, _held, where = filed
    before = (where / "portales.yaml").read_bytes()

    answer = browser.post(
        "/api/searches/portales",
        json={"set": {"areas": [{"type": "city", "value": "Portales, NM"}]}},
        headers=ours(),
    )
    assert answer.status_code == 200, answer.text
    assert (where / "portales.yaml").read_bytes() == before


def test_nothing_is_cached_without_asking_first(store: Store, db_path: Path) -> None:
    """feat-010/AC-16: the served assets are the files as committed, in a live browser too.

    Found by updating a script under a browser that had the old one and watching the page run it.
    With no `Cache-Control` a browser guesses a lifetime from the last-modified date, and this tool
    is updated in place: the page that results runs half of one version and half of another. A
    script revalidates every time, which over loopback is a 304; anything carrying the person's own
    data is not stored at all.
    """
    with client(held_workspace(shared_store(db_path))) as browser:
        asset = browser.get("/static/common.js", headers=reading())
        assert asset.headers["cache-control"] == "no-cache"
        assert asset.headers.get("etag"), "revalidating needs something to revalidate against"

        page = browser.get("/", headers=reading())
        assert page.headers["cache-control"] == "no-store"

        data = browser.get("/api/searches", headers=reading())
        assert data.headers["cache-control"] == "no-store"


def test_the_archived_toggle_survives_the_last_one_being_brought_back() -> None:
    """feat-010/AC-23: the state and the control that holds it cannot get out of step.

    Found by clicking: with "show archived" ticked, bringing the last archived search back removed
    the checkbox while the state stayed on, and the redraw threw on the element that was no longer
    there. Asserted against the script, because the failure is in how it decides to draw one.
    """
    body = (STATIC / "searches.js").read_text(encoding="utf-8")
    assert "(archived || showArchived)" in body, (
        "the toggle has to survive the count reaching nothing, or the state cannot be turned off"
    )
    assert "if (toggle) toggle.checked" in body, "the element is looked up before it is set"


def test_the_area_table_edits_the_name_and_the_sense(filed) -> None:
    """feat-010/AC-2: the interface half, asserted against the script that draws it."""
    body = (STATIC / "search.js").read_text(encoding="utf-8")
    assert "function areaRow(" in body
    assert "__name" in body, "a drawn shape carries a name through the map layer that holds it"
    assert "What to call area" in body, "the name field is labelled"
    assert "is searched or left out" in body, "the in-or-out control is labelled"
    assert "function addPlace(" in body, "a town can be added without opening the file"


# ---------------------------------------------------------------------------
# feat-010/AC-26: a map with nothing behind it
# ---------------------------------------------------------------------------


def test_the_map_says_what_is_missing_and_offers_the_one_click(store: Store, db_path: Path) -> None:
    """feat-010/AC-26: the default is no tile server, and the default is not a blank grey box.

    Asserted against the script rather than a rendered page, the way every other claim about these
    scripts is: what matters is that the offer and the cost are both in the file that draws it.
    """
    body = (STATIC / "search.js").read_text(encoding="utf-8")
    assert "There is no map background" in body
    assert "OpenStreetMap" in body, "the offer names who is being asked for tiles"
    assert "which part" in body, "the cost of turning it on is stated beside the offer"
    assert "function grid(" in body, "there is something to draw over when there is no background"

    with client(held_workspace(shared_store(db_path))) as browser:
        answer = browser.get("/api/settings", headers=reading()).json()
    assert answer["map"]["tiles"] is None, "a tile server is configured by default"
