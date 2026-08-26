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
    assert found["arranged"] == ["Keep or pass", "Rank", "Price", "Annual Taxes"], (
        "without a remembered arrangement the declared one is used, with the controls first and "
        "the unfilled columns last"
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
                 for (let i = 0; i < 200; i++) {
                   if (document.querySelector("#body tr")) break;
                   await wait(100);
                 }
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
        await wait(200);
        const dialog = document.querySelector("dialog.ask");
        const asked = {open: !!(dialog && dialog.open),
                       says: dialog ? dialog.textContent : "",
                       focused: document.activeElement
                                  ? document.activeElement.textContent : ""};

        dialog.dispatchEvent(new Event("cancel"));
        await wait(400);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        return {asked,
                stillThere: !!document.querySelector("#body tr"),
                gone: !document.querySelector("dialog.ask"),
                judgment: (answered.listing.annotation || {}).judgment ?? null};
    """)

    assert found["asked"]["open"], "passing on a house did not ask"
    assert "Pass on this property?" in found["asked"]["says"]
    assert "brings it back" in found["asked"]["says"], "the dialog does not say it is reversible"
    assert found["asked"]["focused"] == "Pass on it", "the dialog does not take focus"
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
        await wait(200);
        [...document.querySelectorAll("dialog.ask button")]
          .find(b => b.textContent === "Pass on it").click();
        await wait(600);
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
        await wait(600);
        const answered = await fetch(`/api/listings/${listing}`).then(r => r.json());
        const asked = !!document.querySelector("dialog.ask");
        document.getElementById("onlykept").click();
        await wait(300);
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
        await wait(400);
        document.querySelector("#body tr button.thumb").click();
        await wait(400);

        const dialog = document.querySelector("dialog.gallery");
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
        await wait(400);
        const again = document.querySelector("dialog.gallery");
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
        await wait(400);
        document.querySelector("#body tr button.thumb").click();
        await wait(400);
        return {opened: !!document.querySelector("dialog.gallery"),
                banner: document.getElementById("banner").textContent};
    """)

    assert not found["opened"], "an empty gallery was opened"
    assert "no photographs" in found["banner"], "nothing said why nothing happened"
