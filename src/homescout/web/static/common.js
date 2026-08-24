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
    if (name === "onclick" || name === "oninput" || name === "onkeydown" ||
        name === "onchange" || name === "onblur" || name === "onfocus") {
      node.addEventListener(name.slice(2), value);
      continue;
    }
    if (name === "dataset") {
      for (const [key, held] of Object.entries(value)) node.dataset[key] = String(held);
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
  ];
  where.replaceChildren(
    skipLink(),
    el("strong", {}, "HomeScout"),
    ...links.map(([href, text]) =>
      link(href, text, {class: href === active ? "here" : null,
                        "aria-current": href === active ? "page" : null}))
  );
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
