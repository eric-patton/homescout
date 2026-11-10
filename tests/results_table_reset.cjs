// B1, feat-010/AC-45, feat-010/AC-57, feat-010/AC-113: reset clears retained column filters.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const storage = new Map();
const found = {
  search: 'commute', run_id: 'run',
  columns: [{name: 'Property', origin: 'listing'}, {name: 'Price', origin: 'listing'}],
  drive_time_areas: [{ref: 'work', name: 'Work', address: 'Work fixture', routing: {direction: 'to'}}],
  drive_time_configured: false,
  rows: ['Boundary55', 'FamilyCollected58', 'Boundary60'].map((name, index) => ({
    listing_id: String(index), values: {Property: name, Price: 200000 + index * 10000},
    drive_times: {work: {status: 'estimated', minutes: 55 + index * 2.5}},
  })),
};
let resultRequests = 0;
const context = vm.createContext({console, CSS: {escape: text => text},
  setTimeout() { return 1; }, clearTimeout() {},
  location: {pathname: '/results/commute'},
  window: {localStorage: {
    getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  }},
  sessionStorage: {getItem() { return null; }, removeItem() {}},
  document: {readyState: 'loading', addEventListener() {},
    getElementById() { return null; }, querySelector() { return null; }},
  fetch: async url => {
    assert.ok(['/api/results/commute', '/api/tags'].includes(url), `Unexpected request: ${url}`);
    if (url === '/api/results/commute') resultRequests++;
    return {ok: true, json: async () => structuredClone(url === '/api/tags' ? {tags: []} : found)};
  },
});
for (const script of ['common.js', 'results.js']) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/homescout/web/static', script),
    'utf8'), context);
}
const run = code => vm.runInContext(code, context);
const value = code => JSON.parse(run(`JSON.stringify(${code})`));

(async () => {
  // Keep real load, setFilter, reset, matching and navigation. Browser acceptance checks rendering.
  run('draw=()=>{}; state.search="commute";');
  await run('load()');
  assert.equal(run('state.shown.length'), 3);
  run('setFilter("Property", "Boundary")');
  assert.equal(run('state.shown.length'), 2);
  assert.deepEqual(value('readResultsVisit("commute").filters'), {Property: 'Boundary'});
  run('state.showPhotos=true;state.wrap=true;remember();reset();');
  await new Promise(setImmediate);
  assert.deepEqual(value('state.filters'), {}, 'reset must clear the applied column filters');
  assert.deepEqual(value('readResultsVisit("commute").filters'), {},
    'reload/navigation must not restore the cleared column filters');
  assert.equal(run('state.shown.length'), 3, 'reset must restore rows hidden by the column');
  assert.equal(run('state.showPhotos'), false);
  assert.equal(run('state.wrap'), false);

  // Reset only the column controls, retaining the visit's other active constraints and sorting.
  run(`state.query='Boundary';state.judgment='all';state.showGone=true;
    state.sortBy='Price';state.descending=true;
    state.drive.context.drive={work:{selected:true,min:'55',max:'60'}};
    setFilter('Property','Boundary55');`);
  assert.equal(run('state.shown.length'), 1);
  run('reset()');
  await new Promise(setImmediate);
  assert.deepEqual(value('state.shown.map(row=>row.values.Property)'), ['Boundary60', 'Boundary55']);
  assert.equal(run('state.query'), 'Boundary');
  assert.equal(run('state.judgment'), 'all');
  assert.equal(run('state.showGone'), true);
  assert.equal(run('state.sortBy'), 'Price');
  assert.equal(run('state.descending'), true);
  assert.equal(run('state.drive.active().length'), 1);

  // An ordinary same-visit reload still retains an active column filter.
  run('setFilter("Property", "Boundary60")');
  await run('load()');
  assert.deepEqual(value('state.filters'), {Property: 'Boundary60'});
  assert.equal(run('state.shown.length'), 1);
  assert.equal(resultRequests, 4);
  console.log('Table reset clears retained column filters; other constraints and reload retention pass.');
})().catch(error => { console.error(error); process.exitCode = 1; });
