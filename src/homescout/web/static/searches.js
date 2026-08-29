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
 * THIS PAGE HOLDS WHAT IS BEING WATCHED. Paused searches stay, because a pause is a search
 * somebody means to come back to and one that vanished when paused would be a pause nobody would
 * use. Archived and deleted ones are read on the set-aside surface: this page used to carry them
 * too, as greyed cards behind a checkbox and a strip of restore buttons at the foot that never
 * shrank and never said what any of them were.
 */

let polling = null;
let held = [];
let summary = {};
/* How many searches are set aside, so the list can say where they are without carrying them. */
let gone = 0;
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
  const aside = await ask("/api/set-aside");
  gone = (aside.deleted || []).length + (aside.archived || []).length;
  draw();
}

function draw() {
  /* What is being watched, and nothing else. Archived and deleted searches are read on their own
   * surface: this page answers "what happened overnight", and it used to carry every search
   * nobody is watching as well, as greyed cards behind a checkbox and a strip of restore buttons
   * at the foot that only ever grew. */
  const visible = held.filter((entry) => !entry.archived);

  shell("Searches",
    el("h1", {}, "HomeScout"),
    el("p", {class: "lede"},
      held.length
        ? "Everything being watched, and what the last run found."
        : "Nothing is being watched yet. A search is a place to look and what you want found " +
          "there. Make one with the button below."),
    overview(),

    el("div", {class: "controls"},
      el("button", {type: "button", class: "primary", onclick: askForName}, "New search"),
      el("button", {type: "button", disabled: !visible.length ? true : null, onclick: runAll},
        "Run all of them"),
      link("/settings", "Settings and tools"),
      /* A link rather than a state, which is the whole reason the checkbox it replaces could go.
       * That checkbox had to stay on screen after the last archived search came back, because the
       * state it held would otherwise have had no control left to turn it off. A page is not a
       * state, so it can simply be absent when there is nothing on it. */
      gone ? link("/archive", `${count(gone, "search", "searches")} set aside`) : null,
    ),
    el("div", {id: "allprogress"}),
    visible.length
      ? el("div", {class: "cards"}, visible.map(card))
      : el("p", {class: "unknown"}, "nothing to show"),
  );
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
    figure({number: summary.properties || 0,
            label: "properties across every search"}),
    figure({
      number: summary.last_run_at ? when(summary.last_run_at) : "never",
      label: "last run",
      title: summary.last_run_at,
    }),
    /* Drawn at zero rather than removed. A tile appearing is harder to notice than a number
     * changing, which is exactly backwards for a strip whose whole job is answering "is there
     * anything for me today": three of these five used to be absent on a quiet morning, so the
     * strip was two wide most days and four on the days something needed attention.
     *
     * A figure about something this installation has not set up at all stays absent, because
     * "none today" and "this does not happen here" are different answers and a zero gives the
     * wrong one. That is product invariant 9's rule rather than a list kept here. */
    figure({number: waiting, label: "waiting for your decision",
            href: waiting ? "/matches" : null, tone: waiting ? "flag" : null}),
    figure({number: trouble, label: "to fix before they run",
            tone: trouble ? "problem" : null}),
    figure({number: running, label: "running right now", tone: running ? "flag" : null}),
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
  /* Only paused reaches this list now. An archived search is read on the set-aside surface,
   * which is where it is brought back from. */
  const standing = entry.paused ? "paused" : null;

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
        onclick: () => standingOf(entry.name, {archived: true}),
      }, "Archive"),
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
      entry.paused
        ? "Paused: skipped by a run of everything, and still run when you ask for it by name."
        : null),
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
      "It is on the set-aside page, with everything else nobody is watching, and it can be brought back from there.",
      "good");
  } catch (error) {
    fail(error);
    return;
  }
  await load();
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
