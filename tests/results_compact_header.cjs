// feat-010/AC-114: the Results page's compact Drive time control, executed from the shipped code.
// Also holds feat-010/AC-111, AC-112 and AC-113 to what they said before the header was compacted:
// the same controls, the same incomplete notice while results are incomplete, the same chips and
// clearing, and the Map page's box exactly as it was.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const STATIC = path.join(__dirname, '../src/homescout/web/static');

function harness() {
  const nodes = new Map();
  let fits = 0;
  class Element {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.attributes = {};
      this.events = {};
      this.hidden = false;
      this.parent = null;
    }
    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name === 'id') { this.id = value; nodes.set(value, this); }
      if (name === 'hidden') this.hidden = true;
      if (name === 'disabled') this.disabled = true;
      if (name === 'checked') this.checked = true;
      if (name === 'value') this.value = value;
    }
    getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
    append(...children) {
      for (const child of children) { child.parent = this; this.children.push(child); }
    }
    replaceChildren(...children) { this.children = []; this._text = undefined; this.append(...children); }
    addEventListener(name, handler) { this.events[name] = handler; }
    get textContent() {
      if (this._text !== undefined) return this._text;
      return this.children.map((child) => child.textContent).join('');
    }
    set textContent(text) { this.children = []; this._text = String(text); }
    replaceWith(next) {
      if (this.parent) {
        const at = this.parent.children.indexOf(this);
        this.parent.children[at] = next;
        next.parent = this.parent;
      }
      if (this.id && nodes.get(this.id) === this) nodes.delete(this.id);
      if (next.id) nodes.set(next.id, next);
      for (const each of walk(next)) if (each.id) nodes.set(each.id, each);
    }
    remove() {
      if (this.parent) this.parent.children = this.parent.children.filter((one) => one !== this);
      for (const each of walk(this)) if (each.id && nodes.get(each.id) === each) nodes.delete(each.id);
    }
  }
  function* walk(node) {
    yield node;
    for (const child of node.children || []) if (child instanceof Element) yield* walk(child);
  }
  const context = vm.createContext({
    Node: Element, console, setTimeout() { return 1; }, clearTimeout() {},
    location: {pathname: '/results/search'}, Date,
    sessionStorage: {getItem() { return null; }, setItem() {}, removeItem() {}},
    document: {readyState: 'loading', addEventListener() {}, createElement: (tag) => new Element(tag),
      createTextNode: (text) => ({textContent: text}), getElementById: (id) => nodes.get(id) || null},
    fetch() { throw new Error('This check must not reach the network'); },
  });
  vm.runInContext(fs.readFileSync(path.join(STATIC, 'common.js'), 'utf8'), context);
  context.fit = () => { fits += 1; };
  const run = (code) => vm.runInContext(code, context);
  const page = new Element('main');
  return {run, nodes, page, walk, fits: () => fits, Element};
}

const AREAS = `[
  {ref:'church', name:'Church', address:'25890 LA-442, Independence, LA 70443', routing:{direction:'to'}},
  {ref:'work', name:'Work', address:'Work public library', routing:{direction:'to'}}]`;
const ROWS = `[
  {listing_id:'a', drive_times:{church:{status:'estimated',minutes:20}, work:{status:'estimated',minutes:58}}},
  {listing_id:'b', drive_times:{church:{status:'estimated',minutes:40}, work:{status:'estimated',minutes:50}}}]`;

function compact(h, areas = AREAS, configured = true) {
  h.run(`var visit = readResultsVisit('search'); var changes = 0;
    var controller = new ResultDriveFilters({search:'search', run_id:'run', rows:${ROWS},
      drive_time_areas:${areas}, drive_time_configured:${configured}}, visit,
      () => { changes++; controller.status(controller.rows); }, {compact: true});`);
  const toggle = h.run('controller.toggle()');
  const panel = h.run('controller.group()');
  const notice = h.run(`el("p", {id: "drive-status", class: "drive-status", role: "status", hidden: true})`);
  h.page.append(toggle, panel, notice);
  for (const node of [toggle, panel, notice]) for (const each of h.walk(node)) if (each.id) h.nodes.set(each.id, each);
  h.run('controller.status(controller.rows)');  // the page's first apply()
  return {toggle: () => h.nodes.get('drive-toggle'), panel: () => h.nodes.get('drive-filters'), notice};
}

// As a browser does: the box holds what was typed, then its listener runs.
const type = (h, id, value) => { const box = h.nodes.get(id); box.value = value; box.events.input({target: box}); };
const tick = (h, id, checked = true) => { const box = h.nodes.get(id); box.checked = checked; box.events.change({target: box}); };

// Collapsed by default, with every input already in the page so ids, values and listeners survive.
{
  const h = harness();
  const {toggle, panel} = compact(h);
  assert.equal(toggle().tagName, 'BUTTON');
  assert.equal(toggle().getAttribute('aria-expanded'), 'false');
  assert.equal(toggle().getAttribute('aria-controls'), 'drive-filters');
  assert.equal(toggle().textContent, 'Drive time');
  assert.equal(panel().tagName, 'FIELDSET');
  assert.equal(panel().hidden, true, 'the panel starts closed on every visit');
  for (const id of ['drive-church', 'drive-church-min', 'drive-church-max', 'drive-work', 'drive-work-min',
    'drive-work-max', 'drive-church-error', 'drive-panel-status']) {
    assert.ok(h.nodes.get(id), `${id} exists while the panel is closed`);
  }
  assert.equal(h.run('controller.open'), false);

  // Opening and closing: the panel shows and hides, the button says so, the table is re-measured.
  const fitsBefore = h.fits();
  toggle().events.click();
  assert.equal(panel().hidden, false);
  assert.equal(toggle().getAttribute('aria-expanded'), 'true');
  assert.ok(h.fits() > fitsBefore, 'opening re-measures the table (AC-53)');
  const fitsOpen = h.fits();
  toggle().events.click();
  assert.equal(panel().hidden, true);
  assert.equal(toggle().getAttribute('aria-expanded'), 'false');
  assert.ok(h.fits() > fitsOpen, 'closing re-measures the table (AC-53)');

  // A value typed while open is still there after closing and reopening.
  toggle().events.click();
  tick(h, 'drive-church');
  type(h, 'drive-church-max', '25');
  const box = h.nodes.get('drive-church-max');
  toggle().events.click();
  toggle().events.click();
  assert.equal(h.nodes.get('drive-church-max'), box, 'the same input, not a rebuilt one');
  assert.equal(h.nodes.get('drive-church-max').value, '25');
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(controller.active())')), [{ref: 'church', min: null, max: 25}]);
}

// The summary names every range in force, so a closed panel hides nothing that is active.
{
  const h = harness();
  const {toggle, panel} = compact(h);
  assert.equal(toggle().textContent, 'Drive time', 'nothing in force');
  tick(h, 'drive-church');
  assert.equal(toggle().textContent, 'Drive time', 'ticked with no bounds is no constraint');
  type(h, 'drive-church-max', '25');
  assert.equal(toggle().textContent, 'Drive time: Church ≤25 min', 'maximum only');
  assert.equal(toggle().getAttribute('data-active'), 'true');
  type(h, 'drive-church-min', '0');
  assert.equal(toggle().textContent, 'Drive time: Church 0-25 min', 'both bounds, zero included');
  tick(h, 'drive-work');
  type(h, 'drive-work-min', '55');
  assert.equal(toggle().textContent, 'Drive time: Church 0-25 min; Work ≥55 min', 'several, minimum only');
  type(h, 'drive-work-max', '50');
  assert.equal(toggle().textContent, 'Drive time: Church 0-25 min; Work: invalid entry',
    'an entry that cannot be used is said, not dropped');
  assert.equal(h.nodes.get('drive-work-error').textContent, 'Minimum cannot be greater than maximum.');
  assert.equal(panel().hidden, true, 'the summary changed without opening the panel');
  h.run('controller.busy = true; controller.status(controller.rows);');
  assert.equal(toggle().textContent, 'Drive time: Church 0-25 min; Work: invalid entry · calculating...');
  h.run('controller.busy = false;');
  tick(h, 'drive-work', false);
  tick(h, 'drive-church', false);
  assert.equal(toggle().textContent, 'Drive time');
  assert.equal(toggle().getAttribute('data-active'), 'false');
}

// To or from is added only when two locations share a name.
{
  const h = harness();
  const {toggle} = compact(h, `[
    {ref:'out', name:'Family', address:'Family public library', routing:{direction:'from'}},
    {ref:'in', name:'Family', address:'Family public library', routing:{direction:'to'}}]`);
  tick(h, 'drive-out');
  type(h, 'drive-out-max', '30');
  tick(h, 'drive-in');
  type(h, 'drive-in-min', '5');
  assert.equal(toggle().textContent, 'Drive time: Family (from) ≤30 min; Family (to) ≥5 min');
}

// No drive-time areas: no button and no panel.
{
  const h = harness();
  h.run(`var bare = new ResultDriveFilters({search:'search', rows:[], drive_time_areas:[]},
    readResultsVisit('search'), () => {}, {compact: true});`);
  assert.equal(h.run('bare.toggle()'), null);
  assert.equal(h.run('bare.group()'), null);
}

// The yellow notice is for incomplete results only; once every estimate is in, the panel says so.
{
  const h = harness();
  const {notice} = compact(h);
  tick(h, 'drive-church');
  type(h, 'drive-church-max', '25');
  assert.equal(notice.hidden, true, 'every estimate is in: no yellow notice');
  assert.match(h.nodes.get('drive-panel-status').textContent, /All candidates evaluated\./);
  h.run(`controller.rows[1].drive_times.church = {status:'pending', minutes:null}; controller.status(controller.rows);`);
  assert.equal(notice.hidden, false, 'a pending estimate shows the notice');
  assert.match(notice.textContent, /Results incomplete\. Showing confirmed matches only\. 1 pending\./);
  assert.ok(notice.children.some((child) => child.textContent === 'Retry driving estimates'), 'Retry in the notice');
  assert.match(h.nodes.get('drive-panel-status').textContent, /Results incomplete/);
  assert.ok(h.nodes.get('drive-panel-status').children.some((child) => child.textContent === 'Retry driving estimates'),
    'Retry in the panel');
  h.run(`controller.rows[1].drive_times.church = {status:'unavailable', minutes:null}; controller.status(controller.rows);`);
  assert.equal(notice.hidden, false);
  assert.match(notice.textContent, /1 unavailable\./);
  h.run(`controller.rows[1].drive_times.church = {status:'estimated', minutes:40}; controller.status(controller.rows);`);
  assert.equal(notice.hidden, true, 'hidden again once all are evaluated');
  h.run(`controller.message = 'Driving estimates failed. Retry when ready.'; controller.status(controller.rows);`);
  assert.equal(notice.hidden, false, 'a failure is shown');
  assert.match(notice.textContent, /Driving estimates failed/);
  h.run(`controller.message = ''; controller.status(controller.rows);`);
  tick(h, 'drive-church', false);
  assert.equal(notice.hidden, true, 'nothing in force: no notice');
}

// Without a routing key: in the notice while rows are missing, otherwise in the panel.
{
  const h = harness();
  const {notice} = compact(h, AREAS, false);
  assert.match(h.nodes.get('drive-panel-status').textContent, /Routing unavailable: configure the ORS key/);
  tick(h, 'drive-church');
  type(h, 'drive-church-max', '25');
  assert.equal(notice.hidden, true);
  assert.match(h.nodes.get('drive-panel-status').textContent, /Routing unavailable: configure the ORS key/);
  h.run(`controller.rows[0].drive_times.church = {status:'unavailable', minutes:null}; controller.status(controller.rows);`);
  assert.equal(notice.hidden, false);
  assert.match(notice.textContent, /1 unavailable\. Routing unavailable: configure the ORS key/);
}

// Chips and clearing still lift drive-time ranges (AC-113), and the summary follows.
{
  const h = harness();
  const {toggle, panel} = compact(h);
  toggle().events.click();
  tick(h, 'drive-church');
  type(h, 'drive-church-max', '25');
  tick(h, 'drive-work');
  type(h, 'drive-work-min', '55');
  const chips = h.run('controller.chips()');
  assert.equal(chips.length, 2);
  chips[0].children.find((child) => child.tagName === 'BUTTON').events.click();
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(controller.active().map(one => one.ref))')), ['work']);
  assert.equal(toggle().textContent, 'Drive time: Work ≥55 min');
  assert.equal(panel().hidden, false, 'clearing one keeps the panel as it was');
  assert.ok(!h.nodes.get('drive-church').checked, 'the cleared location is unticked');
  h.run('controller.clear()');
  assert.deepEqual(JSON.parse(h.run('JSON.stringify(controller.active())')), []);
  assert.equal(toggle().textContent, 'Drive time');
}

// The compact panel carries no routing credit; the Results page says it once, in its bar.
{
  const h = harness();
  const {panel} = compact(h);
  const text = [...h.walk(panel())].map((node) => node.children.map((child) => child.textContent || '').join('')).join(' ');
  assert.doesNotMatch(text, /openrouteservice/);
  assert.match(text, /no live traffic/);
  const results = fs.readFileSync(path.join(STATIC, 'results.js'), 'utf8');
  assert.equal(results.split('"openrouteservice by HeiGIT"').length - 1, 1, 'the credit once on the Results page');
  assert.match(results, /link\("https:\/\/creativecommons\.org\/licenses\/by-sa\/4\.0\/", "CC-BY-SA 4\.0"\)/);
  assert.match(results, /\{compact: true\}/, 'the Results page asks for the compact form');
  const map = fs.readFileSync(path.join(STATIC, 'fire.js'), 'utf8');
  assert.doesNotMatch(map, /compact/, 'the Map page does not');
}

// The Map page's box is exactly what it was: legend, explanation, address, credit, notice rules.
{
  const h = harness();
  h.run(`var mapVisit = readResultsVisit('search');
    var mapped = new ResultDriveFilters({search:'search', run_id:'run', rows:${ROWS},
      drive_time_areas:${AREAS}, drive_time_configured:true}, mapVisit, () => {});`);
  assert.equal(h.run('mapped.toggle()'), null);
  const box = h.run('mapped.group()');
  assert.equal(box.getAttribute('class'), 'drive-filters');
  assert.equal(box.hidden, false);
  assert.equal(box.children[0].tagName, 'LEGEND');
  assert.equal(box.children[0].textContent, 'Drive time');
  assert.equal(box.children[1].textContent, 'Choose locations to narrow these results. All active ranges must match. '
    + 'Minutes are inclusive; blank means no bound. Estimates have no live traffic.');
  assert.equal(box.children[3].textContent, 'Routing: openrouteservice by HeiGIT / OpenStreetMap / CC-BY-SA 4.0.');
  assert.equal(box.children.length, 4);
  for (const each of h.walk(box)) if (each.id) h.nodes.set(each.id, each);
  const place = h.nodes.get('drive-church').parent;
  assert.equal(place.children.at(-1).textContent, '25890 LA-442, Independence, LA 70443', 'the address is shown');
  const notice = h.run(`el("p", {id: "drive-status", class: "drive-status", role: "status", hidden: true})`);
  h.nodes.set('drive-status', notice);
  h.run('mapped.status(mapped.rows)');
  assert.equal(notice.hidden, true, 'nothing in force');
  h.nodes.get('drive-church').events.change({target: {checked: true}});
  h.nodes.get('drive-church-max').events.input({target: {value: '25'}});
  h.run('mapped.status(mapped.rows)');
  assert.equal(notice.hidden, false, 'the Map page still shows its notice whenever a range is in force');
  assert.equal(notice.textContent, 'All candidates evaluated.Retry driving estimates');
}

// An unnamed location is named by its address; the compact line does not print it twice.
{
  const h = harness();
  compact(h, `[{ref:'church', name:'25890 LA-442, Tickfaw, LA 70443', address:'25890 LA-442, Tickfaw, LA 70443',
    routing:{direction:'to'}}]`);
  const place = h.nodes.get('drive-church').parent;
  assert.equal(place.children.filter((child) => child.tagName === 'SPAN').length, 0);
  assert.match(place.textContent, /25890 LA-442, Tickfaw, LA 70443 \(to location\)/);
}

console.log('Compact Drive time control: collapsed, opened, summaries, notice, chips and the Map box pass.');
