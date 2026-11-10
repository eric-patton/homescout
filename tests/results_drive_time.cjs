// feat-010/AC-111-113: execute the shipped matching, controls and navigation helpers.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const path = require('node:path');
const {performance} = require('node:perf_hooks');
const elements = new Map(), storage = new Map();
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.events = {}; this.attributes = {}; }
  setAttribute(key, value) {
    this.attributes[key] = value;
    if (key === 'id') { this.id = value; elements.set(value, this); }
    if (key === 'value') this.value = value;
    if (key === 'disabled') this.disabled = true;
    if (key === 'checked') this.checked = true;
  }
  append(...children) { this.children.push(...children); }
  addEventListener(key, handler) { this.events[key] = handler; }
  replaceChildren(...children) { this.children = children; }
  replaceWith() {}
  remove() {}
}
const context = vm.createContext({Node: Element, console, setTimeout() { return 1; }, clearTimeout() {},
  location: {pathname: '/results/search'}, Date,
  sessionStorage: {getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
  document: {readyState: 'loading', addEventListener() {}, createElement: tag => new Element(tag),
    createTextNode: text => ({textContent: text}), getElementById: id => elements.get(id)},
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/homescout/web/static/common.js'), 'utf8'), context);
const run = code => vm.runInContext(code, context);
const value = code => JSON.parse(run(`JSON.stringify(${code})`));
assert.deepEqual(value('driveBounds({min:"",max:" "})'), {min:null,max:null});
assert.deepEqual(value('driveBounds({min:"0",max:""})'), {min:0,max:null});
for (const min of ['-1', 'NaN', 'Infinity', 'abc']) assert.ok(value(`driveBounds({min:${JSON.stringify(min)}})`).error);
assert.ok(value('driveBounds({min:"61",max:"60"})').error);
run(`var areas = [{ref:'work',name:'Work',address:'Work public library',routing:{direction:'to'}},
  {ref:'family',name:'Family',address:'Family public library',routing:{direction:'from'}}];
var visit = readResultsVisit('search'); var changes = 0;
var controller = new ResultDriveFilters({search:'search',run_id:'run',rows:[],drive_time_areas:areas},
  visit, () => { changes++; }); controller.group();`);
const work = elements.get('drive-work');
work.events.change({target:{checked:true}});
assert.deepEqual(value('controller.active()'), []);
elements.get('drive-work-max').events.input({target:{value:'60'}});
assert.deepEqual(value('controller.active()'), [{ref:'work',min:null,max:60}]);
elements.get('drive-work-min').events.input({target:{value:'55'}});
assert.deepEqual(value('controller.active()'), [{ref:'work',min:55,max:60}]);
run(`var row = {values:{Property:'Family-collected house',Price:250000},judgment:null,
  drive_times:{work:{status:'estimated',minutes:58},family:{status:'estimated',minutes:30}}};`);
assert.equal(run('driveMatch(row, controller.active())'), 'match');
for (const minutes of [55, 60]) assert.equal(run(`row.drive_times.work.minutes=${minutes};driveMatch(row,controller.active())`), 'match');
for (const minutes of [54.999999,60.000001]) assert.equal(run(`row.drive_times.work.minutes=${minutes};driveMatch(row,controller.active())`), 'excluded');
run('row.drive_times.work.minutes=58');
elements.get('drive-family').events.change({target:{checked:true}});
elements.get('drive-family-min').events.input({target:{value:'20'}});
elements.get('drive-family-max').events.input({target:{value:'40'}});
assert.equal(run('driveMatch(row,controller.active())'), 'match');
assert.equal(run('row.drive_times.family.minutes=19.999;driveMatch(row,controller.active())'), 'excluded');
assert.equal(run('row.drive_times.family={status:"pending"};driveMatch(row,controller.active())'), 'pending');
assert.equal(run('row.drive_times.family={status:"unavailable",minutes:null};driveMatch(row,controller.active())'), 'unavailable');
run('controller.clear("family");visit.query="Family-collected";visit.filters={Price:"$250,000"};');
assert.equal(run('matchesResults(row,visit,[{name:"Price",origin:"listing"}])'), true);
assert.equal(run('visit.filters.Price="999";matchesResults(row,visit,[{name:"Price"}])'), false);
elements.get('drive-work-min').events.input({target:{value:'61'}});
assert.deepEqual(value('controller.active()'), []);
assert.equal(elements.get('drive-work-min').attributes['aria-invalid'], 'true');
run('controller.clear();');
assert.deepEqual(value('controller.active()'), []);
run(`visit.query='Family'; carryResults({},'search','/map/search'); resultVisit=null; location.pathname='/map/search';`);
assert.equal(run('readResultsVisit("search").query'), 'Family');
run('resultVisit=null;');
assert.equal(run('readResultsVisit("search").query'), '');
run(`visit = readResultsVisit('search');visit.query='old';carryResults({},'search','/map/search');
  resultVisit=null;location.pathname='/results/other';`);
assert.equal(run('readResultsVisit("other").query'), '');
run(`var navTime=0;Date={now:()=>navTime};resultVisit=null;location.pathname='/results/search';
  visit=readResultsVisit('search');visit.query='retained through editing';
  carryResults({},'search','/search/search');resultVisit=null;location.pathname='/search/search';
  aboutSearch('search','search');navTime=120000;
  carryResults({},'search','/results/search');resultVisit=null;location.pathname='/results/search';`);
assert.equal(run('readResultsVisit("search").query'), 'retained through editing');
run(`var many = Array.from({length:5000}, (_,i) => ({values:{Property:String(i)},
  drive_times:{work:{minutes:i%100,status:'estimated'}}}));
  var active = [{ref:'work',min:55,max:60}];`);
assert.equal(run('many.filter(row=>driveMatch(row,active)==="match").length'), 300);
const started = performance.now();
for (let i=0; i<20; i++) run('many.filter(row=>driveMatch(row,active)==="match")');
assert.ok((performance.now()-started)/20 < 200, 'Full-pool numeric matching exceeds 200ms');
(async () => {
  run(`controller.rows=[{listing_id:'a',latitude:1,longitude:2,drive_times:{work:{status:'estimated',minutes:58}}}];
    visit.drive={work:{selected:true,min:'55',max:'60'}};
    ask=async()=>({search:'other',run_id:'run',areas:[],rows:[],pass:{finished:true}});`);
  await run('controller.poll()');
  assert.equal(run('controller.rows[0].drive_times.work.minutes'), 58);
  assert.ok(run('controller.message.includes("Search results changed")'));
  run(`ask=async()=>({search:'search',run_id:'run',areas:[areas[1]],rows:[],pass:{finished:true}});`);
  await run('controller.poll()');
  assert.deepEqual(value('controller.active()'), []);
  assert.ok(run('controller.message.includes("Changed or removed")'));
  run(`var empty=new ResultDriveFilters({search:'search',rows:[],drive_time_areas:[]},visit,()=>{});`);
  assert.equal(run('empty.group()'), null);
  console.log('Shipped controls, validation, AND matching, stale replies and navigation passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
