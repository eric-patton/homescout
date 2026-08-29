"use strict";
/* What changed since an earlier run.
 *
 * The same document the terminal's `changes --json` produces, rendered. Not a second computation of
 * the same thing: the comparison is the core's, so this surface and that command cannot disagree
 * about what happened, which is what AC-11 asks for.
 */

/* Which search this page is about, so a property link can carry the way back to its table. */
let currently = "";

whenReady(() => {
  nav("/");
  const name = pathParts()[1];
  load(name).catch(fail);
});

async function load(name, since) {
  const path = `/api/changes/${encodeURIComponent(name)}` +
    (since ? `?since=${encodeURIComponent(since)}` : "");
  let found;
  try {
    found = await ask(path);
  } catch (error) {
    shell(`${name} changes`,
      el("h1", {}, name),
      el("p", {class: "notice notice-problem"}, error.message));
    return;
  }
  draw(name, found.searches[0], since);
}

function draw(name, entry, since) {
  const counts = entry.counts || {};
  const picker = el("input", {
    type: "date",
    id: "since",
    value: since || "",
    "aria-label": "Compare against the last run on or before this date",
  });

  currently = name;
  shell(`${name} changes`,
    aboutSearch(name, "changes"),
    el("h1", {}, name),
    el("p", {class: "lede"},
      `${counts.matched || 0} properties · ${counts.new || 0} new · ` +
      `${counts.changed || 0} changed · ${counts.gone || 0} gone · ` +
      `${counts.returned || 0} back`),
    el("div", {class: "controls"},
      el("label", {for: "since"}, "Compare against "),
      picker,
      el("button", {type: "button", onclick: () => load(name, picker.value)}, "Show"),
    ),
    section("New", entry.new, plain),
    section("Price changed", entry.price_changes, priced),
    section("Status changed", entry.status_changes, statused),
    section("Other changes", entry.other_changes, othered),
    section("Gone", entry.gone, plain),
    section("Back", entry.returned, plain),
    section("Newly flagged", entry.flagged, flagged),
  );
}

function section(title, rows, render) {
  if (!rows || !rows.length) return null;
  return el("section", {},
    el("h2", {}, `${title} (${rows.length})`),
    el("table", {class: "plain"},
      el("tbody", {}, rows.map(render))),
  );
}

function address(summary) {
  const parts = [summary.address_line, summary.unit, summary.city, summary.state]
    .filter(Boolean).join(", ");
  return propertyLink(summary.listing_id, parts || summary.listing_id, currently);
}

function plain(summary) {
  return el("tr", {},
    el("td", {}, address(summary)),
    el("td", {}, money(summary.price)),
    el("td", {}, value(summary.listing_status)),
  );
}

function priced(summary) {
  const change = summary.price_change || {};
  return el("tr", {},
    el("td", {}, address(summary)),
    el("td", {}, money(change.before), " → ", money(change.after)),
    el("td", {}, badge(change.direction === "down" ? "cut" : "raised",
                       change.direction === "down" ? "good" : "flag")),
  );
}

function statused(summary) {
  const change = summary.status_change || {};
  return el("tr", {},
    el("td", {}, address(summary)),
    el("td", {}, value(change.before), " → ", value(change.after)),
    el("td", {}, badge("status", "plain")),
  );
}

function othered(summary) {
  return el("tr", {},
    el("td", {}, address(summary)),
    el("td", {}, (summary.fields || []).map((field) =>
      el("div", {}, `${field.field}: `, value(field.before), " → ", value(field.after)))),
    el("td", {}, badge("changed", "plain")),
  );
}

function flagged(summary) {
  return el("tr", {},
    el("td", {}, address(summary)),
    el("td", {}, money(summary.price)),
    el("td", {}, (summary.rules || []).map((rule) => badge(rule, "flag"))),
  );
}
