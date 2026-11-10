// feat-010/AC-112, feat-010/AC-113: real controller timers must survive clearing/navigation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Timers {
  now = 0;
  next = 1;
  pending = new Map();
  set(fn, delay) {
    const id = this.next++;
    this.pending.set(id, {fn, due: this.now + delay});
    return id;
  }
  async advance(milliseconds) {
    const until = this.now + milliseconds;
    let turns = 0;
    while (true) {
      const next = [...this.pending].filter(([, one]) => one.due <= until)
        .sort((a, b) => a[1].due - b[1].due)[0];
      if (!next) break;
      assert.ok(++turns < 100, 'unexpected polling/retry loop');
      this.pending.delete(next[0]);
      this.now = next[1].due;
      await next[1].fn();
    }
    this.now = until;
  }
}

function fixture(startReply = {already_running: false}) {
  const timers = new Timers(), nodes = new Map();
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.disabled = false; }
    setAttribute(name, value) {
      this[name] = value;
      if (name === 'id') nodes.set(value, this);
      if (name === 'disabled') this.disabled = true;
    }
    append(...children) { this.children.push(...children); }
    addEventListener() {}
    replaceChildren(...children) { this.children = children; }
    replaceWith() {}
    remove() {}
  }
  const state = {posts: 0, gets: 0, reply: startReply, snapshot: null};
  const context = vm.createContext({Node: Element, console,
    setTimeout: (fn, delay) => timers.set(fn, delay),
    clearTimeout: id => timers.pending.delete(id),
    document: {createElement: tag => new Element(tag), createTextNode: text => ({textContent: text}),
      getElementById: id => nodes.get(id)},
    fetch() { throw new Error('The regression must not access the network'); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,
    '../src/homescout/web/static/common.js'), 'utf8'), context);
  const run = code => vm.runInContext(code, context);
  context.fetch = async (_, options) => {
    let answer;
    if (options.method === 'POST') {
      state.posts++;
      answer = typeof state.reply === 'function' ? state.reply(state.posts) : state.reply;
    } else {
      state.gets++;
      answer = state.snapshot;
    }
    return {ok:true,json:async()=>structuredClone(answer)};
  };
  run(`var areas = ['work','family'].map(ref => ({ref,name:ref,address:ref,
    routing:{direction:'to'}}));
    var visit={drive:{work:{selected:true,min:'55',max:'60'},
      family:{selected:true,min:'20',max:'40'}}};
    var rows=Array.from({length:3},(_,i)=>({listing_id:String(i),latitude:34+i*.001,
      longitude:-103,drive_times:{work:{status:'pending'},family:{status:'pending'}}}));
    var matches=0;
    var controller=new ResultDriveFilters({search:'commute',run_id:'run',rows,
      drive_time_areas:areas,drive_time_configured:true},visit,()=>{
        matches=rows.filter(row=>driveMatch(row,controller.active())==='match').length;
        controller.status(rows);
      });
    controller.group();`);
  nodes.set('drive-status', new Element('p'));
  const snapshot = (known, finished, familyKnown = known) => {
    const answer = JSON.parse(run('JSON.stringify(rows)'));
    for (let i=0; i<answer.length; i++) {
      answer[i].drive_times = {
        work: i<known ? {status:'estimated',minutes:58} : {status:'pending'},
        family: i<familyKnown ? {status:'estimated',minutes:30} : {status:'pending'},
      };
    }
    return {search:'commute',run_id:'run',areas:JSON.parse(run('JSON.stringify(areas)')),
      configured:true,rows:answer,pass:{finished}};
  };
  state.snapshot = snapshot(1, false);
  return {run, timers, state, snapshot,
    retryDisabled: () => nodes.get('drive-status').children[1].disabled};
}

const cases = [];
function test(name, body) { cases.push([name, body]); }

test('A1: clearing one area keeps later batches updating the remaining area', async () => {
  const f = fixture();
  await f.run('controller.calculate(false)');
  assert.equal(f.run('matches'), 1);
  assert.equal(f.run('controller.busy'), true);
  f.run('controller.clear("work")');
  f.state.snapshot = f.snapshot(3, true);
  await f.timers.advance(1000);
  assert.equal(f.run('matches'), 3);
  assert.equal(f.run('controller.busy'), false);
  assert.equal(f.retryDisabled(), false);
  assert.equal(f.state.posts, 1);
});

for (const reselectBeforeFinish of [false, true]) {
  test(`A1: clear all and reselect ${reselectBeforeFinish ? 'during' : 'after'} the job`, async () => {
    const f = fixture();
    await f.run('controller.calculate(false)');
    f.run('controller.clear()');
    const select = () => f.run(`visit.drive.work={selected:true,min:'55',max:'60'};controller.edited()`);
    if (reselectBeforeFinish) select();
    f.state.snapshot = f.snapshot(3, true);
    await f.timers.advance(1000);
    assert.equal(f.run('controller.busy'), false);
    if (!reselectBeforeFinish) select();
    await f.timers.advance(450);
    assert.equal(f.run('matches'), 3);
    assert.equal(f.retryDisabled(), false);
    assert.equal(f.state.posts, 1);
  });
}

for (const change of ['deselect', 'blank']) {
  test(`A1: ${change} all bounds keeps tracking the running pass`, async () => {
    const f = fixture();
    await f.run('controller.calculate(false)');
    f.run(change === 'deselect'
      ? 'visit.drive.work.selected=false;visit.drive.family.selected=false;controller.edited()'
      : 'for(const draft of Object.values(visit.drive)){draft.min="";draft.max="";}controller.edited()');
    f.state.snapshot = f.snapshot(3, true);
    await f.timers.advance(1000);
    assert.equal(f.run('controller.busy'), false);
    assert.equal(f.timers.pending.size, 0);
  });
}

test('A2: a navigated controller attaches to the same search job and its batches', async () => {
  const f = fixture({already_running:true,running:'result-drive-times',running_on:'commute'});
  await f.run('controller.calculate(false)');
  assert.equal(f.state.gets, 1);
  assert.equal(f.run('controller.busy'), true);
  assert.equal(f.run('matches'), 1);
  f.state.snapshot = f.snapshot(3, true);
  await f.timers.advance(1450);
  assert.equal(f.run('matches'), 3);
  assert.equal(f.run('controller.busy'), false);
  assert.equal(f.retryDisabled(), false);
  assert.equal(f.state.posts, 1, 'completed estimates must not launch another pass');
});

test('A2: an area not covered by the attached pass is calculated once afterward', async () => {
  const f = fixture();
  f.state.reply = count => {
    if (count === 1) return {already_running:true,running:'result-drive-times',running_on:'commute'};
    f.state.snapshot = f.snapshot(3, true);
    return {already_running:false};
  };
  f.state.snapshot = f.snapshot(1, false, 0);
  await f.run('controller.calculate(false)');
  f.state.snapshot = f.snapshot(3, true, 0);
  await f.timers.advance(1450);
  assert.equal(f.run('matches'), 3);
  assert.equal(f.state.posts, 2);
  await f.timers.advance(15000);
  assert.equal(f.state.posts, 2, 'cache/status polling must not retry completed work');
});

for (const [running, running_on] of [['enrich','commute'], ['result-drive-times','elsewhere']]) {
  test(`A2: ${running} on ${running_on} remains an unrelated pass`, async () => {
    const f = fixture({already_running:true,running,running_on});
    await f.run('controller.calculate(false)');
    await f.timers.advance(20000);
    assert.equal(f.state.gets, 0);
    assert.equal(f.state.posts, 1);
    assert.equal(f.run('controller.busy'), false);
    assert.equal(f.retryDisabled(), false);
    assert.match(f.run('controller.message'), /Another pass is running/);
  });
}

(async () => {
  for (const [name, body] of cases) {
    try { await body(); console.log(`PASS ${name}`); }
    catch (error) { console.error(`FAIL ${name}\n${error.stack}`); process.exitCode=1; }
  }
})().catch(error => { console.error(error); process.exitCode=1; });
