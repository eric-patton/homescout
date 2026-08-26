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

/* Both row heights, in pixels, including the border every row carries. */
const ROW_HEIGHT = 26;
const PHOTO_ROW_HEIGHT = 66;
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
};

/* What each site is called on a link back to it. */
const SITES = {realtor: "Realtor", zillow: "Zillow", redfin: "Redfin"};

const state = {
  search: "",
  columns: [],
  all: [],
  shown: [],
  sortBy: null,
  descending: false,
  query: "",
  showGone: false,
  showPassed: false,
  showPhotos: false,
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
  state.columns = arrange(found.columns);
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
      order: state.columns.map((column) => column.name),
      widths: state.widths,
      photos: state.showPhotos,
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

  const byName = new Map(declared.map((column) => [column.name, column]));
  const ordered = [];
  for (const name of held.order || []) {
    if (byName.has(name)) {
      ordered.push(byName.get(name));
      byName.delete(name);
    }
  }
  /* Whatever is left keeps its declared order, except that the columns nothing fills go last.
   * Those are the household's own spreadsheet headings waiting for the household to fill them in,
   * and sitting them among the columns that do have answers is what made the table read as though
   * the tool knew nothing about fire, taxes or crime when it was never asked to. */
  const rest = [...byName.values()];
  ordered.push(...rest.filter((column) => column.origin !== "unfilled"));
  ordered.push(...rest.filter((column) => column.origin === "unfilled"));
  return ordered;
}

function widthOf(name) {
  return state.widths[name] || WIDTHS[name] || DEFAULT_WIDTH;
}

function rowHeight() {
  return state.showPhotos ? PHOTO_ROW_HEIGHT : ROW_HEIGHT;
}

/* The one place the row height is published, so the stylesheet and the arithmetic above cannot
 * come to disagree about what a row is. */
function measure() {
  document.documentElement.style.setProperty("--row-height", `${rowHeight()}px`);
}

function reset() {
  state.widths = {};
  state.showPhotos = false;
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

  const kept = el("input", {
    type: "checkbox",
    id: "showpassed",
    onchange: (event) => { state.showPassed = event.target.checked; apply(); },
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

  shell(
    `${state.search} results`,
    el("h1", {}, `${state.search}`),
    el("p", {class: "lede"},
      "Click a column heading to sort by it. Drag a heading to move that column, or drag its right " +
      "edge to make it wider. Click into a cell with a white background to write your own notes on " +
      "a property, and press Enter to keep them. What you write survives every later run."),
    el("div", {class: "controls"},
      search,
      el("label", {for: "showgone"}, gone, " show properties that disappeared"),
      el("label", {for: "showpassed"}, kept, " show properties you passed on"),
      el("label", {for: "showphotos"}, photos, " show photos"),
      el("button", {type: "button", class: "quiet", onclick: reset,
                    title: "Put the columns back to their original order and width"},
         "reset columns"),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      link(`/changes/${encodeURIComponent(state.search)}`, "what changed"),
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
}

function redrawHeader() {
  const head = document.querySelector("table.grid thead");
  if (head) head.replaceChildren(headerRow());
  sizeColumns();
}

function headerRow() {
  return el("tr", {}, state.columns.map((column, at) => header(column, at)));
}

function header(column, at) {
  const unfilled = column.origin === "unfilled";
  const th = el("th", {
    scope: "col",
    role: "columnheader",
    tabindex: "0",
    draggable: "true",
    class: unfilled ? "unfilled" : null,
    "aria-sort": state.sortBy === column.name
      ? (state.descending ? "descending" : "ascending") : "none",
    title: unfilled
      ? `${column.name}: nothing fills this column. It is here for you to fill in yourself.`
      : `${column.name}: ${column.origin}. Drag to move it, or drag its right edge to resize. ` +
        "Alt with the arrow keys moves it; add Shift to resize it.",
    onclick: () => { if (!arranging) sortBy(column.name); },
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

/* Moving a column is a change to `state.columns`, and everything else on this page reads its order
 * from there: the header, the widths, the cells, and which cell the keyboard is on. */
function move(name, to) {
  const from = state.columns.findIndex((column) => column.name === name);
  const target = Math.max(0, Math.min(to, state.columns.length - 1));
  if (from < 0 || from === target) return;
  const [held] = state.columns.splice(from, 1);
  state.columns.splice(target, 0, held);
  state.focus.column = Math.max(0, Math.min(state.focus.column, state.columns.length - 1));
  remember();
  redrawHeader();
  window_();
  say(`${name} moved to position ${target + 1} of ${state.columns.length}`);
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
  const parts = [`${state.shown.length} of ${state.all.length} properties`];
  if (!state.showGone && hidden) parts.push(`${hidden} disappeared and hidden`);
  if (!state.showPassed && passed) parts.push(`${passed} passed and hidden`);
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
            row.judgment === "pass" ? "passed" : null].filter(Boolean).join(" ") || null,
  });
  state.columns.forEach((column, column_) => tr.append(cellFor(row, column, index, column_)));
  return tr;
}

function cellFor(row, column, index, column_) {
  const held = row.values[column.name];
  const editable = Object.prototype.hasOwnProperty.call(EDITABLE, column.name);
  const selected = state.focus.row === index && state.focus.column === column_;
  const cell = el("td", {
    role: "gridcell",
    tabindex: selected ? "0" : "-1",
    "aria-selected": selected ? "true" : "false",
    "aria-readonly": editable ? null : "true",
    class: editable ? "editable" : null,
    dataset: {column: column.name, index: String(index), col: String(column_)},
    title: held === null || held === undefined ? "" : String(held),
    onclick: () => { focusCell(index, column_); },
    ondblclick: editable ? () => edit(cell, row, column.name) : null,
  });

  if (column.name === "Property") {
    cell.classList.add("property");
    if (state.showPhotos) cell.append(thumbnail(row));
    const said = el("span", {class: "what"},
      link(`/listing/${encodeURIComponent(row.listing_id)}`, held || "not known"));
    for (const flag of row.flags) said.append(badge(flag, "flag"));
    said.append(passToggle(row));
    cell.append(said);
  } else if (column.name === "Listing URL") {
    cell.append(elsewhere(row, held));
  } else if (column.kind === "number" && column.name === "Price") {
    cell.append(money(held));
  } else {
    cell.append(value(held));
  }
  return cell;
}

/* The picture this tool stored for itself, not the one on the listing site: opening this page tells
 * the listing site nothing, and a property that has since disappeared still has its photograph.
 *
 * A property with none gets an empty box of the same size, so the two hold the same space and the
 * addresses stay in a straight line. That matters more in this table than anywhere else on the
 * site, because these rows are read by running an eye straight down a column. */
function thumbnail(row) {
  if (!row.has_image) return el("span", {class: "thumb", "aria-hidden": "true"});
  return el("img", {
    class: "thumb",
    loading: "lazy",
    decoding: "async",
    alt: "",
    src: `/api/listings/${encodeURIComponent(row.listing_id)}/image`,
  });
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
  if (event.key === "Enter") {
    const cell = document.querySelector('td[aria-selected="true"]');
    const name = cell && cell.dataset.column;
    if (cell && Object.prototype.hasOwnProperty.call(EDITABLE, name)) {
      event.preventDefault();
      edit(cell, state.shown[row], name);
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

async function save(cell, row, column, field, typed) {
  const wanted = typed.trim() === "" ? null : (field === "rank" ? Number(typed) : typed);
  cell.className = "editable saving";
  cell.replaceChildren(value(typed), el("span", {class: "rowstate"}, " saving…"));

  try {
    const answered = await send(
      `/api/listings/${encodeURIComponent(row.listing_id)}/annotation`,
      {[field]: wanted});
    /* What the store now holds, not what was typed. */
    row.values[column] = answered[field];
    cell.className = "editable saved";
    cell.replaceChildren(
      value(answered[field]),
      el("span", {class: "rowstate"}, " saved"),
    );
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
    cell.replaceChildren(retry,
                         el("span", {class: "rowstate problem"}, ` not saved: ${error.message}`));
    fail(`That edit was not saved: ${error.message}`);
  }
}

/* ------------------------------------------------------------------ */
/* Saying no to a house, and taking it back                            */
/* ------------------------------------------------------------------ */

/* One control, which both passes and un-passes. There is no separate undo and no menu to go
 * looking through: the button that hid a property is the button that brings it back, and it says
 * which of those it will do. */
function passToggle(row) {
  const already = row.judgment === "pass";
  const button = el("button", {
    type: "button",
    class: already ? "pass on" : "pass",
    "aria-pressed": already ? "true" : "false",
    title: already
      ? "You passed on this one. Press to undo that."
      : "Pass on this property and stop seeing it in this table.",
    onclick: (event) => {
      event.preventDefault();
      event.stopPropagation();
      setJudgment(row, already ? null : "pass", button);
    },
  }, already ? "passed" : "pass");
  return button;
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
