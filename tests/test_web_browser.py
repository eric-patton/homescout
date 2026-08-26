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


def test_the_map_scores_nothing_and_hides_nothing_on_its_own(served) -> None:
    """feat-010/AC-56: a page that quietly ranked houses by how close they are to red would be a
    criterion with no rule behind it and no way to argue with it.

    So what a pin looks like is read off the person's own judgment and off nothing else.
    """
    fire = (STATIC / "fire.js").read_text(encoding="utf-8")

    assert "PINS[row.judgment" in fire, "a pin's appearance is not read from the judgment"
    for arithmetic in ("distance", "nearest", "score", "Math.hypot", "radiusOf"):
        assert arithmetic not in fire, (
            f"{arithmetic!r} suggests this page works something out about proximity, which is a "
            "criterion in disguise"
        )
