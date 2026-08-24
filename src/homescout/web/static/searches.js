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
let summary = {};
let gone = [];
/* Which card is asking "really?". A second click on the same button rather than a browser dialog:
 * a dialog is a modal somebody dismisses by reflex, and this puts the consequence in the button. */
let confirming = null;

whenReady(() => {
  nav("/");
  load().catch(fail);
});

async function load() {
  const found = await ask("/api/searches");
  held = found.searches;
  summary = found.overview || {};
  gone = (await ask("/api/deleted")).searches || [];
  draw();
}

function draw() {
  const visible = held.filter((entry) => showArchived || !entry.archived);
  const archived = held.filter((entry) => entry.archived).length;

  shell("Searches",
    el("h1", {}, "HomeScout"),
    el("p", {class: "lede"},
      held.length
        ? "Everything being watched, and what the last run found."
        : "Nothing is being watched yet. A saved search is a YAML file; make one here or by hand."),
    overview(),

    el("div", {class: "controls"},
      el("button", {type: "button", class: "primary", onclick: askForName}, "New search"),
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
    deletedPanel(),
  );
  const toggle = document.getElementById("showarchived");
  if (toggle) toggle.checked = showArchived;
}

/* The few numbers worth seeing before the list.
 *
 * The list answers "what have I set up". This answers "is there anything for me today", which is
 * the question somebody opening this in the morning actually has, and it is the one the page used
 * to make them work the rest of the screen out for themselves.
 */
function overview() {
  if (!held.length) return null;
  const running = (summary.running || []).length;
  const waiting = summary.waiting_to_review || 0;
  const trouble = summary.searches_with_problems || 0;

  return el("div", {class: "overview"},
    figure({number: summary.properties || 0, label: "properties being watched"}),
    figure({
      number: summary.last_run_at ? when(summary.last_run_at) : "never",
      label: "last run",
      title: summary.last_run_at,
    }),
    waiting
      ? figure({number: waiting, label: "waiting for your decision",
                href: "/matches", tone: "flag"})
      : null,
    trouble
      ? figure({number: trouble, label: "to fix before they run", tone: "problem"})
      : null,
    running ? figure({number: running, label: "running right now", tone: "flag"}) : null,
  );
}

/* One number and what it counts. A link when there is somewhere to go about it, and plain when
 * there is not: a figure that looks clickable and is not is worse than one that does not. */
function figure({number, label, title, href, tone}) {
  const inside = [
    el("span", {class: "figure-number"}, String(number)),
    el("span", {class: "figure-label"}, label),
  ];
  const attributes = {class: "figure" + (tone ? " figure-" + tone : ""), title: title || null};
  return href ? link(href, inside, attributes) : el("div", attributes, inside);
}

function card(entry) {
  const problems = (entry.problems || []).filter((p) => p.severity === "problem");
  const standing = entry.archived ? "archived" : (entry.paused ? "paused" : null);

  return el("div", {class: standing ? "card set-aside" : "card", dataset: {search: entry.name}},
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
        class: "primary",
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
        class: entry.archived ? null : "danger",
        onclick: () => standingOf(entry.name, {archived: !entry.archived}),
      }, entry.archived ? "Bring back" : "Archive"),
      el("button", {type: "button", onclick: () => duplicate(entry.name)}, "Duplicate"),
      confirming === entry.name
        ? el("button", {
            type: "button",
            class: "danger",
            onclick: () => remove(entry.name),
          }, `Yes, delete ${entry.name}`)
        : el("button", {
            type: "button",
            class: "quiet",
            onclick: () => { confirming = entry.name; draw(); },
          }, "Delete"),
      confirming === entry.name
        ? el("button", {type: "button", onclick: () => { confirming = null; draw(); }}, "Cancel")
        : null,
    ),
    confirming === entry.name
      ? el("p", {class: "notice notice-flag"},
          "This takes it out of the list and out of a run of everything. The file is kept, so it " +
          "can be brought back. Everything the runs already found stays in the store: recorded " +
          "history is never deleted.")
      : null,
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

async function remove(name) {
  try {
    const answered = await ask(`/api/searches/${encodeURIComponent(name)}`, {method: "DELETE"});
    confirming = null;
    say(
      `${name} is no longer a saved search. ` +
      (answered.runs_kept
        ? `Its ${answered.runs_kept} runs and everything they found are still here. `
        : "") +
      "Bring it back from the bottom of this page.",
      "good");
  } catch (error) {
    fail(error);
    return;
  }
  await load();
}

async function restore(name) {
  try {
    await send(`/api/searches/${encodeURIComponent(name)}/restore`, {});
  } catch (error) {
    fail(error);
    return;
  }
  say(`${name} is a saved search again, exactly as it was.`, "good");
  await load();
}

/* What was deleted, and the way back. Below the list rather than in it, because these are not
 * saved searches any more and showing them as though they were would be a lie about the state. */
function deletedPanel() {
  if (!gone.length) return null;
  return el("section", {},
    el("h2", {}, "Deleted"),
    el("p", {class: "meta"},
      "Not saved searches any more, and not thrown away either. The file is kept with its areas " +
      "and its comments, and everything the runs found is still in the store."),
    el("div", {class: "actions"},
      gone.map((name) =>
        el("button", {type: "button", onclick: () => restore(name)}, `Bring back ${name}`))),
  );
}

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
