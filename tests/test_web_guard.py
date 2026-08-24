"""The guard against the browser this is served to.

There is no authentication here, by design and by the constitution: one person, one machine. That
settles who may use it. It settles nothing about **what** may use it, and the gap between those two
is the classic hole in every tool that serves an unauthenticated API on a loopback port.

Every page the person visits, in any tab, can send a request to `http://127.0.0.1:8765/`. The
same-origin policy stops that page reading the answer. It does not stop the request, and a `POST`
that overwrites a saved search has done its damage without the answer ever being read. Worse, a
hostile domain whose DNS resolves to `127.0.0.1` is same-origin as far as a browser is concerned,
so it can read the answers too: every property, every note.

Neither of those is fixed by adding a password. Both are fixed by three checks, and this file is
each of them being attacked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    theirs,
)


@pytest.fixture
def browser(store: Store, db_path: Path):
    load(store, [listing("a")])
    # A second connection to the same file, opened the way the interface opens one. The `store`
    # fixture's own connection stays single-threaded, which is what everything else in this suite
    # relies on.
    with client(held_workspace(shared_store(db_path))) as opened:
        yield opened


# ---------------------------------------------------------------------------
# A page on somebody else's site
# ---------------------------------------------------------------------------


def test_a_request_from_another_site_is_refused(browser) -> None:
    """The everyday case: any tab the person has open can send this request."""
    response = browser.post(
        "/api/areas",
        json={"area_type": "city", "area_value": "Portales", "notes": "hello"},
        headers={**theirs(), "X-Homescout": "1"},
    )
    assert response.status_code == 403
    assert "another site" in response.json()["error"]


def test_reading_from_another_site_is_refused_too(browser) -> None:
    """Because the interesting thing to steal is the answer, not the ability to write."""
    response = browser.get("/api/searches", headers=theirs())
    assert response.status_code == 403


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.invalid",
        "http://127.0.0.1.evil.invalid",
        "http://localhost.evil.invalid",
        "http://127.0.0.1:9999",
        "null",
    ],
)
def test_no_other_origin_gets_through(origin: str, browser) -> None:
    """Including the ones that look like this server if you read them quickly."""
    response = browser.get("/api/searches", headers={"Host": "127.0.0.1:8765", "Origin": origin})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# A domain that resolves here
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    ["evil.invalid", "rebind.evil.invalid:8765", "homescout.evil.invalid", "192.168.1.14:8765"],
)
def test_a_request_naming_another_host_is_refused(host: str, browser) -> None:
    """DNS rebinding: the request arrives here, and the browser thinks it is that domain's own.

    The header is what gives it away. A page on `evil.invalid` whose DNS points at this machine
    still sends `Host: evil.invalid`, because that is the name it asked for.
    """
    response = browser.get("/api/searches", headers={"Host": host})
    assert response.status_code == 403
    assert "this machine only" in response.json()["error"]


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "127.0.0.1"])
def test_this_machine_by_its_own_names_is_allowed(host: str, browser) -> None:
    assert browser.get("/api/searches", headers={"Host": host}).status_code == 200


# ---------------------------------------------------------------------------
# A form posted by a hostile page
# ---------------------------------------------------------------------------


def test_a_write_with_no_guard_header_is_refused(browser) -> None:
    """The one that catches a plain form post, which sends no `Origin` a browser will admit to.

    A form cannot set a custom header. Setting one requires a preflight, and a preflight is refused
    by the host and origin checks above, so this closes the case those two leave open.
    """
    response = browser.post(
        "/api/areas",
        json={"area_type": "city", "area_value": "Portales", "notes": "hello"},
        headers={"Host": "127.0.0.1:8765"},
    )
    assert response.status_code == 403
    assert "X-Homescout" in response.json()["error"] or "x-homescout" in response.json()["error"]


def test_a_refused_write_changes_nothing(store: Store, db_path: Path) -> None:
    """The point of all of it: the request is refused before it reaches an operation."""
    load(store, [listing("a")])
    with client(held_workspace(shared_store(db_path))) as browser:
        before = fingerprint(store)
        browser.post(
            "/api/areas",
            json={"area_type": "city", "area_value": "Portales", "notes": "hello"},
            headers={"Host": "127.0.0.1:8765"},
        )
        assert fingerprint(store) == before


def test_a_read_needs_no_guard_header(browser) -> None:
    """Reads are not what the header is for, and requiring it would break a typed-in URL."""
    assert browser.get("/api/searches", headers=reading()).status_code == 200
    assert browser.get("/api/searches").status_code == 200


def test_the_interface_itself_gets_through(store: Store, db_path: Path) -> None:
    """The whole guard is worth nothing if it also stops the pages it is protecting."""
    load(store, [listing("a")])
    with client(held_workspace(shared_store(db_path))) as browser:
        response = browser.post(
            "/api/areas",
            json={"area_type": "city", "area_value": "Portales", "notes": "good water"},
            headers=ours(),
        )
        assert response.status_code == 200, response.text
        assert response.json()["areas"][0]["notes"] == "good water"


def test_the_pages_set_the_header_themselves() -> None:
    """So no page has to remember, which is how one would eventually not."""
    from web_fakes import STATIC

    common = (STATIC / "common.js").read_text(encoding="utf-8")
    assert '"X-Homescout"' in common
    for script in STATIC.glob("*.js"):
        if script.name == "common.js":
            continue
        assert "X-Homescout" not in script.read_text(encoding="utf-8"), (
            f"{script.name} sets the guard header itself; it should go through the shared helper"
        )


def test_a_refusal_says_which_check_refused_it(browser) -> None:
    """A person who changed the port and cannot work out why nothing saves deserves a sentence."""
    said = {
        browser.get("/api/searches", headers={"Host": "evil.invalid"}).json()["error"],
        browser.get("/api/searches", headers=theirs()).json()["error"],
        browser.post("/api/areas", json={}, headers={"Host": "127.0.0.1:8765"}).json()["error"],
    }
    assert len(said) == 3, "three checks, three different explanations"
    assert all(len(message) > 40 for message in said)


# ---------------------------------------------------------------------------
# What every answer carries
# ---------------------------------------------------------------------------


def test_nothing_here_may_be_framed_sniffed_or_leaked_as_a_referrer(browser) -> None:
    response = browser.get("/api/searches", headers=reading())
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
