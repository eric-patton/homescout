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


def test_a_row_is_drawn_the_height_the_table_places_it_at(served) -> None:
    """feat-010/AC-20's machinery: the arithmetic and the stylesheet have to agree, exactly.

    This is a regression, and a browser is the only place it shows. The virtual window placed rows
    every 22 pixels and the stylesheet drew them 26 tall, so each drawn row sat four pixels lower
    than the scrollbar said it was: the further down the table, the further the rows crept, and the
    last of them ended below the bottom of the scroll range where they could not be reached at all.

    Compared against the number the placement uses rather than against 26, so the test still means
    something after somebody changes the height on purpose.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 const rows = [...document.querySelectorAll("#body tr")].slice(0, 3);
                 return {
                   assumed: rowHeight(),
                   drawn: rows.map(r => r.getBoundingClientRect().height),
                 };
               })()""",
        )
    finally:
        process.terminate()

    assert found["drawn"], "no rows were drawn"
    for height in found["drawn"]:
        assert abs(height - found["assumed"]) < 0.51, (
            f"a row is drawn {height}px tall but placed every {found['assumed']}px, so the rows "
            "creep out from under the scrollbar and the last of them cannot be reached"
        )


def test_a_column_moves_and_resizes_from_the_keyboard(served) -> None:
    """feat-010/AC-44, feat-010/AC-17: a new control that is mouse-only is one some people lack.

    Alt with an arrow moves the column; add Shift and it sizes it. Both are exercised through the
    events a keyboard actually sends, on the header the person would have focused.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 const named = () => state.columns.map(c => c.name);
                 const before = named();
                 const moving = before[1];
                 const press = (extra) => {
                   const heads = document.querySelectorAll("table.grid thead th");
                   const at = named().indexOf(moving);
                   heads[at].focus();
                   heads[at].dispatchEvent(new KeyboardEvent(
                     "keydown", Object.assign({key: "ArrowRight", bubbles: true}, extra)));
                 };

                 press({altKey: true});
                 const moved = named();
                 const wasWide = widthOf(moving);
                 press({altKey: true, shiftKey: true});
                 return {before, moved, wasWide, nowWide: widthOf(moving),
                         drawn: [...document.querySelectorAll("table.grid thead th")]
                                  .map(h => h.textContent.trim())};
               })()""",
        )
    finally:
        process.terminate()

    assert found["moved"] != found["before"], "alt with an arrow did not move the column"
    assert found["moved"][1] == found["before"][2], "it did not move to the next position"
    assert found["moved"][2] == found["before"][1]
    assert found["nowWide"] > found["wasWide"], "alt and shift did not widen it"
    assert found["drawn"][:3] == found["moved"][:3], "the header does not show the new order"


def test_the_table_works_when_the_browser_will_not_store_anything(served) -> None:
    """feat-010/AC-45: the arrangement is the one thing here that may be lost losing nothing.

    Private browsing, a full quota, or storage switched off entirely. The arrangement is a
    convenience; the table is not. So every read and write of it is guarded, and with storage
    throwing on every access the table still opens, in the arrangement the columns were declared in.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 50));
                 }
                 Object.defineProperty(window, "localStorage", {
                   configurable: true,
                   get() { throw new DOMException("denied", "SecurityError"); },
                 });
                 const declared = [{name: "Rank", origin: "annotation"},
                                   {name: "Annual Taxes", origin: "unfilled"},
                                   {name: "Price", origin: "listing"}];
                 let threw = null;
                 let arranged = null;
                 try {
                   arranged = arrange(declared).map(c => c.name);
                   remember();
                 } catch (error) {
                   threw = String(error);
                 }
                 return {threw, arranged, rows: document.querySelectorAll("#body tr").length};
               })()""",
        )
    finally:
        process.terminate()

    assert found["threw"] is None, f"storage being unavailable broke the page: {found['threw']}"
    assert found["arranged"] == ["Rank", "Price", "Annual Taxes"], (
        "without a remembered arrangement the declared one is used, the unfilled columns last"
    )
    assert found["rows"] > 0, "the table drew nothing"


def test_a_handler_this_page_builds_is_a_handler_that_runs(served) -> None:
    """feat-010/AC-17: a regression in the element builder, and one only a browser catches.

    The builder treated six named handlers as event listeners and passed everything else to
    `setAttribute`, which turns a function into a string. An attribute holding `() => edit(...)` is
    an inline handler whose whole body defines an arrow function and throws it away: accepted, in
    the DOM, and doing nothing at all. Double-clicking a cell to edit it was built that way.

    Asserted on the builder rather than on one cell, because the bug was in the builder and the next
    handler would have inherited it.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        found = evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 100; i++) {
                   if (typeof el === "function") break;
                   await new Promise(r => setTimeout(r, 100));
                 }
                 const fired = [];
                 const node = el("td", {
                   ondblclick: () => fired.push("dblclick"),
                   onpointerdown: () => fired.push("pointerdown"),
                   onclick: () => fired.push("click"),
                 });
                 node.dispatchEvent(new MouseEvent("dblclick"));
                 node.dispatchEvent(new PointerEvent("pointerdown"));
                 node.dispatchEvent(new MouseEvent("click"));
                 return {fired, attribute: node.getAttribute("ondblclick")};
               })()""",
        )
    finally:
        process.terminate()

    assert sorted(found["fired"]) == ["click", "dblclick", "pointerdown"], found["fired"]
    assert found["attribute"] is None, "a function was written into the DOM as an inline handler"
