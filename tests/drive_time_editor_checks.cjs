/* Execute the real editor state machine with controlled routing/save replies.
 * feat-010/AC-108 feat-010/AC-109: cancellation, stale requests and draft isolation. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const nodes = new Map();
class Element {
  constructor(tag, attrs = {}, children = []) {
    this.tag = tag;
    this.children = children.flat(Infinity).filter(c => c != null && c !== false);
    Object.assign(this, attrs);
    this.value = String(attrs.value ?? '');
    this.classList = {toggle() {}, add() {}, remove() {}};
    if (attrs.id) nodes.set(attrs.id, this);
  }
  addEventListener() {}
  set textContent(value) { this.children = [value]; }
  get textContent() { return this.children.map(c => c.textContent ?? c).join(''); }
  setAttribute(name, value) { this[name] = value; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  replaceWith() {}
  focus() {}
  remove() {}
}
let calls = [], notices = [], answer;
const context = vm.createContext({
  window: {addEventListener() {}},
  document: {getElementById: id => nodes.get(id), querySelector: () => null,
    createTextNode: text => text, createElementNS: (_, tag) => new Element(tag)},
  el: (tag, attrs, ...children) => new Element(tag, attrs, children),
  whenReady() {},
  say: text => notices.push(text), fail: e => notices.push(e.message),
  count: (n, what) => `${n} ${what}`, value: x => x,
  link: (url, label) => new Element('a', {href: url}, [label]),
  send: (...args) => { calls.push(args); return answer(...args); },
  console, URL, Date, Set, Map,
});
vm.runInContext(fs.readFileSync('src/homescout/web/static/search.js', 'utf8'), context);
const run = code => vm.runInContext(code, context);
function button(root, name) {
  if (root instanceof Element && root.tag === 'button' && root.children.includes(name)) return root;
  for (const child of root?.children || []) {
    const found = button(child, name);
    if (found) return found;
  }
}
function click(name) { return button(run('form'), name).onclick(); }
function input(id, value) {
  const node = nodes.get(id);
  node.value = value;
  node.oninput?.({target: node});
}
const shape = minutes => ({type: 'Polygon', coordinates: [[[0, 0], [minutes, 0],
  [0, 1], [0, 0]]]});
const work = {kind: 'drive_time', address: 'Work', center: [30, -90], minutes: 45,
  direction: 'from', provider: 'openrouteservice', public_place: true, matched: 'Matched Work',
  generated_at: '2026-11-09T00:00:00Z', geometry: shape(45), id: 'stable-work',
  name: 'Work', reason: 'Commute', excluded: false};
context.seed = structuredClone(work);
run(`held.search = {areas: [seed], exclusions: []}; held.settings = {};
  held.named = [seed, {...seed, id:'family', name:'Family'}];
  var original = held.named[0]; var family = held.named[1];
  var form;
  var list = areaList();
  function edit(target = original) {
    driveTimeDetails(target).children.at(-1).onclick(); form = driveTimeForm();
  }
  edit();`);
function reply(minutes) {
  return {area: {...work, type: 'drive_time', minutes, geometry: shape(minutes),
    generated_at: '2026-11-10T00:00:00Z', matched: null}};
}
async function preview(minutes) {
  answer = async () => reply(minutes);
  await click('Preview driving area');
}

(async () => {
  assert.equal(nodes.get('driveaddress').disabled, true);
  assert.equal(nodes.get('drivedirection').disabled, true);
  input('driveadjustment', '15'); click('Increase');
  assert.equal(nodes.get('driveminutes').value, '60');
  assert.equal(run('original.minutes'), 45);
  await preview(60);
  assert.equal(run('original.minutes'), 45);
  click('Update drive-time area');
  assert.equal(run('held.named[0] === original'), true);
  assert.equal(run('original.minutes'), 60);
  assert.equal(run('original.matched'), 'Matched Work');
  assert.equal(run('original.id'), 'stable-work');
  assert.equal(run('family.minutes'), 45);
  assert.equal(run('original.direction'), 'from');
  assert.equal(run('original.geometry.coordinates[0][1][0]'), 60);
  run('edit()'); input('driveadjustment', '5'); click('Decrease');
  await preview(55); click('Update drive-time area');
  assert.equal(run('original.minutes'), 55);

  // Invalid adjustment actions and final totals cannot calculate or change the row.
  run('edit()');
  for (const bad of ['', 'abc', '0', '-5', 'Infinity']) {
    input('driveadjustment', bad); click('Increase');
    assert.equal(run('original.minutes'), 55);
  }
  input('driveadjustment', '10'); click('Increase');
  assert.match(notices.at(-1), /at most 60/);
  for (const bad of ['', 'abc', '0', '-1', '61', 'Infinity']) {
    input('driveminutes', bad);
    const count = calls.length;
    await click('Preview driving area');
    assert.equal(calls.length, count);
    assert.equal(run('original.minutes'), 55);
  }

  // Failed and mismatched calculations retain editable input and original geometry.
  input('driveminutes', '50');
  answer = async () => { throw new Error('Routing refused'); };
  await click('Refresh preview');
  assert.equal(nodes.get('driveminutes').value, '50');
  assert.equal(run('driveTimeDraft().preview'), null);
  assert.equal(run('original.minutes'), 55);
  await preview(49);
  assert.match(notices.at(-1), /did not match/);
  assert.equal(run('driveTimeDraft().preview'), null);

  // Delayed replies must be ignored after every invalidating event.
  for (const event of ['cancel', 'input', 'adjustment', 'switch', 'remove']) {
    run('held.named = [original, family]; edit()');
    input('driveminutes', '50');
    let resolve;
    answer = () => new Promise(done => { resolve = done; });
    const pending = click('Preview driving area');
    if (event === 'cancel') click('Cancel');
    if (event === 'input') input('driveminutes', '51');
    if (event === 'adjustment') input('driveadjustment', '3');
    if (event === 'switch') run('edit(family)');
    if (event === 'remove') run('held.named.splice(0, 1); areaList();');
    resolve(reply(50)); await pending;
    assert.equal(run('driveTimeDraft().preview'), null, event);
    assert.equal(run('original.minutes'), 55, event);
    assert.equal(run('held.named.length'), event === 'remove' ? 1 : 2, event);
  }

  // Other panel saves do not discard an area draft or its valid preview.
  run('held.named = [original, family]; edit()');
  input('driveminutes', '50'); await preview(50);
  answer = async () => ({search: {areas: [seed], exclusions: []}});
  await run('save({description:"Another panel"}, "what it looks for")');
  assert.equal(run('driveTimeDraft().preview.area.minutes'), 50);
  const before = calls.length;
  await run('saveAreas()');
  assert.equal(calls.length, before, 'unfinished edit blocks area save');
  click('Update drive-time area');
  answer = async () => { throw new Error('Save failed'); };
  await run('saveAreas()');
  assert.equal(run('original.minutes'), 50);
  assert.equal(run('held.named[0]'), run('original'));
  assert.equal(run('unsaved.has("areas")'), true);
  assert.equal(run('held.savingAreas'), false);

  // Cancel preserves a previous unsaved row change and unrelated panel dirtiness.
  run('touched("criteria"); edit()');
  input('driveminutes', '40'); click('Cancel');
  assert.equal(run('original.minutes'), 50);
  assert.equal(run('unsaved.has("criteria")'), true);
  assert.equal(run('unsaved.has("areas")'), true);
  assert.equal(run('namedArea(original).id'), 'stable-work');
  console.log('Drive-time editor state checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
