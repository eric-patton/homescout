// feat-010/AC-114, feat-010/AC-53: opening and closing the Drive time panel re-measures the table
// and draws the rows its new height shows, and does nothing else.
//
// Review round 1, A1: closing only re-measured the table, and rows are drawn for the height the table
// had plus a 12-row margin, so a panel taller than that margin, closed after scrolling, left blank
// space under the last drawn row until the next scroll.
//
// Review round 2, A1: the shared helper that fixed it was called `relayout`, a name results.js
// already declares for re-laying-out its columns. The page's declaration replaced the shared one, so
// every panel toggle also forgot every measured row height, and a wrapped table, scrolled through
// rows of their own heights, jumped to different listings under the reader.
//
// Runs the shipped fit(), window_() and the compact controller's own toggle, with common.js and
// results.js loaded into one scope in page order, against a small fake layout: the table's top is
// the header's height, plus the panel's height while it is open.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = process.env.HOMESCOUT_STATIC || path.join(__dirname, '../src/homescout/web/static');
const VIEWPORT = 917, HEADER = 200, LINE = 24, AREAS = 25, ROWS = 600;

function page() {
  const nodes = new Map();
  class Element {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.attributes = {};
      this.events = {};
      this.style = {};
      this.hidden = false;
      this.parent = null;
    }
    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name === 'id') { this.id = value; nodes.set(value, this); }
      if (name === 'hidden') this.hidden = true;
      if (name === 'disabled') this.disabled = true;
      if (name === 'checked') this.checked = true;
    }
    getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
    append(...children) { for (const child of children) { child.parent = this; this.children.push(child); } }
    replaceChildren(...children) {
      this.children = [];
      for (const child of children) {
        if (child && child.fragment) this.children.push(...child.children);
        else this.append(child);
      }
    }
    addEventListener(name, handler) { this.events[name] = handler; }
    querySelector() { return null; }
    get textContent() { return this._text !== undefined ? this._text : this.children.map((c) => c.textContent || '').join(''); }
    set textContent(text) { this.children = []; this._text = String(text); }
    replaceWith(next) { if (next.id) nodes.set(next.id, next); }
    remove() {}
  }

  const panelHeight = () => {
    const panel = nodes.get('drive-filters');
    return panel && !panel.hidden ? AREAS * LINE + 40 : 0;
  };
  const scroller = new Element('div');
  scroller.setAttribute('id', 'scroller');
  scroller.scrollTop = 0;
  Object.defineProperty(scroller, 'clientHeight', {get: () => parseFloat(scroller.style.height || '0')});
  scroller.getBoundingClientRect = () => ({top: HEADER + panelHeight()});
  for (const id of ['body', 'sizer', 'above', 'below']) {
    const node = new Element(id === 'body' ? 'tbody' : 'div');
    node.setAttribute('id', id);
    node.firstElementChild = {style: {}};
  }

  const storage = new Map();
  const context = vm.createContext({
    Node: Element, console, setTimeout() { return 1; }, clearTimeout() {}, Date,
    location: {pathname: '/results/search'}, CSS: {escape: (text) => text},
    sessionStorage: {getItem() { return null; }, setItem() {}, removeItem() {}},
    window: {innerHeight: VIEWPORT, scrollY: 0, addEventListener() {},
      localStorage: {getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v),
        removeItem: (k) => storage.delete(k)}},
    document: {
      readyState: 'loading', addEventListener() {},
      createElement: (tag) => new Element(tag),
      createTextNode: (text) => ({textContent: text}),
      createDocumentFragment: () => ({fragment: true, children: [], append(...more) { this.children.push(...more); }}),
      getElementById: (id) => nodes.get(id) || null,
      querySelector: () => null,
      documentElement: {get scrollHeight() {
        return Math.max(VIEWPORT, HEADER + panelHeight() + scroller.clientHeight + 10);
      }},
    },
    fetch() { throw new Error('This check must not reach the network'); },
  });
  // In page order, into one scope, exactly as results.html loads them: a name results.js declares
  // replaces the same name in common.js, which is the collision this file now guards against.
  for (const script of ['common.js', 'results.js']) {
    vm.runInContext(fs.readFileSync(path.join(STATIC, script), 'utf8'), context);
  }
  const run = (code) => vm.runInContext(code, context);
  // A long list, and a search with enough locations to make a tall panel. A drawn row reports the
  // height it really has, which is what `settle` measures.
  run(`var realHeight = () => ROW_HEIGHT;
    rowFor = (row, index) => ({index, dataset: {index: String(index)},
      getBoundingClientRect: () => ({height: realHeight(index)})});
    state.showPhotos = false;
    state.shown = Array.from({length: ${ROWS}}, (_, i) => ({listing_id: String(i)}));
    state.drive = new ResultDriveFilters({search: 'search', run_id: 'run', rows: [],
      drive_time_configured: true, drive_time_areas: Array.from({length: ${AREAS}}, (_, i) =>
        ({ref: 'a' + i, name: 'Place ' + i, address: 'Address ' + i, routing: {direction: 'to'}}))},
      readResultsVisit('search'), () => {}, {compact: true});
    state.drive.toggle(); state.drive.group();`);
  const toggle = () => nodes.get('drive-toggle').events.click();
  const panel = () => nodes.get('drive-filters');
  const drawn = () => nodes.get('body').children.map((row) => row.index);
  return {run, nodes, scroller, toggle, panel, drawn};
}

// One height per row: closing a tall panel after scrolling draws rows to the bottom of the table.
{
  const {run, scroller, toggle, panel, drawn} = page();
  run('state.wrap = false; fit(); window_();');
  const height = run('ROW_HEIGHT');
  const covers = () => {
    const rows = drawn();
    const top = scroller.scrollTop, bottom = scroller.scrollTop + scroller.clientHeight;
    return rows.length && rows[0] * height <= top && (rows[rows.length - 1] + 1) * height >= bottom;
  };
  assert.equal(panel().hidden, true, 'the panel starts closed');
  const closedHeight = scroller.clientHeight;
  assert.ok(covers(), 'rows cover the table on arrival');

  toggle();
  assert.equal(panel().hidden, false);
  assert.ok(scroller.clientHeight < closedHeight, 'the open panel pushes the table down');

  scroller.scrollTop = 100 * height;
  run('window_()');
  assert.ok(covers(), 'rows cover the short table while the panel is open');

  toggle();
  assert.equal(panel().hidden, true);
  assert.equal(scroller.clientHeight, closedHeight, 'the table is given its room back');
  assert.ok(scroller.clientHeight - 240 > run('OVERSCAN') * height,
    'the fixture really is taller than the drawing margin');
  assert.ok(covers(), 'closing the panel draws the rows the taller table now shows (no blank space)');
}

// Wrapped rows of their own heights, all measured already and none of them the guessed height:
// opening and closing the panel keeps every measurement and the same listing at the top.
{
  const {run, scroller, toggle, panel, drawn} = page();
  run(`state.wrap = true;
    realHeight = (index) => (index % 3 === 0 ? 92 : 38);
    for (let i = 0; i < state.shown.length; i++) state.heights.set(String(i), realHeight(i));
    fit(); window_();`);
  assert.notEqual(run('guessHeight()'), 92, 'the measured heights differ from the guess');
  assert.notEqual(run('guessHeight()'), 38, 'the measured heights differ from the guess');
  const measured = run('state.heights.size');
  assert.equal(measured, ROWS);

  toggle();
  assert.equal(panel().hidden, false);
  scroller.scrollTop = run('ladder()[250]');  // the top of listing 250, by measured heights
  run('window_()');
  const atTop = () => run('rowAt(ladder(), document.getElementById("scroller").scrollTop)');
  assert.equal(atTop(), 250);
  const before = scroller.scrollTop;

  toggle();
  assert.equal(panel().hidden, true);
  assert.equal(run('state.heights.size'), measured, 'closing the panel must not forget measured row heights');
  assert.equal(scroller.scrollTop, before, 'the scroll position is left where the reader had it');
  assert.equal(atTop(), 250, 'the same listing is still at the top of the window');
  const rows = drawn();
  assert.ok(rows[0] <= 250 && rows[rows.length - 1] >= 250, 'and it is one of the rows drawn');
  const bottom = run('rowAt(ladder(), document.getElementById("scroller").scrollTop'
    + ' + document.getElementById("scroller").clientHeight)');
  assert.ok(rows[rows.length - 1] >= bottom, 'rows reach the bottom of the taller table');

  // The disclosure beside the heading uses the same helper and must keep them too.
  run('howItWorks("results", "How this table works").events.toggle()');
  assert.equal(run('state.heights.size'), measured, 'toggling the disclosure must not forget them');
  assert.equal(atTop(), 250);
}

console.log('Panel toggles redraw rows for the new height and keep measured heights and position.');
