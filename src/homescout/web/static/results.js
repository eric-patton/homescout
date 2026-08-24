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
 */

const ROW_HEIGHT = 22;
const OVERSCAN = 12;

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

const state = {
  search: "",
  columns: [],
  all: [],
  shown: [],
  sortBy: null,
  descending: false,
  query: "",
  showGone: false,
  focus: {row: 0, column: 0},
};

whenReady(() => {
  nav("/");
  state.search = pathParts()[1] || "";
  load().catch(fail);
});

async function load() {
  const found = await ask(`/api/results/${encodeURIComponent(state.search)}`);
  state.columns = found.columns;
  state.all = found.rows;
  draw();
  apply();
}

/* ------------------------------------------------------------------ */
/* The page around the table                                           */
/* ------------------------------------------------------------------ */

function draw() {
  const search = el("input", {
    type: "search",
    id: "filter",
    placeholder: "filter every column",
    "aria-label": "Filter the table",
    oninput: (event) => { state.query = event.target.value; apply(); },
  });

  const gone = el("input", {
    type: "checkbox",
    id: "showgone",
    onchange: (event) => { state.showGone = event.target.checked; apply(); },
  });

  shell(
    `${state.search} results`,
    el("h1", {}, `${state.search}`),
    el("p", {class: "lede"},
      "Sort by clicking a column. Type in a cell you can edit and press Enter to save it."),
    el("div", {class: "controls"},
      search,
      el("label", {for: "showgone"}, gone, " show properties that disappeared"),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      link(`/changes/${encodeURIComponent(state.search)}`, "what changed"),
    ),
    el("div", {id: "scroller", tabindex: "0", role: "region",
               "aria-label": "Results, scrollable"},
      el("div", {id: "sizer"},
        el("table", {class: "grid", role: "grid"},
          el("thead", {}, headerRow()),
          el("tbody", {id: "body"}),
        ),
      ),
    ),
  );

  const scroller = document.getElementById("scroller");
  scroller.addEventListener("scroll", window_, {passive: true});
  scroller.addEventListener("keydown", key);
}

function headerRow() {
  return el("tr", {},
    state.columns.map((column) =>
      el("th", {
        scope: "col",
        role: "columnheader",
        tabindex: "-1",
        "aria-sort": state.sortBy === column.name
          ? (state.descending ? "descending" : "ascending") : "none",
        title: `${column.name} — ${column.origin}`,
        onclick: () => sortBy(column.name),
        onkeydown: (event) => { if (event.key === "Enter" || event.key === " ") sortBy(column.name); },
      }, column.name + (state.sortBy === column.name ? (state.descending ? " ↓" : " ↑") : ""))
    )
  );
}

function sortBy(name) {
  if (state.sortBy === name) state.descending = !state.descending;
  else { state.sortBy = name; state.descending = false; }
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
  const parts = [`${state.shown.length} of ${state.all.length} properties`];
  if (!state.showGone && hidden) parts.push(`${hidden} disappeared and hidden`);
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

  const first = Math.max(0, Math.floor(scroller.scrollTop / ROW_HEIGHT) - OVERSCAN);
  const many = Math.ceil(scroller.clientHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const slice = state.shown.slice(first, first + many);

  const frag = document.createDocumentFragment();
  slice.forEach((row, offset) => frag.append(rowFor(row, first + offset)));
  body.replaceChildren(frag);
  body.style.transform = `translateY(${first * ROW_HEIGHT}px)`;
  sizer.style.height = Math.max(state.shown.length * ROW_HEIGHT + 30, 30) + "px";
}

function rowFor(row, index) {
  const tr = el("tr", {
    dataset: {listing: row.listing_id, index: String(index)},
    class: row.presence === "disappeared" ? "gone" : null,
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
    cell.append(link(`/listing/${encodeURIComponent(row.listing_id)}`, held || "not known"));
    for (const flag of row.flags) cell.append(badge(flag, "flag"));
  } else if (column.name === "Listing URL" && held) {
    cell.append(link(held, "open listing"));
  } else if (column.kind === "number" && column.name === "Price") {
    cell.append(money(held));
  } else {
    cell.append(value(held));
  }
  return cell;
}

/* ------------------------------------------------------------------ */
/* Keyboard: the table is a grid with roving focus                     */
/* ------------------------------------------------------------------ */

function focusCell(row, column) {
  state.focus = {
    row: Math.max(0, Math.min(row, state.shown.length - 1)),
    column: Math.max(0, Math.min(column, state.columns.length - 1)),
  };
  const wanted = state.focus.row * ROW_HEIGHT;
  const scroller = document.getElementById("scroller");
  if (wanted < scroller.scrollTop) scroller.scrollTop = wanted;
  else if (wanted + ROW_HEIGHT > scroller.scrollTop + scroller.clientHeight) {
    scroller.scrollTop = wanted - scroller.clientHeight + ROW_HEIGHT * 2;
  }
  window_();
  const cell = document.querySelector('td[aria-selected="true"]');
  if (cell) cell.focus({preventScroll: true});
}

function key(event) {
  if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
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
      if (event.key === "Enter") { event.preventDefault(); save(cell, row, column, field, retry.value); }
      event.stopPropagation();
    });
    cell.replaceChildren(retry, el("span", {class: "rowstate problem"}, ` not saved: ${error.message}`));
    fail(`That edit was not saved: ${error.message}`);
  }
}
