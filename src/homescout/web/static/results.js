"use strict";
/* The results table: every column, sorted and filtered here, and judgment written straight onto
 * the row being read.
 *
 * THE ROWS IN VIEW ARE THE ONLY ROWS IN THE DOM, and that is not an optimization, it is the design.
 * Measured in Chrome at 5,000 rows of 32 columns before any of this was written:
 *
 *     rebuild the whole table after a sort   3,766ms      budget: 200ms
 *     redraw only the visible window            25ms
 *
 * Sorting five thousand rows takes half a millisecond. Putting the answer on screen is where all
 * the time goes, and it goes there in proportion to how many elements exist. So the data lives in
 * an array, the DOM holds about sixty rows, and a spacer carries the full height so the scrollbar
 * is honest about how many properties there are. That last part is what makes this different from
 * pagination, which the spec rules out by name.
 *
 * The arithmetic that makes it work has one hard requirement: the height this file assumes a row
 * is and the height the stylesheet actually gives a row must be the same number. They were not.
 * This file placed rows every 22 pixels; the stylesheet asked for 26 and, because `height` on a
 * table cell is only a floor, a floated corner marker in the editable cells took the rendered row
 * to 43. So the rows crept twenty-one pixels per row out from under their own scrollbar, and the
 * end of a long table could not be reached at all. The number is now set here and read by the
 * stylesheet, which also fixes its line height to it, so there is one of it and it is exact.
 */

/* Row heights, in pixels, including the border every row carries. A row is one of these three and
 * never anything in between, because the whole virtual window rests on every row being the same
 * height as every other one. That is also why wrapping is clamped to a fixed number of lines rather
 * than left to grow: a table whose rows are each as tall as their longest cell cannot be placed by
 * arithmetic at all, and would have to measure every one of a thousand rows to know where any of
 * them go. */
const ROW_HEIGHT = 26;
const PHOTO_ROW_HEIGHT = 66;
const WRAP_LINES = 3;
const WRAP_LINE = 17;
const WRAP_ROW_HEIGHT = WRAP_LINES * WRAP_LINE + 5;
const OVERSCAN = 12;

/* Column widths, in pixels: what a column starts at before anybody drags it. Most are the same, and
 * the ones named here are the ones where the default is plainly wrong. An address cut off at the
 * house number is not an address, and four digits do not need eleven rems. */
const DEFAULT_WIDTH = 176;
const MIN_WIDTH = 52;
const WIDTHS = {
  "Rank": 62, "Status": 104, "Property": 340, "Town/Area": 132, "County/Region": 124,
  "Price": 104, "$/sq ft": 82, "Beds": 58, "Baths": 62, "Sq Ft": 76, "Year Built": 84,
  "Acres": 72, "Listing URL": 210, "Listing ID": 250, "Description": 420,
  "Price History & DOM": 210, "Flags": 210, "Sources": 130,
};

/* Which columns a person can write judgment into. The names are the export's, so the table and the
 * spreadsheet cannot disagree about what a column is called. */
const EDITABLE = {
  "Rank": "rank",
  "Verdict": "verdict",
  "Red Flags": "red_flags",
  "Summary": "summary",
  "Next Step": "next_step",
  "Notes": "notes",
  "Annual Taxes": "taxes",
  "Crime/Safety": "crime",
  "Fire/Egress/Terrain": "fire_egress",
  "Sewage & Reclaimed-Water Exposure": "sewage_exposure",
  "Garage/Outbuildings": "outbuildings",
};

/* The one editable column that is not about one property.
 *
 * A town note is addressed by the town, so writing one from a row writes it for every property in
 * that town, which is the whole point of it: a note that only existed on one row is a note nobody
 * sees while looking at any of the others. It is edited here anyway, because this is where somebody
 * is when they form the opinion, and every other cell around it can be typed into. What it must not
 * do is look like a note about this house, so the cell says whose it is before it is opened and the
 * other rows in that town change under it when it is saved. */
const TOWN_NOTE = "Town Analysis Notes";

/* What each site is called on a link back to it. */
const SITES = {realtor: "Realtor", zillow: "Zillow", redfin: "Redfin"};

/* What an empty cell in a column means, for the heading's tooltip. A person looking at a blank
 * column wants to know which kind of blank it is before they go looking for a bug. */
const ORIGINS = {
  listing: "what the listing site reported",
  derived: "worked out by this tool",
  extracted: "recovered from the listing's own description",
  enriched: "public data about where the property is",
  annotation: "yours to write in",
};

/* Saying no to a house has a column of its own, first, and it is not one of the export's columns.
 * It was inside the address cell, after the address and after however many badges the property
 * carried, which on a narrow column put it past the right edge and out of sight: a control nobody
 * can find is a control that does not exist, and it was asked for twice as a feature that was
 * already built. First, fixed width, same place on every row. */
const PASS_COLUMN = {name: "Keep or pass", kind: "control", origin: "control"};

const state = {
  search: "",
  /* Every column the answer declared, in the order this person has put them. `columns` is the
   * subset actually drawn. Two lists rather than one because hiding a column must not lose where it
   * was: showing it again puts it back where it sat, not on the end. */
  declared: [],
  hidden: {},
  columns: [],
  all: [],
  shown: [],
  sortBy: null,
  descending: false,
  query: "",
  showGone: false,
  showPassed: false,
  onlyKept: false,
  showPhotos: false,
  wrap: false,
  widths: {},
  focus: {row: 0, column: 0},
};

/* Set while a header is being dragged or resized, and read by the click handler: a drag that ends
 * over the header it started on must not also be read as a request to sort by it. */
let arranging = null;

whenReady(() => {
  /* The table wants every pixel the window has; every other surface reads better bounded to a
   * comfortable measure. One class rather than a second stylesheet. */
  document.body.classList.add("wide");
  nav("/");
  state.search = pathParts()[1] || "";
  load().catch(fail);
});

async function load() {
  const found = await ask(`/api/results/${encodeURIComponent(state.search)}`);
  state.declared = arrange(found.columns);
  state.columns = visible();
  state.all = found.rows;
  draw();
  apply();
}

/* ------------------------------------------------------------------ */
/* How the columns are laid out, and remembering it                    */
/* ------------------------------------------------------------------ */

/* The layout is this browser's, not the workspace's. It is a view preference, which columns this
 * person wants in front of them and how wide, and writing it into the store would make one
 * person's arrangement everybody's. It is also the one thing here that may be lost without
 * anything being lost: a browser with no storage, or storage switched off, gets the default
 * arrangement and every other part of the page behaves exactly the same. So every read and write
 * of it is guarded and none of them can fail loudly. */
function keep() {
  return `homescout:columns:${state.search}`;
}

function remembered() {
  try {
    return JSON.parse(window.localStorage.getItem(keep()) || "null") || {};
  } catch (error) {
    return {};
  }
}

function remember() {
  try {
    window.localStorage.setItem(keep(), JSON.stringify({
      /* The control column is not the person's to arrange, so it is not in what is remembered. */
      order: state.declared.filter(sortable).map((column) => column.name),
      hidden: Object.keys(state.hidden),
      widths: state.widths,
      photos: state.showPhotos,
      wrap: state.wrap,
    }));
  } catch (error) {
    /* Private browsing, a full quota, storage switched off. The arrangement lasts this visit. */
  }
}

/* The declared columns in the order this person last left them, with anything new appended and
 * anything gone dropped. A saved order is a list of names rather than a list of positions on
 * purpose: a release that adds a column must not silently shuffle an arrangement somebody built. */
function arrange(declared) {
  const held = remembered();
  state.widths = Object.assign({}, held.widths || {});
  state.showPhotos = held.photos === true;
  state.wrap = held.wrap === true;
  state.hidden = {};
  for (const name of held.hidden || []) state.hidden[name] = true;

  const byName = new Map(declared.map((column) => [column.name, column]));
  const ordered = [];
  for (const name of held.order || []) {
    if (byName.has(name)) {
      ordered.push(byName.get(name));
      byName.delete(name);
    }
  }
  /* Anything the remembered order did not mention keeps the order it was declared in. New columns
   * therefore appear where the answer puts them rather than shuffling an arrangement somebody
   * built, and they appear rather than being silently hidden. */
  ordered.push(...byName.values());
  return [PASS_COLUMN, ...ordered];
}

/* The columns actually drawn, which is every declared one that has not been hidden. Recomputed
 * rather than kept in step by hand, so there is no state to get out of step. */
function visible() {
  return state.declared.filter((column) => !state.hidden[column.name]);
}

function relayout() {
  state.columns = visible();
  state.focus.column = Math.max(0, Math.min(state.focus.column, state.columns.length - 1));
  remember();
  redrawHeader();
  window_();
}

function hide(name) {
  if (name === PASS_COLUMN.name) return;
  state.hidden[name] = true;
  relayout();
  say(`${name} hidden. Bring it back from "choose columns".`);
}

function show(name) {
  delete state.hidden[name];
  relayout();
}

function sortable(column) {
  return column.origin !== "control";
}

function widthOf(name) {
  if (name === PASS_COLUMN.name) return 74;
  return state.widths[name] || WIDTHS[name] || DEFAULT_WIDTH;
}

function rowHeight() {
  return Math.max(
    state.wrap ? WRAP_ROW_HEIGHT : ROW_HEIGHT,
    state.showPhotos ? PHOTO_ROW_HEIGHT : 0,
  );
}

/* The one place the row height is published, so the stylesheet and the arithmetic above cannot come
 * to disagree about what a row is. The line height goes with it: with one line to a row it is the
 * row, and when text wraps it is a line of wrapped text, and either way the stylesheet is told
 * rather than left to work it out from a font. */
function measure() {
  const root = document.documentElement.style;
  root.setProperty("--row-height", `${rowHeight()}px`);
  root.setProperty("--cell-line", `${state.wrap ? WRAP_LINE : rowHeight() - 1}px`);
  root.setProperty("--wrap-lines", String(WRAP_LINES));
  const table = document.querySelector("table.grid");
  if (table) table.classList.toggle("wrapped", state.wrap);
}

function reset() {
  state.widths = {};
  state.hidden = {};
  state.showPhotos = false;
  state.wrap = false;
  try {
    window.localStorage.removeItem(keep());
  } catch (error) {
    /* Nothing to forget. */
  }
  load().catch(fail);
}

/* ------------------------------------------------------------------ */
/* The page around the table                                           */
/* ------------------------------------------------------------------ */

function draw() {
  measure();

  const search = el("input", {
    type: "search",
    id: "filter",
    placeholder: "type to narrow the list",
    "aria-label": "Filter the table",
    oninput: (event) => { state.query = event.target.value; apply(); },
  });

  const gone = el("input", {
    type: "checkbox",
    id: "showgone",
    onchange: (event) => { state.showGone = event.target.checked; apply(); },
  });

  const shown = el("input", {
    type: "checkbox",
    id: "showpassed",
    onchange: (event) => { state.showPassed = event.target.checked; apply(); },
  });

  const only = el("input", {
    type: "checkbox",
    id: "onlykept",
    onchange: (event) => { state.onlyKept = event.target.checked; apply(); },
  });

  const photos = el("input", {
    type: "checkbox",
    id: "showphotos",
    checked: state.showPhotos ? "checked" : null,
    onchange: (event) => {
      state.showPhotos = event.target.checked;
      measure();
      remember();
      apply();
    },
  });

  const wrapping = el("input", {
    type: "checkbox",
    id: "wraptext",
    checked: state.wrap ? "checked" : null,
    onchange: (event) => {
      state.wrap = event.target.checked;
      measure();
      remember();
      apply();
    },
  });

  shell(
    `${state.search} results`,
    el("h1", {}, `${state.search}`),
    el("p", {class: "lede"},
      "Click a heading to sort by it, drag it to move the column, drag its right edge to resize, " +
      "right-click it to hide it. Cells with a white background are yours to write in: click one " +
      "and press Enter. What you write survives every later run. Town notes are the exception: " +
      "they belong to the town and appear on every property in it."),
    el("div", {class: "controls"},
      search,
      el("label", {for: "showgone"}, gone, " show properties that disappeared"),
      el("label", {for: "showpassed"}, shown, " show properties you passed on"),
      el("label", {for: "onlykept"}, only, " only what you kept"),
      el("label", {for: "showphotos"}, photos, " show photos"),
      el("label", {for: "wraptext"}, wrapping,
         ` wrap long text (${WRAP_LINES} lines)`),
      el("button", {type: "button", class: "quiet", onclick: chooseColumns,
                    title: "Show or hide columns"}, "choose columns"),
      el("button", {type: "button", class: "quiet", onclick: reset,
                    title: "Put every column back, in its original order and width"},
         "reset columns"),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      link(`/changes/${encodeURIComponent(state.search)}`, "what changed"),
      /* A plain link rather than a button that fetches: the browser's own download is what a
       * person expects from something that hands them a file, and it survives the page being
       * closed while a thousand rows are being written. */
      link(`/api/export/${encodeURIComponent(state.search)}?format=xlsx`, "download the spreadsheet",
           {title: "Every column and every property in this run, as a spreadsheet",
            download: ""}),
      link(`/api/export/${encodeURIComponent(state.search)}?format=csv`, "as csv",
           {title: "The same sheet, comma separated", download: ""}),
    ),
    el("div", {id: "scroller", tabindex: "0", role: "region",
               "aria-label": "Results, scrollable"},
      el("div", {id: "sizer"},
        el("table", {class: "grid", role: "grid"},
          el("colgroup", {id: "widths"}),
          el("thead", {}, headerRow()),
          el("tbody", {id: "body"}),
        ),
      ),
    ),
  );

  sizeColumns();
  const scroller = document.getElementById("scroller");
  scroller.addEventListener("scroll", window_, {passive: true});
  scroller.addEventListener("keydown", key);
  fit();
  window.addEventListener("resize", () => { fit(); window_(); });
}

/* The table is given the room that is actually left, rather than a guess at it.
 *
 * Its height was `100vh` minus a constant, and the constant was wrong: the heading, the paragraph
 * of instructions and a row of controls that wraps come to more than that, so the table's bottom
 * edge sat below the bottom of the window. Everything about that is invisible except the one thing
 * that is not: the horizontal scrollbar belongs to that bottom edge, so a table forty-two columns
 * wide had no visible way to scroll sideways, and the only way to see the far columns was to select
 * text and drag. Measured, so it stays right as the controls wrap and the window changes.
 */
function fit() {
  const scroller = document.getElementById("scroller");
  if (!scroller) return;
  const top = scroller.getBoundingClientRect().top + window.scrollY;
  const room = Math.max(240, window.innerHeight - top - 2);
  scroller.style.height = `${room}px`;
  /* Whatever sits below it, page padding included, would otherwise leave the whole page scrolling
   * by that much: a wheel over the table scrolls the table, and a wheel anywhere else moves the
   * table's bottom edge, which is exactly the sort of thing that makes a scrollbar hard to hit. */
  const over = document.documentElement.scrollHeight - window.innerHeight;
  if (over > 0) scroller.style.height = `${Math.max(240, room - over)}px`;
}

/* Widths live on a `colgroup` rather than on every cell, which is what makes a resize one style
 * change instead of one per visible row. `table-layout: fixed` is what makes the browser honour
 * them. */
function sizeColumns() {
  const group = document.getElementById("widths");
  if (!group) return;
  group.replaceChildren(
    ...state.columns.map((column) =>
      el("col", {style: `width:${widthOf(column.name)}px`,
                 dataset: {column: column.name}})));
  tableWidth();
}

/* The table is told its own width, and that is not a nicety.
 *
 * `table-layout: fixed` takes its columns from the first row it can find when the table's own width
 * is `auto` — and the first row in this table is whichever row the scroll position last put in the
 * DOM. So scrolling changed which row the widths were derived from, and the columns jumped about
 * under the reader. Setting the width to the sum of the declared columns makes the `colgroup` the
 * only thing the layout is derived from, whatever is on screen. */
function tableWidth() {
  const table = document.querySelector("table.grid");
  if (!table) return;
  const total = state.columns.reduce((sum, column) => sum + widthOf(column.name), 0);
  table.style.width = `${total}px`;
}

function redrawHeader() {
  const head = document.querySelector("table.grid thead");
  if (head) head.replaceChildren(headerRow());
  sizeColumns();
}

function headerRow() {
  return el("tr", {}, state.columns.map((column, at) => header(column, at)));
}

/* What a right-click on a heading offers. Hiding is the thing she asked for by name; the chooser
 * is beside it because a control that only removes things and never brings them back is a trap. */
function headerMenu(event, column) {
  event.preventDefault();
  document.querySelectorAll(".menu").forEach((old_) => old_.remove());
  if (!sortable(column)) return;

  const menu = el("div", {class: "menu", role: "menu"},
    el("button", {type: "button", role: "menuitem",
                  onclick: () => { menu.remove(); hide(column.name); }},
       `Hide ${column.name}`),
    el("button", {type: "button", role: "menuitem",
                  onclick: () => { menu.remove(); chooseColumns(); }},
       "Choose columns…"),
  );
  menu.style.left = `${event.clientX}px`;
  menu.style.top = `${event.clientY}px`;
  document.body.append(menu);
  menu.querySelector("button").focus();

  const away = (moved) => {
    if (menu.contains(moved.target)) return;
    menu.remove();
    document.removeEventListener("pointerdown", away, true);
  };
  document.addEventListener("pointerdown", away, true);
  menu.addEventListener("keydown", (pressed) => {
    if (pressed.key === "Escape") { menu.remove(); }
  });
}

/* Every column, with a box each. The way back for anything hidden, and the way to hide several at
 * once without right-clicking each of them in turn. */
function chooseColumns() {
  const boxes = state.declared.filter(sortable).map((column) => {
    const box = el("input", {
      type: "checkbox",
      id: `col-${column.name.replace(/\W+/g, "-")}`,
      checked: state.hidden[column.name] ? null : "checked",
      onchange: (event) => (event.target.checked ? show : hide)(column.name),
    });
    return el("li", {}, el("label", {for: box.id}, box, ` ${column.name}`));
  });

  const dialog = el("dialog", {
    class: "ask columns",
    "aria-labelledby": "whichcolumns",
    onclose: () => dialog.remove(),
    onclick: (event) => { if (event.target === dialog) dialog.close(); },
  },
    el("h2", {id: "whichcolumns"}, "Which columns to show"),
    el("p", {class: "hint"},
      "Unticking one only takes it off this screen. Nothing is deleted, the spreadsheet still has "
      + "every column, and this is remembered in this browser alone."),
    el("ul", {class: "choices"}, boxes),
    el("div", {class: "actions"},
      el("button", {type: "button", class: "quiet",
                    onclick: () => {
                      state.hidden = {};
                      relayout();
                      dialog.close();
                    }}, "Show them all"),
      el("button", {type: "button", class: "primary", onclick: () => dialog.close()}, "Done"),
    ),
  );
  document.body.append(dialog);
  dialog.showModal();
}

function header(column, at) {
  if (!sortable(column)) {
    /* The control column: not sorted, not moved, not resized. Its heading is a word rather than a
     * blank, so the column of buttons under it says what pressing one does. */
    return el("th", {
      scope: "col",
      role: "columnheader",
      class: "control",
      title: "Keep a property to put it on your shortlist, or pass on it to take it out of this " +
             "table. Neither deletes anything.",
    }, column.name);
  }
  const th = el("th", {
    scope: "col",
    role: "columnheader",
    tabindex: "0",
    draggable: "true",
    class: column.origin === "annotation" ? "yours" : null,
    "aria-sort": state.sortBy === column.name
      ? (state.descending ? "descending" : "ascending") : "none",
    title: `${column.name}: ${ORIGINS[column.origin] || column.origin}. Drag to move it, or drag ` +
      "its right edge to resize. Right-click to hide it. Alt with the arrow keys moves it, add " +
      "Shift to resize, and Delete hides it.",
    onclick: () => { if (!arranging) sortBy(column.name); },
    oncontextmenu: (event) => headerMenu(event, column),
    ondragstart: (event) => {
      arranging = column.name;
      event.dataTransfer.effectAllowed = "move";
      /* Some browsers will not start a drag at all without something on the transfer. */
      event.dataTransfer.setData("text/plain", column.name);
      th.classList.add("moving");
    },
    ondragend: () => {
      th.classList.remove("moving");
      setTimeout(() => { arranging = null; }, 0);
    },
    ondragover: (event) => {
      if (arranging === null || arranging === column.name) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      th.classList.add("landing");
    },
    ondragleave: () => th.classList.remove("landing"),
    ondrop: (event) => {
      event.preventDefault();
      th.classList.remove("landing");
      if (arranging !== null) move(arranging, at);
    },
    onkeydown: (event) => headerKey(event, column, at),
  }, column.name + (state.sortBy === column.name ? (state.descending ? " down" : " up") : ""));

  th.append(el("span", {
    class: "grip",
    role: "presentation",
    title: `Drag to set how wide ${column.name} is`,
    onclick: (event) => { event.stopPropagation(); },
    onpointerdown: (event) => startResize(event, column.name, th),
  }));
  return th;
}

/* Everything the mouse can do to a column, the keyboard can do too: sort it, move it, size it.
 * Without this the two new arrangements would be mouse-only, which AC-17 does not allow. */
function headerKey(event, column, at) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    sortBy(column.name);
    return;
  }
  if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    const heads = document.querySelectorAll("table.grid thead th");
    hide(column.name);
    const landed = heads[Math.min(at, state.columns.length - 1)];
    if (landed && landed.isConnected) landed.focus();
    return;
  }
  if (!event.altKey) return;
  const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
  if (!step) return;
  event.preventDefault();

  if (event.shiftKey) {
    setWidth(column.name, widthOf(column.name) + step * 24);
    sizeColumns();
    remember();
    say(`${column.name} is now ${widthOf(column.name)} pixels wide`);
    return;
  }

  move(column.name, at + step);
  const landed = state.columns.findIndex((held) => held.name === column.name);
  const moved = document.querySelectorAll("table.grid thead th")[landed];
  if (moved) moved.focus();
}

/* Moving a column is a change to the declared order, expressed in terms of what is on screen.
 *
 * The position somebody drags to is a position among the columns they can see, and the order that
 * is kept is the full one including whatever is hidden. So the move is made relative to the column
 * currently sitting at that position: a hidden column stays beside the neighbour it was hidden
 * next to, and comes back there rather than on the end. */
function move(name, to) {
  if (name === PASS_COLUMN.name) return;
  const shown = state.columns;
  /* Never before the control column, which stays first so the buttons are in the same place on
   * every row of every arrangement. */
  const target = Math.max(1, Math.min(to, shown.length - 1));
  const from = shown.findIndex((column) => column.name === name);
  if (from < 0 || from === target) return;

  const anchor = shown[target].name;
  const all = state.declared;
  const [held] = all.splice(all.findIndex((column) => column.name === name), 1);
  const beside = all.findIndex((column) => column.name === anchor);
  all.splice(from < target ? beside + 1 : beside, 0, held);

  relayout();
  say(`${name} moved to position ${target + 1} of ${shown.length}`);
}

function setWidth(name, pixels) {
  state.widths[name] = Math.max(MIN_WIDTH, Math.round(pixels));
}

function startResize(event, name, th) {
  event.preventDefault();
  event.stopPropagation();
  arranging = name;
  /* A header being resized must not also be a header being dragged somewhere else. */
  th.draggable = false;
  const startX = event.clientX;
  const startWidth = widthOf(name);
  const col = document.querySelector(`#widths col[data-column="${CSS.escape(name)}"]`);

  const moveTo = (moved) => {
    setWidth(name, startWidth + (moved.clientX - startX));
    if (col) col.style.width = `${widthOf(name)}px`;
    tableWidth();
  };
  const stop = () => {
    window.removeEventListener("pointermove", moveTo);
    window.removeEventListener("pointerup", stop);
    th.draggable = true;
    remember();
    setTimeout(() => { arranging = null; }, 0);
  };
  window.addEventListener("pointermove", moveTo);
  window.addEventListener("pointerup", stop);
}

function sortBy(name) {
  if (state.sortBy === name) state.descending = !state.descending;
  else { state.sortBy = name; state.descending = false; }
  redrawHeader();
  apply();
}

/* ------------------------------------------------------------------ */
/* Sorting and filtering, which happen on the array                    */
/* ------------------------------------------------------------------ */

function apply() {
  const started = performance.now();
  const query = state.query.trim().toLowerCase();
  let kept = state.all;

  if (!state.showGone) kept = kept.filter((row) => row.presence !== "disappeared");
  /* `hidden_by_default` is the core's answer, not this page's opinion. The rule about what passing
   * means lives in one place so that this table and the command line cannot come to disagree. */
  if (!state.showPassed) kept = kept.filter((row) => !row.hidden_by_default);
  /* The shortlist, when that is what somebody is working from. Applied after the passed filter and
   * not instead of it, so "only what you kept" and "show passed" cannot contradict each other: a
   * property is one judgment or the other and never both. */
  if (state.onlyKept) kept = kept.filter((row) => row.judgment === "keep");
  if (query) {
    kept = kept.filter((row) =>
      Object.values(row.values).some(
        (held) => held !== null && held !== undefined &&
                  String(held).toLowerCase().includes(query)));
  }

  if (state.sortBy) {
    const name = state.sortBy;
    const direction = state.descending ? -1 : 1;
    kept = kept.slice().sort((a, b) => compare(a.values[name], b.values[name]) * direction);
  }

  state.shown = kept;
  window_();
  counts(performance.now() - started);
}

/* A property with no value for the column being sorted goes last whichever way the sort points. A
 * missing price is not the cheapest house. */
function compare(a, b) {
  const missingA = a === null || a === undefined || a === "";
  const missingB = b === null || b === undefined || b === "";
  if (missingA && missingB) return 0;
  if (missingA) return 1;
  if (missingB) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, {numeric: true});
}

function counts(took) {
  const hidden = state.all.filter((row) => row.presence === "disappeared").length;
  const passed = state.all.filter((row) => row.judgment === "pass").length;
  const kept = state.all.filter((row) => row.judgment === "keep").length;
  const parts = [`${state.shown.length} of ${state.all.length} properties`];
  if (!state.showGone && hidden) parts.push(`${hidden} disappeared and hidden`);
  if (!state.showPassed && passed) parts.push(`${passed} passed and hidden`);
  if (kept) parts.push(`${kept} kept`);
  parts.push(`${took.toFixed(0)}ms`);
  document.getElementById("counts").replaceChildren(document.createTextNode(parts.join(" · ")));
}

/* ------------------------------------------------------------------ */
/* Drawing the window                                                  */
/* ------------------------------------------------------------------ */

function window_() {
  const scroller = document.getElementById("scroller");
  const body = document.getElementById("body");
  const sizer = document.getElementById("sizer");
  if (!scroller || !body) return;

  const height = rowHeight();
  const first = Math.max(0, Math.floor(scroller.scrollTop / height) - OVERSCAN);
  const many = Math.ceil(scroller.clientHeight / height) + OVERSCAN * 2;
  const slice = state.shown.slice(first, first + many);

  const frag = document.createDocumentFragment();
  slice.forEach((row, offset) => frag.append(rowFor(row, first + offset)));
  body.replaceChildren(frag);
  body.style.transform = `translateY(${first * height}px)`;
  sizer.style.height = Math.max(state.shown.length * height + 30, 30) + "px";
}

function rowFor(row, index) {
  const tr = el("tr", {
    dataset: {listing: row.listing_id, index: String(index)},
    class: [row.presence === "disappeared" ? "gone" : null,
            row.judgment === "pass" ? "passed" : null,
            row.judgment === "keep" ? "kept" : null].filter(Boolean).join(" ") || null,
  });
  state.columns.forEach((column, column_) => tr.append(cellFor(row, column, index, column_)));
  return tr;
}

function writable(name) {
  return Object.prototype.hasOwnProperty.call(EDITABLE, name) || name === TOWN_NOTE;
}

function cellFor(row, column, index, column_) {
  const held = row.values[column.name];
  const editable = writable(column.name);
  const selected = state.focus.row === index && state.focus.column === column_;
  const cell = el("td", {
    role: "gridcell",
    tabindex: selected ? "0" : "-1",
    "aria-selected": selected ? "true" : "false",
    "aria-readonly": editable ? null : "true",
    class: editable ? "editable" : null,
    dataset: {column: column.name, index: String(index), col: String(column_)},
    title: column.name === TOWN_NOTE
      ? `About ${row.values["Town/Area"] || "this town"}, not about this house. ` +
        `Every property there shows it.${held ? ` — ${held}` : ""}`
      : (held === null || held === undefined ? "" : String(held)),
    onclick: () => { focusCell(index, column_); },
    ondblclick: editable ? () => edit(cell, row, column.name) : null,
  });

  /* When text may wrap, everything a cell holds goes inside one box of its own, and that box is
   * what gets clamped: a cell cannot clip its own height in a table, so without something inside it
   * to clamp, a wrapped description would take its row with it and the rows would stop being the
   * same height as each other. When text is kept to a line there is nothing to clamp, so the box is
   * not built at all: it is one more element per cell, and this table's whole performance argument
   * is about how many elements exist. */
  const inner = state.wrap ? el("span", {class: "cell"}) : cell;
  if (!sortable(column)) {
    cell.classList.add("control");
    inner.append(keepToggle(row), passToggle(row));
  } else if (column.name === "Property") {
    cell.classList.add("property");
    if (state.showPhotos) inner.append(thumbnail(row));
    const said = el("span", {class: "what"},
      link(`/listing/${encodeURIComponent(row.listing_id)}`, held || "not known"));
    for (const flag of row.flags) said.append(badge(flag, "flag"));
    inner.append(said);
  } else if (column.name === "Listing URL") {
    inner.append(elsewhere(row, held));
  } else if (column.kind === "number" && column.name === "Price") {
    inner.append(money(held));
  } else if (editable && (held === null || held === undefined || held === "")) {
    /* Blank, not "not known". Everywhere else in this product an empty cell means nobody could
     * determine the value, and saying so is the point. Here nobody was ever going to: this is a
     * column the person writes in themselves, and printing "not known" a thousand times down it
     * says the tool failed at something it was never doing. */
  } else {
    inner.append(value(held));
  }
  if (inner !== cell) cell.append(inner);
  return cell;
}

/* Where a cell's content goes, matching what `cellFor` decided. An edit redraws one cell, and it
 * has to land in the same shape as the ones around it or that row alone loses its clamp. */
function holder(cell) {
  if (!state.wrap) return cell;
  const inner = el("span", {class: "cell"});
  cell.replaceChildren(inner);
  return inner;
}

/* The picture this tool stored for itself, not the one on the listing site: opening this page tells
 * the listing site nothing, and a property that has since disappeared still has its photograph.
 *
 * A property with none gets an empty box of the same size, so the two hold the same space and the
 * addresses stay in a straight line. That matters more in this table than anywhere else on the
 * site, because these rows are read by running an eye straight down a column. */
function thumbnail(row) {
  if (!row.has_image) return el("span", {class: "thumb", "aria-hidden": "true"});
  const picture = el("img", {
    class: "shot",
    loading: "lazy",
    decoding: "async",
    alt: "",
    src: `/api/listings/${encodeURIComponent(row.listing_id)}/image`,
  });
  /* A button rather than an image with a handler on it, so the keyboard reaches it. */
  return el("button", {
    type: "button",
    class: "thumb",
    title: "See every photograph of this property",
    "aria-label": `Photographs of ${row.values["Property"] || "this property"}`,
    onclick: (event) => {
      event.preventDefault();
      event.stopPropagation();
      showPhotos(row).catch(fail);
    },
  }, picture);
}

/* The listing's own photographs, asked for only when somebody wants to see them.
 *
 * They are not in the table's answer and should not be: a thousand rows carrying forty addresses
 * apiece is a payload nobody reads, and the table itself is drawn entirely from pictures this tool
 * stored. So the addresses are fetched for one property at the moment it is asked about. */
async function showPhotos(row) {
  const found = await ask(`/api/listings/${encodeURIComponent(row.listing_id)}`);
  const shown = gallery((found.listing || {}).photo_urls, row.values["Property"]);
  if (!shown) say("This listing carried no photographs beyond the one stored.");
}

/* Where to go and look at this property, once per site it was found on.
 *
 * A merged record is one row here and up to three pages out there, and those pages are not
 * interchangeable: somebody keeping a list on one site can only add that site's page to it. So the
 * cell offers every address it has, each named, rather than the single one the merge happened to
 * settle on. */
function elsewhere(row, held) {
  const links = row.links || [];
  if (!links.length) return held ? link(held, "open listing") : value(null);
  const holder = el("span", {class: "elsewhere"});
  links.forEach((entry, at) => {
    const site = SITES[entry.source] || entry.source;
    if (at) holder.append(document.createTextNode(" "));
    holder.append(link(entry.url, site, {title: `Open this property on ${site}`}));
  });
  return holder;
}

/* ------------------------------------------------------------------ */
/* Keyboard: the table is a grid with roving focus                     */
/* ------------------------------------------------------------------ */

function focusCell(row, column) {
  state.focus = {
    row: Math.max(0, Math.min(row, state.shown.length - 1)),
    column: Math.max(0, Math.min(column, state.columns.length - 1)),
  };
  const height = rowHeight();
  const wanted = state.focus.row * height;
  const scroller = document.getElementById("scroller");
  if (wanted < scroller.scrollTop) scroller.scrollTop = wanted;
  else if (wanted + height > scroller.scrollTop + scroller.clientHeight) {
    scroller.scrollTop = wanted - scroller.clientHeight + height * 2;
  }
  window_();
  const cell = document.querySelector('td[aria-selected="true"]');
  if (cell) cell.focus({preventScroll: true});
}

function key(event) {
  if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
  /* A header has its own keys, including Alt with the arrows, which must not also scroll the grid. */
  if (event.target.tagName === "TH") return;
  const {row, column} = state.focus;
  const moves = {
    ArrowDown: [row + 1, column], ArrowUp: [row - 1, column],
    ArrowRight: [row, column + 1], ArrowLeft: [row, column - 1],
    Home: [row, 0], End: [row, state.columns.length - 1],
    PageDown: [row + 20, column], PageUp: [row - 20, column],
  };
  if (moves[event.key]) {
    event.preventDefault();
    focusCell(moves[event.key][0], moves[event.key][1]);
    return;
  }
  if (event.key === "Delete" || event.key === "Backspace") {
    const cell = document.querySelector('td[aria-selected="true"]');
    if (cell && cell.dataset.column === PASS_COLUMN.name) {
      event.preventDefault();
      const button = cell.querySelector("button.pass");
      if (button) button.click();
      return;
    }
  }
  if (event.key === "Enter") {
    const cell = document.querySelector('td[aria-selected="true"]');
    const name = cell && cell.dataset.column;
    if (cell && writable(name)) {
      event.preventDefault();
      edit(cell, state.shown[row], name);
    } else if (cell && name === PASS_COLUMN.name) {
      /* The control column answers to the keyboard the same way it answers to a press. Enter keeps
       * and Delete passes, because the destructive-looking one should not be the one under the key
       * a person presses to move on. */
      event.preventDefault();
      const button = cell.querySelector("button.keep");
      if (button) button.click();
    }
  }
}

/* ------------------------------------------------------------------ */
/* Editing in place                                                    */
/* ------------------------------------------------------------------ */

/* The rule this is built around: a person must never be left believing an edit was recorded when
 * it was not. So a failure keeps the typed value, marks the row in words as well as colour, and
 * leaves the field editable; and a success takes its values from what the store returned rather
 * than from what was typed, which is what makes two tabs editing the same property behave. */
function edit(cell, row, column) {
  if (!row) return;
  const field = EDITABLE[column];
  if (column === TOWN_NOTE) return editTownNote(cell, row);
  const before = row.values[column];
  const input = el("input", {
    type: column === "Rank" ? "number" : "text",
    value: before === null || before === undefined ? "" : String(before),
    "aria-label": `${column} for ${row.values["Property"] || row.listing_id}`,
  });

  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    if (!commit) { window_(); focusCell(state.focus.row, state.focus.column); return; }
    save(cell, row, column, field, input.value);
  };

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); finish(true); }
    else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    else if (event.key === "Tab") { finish(true); }
    event.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));

  cell.replaceChildren(input);
  input.focus();
  input.select();
}

/* Editing the note about a town, from a row that happens to be in it.
 *
 * Written the same way as every other cell, and saved somewhere else entirely: to the town rather
 * than to the property. So every other row in that town takes the new note too, without a reload,
 * because a person who has just written "the water here is hard" and sees it appear on one of the
 * nine houses they are looking at in that town would reasonably conclude it had gone in wrong.
 */
function editTownNote(cell, row) {
  const town = (row.values["Town/Area"] || "").trim();
  if (!town) {
    fail("This property has no town, so there is nowhere to hang a note about one.");
    return;
  }
  const before = row.values[TOWN_NOTE];
  const input = el("input", {
    type: "text",
    value: before === null || before === undefined ? "" : String(before),
    "aria-label": `Notes about ${town}, shown on every property there`,
  });

  let done = false;
  const finish = (commit) => {
    if (done) return;
    done = true;
    if (!commit) { window_(); focusCell(state.focus.row, state.focus.column); return; }
    saveTownNote(cell, town, input.value);
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); finish(true); }
    else if (event.key === "Escape") { event.preventDefault(); finish(false); }
    else if (event.key === "Tab") { finish(true); }
    event.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));

  cell.replaceChildren(input);
  input.focus();
  input.select();
}

async function saveTownNote(cell, town, typed) {
  const wanted = typed.trim() === "" ? null : typed;
  cell.className = "editable saving";
  cell.replaceChildren();
  holder(cell).append(value(typed), el("span", {class: "rowstate"}, " saving…"));

  try {
    await send("/api/areas", {area_type: "city", area_value: town, notes: wanted});
    /* Every row in that town, not only this one. */
    let touched = 0;
    for (const held of state.all) {
      if ((held.values["Town/Area"] || "").trim() === town) {
        held.values[TOWN_NOTE] = wanted;
        touched += 1;
      }
    }
    apply();
    say(`Noted about ${town}, on ${count(touched, "property", "properties")} there.`);
  } catch (error) {
    cell.className = "editable unsaved";
    const retry = el("input", {type: "text", value: typed,
                               "aria-label": `Notes about ${town}, not saved: ${error.message}`});
    retry.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        saveTownNote(cell, town, retry.value);
      }
      event.stopPropagation();
    });
    cell.replaceChildren();
    holder(cell).append(
      retry, el("span", {class: "rowstate problem"}, ` not saved: ${error.message}`));
    fail(`That note was not saved: ${error.message}`);
  }
}

async function save(cell, row, column, field, typed) {
  const wanted = typed.trim() === "" ? null : (field === "rank" ? Number(typed) : typed);
  cell.className = "editable saving";
  cell.replaceChildren();
  holder(cell).append(value(typed), el("span", {class: "rowstate"}, " saving…"));

  try {
    const answered = await send(
      `/api/listings/${encodeURIComponent(row.listing_id)}/annotation`,
      {[field]: wanted});
    /* What the store now holds, not what was typed. */
    row.values[column] = answered[field];
    cell.className = "editable saved";
    cell.replaceChildren();
    holder(cell).append(value(answered[field]), el("span", {class: "rowstate"}, " saved"));
    setTimeout(() => { if (cell.isConnected) cell.className = "editable"; }, 2000);
  } catch (error) {
    /* Not saved, and it says so, and the typed value is still there to try again with. */
    cell.className = "editable unsaved";
    const retry = el("input", {type: "text", value: typed,
                               "aria-label": `${column}, not saved: ${error.message}`});
    retry.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        save(cell, row, column, field, retry.value);
      }
      event.stopPropagation();
    });
    cell.replaceChildren();
    holder(cell).append(
      retry, el("span", {class: "rowstate problem"}, ` not saved: ${error.message}`));
    fail(`That edit was not saved: ${error.message}`);
  }
}

/* ------------------------------------------------------------------ */
/* Saying no to a house, and taking it back                            */
/* ------------------------------------------------------------------ */

/* One control, which both passes and un-passes. There is no separate undo and no menu to go
 * looking through: the button that hid a property is the button that brings it back, and it says
 * which of those it will do. */
/* The other half of the same judgment, and the one worth making effortless: a shortlist is what a
 * person actually works from after a table of a thousand has been read once. No question asked,
 * because keeping a house costs nothing and un-keeping it is the same button. */
function keepToggle(row) {
  const already = row.judgment === "keep";
  const what = row.values["Property"] || "this property";
  const button = el("button", {
    type: "button",
    class: already ? "keep on" : "keep",
    "aria-pressed": already ? "true" : "false",
    "aria-label": already ? `Take ${what} off your shortlist` : `Keep ${what}`,
    title: already
      ? "On your shortlist. Press to take it off."
      : "Keep this one: put it on your shortlist.",
    onclick: (event) => {
      event.preventDefault();
      event.stopPropagation();
      setJudgment(row, already ? null : "keep", button);
    },
  }, already ? "★" : "☆");
  return button;
}

function passToggle(row) {
  const already = row.judgment === "pass";
  const what = row.values["Property"] || "this property";
  const button = el("button", {
    type: "button",
    class: already ? "pass on" : "pass",
    "aria-pressed": already ? "true" : "false",
    "aria-label": already ? `Undo passing on ${what}` : `Pass on ${what}`,
    title: already
      ? "You passed on this one. Press to bring it back."
      : "Pass on this property and stop seeing it in this table.",
    onclick: async (event) => {
      event.preventDefault();
      event.stopPropagation();
      /* Only one direction asks. Passing takes a house out of the table you are working through,
       * and doing it by a mis-aimed click on a 26-pixel row is exactly the accident worth one
       * question. Bringing one back is not: it puts a row in front of you, which is its own undo,
       * and asking about it would be a dialog with nothing to protect. */
      if (!already && !(await confirmPass(what))) return;
      setJudgment(row, already ? null : "pass", button);
    },
  }, already ? "undo" : "✕");
  return button;
}

/* The question, as a dialog on this page rather than the browser's own.
 *
 * `showModal` gives the focus trap, the Escape key and the backdrop without any of them being
 * written here, and unlike `confirm()` it does not stop the page: a browser-level prompt blocks
 * every timer and every pending request behind it, including the save of the annotation somebody
 * was in the middle of typing.
 */
function confirmPass(what) {
  return new Promise((resolve) => {
    let answered = false;
    const done = (yes) => {
      if (answered) return;
      answered = true;
      resolve(yes);
      dialog.close();
      dialog.remove();
    };

    const yes = el("button", {type: "button", class: "primary",
                              onclick: () => done(true)}, "Pass on it");
    const no = el("button", {type: "button", class: "quiet",
                             onclick: () => done(false)}, "Keep it");

    const dialog = el("dialog", {
      class: "ask",
      "aria-labelledby": "askwhat",
      /* The backdrop, Escape, and anything else that closes it without an answer all mean no. */
      onclose: () => done(false),
      oncancel: () => done(false),
      onclick: (event) => { if (event.target === dialog) done(false); },
    },
      el("h2", {id: "askwhat"}, "Pass on this property?"),
      el("p", {}, what),
      el("p", {class: "hint"},
        "It leaves this table and stays out of every later one. Nothing is deleted: every run " +
        "still watches it, and \"show properties you passed on\" brings it back."),
      el("div", {class: "actions"}, no, yes),
    );

    document.body.append(dialog);
    dialog.showModal();
    yes.focus();
  });
}

async function setJudgment(row, wanted, button) {
  const was = row.judgment;
  button.disabled = true;
  try {
    const answered = await send(
      `/api/listings/${encodeURIComponent(row.listing_id)}/annotation`,
      {judgment: wanted});
    /* What the store now holds, not what was asked for. */
    row.judgment = answered.judgment ?? null;
    row.hidden_by_default = row.judgment === "pass" && !state.showPassed;
    apply();
  } catch (error) {
    row.judgment = was;
    button.disabled = false;
    button.className = "pass unsaved";
    button.title = `Not saved: ${error.message}. Press to try again.`;
  }
}
