// feat-010/AC-114, feat-010/AC-53: closing a tall Drive time panel after scrolling draws the rows
// the taller table now shows. Review round 1, A1: closing only re-measured the table, and rows are
// drawn for the height the table had plus a 12-row margin, so a panel taller than that margin left
// blank space under the last drawn row until the next scroll.
//
// Runs the shipped fit(), window_() and the compact controller's own toggle against a small fake
// layout: the table's top is the header's height, plus the panel's height while it is open.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = process.env.HOMESCOUT_STATIC || path.join(__dirname, '../src/homescout/web/static');
const VIEWPORT = 917, HEADER = 200, LINE = 24, AREAS = 25;

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
for (const script of ['common.js', 'results.js']) {
  vm.runInContext(fs.readFileSync(path.join(STATIC, script), 'utf8'), context);
}
const run = (code) => vm.runInContext(code, context);

// A long list, one height per row, and a search with enough locations to make a tall panel.
run(`rowFor = (row, index) => ({index});
  state.wrap = false; state.showPhotos = false;
  state.shown = Array.from({length: 600}, (_, i) => ({listing_id: String(i)}));
  state.drive = new ResultDriveFilters({search: 'search', run_id: 'run', rows: [],
    drive_time_configured: true, drive_time_areas: Array.from({length: ${AREAS}}, (_, i) =>
      ({ref: 'a' + i, name: 'Place ' + i, address: 'Address ' + i, routing: {direction: 'to'}}))},
    readResultsVisit('search'), () => {}, {compact: true});
  state.drive.toggle(); state.drive.group();`);
const height = run('ROW_HEIGHT');
const drawn = () => nodes.get('body').children.map((row) => row.index);
const covers = () => {
  const rows = drawn();
  const top = scroller.scrollTop, bottom = scroller.scrollTop + scroller.clientHeight;
  return rows.length && rows[0] * height <= top && (rows[rows.length - 1] + 1) * height >= bottom;
};

run('fit(); window_();');
assert.equal(nodes.get('drive-filters').hidden, true, 'the panel starts closed');
const closedHeight = scroller.clientHeight;
assert.ok(covers(), 'rows cover the table on arrival');

// Open the tall panel: the table shrinks to its minimum.
nodes.get('drive-toggle').events.click();
assert.equal(nodes.get('drive-filters').hidden, false);
assert.ok(scroller.clientHeight < closedHeight, 'the open panel pushes the table down');

// Scroll well into the list while it is open, as the scroll listener would.
scroller.scrollTop = 100 * height;
run('window_()');
assert.ok(covers(), 'rows cover the short table while the panel is open');

// Close it: the table grows by more than the drawing margin, and its rows must follow.
nodes.get('drive-toggle').events.click();
assert.equal(nodes.get('drive-filters').hidden, true);
assert.equal(scroller.clientHeight, closedHeight, 'the table is given its room back');
assert.ok(scroller.clientHeight - 240 > run('OVERSCAN') * height,
  'the fixture really is taller than the drawing margin');
assert.ok(covers(), 'closing the panel draws the rows the taller table now shows (no blank space)');

console.log('Closing a tall Drive time panel after scrolling redraws the rows for the new height.');
