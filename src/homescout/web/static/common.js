"use strict";
/* What every surface shares.
 *
 * One rule shapes this whole file, and it is the security requirement made structural rather than
 * careful: THERE IS EXACTLY ONE WAY TO PUT SOMETHING ON A PAGE, and it uses textContent. There is
 * no innerHTML anywhere in this package, no template literal that produces markup, and a test
 * asserts both. A listing description containing a script tag is a description containing the
 * characters of one, because there is no other path to take, not because anybody escaped it.
 */

/** Build an element. Children that are strings become text nodes, always. */
function el(tag, attributes, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes || {})) {
    if (value === null || value === undefined || value === false) continue;
    /* Any `on...` whose value is a function is a listener, and the list is not enumerated here.
     * It used to be, and the six names on it were the six somebody had needed so far; a seventh
     * fell through to `setAttribute`, which stringifies the function into an inline handler that
     * defines an arrow function, discards it, and does nothing at all. That is a handler that
     * silently never runs, and `ondblclick` on the results table was one for months. */
    if (name.startsWith("on") && typeof value === "function") {
      node.addEventListener(name.slice(2), value);
      continue;
    }
    if (name === "dataset") {
      for (const [key, held] of Object.entries(value)) node.dataset[key] = String(held);
      continue;
    }
    /* A textarea holds its text as content rather than in an attribute, so `value=` on one is
     * silently ignored: the box renders empty, and a save built from it writes an empty box back
     * over whatever was there. Set the property instead, which is what the caller meant. */
    if (name === "value" && tag === "textarea") {
      node.value = String(value);
      continue;
    }
    node.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

/* The one anchor that is not a navigation: a fragment within this page. It has its own builder
 * rather than a special case inside `link()`, so `link()` stays a rule with no exceptions. */
function skipLink() {
  const node = el("a", {class: "skip"}, "Skip to the content");
  node.setAttribute("href", "#main");
  return node;
}

/** A link, but only to somewhere a link may go. */
function link(href, text, attributes) {
  const target = webAddress(href);
  if (!target) return el("span", attributes, text);
  return el("a", Object.assign({href: target}, attributes || {}), text);
}

/** http and https only. A listing URL is text a listing site chose. */
function webAddress(href) {
  if (typeof href !== "string" || !href.trim()) return null;
  try {
    const parsed = new URL(href, window.location.origin);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") ? parsed.href : null;
  } catch (_) {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Talking to the server                                               */
/* ------------------------------------------------------------------ */

/* The header the server requires on anything that changes something. Set here, once, so no page
 * has to remember it, and so a form posted by another site cannot have it. */
const GUARD = {"X-Homescout": "1"};

async function ask(path, options) {
  const settings = Object.assign({headers: {}}, options || {});
  settings.headers = Object.assign({"Accept": "application/json"}, settings.headers);
  if (settings.body !== undefined && typeof settings.body !== "string") {
    settings.body = JSON.stringify(settings.body);
    settings.headers["Content-Type"] = "application/json";
  }
  if (settings.method && settings.method !== "GET") Object.assign(settings.headers, GUARD);

  const response = await fetch(path, settings);
  let document_ = null;
  try { document_ = await response.json(); } catch (_) { document_ = null; }
  if (!response.ok) {
    const said = (document_ && document_.error) || `${response.status} ${response.statusText}`;
    const failure = new Error(said);
    failure.status = response.status;
    throw failure;
  }
  return document_;
}

/* A write. POST unless something says otherwise: PUT is for the handful of places where what
 * is sent is the whole of a thing rather than a change to it, which is what a set of ticked
 * boxes is. */
const send = (path, body, method) => ask(path, {method: method || "POST", body: body});

/* ------------------------------------------------------------------ */
/* A hazard layer, drawn as map tiles                                  */
/* ------------------------------------------------------------------ */

/* Here rather than on the fire map, because two pages draw it now.
 *
 * Leaflet asks for a tile by its column, row and zoom; the service answers about a rectangle in
 * metres. The whole of this function is that conversion, and it is the sort of thing that is
 * written twice and then diverges: one page would end up half a tile out and nobody would be able
 * to say which page was right.
 *
 * Nothing here runs until it is called, so a page with no Leaflet can still load this file.
 */
function arcgisLayer(layer, options) {
  const Layer = L.TileLayer.extend({
    getTileUrl(coords) {
      const size = this.getTileSize();
      const map = this._map;
      const topLeft = map.unproject(coords.scaleBy(size), coords.z);
      const bottomRight = map.unproject(coords.add([1, 1]).scaleBy(size), coords.z);
      const a = L.Projection.SphericalMercator.project(topLeft);
      const b = L.Projection.SphericalMercator.project(bottomRight);
      const query = new URLSearchParams({
        bbox: `${a.x},${b.y},${b.x},${a.y}`,
        size: `${size.x},${size.y}`,
      });
      return `/api/hazard/${encodeURIComponent(layer)}?${query}`;
    },
  });
  return new Layer("", Object.assign({maxZoom: 16, maxNativeZoom: 16}, options || {}));
}

/* ------------------------------------------------------------------ */
/* Showing a value                                                     */
/* ------------------------------------------------------------------ */

/* Three states, three appearances, all of them text (AC-10, AC-18). A blank cell is deliberately
 * not used for "nobody determined it": a blank reads as an empty string somebody could have
 * filled in, and a run of blanks in a wide table reads as a broken column. */
function value(held) {
  if (held === null || held === undefined || held === "") {
    return el("span", {class: "unknown", title: "nobody determined this"}, "not known");
  }
  if (held === "none") return el("span", {class: "negative"}, "none");
  if (held === true) return el("span", {}, "yes");
  if (held === false) return el("span", {}, "no");
  return el("span", {}, String(held));
}

function money(held) {
  if (held === null || held === undefined || held === "") return value(null);
  return el("span", {}, "$" + Number(held).toLocaleString());
}

/* A stored timestamp, said the way somebody would say it.
 *
 * Everything is stored in UTC to the microsecond, which is right for the store and unreadable on a
 * card. Recent times are said in relation to now, because "three hours ago" is what the question
 * "has this run today" actually wants; anything older gets its date, in this machine's own zone.
 */
function when(text) {
  if (!text) return null;
  const at = new Date(text);
  if (isNaN(at)) return text;
  const seconds = (Date.now() - at.getTime()) / 1000;
  if (seconds < 90) return "just now";
  if (seconds < 5400) return `${Math.round(seconds / 60)} minutes ago`;
  if (seconds < 79200) return `${Math.round(seconds / 3600)} hours ago`;
  if (seconds < 6 * 86400) return `${Math.round(seconds / 86400)} days ago`;
  return at.toLocaleDateString(undefined, {year: "numeric", month: "short", day: "numeric"});
}

/** A count with its noun, singular when it is one of them. */
function count(many, one, plural) {
  return `${many} ${many === 1 ? one : (plural || one + "s")}`;
}

/** A badge. Always carries its text, because nothing here is conveyed by colour alone (AC-18). */
function badge(text, kind) {
  return el("span", {class: "badge badge-" + (kind || "plain")}, text);
}

/* ------------------------------------------------------------------ */
/* The page itself                                                     */
/* ------------------------------------------------------------------ */

function shell(title, ...children) {
  const main = document.getElementById("main");
  document.title = title + " · HomeScout";
  main.replaceChildren(...children.flat().filter(Boolean));
}

function say(message, kind) {
  const where = document.getElementById("banner");
  if (!where) return;
  where.replaceChildren(
    message ? el("p", {class: "notice notice-" + (kind || "plain"), role: "status"}, message) : ""
  );
  /* The banner sits above every surface, so saying something moves everything under it down by the
   * height of a notice. On a surface that measures its own height from where its box falls, that
   * is the table's bottom edge, and the horizontal scrollbar on it, going below the window: the
   * exact fault AC-53 exists to prevent, reintroduced by a sentence. A surface that does not
   * measure anything is unaffected and does not define this. */
  if (typeof fit === "function") fit();
}

function fail(error) {
  say(String(error && error.message ? error.message : error), "problem");
}

function nav(active) {
  const where = document.getElementById("nav");
  if (!where) return;
  const links = [
    ["/", "Searches"],
    ["/matches", "Matches to review"],
    ["/settings", "Settings"],
    ["/tools", "Tools"],
  ];
  where.replaceChildren(
    skipLink(),
    link("/", "HomeScout", {class: "brand"}),
    ...links.map(([href, text]) =>
      link(href, text, {class: href === active ? "here" : null,
                        "aria-current": href === active ? "page" : null})),
    /* Where the marker goes. In `nav` rather than in nine HTML files, and started from here rather
     * than by each surface remembering to, because "is something still going" is asked from
     * wherever you happen to be standing and the answer used to require navigating to the one page
     * that might know. */
    el("span", {id: "running", class: "running"})
  );
  watchTheMachine();
}

/* ------------------------------------------------------------------ */
/* What is running, anywhere on this machine                           */
/* ------------------------------------------------------------------ */

/* How often the marker asks. One ask on one schedule for the whole page: six surfaces polling for
 * themselves would be six answers that can disagree and six requests where one will do. Slower than
 * a progress panel on purpose - this answers "is anything happening", which changes twice an hour,
 * not "how far along is it" - and it matters here because this runs on the results table too, whose
 * own read is the most expensive this interface has and which every request queues behind. */
const RUNNING_EVERY = 5000;

let machineTimer = null;
let machineSaid = null;

/* Which screen shows a given pass in detail. A marker you cannot follow is a marker that makes you
 * go looking, which is the thing this exists to stop. */
function showingPass(pass) {
  return (pass.task === "run" || pass.task === "run-all") ? "/" : "/tools";
}

function nameOfPass(pass) {
  const named = {
    "run": "Running a search",
    "run-all": "Running every search",
    "enrich": "Attaching public data",
    "extract": "Asking the model",
    "assess": "Reading the properties",
    "deliver": "Writing the digest",
    "broadband": "Loading broadband data",
  }[pass.task] || pass.task;
  return pass.subject ? `${named}: ${pass.subject}` : named;
}

function watchTheMachine() {
  const where = document.getElementById("running");
  if (!where) return;
  if (machineTimer) clearInterval(machineTimer);
  machineSaid = null;

  const tick = async () => {
    let passes = [];
    try {
      passes = (await ask("/api/under-way")).passes || [];
    } catch (_) {
      /* A page that cannot ask says nothing rather than saying something wrong. */
      return;
    }
    const said = passes.map((p) => `${p.task}:${p.subject || ""}`).join(",");
    if (said === machineSaid) return;
    machineSaid = said;

    if (!passes.length) where.replaceChildren();
    else {
      const first = passes[0];
      where.replaceChildren(
        link(showingPass(first), nameOfPass(first), {class: "marker", title: "Started " +
          (first.started_at || "just now")}),
        passes.length > 1 ? el("span", {class: "more"}, `+${passes.length - 1}`) : null);
    }
    /* Appearing and going away both change the height above a table that measures its own, which
     * is the fault AC-53 exists to prevent, reintroduced by a marker. */
    if (typeof fit === "function") fit();
  };

  tick();
  machineTimer = setInterval(tick, RUNNING_EVERY);
}

/* Pick up a pass that is already running, on a page that has just loaded.
 *
 * The whole of AC-83. The panel below was always real and was started in exactly one place, the
 * button handler, so reloading or arriving from another device showed an idle-looking page while a
 * pass was twenty minutes in. Nothing is drawn when nothing is running: this installation is idle
 * almost all of the time, and a line saying so on every visit is a line to learn to ignore.
 */
async function rejoinBackgroundTask(task, where, label, done) {
  let status;
  try {
    status = await ask(`/api/tasks/${encodeURIComponent(task)}`);
  } catch (_) {
    return false;
  }
  if (!status || !status.running) return false;
  watchBackgroundTask(task, where, label, done);
  return true;
}

/* ------------------------------------------------------------------ */
/* Where you are, on a page about one search                           */
/* ------------------------------------------------------------------ */

/* The four screens a saved search has, and the order they are read in.
 *
 * Built here rather than on each page, and that is the whole point of it. Five pages each grew the
 * links their author needed that day: the results table reached the comparison and the map, the
 * comparison reached the table, the map reached the table, and the search builder reached none of
 * them. Nobody decided that. It is what five copies of a navigation look like after a year.
 *
 * The nav bar above this is not a substitute. It names the same three destinations everywhere, so
 * on any page about a search it reports "Searches", which is where the reader is not.
 */
const SEARCH_PAGES = [
  ["results", "Results", "/results/"],
  ["changes", "What changed", "/changes/"],
  ["map", "Map", "/map/"],
  ["search", "Edit", "/search/"],
];

/** Which search this is, and one press to each of its other screens. */
function aboutSearch(name, here) {
  if (!name) return null;
  return [
    el("p", {class: "crumbs"},
      link("/", "Searches"), " / ", el("span", {}, name)),
    el("nav", {class: "surfaces", "aria-label": `The screens about ${name}`},
      SEARCH_PAGES.map(([key, said, path]) =>
        key === here
          ? el("span", {class: "surface here", "aria-current": "page"}, said)
          : link(path + encodeURIComponent(name), said, {class: "surface"}))),
  ];
}

/* The way back from a property to the table it was read from.
 *
 * A property can be in several saved searches, so "back to the search" has no single answer. What
 * it has is the table the reader arrived from, which is a fact about this visit rather than about
 * the property, so it travels in the address: every link to a property carries where it was linked
 * from, and a property page opened without one simply offers no way back rather than guessing.
 */
function fromSearch() {
  try {
    return new URL(window.location.href).searchParams.get("from") || "";
  } catch (_) {
    return "";
  }
}

/** A link to one property, remembering the table it is being opened from. */
function propertyLink(listingId, text, search, attributes) {
  const where = `/listing/${encodeURIComponent(listingId)}` +
    (search ? `?from=${encodeURIComponent(search)}` : "");
  return link(where, text, attributes);
}

/* ------------------------------------------------------------------ */
/* Explanation that is the same on every visit                         */
/* ------------------------------------------------------------------ */

/* A disclosure that says what it holds.
 *
 * Every surface here opened with a paragraph above its controls, and on the results table it was
 * five lines. The writing is worth having and worth having once: read on the first visit, and a
 * screen-inch of furniture on every visit after.
 *
 * Open the first time somebody is on a surface and closed afterwards, remembered on the same terms
 * as every other view preference on these pages (AC-45): this browser's, never the workspace's, and
 * a browser that cannot store it simply gets the open state every time, which is the safe way round.
 *
 * What goes behind one is what is identical on every visit. A sentence that changes with the state
 * of the thing it is about stays where it is: a disclosure that hid something a person needs on a
 * later visit would be worse than the paragraph it replaced.
 */
function howItWorks(surface, said, ...content) {
  const key = `homescout:read:${surface}`;
  let read = false;
  try { read = window.localStorage.getItem(key) === "1"; } catch (_) { read = false; }

  const holder = el("details", {class: "howto", open: read ? null : true},
    el("summary", {}, said),
    ...content.flat().filter(Boolean));
  holder.addEventListener("toggle", () => {
    try { window.localStorage.setItem(key, holder.open ? "0" : "1"); } catch (_) { /* fine */ }
    /* This is the largest thing on these pages that changes height, and on the results table the
     * height of everything above the table is what the table's own height is measured from. A
     * surface that does not measure things is unaffected; one that does says so by defining this. */
    if (typeof fit === "function") fit();
  });
  return holder;
}

/* ------------------------------------------------------------------ */
/* What to call a property                                             */
/* ------------------------------------------------------------------ */

/* A property with no address, said as what is known about it.
 *
 * Some sources answer with a record that has coordinates, a price and no address at all, and six of
 * the fourteen new properties in the workspace this was written against were like that. Named by
 * their identifier they read as `6e03116ebc1f49cb8de9c32f28e66083`, which is exact, is how the
 * property is asked for again, and is not a thing a person can read, recognise or say aloud.
 *
 * So the identifier is kept everywhere it already is and stops being what somebody is asked to
 * read. Here rather than on four surfaces, because four surfaces name a property and four copies is
 * how one of them goes on printing the string after the others stopped.
 */
function propertyName(fields, listingId) {
  const held = fields || {};
  const address = [held.address_line, held.unit, held.city, held.state, held.postal_code]
    .filter(Boolean).join(", ");
  if (address) return address;
  const where = [held.city, held.state].filter(Boolean).join(", ");
  if (where) return `Unnamed property in ${where}`;
  if (held.county) return `Unnamed property in ${held.county}`;
  /* Nothing at all is known about where it is, so the identifier is all there is. Shortened,
   * because eight characters tell two records apart on a screen and thirty-two do not tell you
   * any more than that. */
  return `Unnamed property ${String(listingId || "").slice(0, 8)}`;
}

/* ------------------------------------------------------------------ */
/* Which properties, by what was decided about them                    */
/* ------------------------------------------------------------------ */

/* One question, one control, and the same one on both surfaces that ask it.
 *
 * `play` is everything not passed on: the ones still to look at and the ones kept, because a kept
 * property is on the shortlist and is hidden from nothing. It is the default, and it draws exactly
 * what the two checkboxes it replaces drew when neither was ticked.
 *
 * Here rather than on the results table, because AC-67 says the map and the table hide the same
 * properties with the same controls and the same words on them, and two copies of a control is how
 * two surfaces come to disagree about what a word means. The words below are the only ones either
 * page uses for this.
 */
const JUDGMENTS = [
  ["play", "In play",
   "Everything you have not passed on: the ones still to look at, and the ones you kept."],
  ["keep", "Kept", "Your shortlist, and nothing else."],
  ["pass", "Passed on", "The ones you said no to. Nothing was deleted; they are still watched."],
  ["all", "All", "Every property in the run, whatever you decided about it."],
];

/** How each narrowing is said, wherever it is said. One phrasing, both surfaces. */
function heldBack(many, why) {
  return why === "pass" ? `${many} passed on, hidden` : `${many} off the market, hidden`;
}

/** The chooser itself. `pick` is handed the new answer; redrawing is the caller's business. */
function judgmentChooser(current, pick) {
  const held = el("div", {class: "choice", id: "judgment", role: "group",
                          "aria-label": "Which properties to show"},
    JUDGMENTS.map(([key, said, why]) =>
      el("button", {
        type: "button",
        "aria-pressed": current === key ? "true" : "false",
        title: why,
        onclick: () => { if (current !== key) pick(key); },
      }, said)));
  return held;
}

/** Put the chooser back in step when the answer was changed from somewhere else. */
function redrawChooser(current, pick) {
  const held = document.getElementById("judgment");
  if (held) held.replaceWith(judgmentChooser(current, pick));
}

/* A list of places to go and get something this tool cannot get for you.
 *
 * Every entry is a page a person signs into as themselves. Nothing here is fetched and nothing is
 * fetched for them: the tool's job is to stop somebody having to search for the name of the page
 * that issues the key it just told them was missing.
 */
function whereToGet(entries) {
  if (!entries || !entries.length) return null;
  return el("ul", {class: "sources"},
    entries.map((entry) => el("li", {},
      link(entry.url, entry.what, {class: "what", target: "_blank", rel: "noopener noreferrer"}),
      entry.note ? el("span", {class: "note"}, entry.note) : null)));
}

/* A row in a list of settings: what it is called, and what it currently says. */
function setting(name, ...what) {
  return el("div", {class: "setting"},
    el("span", {class: "name"}, name),
    el("span", {class: "what"}, ...what));
}

/* Watching something that takes minutes.
 *
 * A run of everything, an enrichment pass, extraction and a digest are all slow for the same
 * reason: politeness is a requirement rather than a nicety. So each is started, and the page asks
 * how it is going, showing the same words the terminal prints because it is the same callback.
 */
function watchBackgroundTask(task, where, label, done) {
  let timer = null;
  const tick = async () => {
    let status;
    try {
      status = await ask(`/api/tasks/${encodeURIComponent(task)}`);
    } catch (error) {
      if (timer) clearInterval(timer);
      fail(error);
      return;
    }
    where.replaceChildren(
      el("pre", {class: "progress", role: "log", "aria-live": "polite"},
        (status.progress || []).join("\n") || "starting…"));

    if (status.finished) {
      if (timer) clearInterval(timer);
      if (status.status === "stopped") {
        /* Neither running nor finished, and saying either would be untrue. Only the pass itself can
         * record how it ended, so a process that was killed leaves a row nobody can complete; the
         * store reads that as stopped and this repeats it rather than deciding. */
        say(`${label}: stopped without finishing. Nothing recorded how it ended, which usually ` +
            `means the process it was running in went away. What it had done is kept.`, "problem");
      } else if (status.failed) {
        say(`${label}: could not finish. ${status.failed}`, "problem");
      } else {
        const outcome = status.outcome || {};
        say(`${label}: ${outcome.summary || "done"}`, outcome.degraded ? "problem" : "good");
      }
      if (done) done();
    }
  };
  tick();
  timer = setInterval(tick, 1500);
  return () => { if (timer) clearInterval(timer); };
}

/** What is in the address bar, since these are six pages rather than one application. */
function pathParts() {
  return window.location.pathname.split("/").filter(Boolean).map(decodeURIComponent);
}

function whenReady(go) {
  const start = () => { try { go(); } catch (error) { fail(error); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
}

/* ------------------------------------------------------------------ */
/* Looking at a property's photographs                                 */
/* ------------------------------------------------------------------ */

/* The bigger rendition of a picture, where the site is one whose addresses say what size they are.
 *
 * What a listing site hands over is a thumbnail, and a small one: Realtor's photo addresses end in
 * `s` and answer at 120 by 80 pixels, which is a picture you cannot see a roof line in. The same
 * address ending in `o` is the original at 1024 by 683. Zillow's `-p_e` is 596 wide and its
 * `-uncropped_scaled_within_1536_1152` is 1536 and, as the name says, not cropped to a shape.
 *
 * This is a rule about somebody else's addressing scheme, so it is written as one and it is allowed
 * to be wrong: every rewritten address falls back to the stored one the moment it fails to load. An
 * address from a host with no rule here, a signed map tile among them, is left exactly as it is.
 */
const RENDITIONS = [
  {host: "rdcpix.com", from: /-m(\d+)s\.jpg$/i, to: "-m$1o.jpg"},
  {host: "zillowstatic.com", from: /-(?:p|cc_ft|o)_?[a-z0-9]*\.jpg$/i,
   to: "-uncropped_scaled_within_1536_1152.jpg"},
];

function biggest(url) {
  try {
    const {hostname} = new URL(url);
    for (const rule of RENDITIONS) {
      if (hostname.endsWith(rule.host) && rule.from.test(url)) {
        return url.replace(rule.from, rule.to);
      }
    }
  } catch (_) {
    /* Not an address this can reason about. */
  }
  return url;
}

/** An address a picture can actually be loaded from, or nothing.
 *
 * Every photograph address the listing sites hand over is stored as `http`, and this interface is
 * reached over `https` as soon as it is put behind anything: a browser refuses an `http` image on
 * an `https` page outright, before the request is made, and the gallery would be a row of broken
 * frames. The hosts all answer on `https`, and the upgrade is only applied when the page is itself
 * `https`, so nothing that would have loaded stops loading.
 */
function pictureAddress(href, protocol) {
  const target = webAddress(href);
  if (!target) return null;
  const page = protocol || window.location.protocol;
  if (page === "https:" && target.startsWith("http://")) {
    return `https://${target.slice("http://".length)}`;
  }
  return target;
}

/* Every picture a listing carried, one at a time, over the page.
 *
 * The one thing worth being deliberate about: these are the listing site's own addresses, not
 * pictures this tool holds. Everywhere else, looking at a property here tells the listing site
 * nothing, because the one stored thumbnail is served from this machine. A gallery of forty photos
 * cannot work that way without keeping forty photos per property, so it fetches them, and the
 * dialog says so rather than leaving somebody to infer it. Nothing is fetched until somebody opens
 * it, and only the picture on screen and its two neighbours are asked for.
 */
function gallery(photos, what) {
  const urls = (photos || []).map(pictureAddress).filter(Boolean);
  if (!urls.length) return null;

  let at = 0;
  const frame = el("img", {class: "plate", alt: `Photograph of ${what || "this property"}`});
  const counter = el("span", {class: "counter", role: "status"}, "");
  const preload = [];

  /* A rewritten address that does not load falls back to the stored one, once. Guessing at another
   * site's renditions is worth it for a picture forty times the size, but not at the price of a
   * broken frame if they change the scheme. */
  frame.addEventListener("error", () => {
    const stored = urls[at];
    if (frame.getAttribute("src") !== stored) frame.src = stored;
  });

  const show = (index) => {
    at = (index + urls.length) % urls.length;
    frame.src = biggest(urls[at]);
    counter.replaceChildren(document.createTextNode(`${at + 1} of ${urls.length}`));
    /* The next one and the one before, so pressing an arrow shows a picture rather than a gap. */
    for (const near of [at + 1, at - 1]) {
      const url = biggest(urls[(near + urls.length) % urls.length]);
      if (preload.includes(url)) continue;
      preload.push(url);
      const ahead = new Image();
      ahead.src = url;
    }
  };

  const back = el("button", {type: "button", class: "quiet page", "aria-label": "Previous photo",
                             onclick: () => show(at - 1)}, "‹");
  const on = el("button", {type: "button", class: "quiet page", "aria-label": "Next photo",
                           onclick: () => show(at + 1)}, "›");
  const shut = el("button", {type: "button", class: "quiet close", "aria-label": "Close",
                             onclick: () => dialog.close()}, "Close");

  const dialog = el("dialog", {
    class: "gallery",
    "aria-label": `Photographs of ${what || "this property"}`,
    onclose: () => dialog.remove(),
    onclick: (event) => { if (event.target === dialog) dialog.close(); },
    onkeydown: (event) => {
      if (event.key === "ArrowRight") { event.preventDefault(); show(at + 1); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); show(at - 1); }
    },
  },
    el("div", {class: "plateframe"}, back, frame, on),
    el("div", {class: "under"},
      counter,
      el("span", {class: "meta"},
        "From the listing site, not from this tool, so opening this asks them for the pictures."),
      shut,
    ),
  );

  document.body.append(dialog);
  show(0);
  dialog.showModal();
  on.focus();
  return dialog;
}
