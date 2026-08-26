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

const send = (path, body) => ask(path, {method: "POST", body: body});

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
    ["/settings", "Settings and tools"],
  ];
  where.replaceChildren(
    skipLink(),
    link("/", "HomeScout", {class: "brand"}),
    ...links.map(([href, text]) =>
      link(href, text, {class: href === active ? "here" : null,
                        "aria-current": href === active ? "page" : null}))
  );
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
      if (status.failed) {
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
