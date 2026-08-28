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
from web_fakes import STATIC, held_workspace, listing, load, shared_store

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
            # A real window, because two of these tests are about what fits in one. The default
            # headless viewport is short enough that no table could fit under the page's heading.
            "--window-size=1600,1000",
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
                 await new Promise(r => setTimeout(r, 200));
                 const panel = document.querySelector(".writing");
                 if (!panel) return {error: "Enter did not open an editor"};
                 const box = panel.querySelector("textarea");
                 box.value = "worth a look";
                 // Ctrl with Enter, because a plain Enter in prose is a new line.
                 box.dispatchEvent(new KeyboardEvent(
                   "keydown", {key: "Enter", ctrlKey: true, bubbles: true}));
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
                 await new Promise(r => setTimeout(r, 200));
                 const box = document.querySelector(".writing textarea");
                 box.value = "do not lose this";
                 box.dispatchEvent(new KeyboardEvent(
                   "keydown", {key: "Enter", ctrlKey: true, bubbles: true}));
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
                         /* The name the heading says it is, rather than the text in it: a heading
                            also holds its sort marker and its filter button. */
                         drawn: [...document.querySelectorAll("table.grid thead th")]
                                  .map(h => h.dataset.column || h.textContent.trim())};
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
                                   {name: "Annual Taxes", origin: "annotation"},
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
    assert found["arranged"] == ["Keep or pass", "Rank", "Annual Taxes", "Price"], (
        "without a remembered arrangement the declared order is used, with the controls first"
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


def opened(served, script):
    """Run one script against a loaded results table, and always close the browser."""
    base, _held, _store = served
    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        return evaluate(
            connection,
            """(async () => {
                 const wait = (ms) => new Promise(r => setTimeout(r, ms));
                 /* Wait for a condition rather than for a duration. A fixed delay is long enough
                    on an idle machine and not on one running the whole suite, which is a test that
                    fails for a reason that has nothing to do with what it is testing. */
                 const until = async (ready, patience = 100) => {
                   for (let i = 0; i < patience; i++) {
                     const found = ready();
                     if (found) return found;
                     await wait(50);
                   }
                   return null;
                 };
                 await until(() => document.querySelector("#body tr"));
                 """ + script + """
               })()""",
        )
    finally:
        process.terminate()


def test_a_tag_is_made_and_put_on_a_property_from_its_own_cell(served) -> None:
    """feat-010/AC-63: the household's own words, made at the moment somebody wants one.

    Keeping and passing answer the tool's question. This is for everything else, and the control is
    the whole design: a list of the words already in use, ticked or not, and one line to make a new
    one. Not a box to type a comma-separated list into, because that is how a vocabulary of eight
    words becomes a vocabulary of fourteen, half of them typos of the other half, with nothing on
    the page ever saying so.

    Three things are pinned. A new word goes on the property and into the vocabulary in one action,
    because that is the moment somebody knows they want it. Unticking one takes it off, since the
    whole list is what is sent. And the cell shows what the store now holds rather than what was
    ticked, which is what makes the store the authority on which spelling of a word is this
    workspace's.
    """
    found = opened(served, """
        show("Tags");
        await until(() => document.querySelector('#body td[data-column="Tags"]'));

        const cell = () => document.querySelector('#body td[data-column="Tags"]');
        const open = () => {
          const at = cell();
          edit(at, state.shown[Number(at.dataset.index)], "Tags");
          return document.querySelector(".writing.tagging");
        };
        const typeIn = async (panel, word) => {
          const box = panel.querySelector('input[type="text"]');
          box.value = word;
          box.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
          await wait(30);
        };

        let panel = open();
        const empty = panel.textContent;
        await typeIn(panel, "Barn");
        await typeIn(panel, "drive by");
        panel.querySelector("button.primary").click();
        await until(() => cell().querySelectorAll(".tag").length === 2);
        const both = [...cell().querySelectorAll(".tag")].map((one) => one.textContent);

        /* Open it again: the two words are now choices, and both are ticked. */
        panel = open();
        const offered = [...panel.querySelectorAll(".choices label")].map((one) => ({
          word: one.textContent, ticked: one.querySelector("input").checked,
        }));

        /* A second spelling of a word already in use must not become a second word. */
        await typeIn(panel, "BARN");
        const afterShouting = panel.querySelectorAll(".choices label").length;

        /* Untick the first and save: the whole list is what is sent, so it comes off. */
        const first = panel.querySelector(".choices label input");
        first.checked = false;
        first.dispatchEvent(new Event("change", {bubbles: true}));
        panel.querySelector("button.primary").click();
        await until(() => cell().querySelectorAll(".tag").length === 1);

        const left = [...cell().querySelectorAll(".tag")].map((one) => one.textContent);
        const vocabulary = (await ask("/api/tags")).tags.map((one) => one.name);
        return {empty, both, offered, afterShouting, left, vocabulary};
    """)

    assert "No tags yet" in found["empty"], found["empty"]
    assert found["both"] == ["Barn", "drive by"], found["both"]

    assert [one["word"] for one in found["offered"]] == ["Barn", "drive by"], found["offered"]
    assert all(one["ticked"] for one in found["offered"]), (
        "the words this property carries are offered unticked, so saving would take them all off"
    )
    assert found["afterShouting"] == 2, (
        "typing a word that is already in the vocabulary in different case made a second word, "
        f"so the list now holds {found['afterShouting']} of them"
    )

    assert found["left"] == ["drive by"], (
        f"unticking a tag did not take it off the property: {found['left']}"
    )
    #: The word survives losing its last property. That is what makes it a vocabulary rather than
    #: a side effect of whichever houses happen to be tagged today.
    assert sorted(found["vocabulary"]) == ["Barn", "drive by"], found["vocabulary"]


def test_the_headings_stay_at_the_top_however_far_down_the_list_goes(served) -> None:
    """feat-010/AC-53: a heading that leaves is a column of numbers nobody can name.

    The failure this pins is not "the headings were never stuck". They were, and they let go
    partway down, which is the worse shape of the bug: it works long enough to be trusted, and the
    first anybody knows is a screen of prices, acreages and years with nothing above them.

    A sticky cell is stuck to its own table and no further. The window draws sixty rows of a
    thousand, so the table was sixty rows tall, so the headings held for sixty rows. The rows the
    window is not drawing are now blank rows with a height rather than a transform on the ones it
    is, because a transform moves paint and the table has to actually be that tall.

    The scroller is made short on purpose so the drawn window is a small fraction of the list
    whatever size the machine running this opened its browser at. A test that only reproduces on a
    tall screen is a test that passes on the machine where it matters.
    """
    found = opened(served, """
        const scroller = document.getElementById("scroller");
        scroller.style.height = "200px";
        scroller.dispatchEvent(new Event("scroll"));
        await until(() => document.querySelector("#body tr"));

        const heading = () => document.querySelector("table.grid thead th");
        const where = () => {
          const box = heading().getBoundingClientRect();
          const seen = scroller.getBoundingClientRect();
          return Math.round(box.top - seen.top);
        };

        scroller.scrollTop = 0;
        await until(() => true);
        const atTop = where();

        /* Past the end of the drawn window, which is where it used to let go. */
        scroller.scrollTop = Math.round(scroller.scrollHeight / 2);
        await until(() => document.querySelector("#body tr").dataset.index !== "0");
        const partway = where();

        scroller.scrollTop = scroller.scrollHeight;
        await until(() => true);
        await wait(150);
        const atEnd = where();
        const named = heading().dataset.column || heading().textContent.trim();
        const last = [...document.querySelectorAll("#body tr")].pop();

        return {atTop, partway, atEnd, named,
                rows: document.querySelectorAll("#body tr").length,
                total: state.shown.length,
                lastDrawn: Number(last.dataset.index)};
    """)

    assert found["rows"] < found["total"], (
        "every row is in the page, so this cannot tell a table that is tall enough from one that "
        "is not: the window is not windowing"
    )
    assert found["lastDrawn"] == found["total"] - 1, (
        "the end of the list is not the end of the list"
    )

    #: Where they sit unscrolled is the baseline, rather than zero: the box has a border, and one
    #: pixel of it is not the bug.
    assert found["atTop"] <= 2, f"the headings do not start at the top of the box: {found['atTop']}"
    assert found["partway"] == found["atTop"], (
        f"the headings slid {found['partway'] - found['atTop']}px out of the box halfway down"
    )
    assert found["atEnd"] == found["atTop"], (
        f"the headings slid {found['atEnd'] - found['atTop']}px out of the box at the end of the "
        "list, which is exactly where somebody needs them most and least expects to lose them"
    )
    assert found["named"], "the heading is there and says nothing"


def test_the_columns_stay_put_when_the_table_is_scrolled(served) -> None:
    """feat-010/AC-44: a width somebody set has to survive them reading the table.

    A regression, and one with an unobvious cause. `table-layout: fixed` derives its columns from
    the first row it can find whenever the table's own width is `auto`, and the first row in this
    table is whichever row the scroll position last put in the DOM. So scrolling changed the row the
    layout was derived from and every column jumped. The table is now told its own width, the sum of
    the declared columns, so the `colgroup` is the only thing the layout comes from.
    """
    found = opened(served, """
        const scroller = document.getElementById("scroller");
        const widths = () => [...document.querySelectorAll("#body tr")[2].children]
          .map(c => Math.round(c.getBoundingClientRect().width));
        scroller.scrollTop = 0;
        await wait(200);
        const atTop = widths();
        scroller.scrollTop = Math.round(scroller.scrollHeight / 2);
        await wait(300);
        const partway = widths();
        scroller.scrollTop = scroller.scrollHeight;
        await wait(300);
        return {atTop, partway, atEnd: widths()};
    """)

    assert found["atTop"] == found["partway"] == found["atEnd"], (
        "the columns changed width as the table was scrolled"
    )
    assert len(set(found["atTop"])) > 1, "the columns are not all the same width, so this measures"


def test_wrapped_text_does_not_make_a_row_taller(served) -> None:
    """feat-010/AC-47: wrapping is clamped, because the rows have to stay the same height.

    Every row being the same height is what lets a thousand of them be placed by arithmetic instead
    of measured. So "wrap long text" is a fixed number of lines rather than as many as the longest
    cell wants, and the clamp is on a box inside the cell: a table cell cannot clip its own height,
    and `overflow: hidden` on a `td` does not stop its content taking the row with it.
    """
    found = opened(served, """
        /* Real prose, put on the rows rather than into the fixture, because the point of the test
           is what the table does with text far longer than a column is wide. */
        const long = ("A quiet adobe on a rise at the end of a graded county road, with a metal " +
                      "roof, a new septic system, a producing well, and views in every direction " +
                      "over open country to the mountains beyond it. ").repeat(4);
        state.all.slice(0, 8).forEach(r => {
          r.values["Description"] = long;
          r.values["Town Analysis Notes"] = long;
        });
        apply();
        await wait(300);
        const before = [...document.querySelectorAll("#body tr")]
          .slice(0, 8).map(r => r.getBoundingClientRect().height);

        document.getElementById("wraptext").click();
        await wait(500);
        const rows = [...document.querySelectorAll("#body tr")];
        const cell = rows[0].querySelector('td[data-column="Description"] .cell');
        return {assumed: rowHeight(),
                unwrapped: before,
                drawn: rows.slice(0, 8).map(r => r.getBoundingClientRect().height),
                cellHeight: cell ? cell.getBoundingClientRect().height : null,
                wrapped: cell ? getComputedStyle(cell.parentElement).whiteSpace : null,
                lines: WRAP_LINES};
    """)

    assert found["wrapped"] == "normal", "the cells are not wrapping, so this measures nothing"
    assert found["assumed"] > max(found["unwrapped"]), "wrapping did not make the rows taller"
    assert found["cellHeight"] <= found["assumed"], "a wrapped cell is taller than its row"

    assert found["lines"] > 1, "wrapping to one line is not wrapping"
    for height in found["drawn"]:
        assert abs(height - found["assumed"]) < 0.51, (
            f"a wrapped row is {height}px against a placement of {found['assumed']}px"
        )


def test_passing_on_a_house_asks_first_and_escape_means_no(served) -> None:
    """feat-010/AC-48: one mis-aimed click on a 26-pixel row should not empty a table.

    Escape is asserted rather than the Cancel button, because a modal dialog's keyboard answer is
    the one that has to work: the pointer's way of dismissing it is a convenience on top.
    """
    found = opened(served, """
        const row = document.querySelector("#body tr");
        const listing = row.dataset.listing;
        row.querySelector("button.pass").click();
        const dialog = await until(() => document.querySelector("dialog.ask"));
        const asked = {open: !!(dialog && dialog.open),
                       says: dialog ? dialog.textContent : "",
                       /* The cursor is in the box, so the reason can simply be typed. */
                       focused: document.activeElement.tagName,
                       asksWhy: !!(dialog && dialog.querySelector("textarea"))};

        dialog.dispatchEvent(new Event("cancel"));
        await until(() => !document.querySelector("dialog.ask"));
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {asked,
                stillThere: !!document.querySelector("#body tr"),
                gone: !document.querySelector("dialog.ask"),
                judgment: (answered.listing.annotation || {}).judgment ?? null};
    """)

    assert found["asked"]["open"], "passing on a house did not ask"
    assert "Pass on this property?" in found["asked"]["says"]
    assert "brings it back" in found["asked"]["says"], "the dialog does not say it is reversible"
    assert found["asked"]["asksWhy"], "the dialog does not ask why"
    assert found["asked"]["focused"] == "TEXTAREA", (
        "the cursor is not in the box, so the reason cannot simply be typed"
    )
    assert found["gone"], "the dialog stayed open after being dismissed"
    assert found["judgment"] is None, "escaping the question passed on the house anyway"


def test_saying_yes_to_the_question_passes_on_the_house(served) -> None:
    """feat-010/AC-48, feat-010/AC-35: because a test that only proves it asks would pass on a
    dialog whose buttons do nothing."""
    found = opened(served, """
        const row = document.querySelector("#body tr");
        const listing = row.dataset.listing;
        const before = state.shown.length;
        row.querySelector("button.pass").click();
        await until(() => document.querySelector("dialog.ask"));
        [...document.querySelectorAll("dialog.ask button")]
          .find(b => b.textContent === "Pass on it").click();
        await until(() => state.shown.length !== before);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {before, after: state.shown.length,
                judgment: (answered.listing.annotation || {}).judgment ?? null};
    """)

    assert found["judgment"] == "pass"
    assert found["after"] == found["before"] - 1, "the property did not leave the table"


def test_keeping_a_house_takes_one_press_and_no_question(served) -> None:
    """feat-010/AC-49: the shortlist is what a person works from, so it has to be cheap to build.

    No question asked, deliberately: keeping a house costs nothing, hides nothing, and the same
    button takes it off again.
    """
    found = opened(served, """
        const row = document.querySelector("#body tr");
        const listing = row.dataset.listing;
        const before = state.shown.length;
        row.querySelector("button.keep").click();
        await until(() => state.all[0].judgment === "keep");
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        const asked = !!document.querySelector("dialog.ask");
        document.getElementById("onlykept").click();
        await until(() => state.shown.length !== before);
        return {asked, before, whileKeptOnly: state.shown.length,
                judgment: (answered.listing.annotation || {}).judgment ?? null};
    """)

    assert found["judgment"] == "keep"
    assert not found["asked"], "keeping a house asked a question it did not need to ask"
    assert found["whileKeptOnly"] == 1, "only what you kept did not narrow to the kept one"
    assert found["before"] > 1, "the table had nothing else in it, so that proves little"


def test_the_keep_and_pass_controls_are_the_first_thing_on_a_row(served) -> None:
    """feat-010/AC-49: a control nobody can find is a control that does not exist.

    They were inside the address cell, after the address and after however many badges the property
    carried, so on a narrow column they sat past the right edge and were reported twice as a missing
    feature. First column, fixed width, same place on every row, and it cannot be dragged out of
    that position.
    """
    found = opened(served, """
        const first = document.querySelector("#body tr").children[0];
        move("Price", 0);
        await wait(200);
        return {column: first.dataset.column,
                buttons: [...first.querySelectorAll("button")].map(b => b.className),
                afterTryingToDisplaceIt: state.columns[0].name,
                header: document.querySelector("table.grid thead th").textContent};
    """)

    assert found["buttons"] == ["keep", "pass"], found["buttons"]
    assert found["afterTryingToDisplaceIt"] == found["column"], (
        "another column was allowed in front of the controls"
    )
    assert found["header"].strip(), "the control column has no heading to say what it does"


def test_the_thumbnail_opens_every_photograph_the_listing_carried(served) -> None:
    """feat-010/AC-51: the one stored picture is a way in to the forty the listing had.

    A property in this search carries thirty-eight photographs at the median. Judging a house on its
    roof line, its siding and what stands behind it needs all of them, and until now the only way to
    see any but the first was to open the listing site.

    The pictures themselves are never fetched here: the test points them at a path this server does
    not serve, because what is being asserted is which address ends up in the `img` and how the
    gallery moves between them, not whether a listing site answered.
    """
    found = opened(served, """
        /* Photographs arrive with the property, so they are put on the one being opened. */
        const shots = ["https://pics.invalid/a.jpg", "https://pics.invalid/b.jpg",
                       "https://pics.invalid/c.jpg"];
        /* What the sites actually hand over. Every one of these is stored as http, and on an https
           page a browser will not load one at all, so the gallery has to ask for it as https. */
        const asStored = shots.map(u => u.replace("https://", "http://"));
        window.ask = async () => ({listing: {photo_urls: shots}});

        state.all[0].has_image = true;
        document.getElementById("showphotos").click();
        (await until(() => document.querySelector("#body tr button.thumb"))).click();

        const dialog = await until(() => document.querySelector("dialog.gallery"));
        const plate = () => dialog.querySelector("img.plate").getAttribute("src");
        const counter = () => dialog.querySelector(".counter").textContent;

        const first = {src: plate(), says: counter()};
        dialog.querySelector('button[aria-label="Next photo"]').click();
        const second = {src: plate(), says: counter()};
        dialog.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowLeft", bubbles: true}));
        const back = {src: plate(), says: counter()};
        /* Off the front, which must land on the last rather than on nothing. */
        dialog.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowLeft", bubbles: true}));
        const wrapped = {src: plate(), says: counter()};

        const said = dialog.textContent;
        dialog.close();
        await wait(200);
        /* And again with the addresses in the form they are really stored in. */
        window.ask = async () => ({listing: {photo_urls: asStored}});
        document.querySelector("#body tr button.thumb").click();
        const again = await until(() => document.querySelector("dialog.gallery"));
        const asked = again.querySelector("img.plate").getAttribute("src");
        again.close();
        await wait(100);

        /* The page this test is served over is http, where nothing needs upgrading, so the rule
           that matters over https is asked directly. */
        const upgrade = {
          onHttps: pictureAddress("http://ap.rdcpix.com/a.jpg", "https:"),
          onHttp: pictureAddress("http://ap.rdcpix.com/a.jpg", "http:"),
          alreadySecure: pictureAddress("https://ap.rdcpix.com/a.jpg", "https:"),
          refused: pictureAddress("javascript:alert(1)", "https:"),
        };
        /* What the sites hand over is a thumbnail; these are the addresses of the real picture. */
        const bigger = {
          realtor: biggest("https://ap.rdcpix.com/89da51l-m1071147296s.jpg"),
          zillow: biggest("https://photos.zillowstatic.com/fp/cd4fa8-p_e.jpg"),
          alreadyBig: biggest(
            "https://photos.zillowstatic.com/fp/cd4fa8-uncropped_scaled_within_1536_1152.jpg"),
          unknownHost: biggest("https://maps.googleapis.com/maps/api/staticmap?size=575x242"),
          notAnAddress: biggest("not an address at all"),
        };

        return {first, second, back, wrapped, said, asked, upgrade, bigger,
                secure: window.location.protocol === "https:",
                gone: !document.querySelector("dialog.gallery"),
                shots};
    """)

    assert found["first"]["src"] == found["shots"][0]
    assert found["first"]["says"] == "1 of 3"
    assert found["second"]["src"] == found["shots"][1], "the next photo did not come up"
    assert found["back"]["src"] == found["shots"][0], "the left arrow did not go back"
    assert found["wrapped"]["src"] == found["shots"][2], "going back off the front lost the gallery"
    assert "not from this tool" in found["said"], (
        "the gallery does not say the pictures come from the listing site, which is the one place "
        "in this product where looking at a property is not free of it"
    )
    assert found["gone"], "the gallery stayed in the page after being closed"
    # This test's server is plain http, where an http picture loads and nothing needs upgrading.
    # The rule under test is the one that applies over https, which is how this is really reached.
    assert found["asked"] == (found["shots"][0] if found["secure"] else
                              found["shots"][0].replace("https://", "http://"))
    assert found["upgrade"] == {
        "onHttps": "https://ap.rdcpix.com/a.jpg",
        "onHttp": "http://ap.rdcpix.com/a.jpg",
        "alreadySecure": "https://ap.rdcpix.com/a.jpg",
        "refused": None,
    }, found["upgrade"]
    assert found["bigger"] == {
        # Realtor's `s` is 120 by 80 pixels. Its `o` is the original, at 1024 by 683.
        "realtor": "https://ap.rdcpix.com/89da51l-m1071147296o.jpg",
        # Zillow's `-p_e` is 596 wide; uncropped is 1536 and is not cropped to a shape.
        "zillow": "https://photos.zillowstatic.com/fp/cd4fa8-uncropped_scaled_within_1536_1152.jpg",
        "alreadyBig":
            "https://photos.zillowstatic.com/fp/cd4fa8-uncropped_scaled_within_1536_1152.jpg",
        # A host with no rule is left alone, signed map tiles among them: rewriting one breaks it.
        "unknownHost": "https://maps.googleapis.com/maps/api/staticmap?size=575x242",
        "notAnAddress": "not an address at all",
    }, found["bigger"]


def test_a_listing_with_no_photographs_says_so_rather_than_opening_nothing(served) -> None:
    """feat-010/AC-51: the spec's edge case, on the surface where it is most likely."""
    found = opened(served, """
        window.ask = async () => ({listing: {photo_urls: []}});
        state.all[0].has_image = true;
        document.getElementById("showphotos").click();
        (await until(() => document.querySelector("#body tr button.thumb"))).click();
        await until(() => document.getElementById("banner").textContent.trim());
        return {opened: !!document.querySelector("dialog.gallery"),
                banner: document.getElementById("banner").textContent};
    """)

    assert not found["opened"], "an empty gallery was opened"
    assert "no photographs" in found["banner"], "nothing said why nothing happened"


def test_a_column_can_be_hidden_and_brought_back(served) -> None:
    """feat-010/AC-52: forty-two columns is more than anybody needs at once.

    Hiding is by right-click, which is what was asked for, and by Delete on a focused heading, so it
    is not mouse-only. Bringing one back is from the chooser, because a control that only removes
    things and never restores them is a trap. Where it comes back is where it was: the order that is
    kept is the full one, so a hidden column keeps its place among the others rather than landing on
    the end.
    """
    found = opened(served, """
        const named = () => state.columns.map(c => c.name);
        const before = named();
        const victim = before[2];
        const after_it = before[3];

        /* Right-click the heading, then the first thing its menu offers. */
        const heads = () => document.querySelectorAll("table.grid thead th");
        heads()[2].dispatchEvent(new MouseEvent("contextmenu", {bubbles: true, clientX: 40,
                                                                clientY: 40}));
        const menu = await until(() => document.querySelector(".menu"));
        const offered = [...menu.querySelectorAll("button")].map(b => b.textContent);
        menu.querySelector("button").click();
        await until(() => named().indexOf(victim) < 0);

        const hidden = named();
        const cells = document.querySelector("#body tr").children.length;

        /* And back, from the chooser. */
        chooseColumns();
        const dialog = await until(() => document.querySelector("dialog.columns"));
        const box = [...dialog.querySelectorAll("label")]
          .find(l => l.textContent.trim() === victim).querySelector("input");
        const wasTicked = box.checked;
        box.click();
        box.dispatchEvent(new Event("change", {bubbles: true}));
        await until(() => named().indexOf(victim) >= 0);
        const restored = named();
        dialog.close();

        return {before, hidden, restored, offered, cells, wasTicked, victim, after_it,
                columns: state.columns.length, declared: state.declared.length};
    """)

    assert found["offered"][0] == f"Hide {found['victim']}", found["offered"]
    assert found["victim"] not in found["hidden"], "the column was not hidden"
    assert found["cells"] == len(found["hidden"]), "a row still draws a cell for a hidden column"
    assert found["declared"] == len(found["before"]), "hiding forgot the column, not hid it"
    assert not found["wasTicked"], "the chooser showed a hidden column as shown"
    assert found["restored"] == found["before"], (
        "the column came back somewhere other than where it was"
    )


def test_the_control_column_cannot_be_hidden(served) -> None:
    """feat-010/AC-49, feat-010/AC-52: keeping and passing are in the same place on every
    arrangement, including the one where somebody has hidden everything else."""
    found = opened(served, """
        const first = state.columns[0].name;
        const heads = document.querySelectorAll("table.grid thead th");
        heads[0].dispatchEvent(new MouseEvent("contextmenu", {bubbles: true}));
        await wait(200);
        const menu = document.querySelector(".menu");
        hide(first);
        await wait(200);
        const inChooser = (() => {
          chooseColumns();
          const dialog = document.querySelector("dialog.columns");
          const names = [...dialog.querySelectorAll("label")].map(l => l.textContent.trim());
          dialog.close();
          return names;
        })();
        return {first, still: state.columns[0].name, menu: !!menu, inChooser};
    """)

    assert found["still"] == found["first"], "the controls were hidden"
    assert not found["menu"], "right-clicking the control column offered to hide it"
    assert found["first"] not in found["inChooser"], "the chooser offered to hide the controls"


def test_the_table_ends_above_the_bottom_of_the_window(served) -> None:
    """feat-010/AC-53: a table this wide needs its sideways scrollbar to be reachable.

    The table's height was the window's minus a constant, and the constant was wrong: a heading, a
    paragraph of instructions and a controls row that wraps come to more than it, so the table's
    bottom edge sat below the bottom of the window. Everything about that is invisible except the
    one thing that is not, because the horizontal scrollbar lives on that edge. The only way to
    reach the far columns was to select text and drag.
    """
    found = opened(served, """
        const scroller = document.getElementById("scroller");
        const box = scroller.getBoundingClientRect();
        return {
          bottom: Math.round(box.bottom),
          windowHeight: window.innerHeight,
          scrollsSideways: scroller.scrollWidth > scroller.clientWidth,
          barHeight: scroller.offsetHeight - scroller.clientHeight,
          pageScrolls: document.documentElement.scrollHeight > window.innerHeight,
        };
    """)

    assert found["scrollsSideways"], "the table fits, so this measures nothing"
    assert found["barHeight"] > 0, "there is no horizontal scrollbar to be reachable"
    assert found["bottom"] <= found["windowHeight"], (
        f"the table's bottom edge, and its scrollbar with it, is "
        f"{found['bottom'] - found['windowHeight']}px below the bottom of the window"
    )
    assert not found["pageScrolls"], (
        "the page scrolls underneath the table, so the scrollbar moves as you reach for it"
    )


def test_the_columns_a_person_writes_in_can_be_written_in(served) -> None:
    """feat-011/AC-5: the five headings the household's own sheet has.

    They were carried as columns nothing filled, drawn empty on every row and marked as the
    person's to fill in, with no way to fill them in. The mark was a promise the page could not
    keep.
    """
    found = opened(served, """
        const wanted = ["Annual Taxes", "Crime/Safety", "Fire/Egress/Terrain",
                        "Sewage & Reclaimed-Water Exposure", "Garage/Outbuildings"];
        const row = state.shown[0];
        const at = state.columns.findIndex(c => c.name === "Annual Taxes");
        focusCell(0, at);
        const cell = document.querySelector('td[aria-selected="true"]');
        cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
        const panel = await until(() => document.querySelector(".writing"));
        const box = panel.querySelector("textarea");
        box.value = "$1,840 in 2025";
        box.dispatchEvent(new KeyboardEvent(
          "keydown", {key: "Enter", ctrlKey: true, bubbles: true}));
        await until(() => cell.className.includes("saved"));

        const answered = await fetch(`/api/listings/${row.listing_id}`).then(r => r.json());
        return {
          writable: wanted.every(name => Object.prototype.hasOwnProperty.call(EDITABLE, name)),
          stored: (answered.listing.annotation || {}).taxes ?? null,
          shown: row.values["Annual Taxes"],
        };
    """)

    assert found["writable"], "one of the five still cannot be typed into"
    assert found["stored"] == "$1,840 in 2025", "what was typed did not reach the store"
    assert found["shown"] == "$1,840 in 2025", "the row does not hold what the store returned"


def test_a_town_note_typed_on_one_row_appears_on_the_others(served) -> None:
    """feat-010/AC-19: because a note that only shows on the row it was typed on reads as a bug.

    Every other cell on a row is about that one house. This one is about the town, so it is saved
    to the town, and the rows around it have to take it too, there and then. Somebody who writes
    "the water here is hard", sees it on one of the nine houses they have open in that town, and
    concludes it went in wrong is right to conclude that.
    """
    found = opened(served, """
        const at = state.columns.findIndex(c => c.name === "Town Analysis Notes");
        const town = state.shown[0].values["Town/Area"];
        const alsoThere = state.all.filter(r => r.values["Town/Area"] === town).length;

        focusCell(0, at);
        const cell = document.querySelector('td[aria-selected="true"]');
        const before = cell.getAttribute("title");
        cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
        const panel = await until(() => document.querySelector(".writing"));
        const saysWhose = panel.textContent;
        const box = panel.querySelector("textarea");
        box.value = "the water here is hard";
        box.dispatchEvent(new KeyboardEvent(
          "keydown", {key: "Enter", ctrlKey: true, bubbles: true}));

        await until(() => state.all[1].values["Town Analysis Notes"]);
        const answered = await fetch("/api/areas").then(r => r.json());
        return {
          town, alsoThere, before, saysWhose,
          onFirst: state.all[0].values["Town Analysis Notes"],
          onSecond: state.all[1].values["Town Analysis Notes"],
          stored: (answered.areas || []).map(a => [a.area_type, a.area_value, a.notes]),
          banner: document.getElementById("banner").textContent,
        };
    """)

    assert found["alsoThere"] > 1, "one property in the town, so this proves nothing"
    assert found["onFirst"] == "the water here is hard"
    assert found["onSecond"] == "the water here is hard", "the town's other rows did not take it"
    assert ["city", found["town"], "the water here is hard"] in found["stored"], (
        "the note was not saved against the town"
    )
    assert "not about this house" in (found["before"] or ""), (
        "the cell does not say the note belongs to the town before it is opened"
    )
    assert "every property there shows it" in found["saysWhose"], (
        "the box being written in does not say the note belongs to the town"
    )
    assert found["town"] in found["banner"], "nothing said what was written or where it went"


def test_a_cell_past_the_fold_can_still_be_typed_into(served) -> None:
    """feat-010/AC-5, feat-010/AC-17: a column you have to scroll to is a column you can edit.

    The failure this pins is complete and was invisible from the code. Putting focus in the box
    scrolls the table sideways to bring it into view; scrolling is what redraws the window; a redraw
    replaces every row, the one being edited included. So the box opened and vanished in the same
    frame, and every column past the right edge could not be typed into at all. Double-clicking
    appeared to work only because it happened to leave the cell where it already was.

    Asserted after a wait rather than in the same tick, because the scroll event that did the damage
    is asynchronous: a test that reads the box immediately gets the one that is about to be thrown
    away, and passes while the feature is broken. That is exactly what the existing edit tests did.
    """
    found = opened(served, """
        const scroller = document.getElementById("scroller");
        scroller.scrollLeft = 0;
        await wait(200);

        /* A column well past the right edge of the screen. */
        const at = state.columns.findIndex(c => c.name === "Annual Taxes");
        const head = document.querySelectorAll("table.grid thead th")[at];
        const offScreen = head.offsetLeft > scroller.clientWidth;

        focusCell(0, at);
        await wait(150);
        const cell = document.querySelector('td[aria-selected="true"]');
        cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));

        const straightAway = !!document.querySelector(".writing textarea");
        await wait(400);
        const box = document.querySelector(".writing textarea");
        if (box) {
          box.value = "$1,840 in 2025";
          box.dispatchEvent(new KeyboardEvent(
            "keydown", {key: "Enter", ctrlKey: true, bubbles: true}));
          await until(() => state.all.some(r => r.values["Annual Taxes"]));
        }
        return {offScreen, straightAway,
                survived: !!box,
                stored: state.shown[0].values["Annual Taxes"] ?? null,
                redrawn: !document.querySelector(".writing")};
    """)

    assert found["offScreen"], "the column was already on screen, so this measures nothing"
    assert found["straightAway"], "the box never opened at all"
    assert found["survived"], (
        "the box opened and was thrown away by the redraw that focusing it caused"
    )
    assert found["stored"] == "$1,840 in 2025", "what was typed did not reach the store"
    assert found["redrawn"], "the window never caught up after the edit finished"


def test_escaping_an_edit_puts_the_table_back(served) -> None:
    """feat-010/AC-5: the window holds still during an edit, so it has to start again after one.

    The other half of that guard. It reads "is somebody typing" off the box being in the page, so an
    abandoned edit has to take its box out, or the table freezes on an edit nobody is making.
    """
    found = opened(served, """
        const at = state.columns.findIndex(c => c.name === "Verdict");
        focusCell(0, at);
        await wait(150);
        const cell = document.querySelector('td[aria-selected="true"]');
        cell.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
        await wait(200);
        const opened_ = !!document.querySelector(".writing textarea");

        document.querySelector(".writing textarea")
          .dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
        await wait(200);

        /* And the window works again: scrolling redraws the rows it should. */
        const scroller = document.getElementById("scroller");
        const before = document.querySelector("#body tr").dataset.index;
        scroller.scrollTop = 4000;
        await wait(300);
        return {opened_, closed: !document.querySelector(".writing"),
                before, after: document.querySelector("#body tr").dataset.index};
    """)

    assert found["opened_"], "the box never opened"
    assert found["closed"], "Escape left the box in the page"
    assert found["after"] != found["before"], (
        "the table stopped redrawing, so it is frozen on an edit nobody is making"
    )


# ---------------------------------------------------------------------------
# Real input, rather than events the page dispatches to itself
#
# Everything above drives the page by dispatching events from inside it, which is enough for almost
# everything and was not enough here. A double-click is not an event a page can honestly fake: it is
# the browser's own judgment that two clicks landed on the same element, and the bug below lived
# entirely in that judgment. A dispatched `dblclick` skips it and passes on a page where clicking
# twice does nothing at all. So these go through the browser's input pipeline instead.


def command(connection, method, params=None, message_id=1):
    connection.send(
        json.dumps({"id": message_id, "method": method, "params": params or {}})
    )
    while True:
        found = json.loads(connection.recv())
        if found.get("id") == message_id:
            return found.get("result", {})


def click_at(connection, x, y, clicks=1):
    """A real mouse click, at real coordinates, with a real click count."""
    for kind in ("mousePressed", "mouseReleased"):
        command(
            connection,
            "Input.dispatchMouseEvent",
            {"type": kind, "x": x, "y": y, "button": "left", "clickCount": clicks},
        )


def press_enter(connection):
    for kind in ("keyDown", "keyUp"):
        command(
            connection,
            "Input.dispatchKeyEvent",
            {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
        )


def test_double_clicking_a_cell_opens_it_for_editing(served) -> None:
    """feat-010/AC-5: the way a person expects to edit a cell, and the way that never worked.

    Selecting a cell used to redraw the whole window, so the first click of a double-click replaced
    every row in the table. The second click therefore landed on a different element from the first,
    and a browser only reports a double-click when both halves hit the same one. So double-clicking
    a cell did nothing, on every editable column, and had done nothing since the table was written.

    It survived every test because a test can dispatch a `dblclick` event directly, and one that
    does asserts that the handler works rather than that the browser ever calls it. This one clicks.
    """
    base, _held, _store = served

    process, debug = chrome(f"{base}/results/portales")
    try:
        connection = talk(debug, "/results/portales")
        evaluate(
            connection,
            """(async () => {
                 for (let i = 0; i < 200; i++) {
                   if (document.querySelector("#body tr")) break;
                   await new Promise(r => setTimeout(r, 100));
                 }
                 /* Scrolled to, the way somebody reading that column would have. */
                 const at = state.columns.findIndex(c => c.name === "Verdict");
                 const scroller = document.getElementById("scroller");
                 const head = document.querySelectorAll("table.grid thead th")[at];
                 scroller.scrollLeft = head.offsetLeft - scroller.clientWidth / 2;
                 await new Promise(r => setTimeout(r, 400));
                 return true;
               })()""",
        )
        where = evaluate(
            connection,
            """(() => {
                 const at = state.columns.findIndex(c => c.name === "Verdict");
                 const cell = document.querySelector("#body tr:nth-child(2)").children[at];
                 const box = cell.getBoundingClientRect();
                 return {x: Math.round(box.left + box.width / 2),
                         y: Math.round(box.top + box.height / 2),
                         column: cell.dataset.column};
               })()""",
        )
        assert where["column"] == "Verdict", where

        click_at(connection, where["x"], where["y"], clicks=1)
        click_at(connection, where["x"], where["y"], clicks=1)
        click_at(connection, where["x"], where["y"], clicks=2)
        time.sleep(0.4)
        opened_ = evaluate(connection, '!!document.querySelector(".writing textarea")')

        command(connection, "Input.insertText", {"text": "worth a look"})
        # Saved from the button, which is what a person's hand does after typing a note.
        evaluate(
            connection,
            """[...document.querySelectorAll(".writing button")]
                 .find(b => b.textContent === "Save").click()""",
        )
        time.sleep(1.0)
        found = evaluate(
            connection,
            """(async () => {
                 const row = state.shown[1];
                 const answered = await fetch(`/api/listings/${row.listing_id}`)
                   .then(r => r.json());
                 return {shown: row.values["Verdict"],
                         stored: (answered.listing.annotation || {}).verdict ?? null};
               })()""",
        )
    finally:
        process.terminate()

    assert opened_, "double-clicking a cell did not open it for editing"
    assert found["stored"] == "worth a look", "what was typed did not reach the store"
    assert found["shown"] == "worth a look", "the row does not hold what the store returned"


def test_clicking_a_cell_does_not_rebuild_the_rows(served) -> None:
    """feat-010/AC-5: the reason double-clicking could not work, pinned directly.

    Selecting is two attributes on two cells. It has no business replacing every row in the table,
    and while it did, no interaction that depends on two events reaching the same element could
    survive it.
    """
    found = opened(served, """
        const before = document.querySelector("#body tr").children[3];
        focusCell(0, 3);
        await wait(200);
        const after = document.querySelector("#body tr").children[3];
        return {sameElement: before === after,
                selected: after.getAttribute("aria-selected"),
                focused: document.activeElement === after};
    """)

    assert found["sameElement"], (
        "selecting a cell replaced the row it is in, so a second click lands somewhere else"
    )
    assert found["selected"] == "true", "the cell was not selected"
    assert found["focused"], "the keyboard did not follow the selection"


def test_passing_on_a_house_records_why(served) -> None:
    """feat-010/AC-54: the reason is asked for where the decision is made, and kept.

    A reason recorded a week later is a reconstruction. This is the most valuable thing anybody
    writes in this tool and the easiest to lose, so it is asked for in the same breath as the
    decision, in the box the cursor is already in, and it lands in the column that has always meant
    "what I concluded about this house".
    """
    found = opened(served, """
        const listing = state.shown[0].listing_id;
        document.querySelector("#body tr button.pass").click();
        const dialog = await until(() => document.querySelector("dialog.ask"));
        const box = dialog.querySelector("textarea");
        box.value = "roof is flat at the back and the lot backs onto the highway";
        [...dialog.querySelectorAll("button")].find(b => b.textContent === "Pass on it").click();

        await until(() => state.all.find(r => r.listing_id === listing).judgment === "pass");
        await until(() => state.all.find(r => r.listing_id === listing).values["Verdict"]);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {judgment: (answered.listing.annotation || {}).judgment ?? null,
                verdict: (answered.listing.annotation || {}).verdict ?? null};
    """)

    assert found["judgment"] == "pass"
    assert found["verdict"] == "roof is flat at the back and the lot backs onto the highway"


def test_passing_without_a_reason_still_passes(served) -> None:
    """feat-010/AC-54: wanted, never demanded. Clearing forty houses must not mean typing forty."""
    found = opened(served, """
        const listing = state.shown[0].listing_id;
        document.querySelector("#body tr button.pass").click();
        const dialog = await until(() => document.querySelector("dialog.ask"));
        [...dialog.querySelectorAll("button")].find(b => b.textContent === "Pass on it").click();

        await until(() => state.all.find(r => r.listing_id === listing).judgment === "pass");
        await wait(400);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {judgment: (answered.listing.annotation || {}).judgment ?? null,
                verdict: (answered.listing.annotation || {}).verdict ?? null};
    """)

    assert found["judgment"] == "pass", "an unexplained pass did not pass"
    assert found["verdict"] is None, "an empty box wrote an empty reason over the verdict"


def test_keeping_a_house_records_the_keep_before_asking_why(served) -> None:
    """feat-010/AC-54, feat-010/AC-49: the shortlist stays cheap to build.

    Keeping hides nothing and the same button undoes it, so there is nothing to confirm. The house
    is on the list the moment the star is pressed, and the box that opens afterwards is an offer:
    Escape leaves it kept and unexplained.
    """
    found = opened(served, """
        const listing = state.shown[0].listing_id;
        document.querySelector("#body tr button.keep").click();
        await until(() => state.all.find(r => r.listing_id === listing).judgment === "keep");
        const keptBeforeAnyTyping =
          (await fetch(`/api/listings/${listing}`).then(r => r.json()))
            .listing.annotation.judgment;

        const panel = await until(() => document.querySelector(".writing"));
        const asks = panel.textContent;
        const box = panel.querySelector("textarea");
        box.value = "metal roof, five acres, and the well is new";
        [...panel.querySelectorAll("button")].find(b => b.textContent === "Save").click();

        await until(() => state.all.find(r => r.listing_id === listing).values["Verdict"]);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {keptBeforeAnyTyping, asks,
                judgment: (answered.listing.annotation || {}).judgment ?? null,
                verdict: (answered.listing.annotation || {}).verdict ?? null,
                stillShown: !!state.shown.find(r => r.listing_id === listing)};
    """)

    assert found["keptBeforeAnyTyping"] == "keep", (
        "the keep waited on the reason, so a shortlist costs a sentence per house"
    )
    assert "Why keep it?" in found["asks"], "nothing asked why"
    assert found["judgment"] == "keep"
    assert found["verdict"] == "metal roof, five acres, and the well is new"
    assert found["stillShown"], "keeping a house took it out of the table"


def test_escaping_the_reason_leaves_the_house_kept(served) -> None:
    """feat-010/AC-54: the reason is an offer, and an offer has to be refusable."""
    found = opened(served, """
        const listing = state.shown[0].listing_id;
        document.querySelector("#body tr button.keep").click();
        const panel = await until(() => document.querySelector(".writing"));
        panel.querySelector("textarea").dispatchEvent(
          new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
        await until(() => !document.querySelector(".writing"));
        await wait(300);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {judgment: (answered.listing.annotation || {}).judgment ?? null,
                verdict: (answered.listing.annotation || {}).verdict ?? null};
    """)

    assert found["judgment"] == "keep", "refusing to say why undid the keep"
    assert found["verdict"] is None


def on_the_map(served, script):
    """Run one script against a loaded fire map, and always close the browser."""
    base, _held, _store = served
    process, debug = chrome(f"{base}/fire/portales")
    try:
        connection = talk(debug, "/fire/portales")
        return evaluate(
            connection,
            """(async () => {
                 const wait = (ms) => new Promise(r => setTimeout(r, ms));
                 const until = async (ready, patience = 100) => {
                   for (let i = 0; i < patience; i++) {
                     const found = ready();
                     if (found) return found;
                     await wait(50);
                   }
                   return null;
                 };
                 await until(() => held.markers && held.rows.length);
                 """ + script + """
               })()""",
        )
    finally:
        process.terminate()


def test_a_property_is_passed_on_from_its_pin(served) -> None:
    """feat-010/AC-56: the decision is made where the reason for it is visible.

    "Half a mile from the red" is a thing somebody can see in a second on this page and cannot
    easily say from a table of numbers, which is the whole argument for deciding here at all. So
    the pin offers the same decision the table does, asks the same question about why, and records
    both in the same place.
    """
    found = on_the_map(served, """
        const row = held.rows[0];
        const listing = row.listing_id;
        const before = held.markers.getLayers().length;

        /* Open the pin, then answer what it asks. */
        held.markers.getLayers()[0].openPopup();
        const bubble = await until(() => document.querySelector(".pin"));
        [...bubble.querySelectorAll("button")].find(b => b.textContent.includes("pass")).click();

        const dialog = await until(() => document.querySelector("dialog.ask"));
        const asks = dialog.textContent;
        dialog.querySelector("textarea").value = "half a mile from the red";
        [...dialog.querySelectorAll("button")].find(b => b.textContent === "Pass on it").click();

        await until(() => held.markers.getLayers().length !== before);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {asks, before, after: held.markers.getLayers().length,
                judgment: (answered.listing.annotation || {}).judgment ?? null,
                verdict: (answered.listing.annotation || {}).verdict ?? null};
    """)

    assert "Pass on this property?" in found["asks"]
    assert found["judgment"] == "pass"
    assert found["verdict"] == "half a mile from the red"
    assert found["after"] == found["before"] - 1, "the pin stayed on the map after being passed on"


def test_the_map_draws_the_properties_and_says_what_it_cannot(served) -> None:
    """feat-010/AC-55: a property with no location is not on the map and is not silently gone.

    The count line is the whole of it. A map that quietly drops the properties it cannot place
    tells somebody they have looked at everything when they have not.
    """
    found = on_the_map(served, """
        return {pins: held.markers.getLayers().length,
                rows: held.rows.length,
                without: held.without,
                says: document.getElementById("counts").textContent,
                legend: document.querySelector(".legend").textContent,
                tiles: !!held.hazard};
    """)

    assert found["pins"] == found["rows"] > 0
    assert "on the map" in found["says"]
    assert found["tiles"], "no hazard layer was added, so the map is properties over nothing"
    for word in ("very high", "non-burnable", "kept", "passed on"):
        assert word in found["legend"], f"the legend does not explain {word}"


def body_of(source: str, name: str) -> str:
    """One function out of a source file, by counting its braces.

    Crude on purpose. The alternative is a JavaScript parser in the test suite, and what is being
    asked here is narrow enough that brace counting answers it exactly: what does *this* function
    have in it.
    """
    at = source.index(f"function {name}(")
    depth = 0
    for end in range(source.index("{", at), len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[at : end + 1]
    raise AssertionError(f"{name} has no end")


def test_the_map_scores_nothing_and_hides_nothing_on_its_own(served) -> None:
    """feat-010/AC-56: a page that quietly ranked houses by how close they are to red would be a
    criterion with no rule behind it and no way to argue with it.

    So what a pin looks like is read off the person's own judgment and off nothing else.

    This used to be asserted by banning the word "distance" anywhere in the file, and that stopped
    being the same claim the moment the page grew a ruler somebody drags and a wind overlay that
    asks about the stations nearest the middle of the screen. Both of those measure distances; the
    difference is who is doing the measuring and what it decides. So the ban moved to where the
    claim actually lives: the one function that turns a property into a pin.
    """
    fire = (STATIC / "fire.js").read_text(encoding="utf-8")
    drawing = body_of(fire, "plot")

    assert "PINS[row.judgment" in drawing, "a pin's appearance is not read from the judgment"
    for arithmetic in ("distance", "nearest", "score", "Math.hypot", "hazard"):
        assert arithmetic not in drawing, (
            f"{arithmetic!r} in the function that draws a property means this page works something "
            "out about that property, which is a criterion in disguise"
        )
    assert drawing.count("continue") == 1, (
        "a property is left off this map for more than one reason, and the one reason allowed is "
        "the judgment the person made themselves"
    )
    assert 'row.judgment === "pass"' in drawing

    for anywhere in ("Math.hypot", "score(", "nearestHazard", "hazardNear"):
        assert anywhere not in fire, (
            f"{anywhere!r} suggests this page works out how close a property is to something"
        )
def test_a_column_is_narrowed_by_typing_into_its_filter(served) -> None:
    """feat-010/AC-57: one search box cannot ask about one column.

    Typing a town into the box at the top finds the properties in it, the ones whose description
    mentions it and the ones whose agent works there, and there is no way to say which was meant.
    So each heading carries its own, the button is drawn on every column rather than appearing on
    hover, and what it is narrowed to is written out above the table in words: a table quietly
    missing four hundred rows is the worst thing this screen can do.
    """
    found = opened(served, """
        const all = state.shown.length;
        const at = state.columns.findIndex(c => c.name === "Property");
        const th = document.querySelectorAll("table.grid thead th")[at];

        th.querySelector(".sift").click();
        const panel = await until(() => document.querySelector(".sifter"));
        const box = panel.querySelector("input");
        box.value = "p0001";
        box.dispatchEvent(new Event("input", {bubbles: true}));
        await until(() => state.shown.length !== all);

        const bar = document.getElementById("sifted");
        let remembered = null;
        try { remembered = window.localStorage.getItem(keep()); } catch (e) { remembered = null; }

        return {
          all,
          narrowed: state.shown.length,
          addresses: state.shown.map(r => r.values["Property"]),
          marked: th.classList.contains("filtered"),
          button: th.querySelector(".sift").getAttribute("aria-label"),
          buttons: document.querySelectorAll("table.grid thead th .sift").length,
          columns: state.columns.length,
          said: bar.hidden ? "" : bar.textContent,
          drawn: document.querySelectorAll("#body tr").length,
          remembered: remembered || "",
        };
    """)

    assert found["all"] == 60, found["all"]
    assert found["narrowed"] == 10, "the filter did not narrow the table to the ten matching rows"
    assert all("p0001" in address for address in found["addresses"])
    assert found["drawn"] == found["narrowed"], "the rows drawn do not match the rows kept"
    assert found["marked"], "the filtered column is not marked on its heading"
    assert "p0001" in found["button"], (
        "the button says nothing about what it is filtering, so the state is colour alone"
    )
    assert "Property" in found["said"] and "p0001" in found["said"], (
        f"the filter is not named above the table: {found['said']!r}"
    )
    assert "clear all filters" in found["said"]
    assert found["buttons"] == found["columns"] - 1, (
        "every column but the keep-or-pass control should carry a filter button"
    )
    assert "p0001" not in found["remembered"], (
        "the filter was written into this browser's storage, so it would come back days later "
        "and hide rows for a reason nobody remembers setting"
    )


def test_one_press_lifts_every_filter(served) -> None:
    """feat-010/AC-57: a person whose rows have gone missing needs one thing to press.

    The whole-table search box goes with the column filters, which is the whole point of it: a
    filter here and a search box up there, with no way of knowing which is still holding, is how
    somebody concludes the tool has lost their properties.
    """
    found = opened(served, """
        const all = state.shown.length;
        const search = document.getElementById("filter");
        search.value = "Example";
        search.dispatchEvent(new Event("input", {bubbles: true}));
        setFilter("Property", "p0001");
        setFilter("Town/Area", "nowhere at all");
        await until(() => state.shown.length === 0);

        const bar = document.getElementById("sifted");
        const chips = bar.querySelectorAll(".chip").length;
        const said = bar.textContent;

        bar.querySelector(".clearall").click();
        await until(() => state.shown.length === all);

        return {all, chips, said,
                after: state.shown.length,
                query: document.getElementById("filter").value,
                filters: Object.keys(state.filters).length,
                packed: bar.hidden,
                marked: document.querySelectorAll("table.grid thead th.filtered").length};
    """)

    assert found["all"] == 60
    assert found["chips"] == 3, "the search box is not listed beside the column filters"
    assert "any column" in found["said"], "the whole-table search is not named in the list"
    assert found["after"] == found["all"], "clearing every filter did not bring the rows back"
    assert found["query"] == "", "the search box still held its text after every filter was lifted"
    assert found["filters"] == 0
    assert found["packed"], "the list of filters stayed on screen with nothing in it"
    assert found["marked"] == 0, "a heading still says it is filtered"


def test_a_filter_matches_the_cell_as_it_is_shown(served) -> None:
    """feat-010/AC-57, feat-010/AC-10: somebody types what is in front of them.

    A price reads $425,000 and is held as the number 425000, and a filter that answered nothing to
    the first of those would be the wrong one. The same rule makes the other question askable: a
    column this tool could not fill prints "not known", so typing that finds exactly the properties
    nobody could determine it for, which is a question that has been asked out loud more than once.
    A column the person writes in themselves is the exception, because an empty one there was never
    unknown; nobody set out to determine it.
    """
    found = opened(served, """
        const priced = state.all[0].values["Price"];
        const asMoney = "$" + Number(priced).toLocaleString();
        setFilter("Price", asMoney);
        const money = {typed: asMoney, rows: state.shown.length};
        setFilter("Price", String(priced));
        const plain = state.shown.length;
        setFilter("Price", "");

        const blank = (row, name) => {
          const held = row.values[name];
          return held === null || held === undefined || held === "";
        };
        const empty = state.columns.find(c =>
          c.origin !== "annotation" && c.origin !== "control" &&
          state.all.every(r => blank(r, c.name)));
        setFilter(empty.name, "not known");
        const unknown = {column: empty.name, rows: state.shown.length};
        setFilter(empty.name, "");

        const mine = state.columns.find(c => c.origin === "annotation");
        setFilter(mine.name, "not known");
        const yours = {column: mine.name, rows: state.shown.length};
        setFilter(mine.name, "");

        setFilter("Town/Area", "PORTALES");
        const shouted = state.shown.length;

        clearFilters();
        return {money, plain, unknown, yours, shouted, back: state.shown.length};
    """)

    assert found["money"]["rows"] == 1, (
        f"a price typed the way it is printed ({found['money']['typed']}) matched "
        f"{found['money']['rows']} rows"
    )
    assert found["plain"] == 1, "the same price typed as bare digits did not match"
    assert found["unknown"]["rows"] == 60, (
        f"\"not known\" found {found['unknown']['rows']} of the 60 rows in "
        f"{found['unknown']['column']}, which is empty for every one of them"
    )
    assert found["yours"]["rows"] == 0, (
        f"\"not known\" matched empty cells in {found['yours']['column']}, a column nobody was "
        "ever going to fill in but the person themselves"
    )
    assert found["shouted"] == 60, "the filter was fussy about upper and lower case"
    assert found["back"] == 60
def test_the_map_says_how_far_things_are(served) -> None:
    """feat-010/AC-58: a fire map with no distances on it asks a question it cannot answer.

    Two of them, because they answer different halves. The bar in the corner says how big the
    screen is, which is the question at a glance and the one that changes every time somebody
    zooms. The ruler answers the question actually being asked, which is how far this house is
    from that red: a bar fixed in a corner cannot be held up against two things somewhere else on
    the map, so this one comes off the corner and is dragged to them.
    """
    found = on_the_map(served, """
        held.map.setView([34.18, -103.34], 11);
        await until(() => true);
        const bar = document.querySelector(".leaflet-control-scale");
        const wide = bar.textContent;

        held.map.setZoom(8);
        await until(() => document.querySelector(".leaflet-control-scale").textContent !== wide);
        const far = document.querySelector(".leaflet-control-scale").textContent;

        document.getElementById("ruler").click();
        await until(() => document.querySelector(".rule-middle"));

        /* Two points a known way apart: a tenth of a degree of latitude is 11.1 km, near enough
           to seven miles, and it is the same everywhere so this does not depend on where it is. */
        rule.a.setLatLng(L.latLng(34.10, -103.34));
        rule.b.setLatLng(L.latLng(34.20, -103.34));
        reread();
        await until(() => rule.middle.getTooltip());

        const reading = rule.middle.getTooltip().getContent().textContent;
        const metres = Math.round(held.map.distance(rule.a.getLatLng(), rule.b.getLatLng()));
        const middleWas = rule.middle.getLatLng();

        /* Carry the whole thing somewhere else: both ends move together and the length does not. */
        rule.middle.fire("dragstart");
        rule.middle.setLatLng(L.latLng(34.30, -103.10));
        rule.middle.fire("drag");
        await until(() => true);
        const moved = rule.middle.getTooltip().getContent().textContent;
        const ends = [String(rule.a.getLatLng()), String(rule.b.getLatLng())];

        /* And it comes off again. */
        document.getElementById("ruler").click();
        await until(() => !document.querySelector(".rule-middle"));

        return {wide, far, reading, metres, moved, ends,
                middleWas: String(middleWas),
                gone: !document.querySelector(".rule-end"),
                short: howFar(L.latLng(34.10, -103.34), L.latLng(34.1004, -103.34))};
    """)

    assert "mi" in found["wide"], f"the scale is not in miles: {found['wide']!r}"
    assert found["far"] != found["wide"], "the scale did not change when the map was zoomed out"
    assert 11_000 < found["metres"] < 11_300, found["metres"]
    assert found["reading"] == "6.91 miles", found["reading"]
    assert found["moved"] == found["reading"], (
        "carrying the ruler somewhere else changed how long it is"
    )
    assert "34.25" in found["ends"][0] and "34.35" in found["ends"][1], found["ends"]
    assert found["gone"], "switching it off left the ruler on the map"
    assert "feet" in found["short"], (
        f"a distance shorter than a house's frontage was given in miles: {found['short']!r}"
    )


def test_the_list_under_the_map_holds_exactly_what_the_map_is_showing(served) -> None:
    """feat-010/AC-62: a pin is very good at "where" and says nothing until it is opened.

    Reading a screenful of them means clicking every one, which is the thing that made somebody
    ask for a list. The rule that makes the list worth having rather than confusing is that it is
    not a second table with its own idea of what is going on: it holds the pins the map is drawing,
    hides what the map hides, and re-reads itself when the map moves.

    Pinned by moving somewhere with nothing on it. A list that stayed full there would be a list
    about the run rather than about the screen, which is a different and much less useful thing.
    """
    found = on_the_map(served, """
        const heading = () => document.getElementById("listcount").textContent;
        const rows = () => document.querySelectorAll("table.onscreen tbody tr").length;

        await until(() => rows());
        const everywhere = rows();
        const said = heading();

        /* The middle of the Pacific. Nothing this run found is there. */
        held.map.setView([0, -150], 6);
        await until(() => rows() === 0);
        const nowhere = rows();
        const empty = document.querySelector(".onmap .notice") ? heading() : "";

        held.map.setView([34.1862, -103.3452], 12);
        await until(() => rows() > 0);

        /* Cheapest first, and the button on the row is what opens its pin. */
        const money = "table.onscreen tbody tr td.numeric:first-of-type";
        const prices = [...document.querySelectorAll(money)]
          .map((cell) => Number(cell.textContent.replace(/[^0-9]/g, "")))
          .filter((one) => one > 0);
        const opener = document.querySelector("table.onscreen td.address button");
        const address = opener.textContent;
        opener.click();
        const bubble = await until(() => document.querySelector(".leaflet-popup .pin"));

        return {everywhere, said, nowhere, empty, prices,
                back: rows(),
                address,
                opened: bubble ? bubble.textContent : ""};
    """)

    assert found["everywhere"] > 0, "the list under the map was empty with pins on the map"
    assert "propert" in found["said"], found["said"]
    assert found["nowhere"] == 0, (
        "the list still held properties over an empty ocean, so it is a list about the run rather "
        "than about what is on screen"
    )
    assert "No properties" in found["empty"] or "Nothing" in found["empty"], found["empty"]
    assert found["back"] > 0, "coming back to where the properties are did not refill the list"

    assert found["prices"] == sorted(found["prices"]), (
        f"the list is not cheapest first: {found['prices']}"
    )
    assert found["opened"], "the row's button did not open that property's pin"


def test_the_counties_and_towns_and_rain_are_drawn_over_the_fire(served, monkeypatch) -> None:
    """feat-010/AC-60, feat-010/AC-61: the map is a wall of colour with no words on it.

    The basemap has town names and they are underneath a raster whose whole job is to be opaque
    enough to read, so the moment this map becomes useful it also becomes anonymous. These are the
    names put back on top, with the one number the hazard model cannot give: how dry the ground is.

    Two things are checked that a screenshot would not settle. A label must take no pointer at all,
    because a name sitting over a town would otherwise make the houses in that town unopenable,
    and that fault looks exactly like a mis-click. And turning the rain on has to turn the names on
    with it, box and all, because the number is written under a county's name.
    """
    from homescout.enrich import ground

    counties = json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "properties": {"BASENAME": "Roosevelt", "COUNTY": "041",
                           "CENTLAT": "+34.1862", "CENTLON": "-103.3452"},
            "geometry": {"type": "Polygon",
                         "coordinates": [[[-103.9, 33.8], [-102.9, 33.8], [-102.9, 34.6],
                                          [-103.9, 34.6], [-103.9, 33.8]]]},
        }],
    })
    #: Two towns, one of them sitting exactly where the county's own name goes. That one must not
    #: be drawn: two names in the same place is neither name, and the county is the one that wins
    #: because somebody who cannot read the town can still see which county they are in.
    towns = json.dumps({"features": [
        {"attributes": {"BASENAME": "Clovis, NM", "AREALAND": "30000000",
                        "CENTLAT": "+34.4048", "CENTLON": "-103.2052"}},
        {"attributes": {"BASENAME": "Portales, NM", "AREALAND": "20000000",
                        "CENTLAT": "+34.1862", "CENTLON": "-103.3452"}},
    ]})
    rain = json.dumps({
        "description": {"title": "Roosevelt County, New Mexico January-December Precipitation"},
        "data": {f"{year}12": {"value": 16.0} for year in range(1990, 2026)},
    })

    def fetched(url: str, what: str) -> bytes:
        if "/88/query" in url:
            return towns.encode()
        if "pcp/ann" in url:
            return rain.encode()
        return counties.encode()

    monkeypatch.setattr(ground, "_fetch", fetched)

    found = on_the_map(served, """
        held.map.setView([34.1862, -103.3452], 9);
        await until(() => true);

        /* The rain alone, to prove it brings the names with it. The wait is for the number and
           not for the label: the names are drawn the moment the county lines land and the rain is
           a second, slower request, so waiting for the label catches the map halfway. */
        document.getElementById("rain").click();
        await until(() => document.querySelector(".mapname.county .rain"), 300);
        const county = document.querySelector(".mapname.county");

        const box = county.getBoundingClientRect();
        const under = document.elementFromPoint(Math.round(box.left + box.width / 2),
                                                Math.round(box.top + box.height / 2));

        return {namesTicked: document.getElementById("names").checked,
                counties: document.querySelectorAll(".mapname.county").length,
                towns: document.querySelectorAll(".mapname.town").length,
                outlines: land.shapes.getLayers().length,
                said: county.textContent,
                townSaid: (document.querySelector(".mapname.town") || {}).textContent || "",
                note: document.getElementById("landcount").textContent,
                throughIt: !!(under && !under.closest(".mapname"))};
    """)

    assert found["namesTicked"], (
        "the rain was turned on and the names were not, so the number is written under nothing"
    )
    assert found["counties"] == 1 and found["outlines"] >= 1, found
    assert found["towns"] == 1, (
        "the town whose name sits exactly under the county's was drawn anyway, so both are "
        f"unreadable: {found['towns']} town labels"
    )

    assert "ROOSEVELT" in found["said"].upper(), found["said"]
    assert "16.0 in" in found["said"], (
        f"the rainfall is missing or has no unit on it: {found['said']!r}"
    )
    assert "Clovis" in found["townSaid"] and ", NM" not in found["townSaid"], (
        f"the town is not named the way somebody says it: {found['townSaid']!r}"
    )
    assert "30 years" in found["note"], found["note"]

    assert found["throughIt"], (
        "a pointer at the middle of a map label lands on the label, so a name over a town makes "
        "every house in that town impossible to open"
    )


def facing(monkeypatch, table: str, stations: str):
    """The weather archive, replaced, in the server this browser is talking to.

    The server runs in a thread of this same process, so replacing the fetch here replaces it
    there. Which is the whole reason this test can exist: a rose is a ten-second query on somebody
    else's public archive and no test suite should ever make one.
    """
    from homescout.enrich import wind

    def fetched(url: str, what: str) -> bytes:
        return (stations if url.endswith(".geojson") else table).encode()

    monkeypatch.setattr(wind, "_fetch", fetched)


def test_the_wind_is_drawn_where_it_is_measured_and_says_which_way(served, monkeypatch) -> None:
    """feat-010/AC-59: which red matters depends on which way the weather moves through here.

    A house half a mile from a wall of red is in a different position depending on whether the wind
    normally comes over that red or normally carries away from it, and no value in this tool says
    which. So the stations that have measured it for thirty years are drawn where they are, and
    each one opens into what it actually recorded.

    Every claim on that bubble is a claim about decades, not about Thursday, which is the only
    version of this question worth putting in front of somebody buying a house.

    And which way it points is measured off the drawing, not off the caption. The fixture's wind
    comes out of the west, so a glyph that answers the question this page is asking leans east. A
    glyph leaning west is a wind rose: right by a convention older than anybody here, and read
    backwards by the person it is drawn for.

    One arrow here, not two. In this fixture the hard wind pushes the same way the everyday wind
    does, and drawing that twice would say there are two answers where there is one.
    """
    from test_web_wind import STATIONS, TABLE

    facing(monkeypatch, TABLE, STATIONS)

    found = on_the_map(served, """
        /* Over the stations. The properties in this fixture are in Portales and the stations in
           it are up by Taos, and the overlay deliberately only asks about what is on screen. */
        held.map.setView([36.44, -105.48], 9);
        await until(() => true);
        document.getElementById("wind").click();
        await until(() => document.querySelector(".windarrow svg"), 200);

        const glyph = document.querySelector(".windarrow");
        const box = glyph.getBoundingClientRect();
        const paths = glyph.querySelectorAll("path").length;

        /* Which way the thing actually points, off its own geometry. Each arrow is one closed
           outline, so the middle of its box is somewhere along its own shaft, and where that sits
           relative to the station is the whole claim this overlay makes. */
        const svg = glyph.querySelector("svg");
        const mid = svg.viewBox.baseVal.width / 2;
        let leans = {x: 0, y: 0}, furthest = -1;
        for (const path of svg.querySelectorAll("path")) {
          const at = path.getBBox();
          const away = {x: at.x + at.width / 2 - mid, y: at.y + at.height / 2 - mid};
          const out = Math.hypot(away.x, away.y);
          if (out > furthest) { furthest = out; leans = away; }
        }
        /* What a real pointer would land on. A rose behind the map's own surface is decoration:
           it draws, it never opens, and only a hit test finds that. */
        const hit = document.elementFromPoint(Math.round(box.left + box.width / 2),
                                              Math.round(box.top + box.height / 2));

        glyph.dispatchEvent(new MouseEvent("click", {bubbles: true,
          clientX: box.left + box.width / 2, clientY: box.top + box.height / 2}));
        const bubble = await until(() => document.querySelector(".pin.wind"));

        return {roses: Object.keys(wind.roses).length,
                stations: wind.stations.length,
                paths,
                leans,
                reachable: !!(hit && hit.closest && hit.closest(".windarrow")),
                said: bubble ? bubble.textContent : "",
                legend: document.querySelector(".legend").textContent,
                season: document.getElementById("season").value};
    """)

    assert found["stations"] == 2, found["stations"]
    assert found["roses"] >= 1, "no station's record was drawn"
    assert found["paths"] == 1, (
        "the everyday wind and the hard wind push the same way in this fixture, so there is one "
        f"answer here and it should be drawn once: {found['paths']} arrows"
    )
    assert found["reachable"], (
        "a pointer at the middle of an arrow does not land on it, so it can never be opened"
    )
    assert found["season"] == "april", "the default is not the month that both blows and burns"

    assert found["leans"]["x"] > 3, (
        "the glyph does not lean east, and the wind in this fixture comes out of the west: it is "
        f"pointing back at where the air came from rather than where it goes ({found['leans']})"
    )
    assert abs(found["leans"]["y"]) < abs(found["leans"]["x"]), found["leans"]

    assert "Most often pushes toward the east" in found["said"], found["said"]
    assert "hourly readings" in found["said"], "the bubble does not say what it is a summary of"
    assert "pushes" in found["said"], (
        "the bubble never says which way a direction means, which inverts every conclusion "
        "somebody would draw from it"
    )
    assert "a fire would run" in found["legend"], (
        "the legend leaves the reader to work out what a direction means for a fire"
    )


def test_the_hard_wind_gets_its_own_arrow_when_it_pushes_somewhere_else(served, monkeypatch):
    """feat-010/AC-59: the one case where a station has two answers rather than one.

    "It normally pushes east, and when it blows hard enough to move a fire it pushes north" is two
    facts about one place and both of them decide which side of a house to worry about. Nothing
    else on this page can say that, and a single arrow cannot either.

    The other half of the rule is in the test above: when the hard wind agrees with the everyday
    wind, there is one answer and it is drawn once. Both halves matter, because a second arrow
    that is always there is not a second answer, it is decoration that looks like one.
    """
    from test_web_wind import STATIONS, TABLE

    #: The same station, with the hard wind moved round to the south. Everyday wind still out of
    #: the west and still the most common, so the pale arrow pushes east; the hard wind now comes
    #: out of the south, so the dark one pushes north.
    disagreeing = TABLE.replace(
        "259-280  ,         ,    8.000,    4.000,    0.000,    2.000,    4.000,    6.000",
        "259-280  ,         ,   12.000,    4.000,    0.000,    2.000,    1.000,    0.000",
    ).replace(
        "169-190  ,         ,    2.000,    4.000,    4.000,    6.000,    0.000,    0.000",
        "169-190  ,         ,    2.000,    4.000,    4.000,    2.000,    4.000,    0.000",
    )
    facing(monkeypatch, disagreeing, STATIONS)

    found = on_the_map(served, """
        held.map.setView([36.44, -105.48], 9);
        await until(() => true);
        document.getElementById("wind").click();
        await until(() => document.querySelector(".windarrow svg"), 200);

        const glyph = document.querySelector(".windarrow");
        const svg = glyph.querySelector("svg");
        const mid = svg.viewBox.baseVal.width / 2;
        const arrows = [...svg.querySelectorAll("path")].map((path) => {
          const at = path.getBBox();
          return {fill: path.getAttribute("fill"),
                  x: Math.round(at.x + at.width / 2 - mid),
                  y: Math.round(at.y + at.height / 2 - mid)};
        });

        const box = glyph.getBoundingClientRect();
        glyph.dispatchEvent(new MouseEvent("click", {bubbles: true,
          clientX: box.left + box.width / 2, clientY: box.top + box.height / 2}));
        const bubble = await until(() => document.querySelector(".pin.wind"));
        return {arrows, said: bubble ? bubble.textContent : ""};
    """)

    arrows = found["arrows"]
    assert len(arrows) == 2, f"the hard wind pushes somewhere else and was not drawn: {arrows}"

    everyday = [one for one in arrows if one["fill"] == "#a276cf"]
    hard = [one for one in arrows if one["fill"] == "#4c1d95"]
    assert len(everyday) == 1 and len(hard) == 1, arrows

    assert everyday[0]["x"] > 3 and abs(everyday[0]["y"]) < abs(everyday[0]["x"]), (
        f"the everyday wind is out of the west and its arrow does not push east: {everyday[0]}"
    )
    assert hard[0]["y"] < -3 and abs(hard[0]["x"]) < abs(hard[0]["y"]), (
        f"the hard wind is out of the south and its arrow does not push north: {hard[0]}"
    )

    assert "Most often pushes toward the east" in found["said"], found["said"]
    assert "most often pushes toward the north" in found["said"], found["said"]
