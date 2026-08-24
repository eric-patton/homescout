"use strict";
/* The landing surface: what searches exist, what each one last found, and everything you can do to
 * one.
 *
 * The list rather than the map, because the common daily act is "what happened overnight" and the
 * rare act is "define a new area".
 *
 * A run takes minutes, because politeness is a requirement, so starting one does not block the
 * page. It is started, and then the page asks how it is going, showing the same words the terminal
 * prints because it is the same progress callback.
 *
 * Paused and archived are properties of the file, and neither deletes anything. A paused search is
 * one nobody is watching this month; an archived one is one nobody is watching at all; both are
 * still a file with everything in it, and both still run when you ask for them by name.
 */

let polling = null;
let showArchived = false;
let held = [];

whenReady(() => {
  nav("/");
  load().catch(fail);
});

async function load() {
  const found = await ask("/api/searches");
  held = found.searches;
  draw();
}

function draw() {
  const visible = held.filter((entry) => showArchived || !entry.archived);
  const archived = held.filter((entry) => entry.archived).length;

  shell("Searches",
    el("h1", {}, "Saved searches"),
    el("p", {class: "lede"},
      held.length
        ? `${visible.length} shown of ${held.length}. Running one takes a few minutes.`
        : "None yet. A saved search is a YAML file; make one here or by hand."),

    el("div", {class: "controls"},
      el("button", {type: "button", onclick: askForName}, "New search"),
      el("button", {type: "button", disabled: !visible.length ? true : null, onclick: runAll},
        "Run all of them"),
      link("/settings", "Settings and tools"),
      /* Shown while it is ticked even once the count reaches nothing, because bringing the last
       * archived search back would otherwise take the control away with the state still on, and
       * there would be no way to turn it off. */
      (archived || showArchived)
        ? el("label", {},
            el("input", {
              type: "checkbox",
              id: "showarchived",
              onchange: (event) => { showArchived = event.target.checked; draw(); },
            }),
            archived ? ` show ${count(archived, "archived search", "archived searches")}`
                     : " show archived searches (there are none)")
        : null,
    ),
    el("div", {id: "allprogress"}),
    visible.length
      ? el("div", {class: "cards"}, visible.map(card))
      : el("p", {class: "unknown"}, "nothing to show"),
  );
  const toggle = document.getElementById("showarchived");
  if (toggle) toggle.checked = showArchived;
}

function card(entry) {
  const problems = (entry.problems || []).filter((p) => p.severity === "problem");
  const standing = entry.archived ? "archived" : (entry.paused ? "paused" : null);

  return el("div", {class: "card", dataset: {search: entry.name}},
    el("h3", {}, entry.name, standing ? " " : null,
      standing ? badge(standing, standing === "archived" ? "plain" : "flag") : null),
    entry.description ? el("p", {}, entry.description) : null,
    el("p", {class: "meta"},
      `${count(entry.areas || 0, "area")} · ` +
      `${(entry.sources || []).join(", ") || "no sources"} · ` +
      `${count(entry.runs || 0, "completed run")}`),
    el("p", {class: "meta"},
      entry.running
        ? badge("a run is under way", "flag")
        : (entry.last_completed_at
            ? el("span", {title: entry.last_completed_at}, `last run ${when(entry.last_completed_at)}`)
            : "never run")),
    problems.length
      ? el("p", {class: "notice notice-problem"},
          `${problems.length} things to fix before this can run: ` +
          problems.map((p) => `${p.location} ${p.message}`).join(" · "))
      : null,

    el("div", {class: "actions"},
      el("button", {
        type: "button",
        disabled: problems.length ? true : null,
        onclick: () => run(entry.name),
      }, "Run now"),
      link(`/results/${encodeURIComponent(entry.name)}`, "Results"),
      link(`/changes/${encodeURIComponent(entry.name)}`, "What changed"),
      link(`/search/${encodeURIComponent(entry.name)}`, "Edit"),
    ),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        onclick: () => standingOf(entry.name, {paused: !entry.paused}),
      }, entry.paused ? "Resume" : "Pause"),
      el("button", {
        type: "button",
        onclick: () => standingOf(entry.name, {archived: !entry.archived}),
      }, entry.archived ? "Bring back" : "Archive"),
      el("button", {type: "button", onclick: () => duplicate(entry.name)}, "Duplicate"),
    ),
    el("p", {class: "meta"},
      entry.archived
        ? "Archived: out of the list and skipped by a run of everything. Nothing is deleted."
        : (entry.paused
            ? "Paused: skipped by a run of everything, and still run when you ask for it by name."
            : null)),
    el("div", {id: `progress-${entry.name}`}),
  );
}

/* ------------------------------------------------------------------ */
/* Making and changing searches                                        */
/* ------------------------------------------------------------------ */

async function askForName() {
  const name = window.prompt(
    "A name for the new search. It becomes the file name, so letters, digits, dashes, " +
    "underscores and dots.");
  if (!name) return;
  try {
    await ask(`/api/searches/${encodeURIComponent(name.trim())}`, {method: "PUT"});
  } catch (error) {
    fail(error);
    return;
  }
  say(`Made ${name.trim()}. It has one example area in it; edit it before running.`, "good");
  window.location.href = `/search/${encodeURIComponent(name.trim())}`;
}

async function duplicate(name) {
  const wanted = window.prompt(`A name for the copy of ${name}.`, `${name}-copy`);
  if (!wanted) return;
  try {
    await send(`/api/searches/${encodeURIComponent(name)}/duplicate`, {name: wanted.trim()});
  } catch (error) {
    fail(error);
    return;
  }
  say(`Copied ${name} to ${wanted.trim()}, comments and all.`, "good");
  await load();
}

async function standingOf(name, change) {
  try {
    await send(`/api/searches/${encodeURIComponent(name)}/standing`, change);
  } catch (error) {
    fail(error);
    return;
  }
  await load();
}

/* ------------------------------------------------------------------ */
/* Running                                                             */
/* ------------------------------------------------------------------ */

async function run(name) {
  say(`Starting ${name}…`);
  try {
    await send(`/api/searches/${encodeURIComponent(name)}/run`, {});
  } catch (error) {
    fail(error);
    return;
  }
  watch(name);
}

async function runAll() {
  say("Running every search that is not paused or archived…");
  try {
    await send("/api/run-all", {});
  } catch (error) {
    fail(error);
    return;
  }
  watchTask("run-all", document.getElementById("allprogress"), "Every search");
}

function watch(name) {
  const where = document.getElementById(`progress-${name}`);
  if (polling) clearInterval(polling);
  const tick = async () => {
    let status;
    try {
      status = await ask(`/api/runs/${encodeURIComponent(name)}/status`);
    } catch (error) {
      fail(error);
      clearInterval(polling);
      return;
    }
    where.replaceChildren(
      el("pre", {class: "progress", role: "log", "aria-live": "polite"},
        (status.progress || []).join("\n") || "starting…"));

    if (status.finished) {
      clearInterval(polling);
      polling = null;
      if (status.failed) {
        say(`${name}: the run could not finish. ${status.failed}`, "problem");
      } else if (status.outcome) {
        const counts = status.outcome.counts || {};
        const failed = (status.outcome.sources || []).filter((s) => s.outcome !== "ok");
        say(
          `${name}: ${counts.new || 0} new, ${counts.changed || 0} changed, ` +
          `${counts.gone || 0} gone` +
          (failed.length ? `. ${failed.map((s) => `${s.source} ${s.outcome}`).join(", ")}` : ""),
          failed.length ? "problem" : "good");
      }
      load().catch(fail);
    }
  };
  tick();
  polling = setInterval(tick, 1500);
}

/* The same watching, for the things that are not one search: a run of everything, an enrichment
 * pass, extraction, a digest. Shared with the settings surface through `common.js`. */
function watchTask(task, where, label) {
  watchBackgroundTask(task, where, label, () => load().catch(fail));
}
