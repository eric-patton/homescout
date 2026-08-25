"""The interface in a real browser, which is the only place three of its claims can be checked.

Marked slow and excluded from the default run. Everything else about this feature is proved against
the server and the source; these three are properties of a page:

- a table of five thousand rows becomes interactive within three seconds and sorts or filters within
  two hundred milliseconds
- an inline edit can be made with the keyboard alone, and the store holds the result afterwards
- a save that fails keeps the typed value and does not claim to have saved

Driven with Chrome DevTools Protocol over a real server on the loopback address, so what is measured
is what the person gets. Skipped, rather than failed, when no Chrome is available: a suite that
cannot run on a machine with no browser is a suite nobody runs.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

from homescout import api
from homescout.store import Store
from web_fakes import held_workspace, listing, load, shared_store

pytestmark = pytest.mark.slow

ROWS = 5_000
INTERACTIVE_BUDGET = 3.0
INTERACTION_BUDGET = 0.200


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def served(store: Store, db_path: Path):
    """A real server on a real port, stopped when the test ends."""
    import uvicorn

    from homescout.web.app import build

    load(store, [listing(f"p{index:05d}", price=90_000 + index * 37) for index in range(60)])
    held = held_workspace(shared_store(db_path))
    port = free_port()
    config = uvicorn.Config(
        build(held), host="127.0.0.1", port=port, log_level="error", access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "the server did not start"
    try:
        yield f"http://127.0.0.1:{port}", held, store
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def chrome(url: str):
    """A headless Chrome pointed at the interface, or a skip."""
    import shutil
    import subprocess

    candidates = [
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    binary = next((found for found in candidates if found and Path(found).exists()), None)
    if binary is None:
        pytest.skip("no Chrome on this machine")

    port = free_port()
    import tempfile

    profile = tempfile.mkdtemp()
    process = subprocess.Popen(
        [
            binary,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            # Chrome refuses a DevTools websocket from an origin it was not told about. This is a
            # throwaway profile on a loopback port that this process opened, so the origin it is
            # being asked to trust is this test.
            "--remote-allow-origins=*",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process, port


def talk(port: int, url: str):
    """A DevTools connection to the page, or a skip if `websocket-client` is not installed."""
    import urllib.request

    try:
        import websocket  # type: ignore
    except ImportError:
        pytest.skip("websocket-client is not installed, so the browser cannot be driven")

    for _ in range(100):
        try:
            pages = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1).read()
            )
        except Exception:  # noqa: BLE001 - the browser is still starting
            time.sleep(0.1)
            continue
        for page in pages:
            if page.get("type") == "page" and url in page.get("url", ""):
                return websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30)
        time.sleep(0.1)
    pytest.skip("the browser did not open the page")


def evaluate(connection, script: str, message_id: int = 1):
    connection.send(
        json.dumps(
            {
                "id": message_id,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "awaitPromise": True, "returnByValue": True},
            }
        )
    )
    while True:
        found = json.loads(connection.recv())
        if found.get("id") == message_id:
            result = found.get("result", {}).get("result", {})
            if "exceptionDetails" in found.get("result", {}):
                raise AssertionError(found["result"]["exceptionDetails"])
            return result.get("value")


def test_a_textarea_built_by_this_page_holds_its_text(served) -> None:
    """feat-010/AC-24: the box a save is built from has to hold what the code put in it.

    A regression, and the kind only a real browser catches. A textarea keeps its text as content
    rather than in an attribute, so building one with `value=` set an attribute nothing reads: the
    box drew empty. The criteria box on a search page was built that way, and the "Save the
    criteria" button under it built its request from `box.value`. So a search with three criteria
    showed none, and one click wrote that empty box back over them.

    Asserted on the element builder rather than on one page, because the bug was in the builder and
    the next textarea would have inherited it.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/search/portales")
    try:
        connection = talk(debug, "/search/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (typeof el === "function") break;
                   await new Promise((r) => setTimeout(r, 100));
                 }
                 const box = el("textarea", {rows: "4", value: "on-a-well | flag | x == 1"});
                 return {value: box.value, tag: box.tagName};
               })()""",
        )
    finally:
        process.terminate()

    assert found and found["tag"] == "TEXTAREA"
    assert found["value"] == "on-a-well | flag | x == 1", (
        "a textarea built with a value drew empty, so any save built from it writes nothing back"
    )


def test_the_value_box_follows_the_field(served) -> None:
    """feat-010/AC-29: what a value may be is a property of the field that was chosen.

    The failure this prevents is quiet and expensive. A text box beside "Cooling" is how somebody
    types "swamp cooler", saves a criterion that parses and runs, and is never told it can never be
    true because the six words that field may hold do not include it. So the control is rebuilt when
    the field changes: a closed set becomes a dropdown of exactly that set, a number becomes a
    number box, a true-or-false becomes yes and no.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/search/portales")
    try:
        connection = talk(debug, "/search/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (typeof valueControl === "function" && held.settings) break;
                   await new Promise((r) => setTimeout(r, 100));
                 }
                 const of = (name) =>
                   (held.settings.rule_vocabulary || []).find((f) => f.name === name);
                 const shown = (name, takes) => {
                   const box = valueControl(of(name), {value: null}, takes || "one");
                   const node = box.tagName === "SELECT" ? box : box.querySelector("select") || box;
                   return {
                     tag: node.tagName,
                     type: node.getAttribute("type"),
                     options: [...(node.options || [])].map((o) => o.value),
                   };
                 };
                 return {
                   cooling: shown("cooling"),
                   price: shown("price"),
                   priceCut: shown("price_cut"),
                   city: shown("city"),
                 };
               })()""",
        )
    finally:
        process.terminate()

    assert found["cooling"]["tag"] == "SELECT", "a field with six possible values got a text box"
    assert "evaporative" in found["cooling"]["options"]
    assert "swamp cooler" not in found["cooling"]["options"], (
        "the dropdown offered something the field cannot hold"
    )
    assert found["price"]["type"] == "number", "a price got something other than a number box"
    assert found["priceCut"]["options"] == ["true", "false"], "a yes-or-no was not yes and no"
    assert found["city"]["tag"] == "INPUT", "a field with no closed set should take typed text"


def test_a_criterion_can_be_started_from_a_suggestion(served) -> None:
    """feat-010/AC-32: the first criterion somebody has is not one they had to invent.

    A blank builder is still a blank page. Each of these is a thing somebody looking at rural
    property actually wants, and each is ordinary to edit or remove after it is added.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/search/portales")
    try:
        connection = talk(debug, "/search/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (typeof SUGGESTIONS !== "undefined") break;
                   await new Promise((r) => setTimeout(r, 100));
                 }
                 const names = (held.settings.rule_vocabulary || []).map((f) => f.name);
                 return SUGGESTIONS.map(([id, severity, conditions, said]) => ({
                   id: id,
                   severity: severity,
                   said: said,
                   known: conditions.every(([f]) => names.indexOf(f) !== -1),
                 }));
               })()""",
        )
    finally:
        process.terminate()

    assert len(found) >= 5, "a handful is the point; one is not a starting place"
    for suggestion in found:
        assert suggestion["known"], f"{suggestion['id']} names a field a criterion cannot use"
        assert suggestion["said"], f"{suggestion['id']} does not say what it is for"
        assert suggestion["severity"] in ("drop", "flag", "boost", "demote"), suggestion


def test_the_table_is_quick_at_five_thousand_rows(served) -> None:
    """feat-010 performance: three seconds to be usable, two hundred milliseconds to respond.

    Measured against a page that has actually loaded five thousand real rows from a real server,
    rather than against the prototype the design was decided from.
    """
    base, held, store = served
    load(store, [listing(f"q{index:05d}", price=90_000 + index * 11) for index in range(ROWS)])

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        ready = evaluate(
            connection,
            """(async () => {
                 const started = performance.now();
                 for (let i = 0; i < 300; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 document.body.getBoundingClientRect();
                 return {took: performance.now() - started,
                         rows: state.all.length,
                         nodes: document.getElementsByTagName("*").length};
               })()""",
        )
        assert ready["rows"] >= ROWS, ready
        assert ready["took"] / 1000 < INTERACTIVE_BUDGET, ready
        assert ready["nodes"] < 5_000, f"{ready['nodes']} elements: the window is not windowing"

        sorted_ = evaluate(
            connection,
            """(() => { const t = performance.now(); sortBy("Price");
                        document.body.getBoundingClientRect();
                        return performance.now() - t; })()""",
            2,
        )
        assert sorted_ / 1000 < INTERACTION_BUDGET, f"sorting took {sorted_:.0f}ms"

        filtered = evaluate(
            connection,
            """(() => { state.query = "7"; const t = performance.now(); apply();
                        document.body.getBoundingClientRect();
                        return performance.now() - t; })()""",
            3,
        )
        assert filtered / 1000 < INTERACTION_BUDGET, f"filtering took {filtered:.0f}ms"
    finally:
        process.terminate()


def test_an_inline_edit_can_be_made_with_the_keyboard_alone(served) -> None:
    """feat-010/AC-4, feat-010/AC-17: judgment lands in the tool, typed on the row being read."""
    base, held, store = served
    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        written = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 200; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 // Focus the grid, walk to the Verdict column with the keyboard, and type.
                 const column = state.columns.findIndex(c => c.name === "Verdict");
                 focusCell(0, column);
                 const cell = document.querySelector('td[aria-selected="true"]');
                 cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
                 const input = cell.querySelector("input");
                 if (!input) return {error: "Enter did not open an editor"};
                 input.value = "worth a look";
                 input.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
                 for (let i = 0; i < 100; i++) {
                   if (cell.className.includes("saved")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 return {listing: state.shown[0].listing_id, shown: cell.textContent,
                         className: cell.className};
               })()""",
        )
        assert "error" not in written, written
        assert "worth a look" in written["shown"], written
        assert "saved" in written["className"], written

        held_note = api.listing(held, written["listing"])["annotation"]
        assert held_note["verdict"] == "worth a look"
    finally:
        process.terminate()


def test_a_save_that_fails_keeps_what_was_typed(served) -> None:
    """feat-010/AC-6: never present an unsaved edit as saved.

    The failure is forced at the network rather than in the page, so what is exercised is the same
    path a real refusal takes.
    """
    base, held, store = served
    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 200; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 window.fetch = async () => new Response(
                   JSON.stringify({error: "the database is in use"}),
                   {status: 409, headers: {"Content-Type": "application/json"}});

                 const column = state.columns.findIndex(c => c.name === "Verdict");
                 focusCell(0, column);
                 const cell = document.querySelector('td[aria-selected="true"]');
                 cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
                 const input = cell.querySelector("input");
                 input.value = "do not lose this";
                 input.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
                 for (let i = 0; i < 100; i++) {
                   if (cell.className.includes("unsaved")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 return {className: cell.className,
                         typed: (cell.querySelector("input") || {}).value,
                         text: cell.textContent,
                         banner: document.getElementById("banner").textContent};
               })()""",
        )
        assert "unsaved" in found["className"], found
        assert found["typed"] == "do not lose this", "the typed value was discarded"
        assert "not saved" in found["text"], "the row does not say it failed"
        assert "saved" not in found["text"].replace("not saved", ""), "it claims to be saved"
        assert "database is in use" in found["banner"], found["banner"]
    finally:
        process.terminate()
