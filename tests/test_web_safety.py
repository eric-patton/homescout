"""Text somebody else wrote, on a page.

Every value on every surface came from a listing site or from something a person typed into a note,
and a page is a place where text can be an instruction. The whole defence is that there is exactly
one way to put something on a page and it uses `textContent`; these tests check that the hostile
values reach the browser as data and check what the browser does with them.

The part that can be tested here without a browser is that the server hands the values over
unaltered rather than pre-escaped: pre-escaping would be the wrong fix, because it produces `&lt;`
in an export and a digest as well, and the digest already learned that lesson.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from homescout import api
from homescout.store import Store
from web_fakes import STATIC, client, held_workspace, listing, load, ours, reading, shared_store

#: The things a page could be made to do, if any of this became markup.
HOSTILE = (
    '<script>window.__owned = true</script>',
    '<img src=x onerror="window.__owned = true">',
    "<svg onload=alert(1)>",
    '"><script>alert(1)</script>',
    "javascript:alert(1)",
    "<iframe src=https://evil.invalid></iframe>",
)


@pytest.fixture
def opened(store: Store, db_path: Path):
    load(
        store,
        [
            listing(
                "a",
                description="\n".join(HOSTILE),
                address_line=HOSTILE[0],
                city="<b>Portales</b>",
            )
        ],
    )
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        yield browser, held


def test_the_server_hands_over_the_text_unaltered(opened) -> None:
    """Not pre-escaped, which would be the wrong fix.

    A value escaped here would arrive escaped in the export and the digest too, and the person would
    read `&lt;b&gt;` in a spreadsheet. The escaping belongs where the markup is, and there is no
    markup, so there is no escaping.
    """
    browser, held = opened
    rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]
    assert rows[0]["values"]["Town/Area"] == "<b>Portales</b>"

    listing_id = rows[0]["listing_id"]
    found = browser.get(f"/api/listings/{listing_id}", headers=reading()).json()["listing"]
    for hostile in HOSTILE:
        assert hostile in found["fields"]["description"]


def test_a_hostile_note_survives_being_written_and_read(opened) -> None:
    browser, held = opened
    rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]
    listing_id = rows[0]["listing_id"]

    response = browser.post(
        f"/api/listings/{listing_id}/annotation",
        json={"notes": HOSTILE[1], "verdict": HOSTILE[0]},
        headers=ours(),
    )
    assert response.status_code == 200
    assert response.json()["notes"] == HOSTILE[1]

    held_note = api.listing(held, listing_id)["annotation"]
    assert held_note["verdict"] == HOSTILE[0]


def test_no_page_or_script_interpolates_anything_into_markup() -> None:
    """The mechanism, checked in the source: there is no template that produces markup."""
    for script in sorted(STATIC.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        # A template literal containing a tag is how this rule breaks in every codebase.
        assert "`<" not in text, f"{script.name} builds markup from a template literal"
        assert "'<" not in text.replace("'<'", ""), f"{script.name} may build markup from a string"


def test_the_only_way_to_put_text_on_a_page_uses_text_content() -> None:
    common = (STATIC / "common.js").read_text(encoding="utf-8")
    assert "createTextNode" in common
    assert "createElement" in common


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///C:/Windows/System32/calc.exe",
        "vbscript:msgbox(1)",
    ],
)
def test_a_listing_url_that_is_not_a_web_address_is_carried_but_not_made_clickable(
    href: str, store: Store, db_path: Path
) -> None:
    """The server carries what the source said; the page decides what may become a link.

    Both halves matter. Dropping the value here would lose evidence about what a source returned,
    which this product keeps on principle. Making it a link would put it one click away.
    """
    load(store, [listing("a", listing_url=href)])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]
    assert rows[0]["listing_url"] == href

    common = (STATIC / "common.js").read_text(encoding="utf-8")
    assert 'parsed.protocol === "http:"' in common
    assert 'parsed.protocol === "https:"' in common


def test_every_anchor_goes_through_the_checked_helper() -> None:
    """Because one hand-built anchor is how the check gets bypassed.

    `common.js` has the only two: `link()`, which checks its target, and `skipLink()`, which is a
    fragment within the page and is not a navigation at all. Every other file builds none.
    """
    for script in sorted(STATIC.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        anchors = text.count('el("a"')
        if script.name == "common.js":
            assert anchors == 2, "link() and skipLink(), and nothing else"
        else:
            assert anchors == 0, f"{script.name} builds an anchor itself instead of link()"


def test_no_property_is_scored_or_ranked_by_a_data_centre() -> None:
    """feat-010/AC-56, feat-010/AC-88: the layer says where they are and decides nothing.

    Asserted rather than assumed, because this is the first thing drawn on that page that a person
    arrives with an opinion about, and "quietly demote anything within five miles" is a small,
    reasonable-sounding edit that would turn a map into a judgment nobody could argue with. The
    place to make that decision is a rule the person wrote, which is what the enriched values are
    for; it is not this page.

    Read off the two functions that decide which properties are drawn and how each one looks. If
    either ever consults the data centre layer, this fails.
    """
    text = (STATIC / "fire.js").read_text(encoding="utf-8")

    for name in ("function worthDrawing(", "function plot(", "function popup("):
        at = text.index(name)
        body = text[at : text.index(chr(10) + "}", at)]
        assert "centers" not in body, (
            f"{name} consults the data centre layer to decide something about a property"
        )

    # And the pins themselves know only about the judgment a person made.
    pins = text[text.index("const PINS = {") : text.index("};", text.index("const PINS = {"))]
    assert set(re.findall(r"^\s*(\w+):", pins, re.M)) == {"keep", "pass", "none"}, pins


# ---------------------------------------------------------------------------
# What the store is left holding
# ---------------------------------------------------------------------------


def test_nothing_hostile_changes_what_the_store_holds(opened, store: Store) -> None:
    from web_fakes import fingerprint

    browser, held = opened
    before = fingerprint(store)
    for hostile in HOSTILE:
        browser.get(f"/api/listings/{hostile}", headers=reading())
        browser.get(f"/api/results/{hostile}", headers=reading())
        browser.get(f"/api/searches/{hostile}", headers=reading())
    assert fingerprint(store) == before
