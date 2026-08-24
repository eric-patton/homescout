"use strict";
/* The landing surface: what searches exist, what each one last found, and running one.
 *
 * The list rather than the map, because the common daily act is "what happened overnight" and the
 * rare act is "define a new area".
 *
 * A run takes minutes, because politeness is a requirement, so starting one does not block the
 * page. It is started, and then the page asks how it is going, showing the same words the terminal
 * prints because it is the same progress callback.
 */

let polling = null;

whenReady(() => {
  nav("/");
  load().catch(fail);
});

async function load() {
  const found = await ask("/api/searches");
  draw(found.searches);
}

function draw(searches) {
  if (!searches.length) {
    shell("Searches",
      el("h1", {}, "No saved searches yet"),
      el("p", {class: "lede"},
        "A saved search is a YAML file. Make one with homescout searches create <name>, " +
        "or open one you already wrote by hand."));
    return;
  }

  shell("Searches",
    el("h1", {}, "Saved searches"),
    el("p", {class: "lede"}, `${searches.length} searches. Running one takes a few minutes.`),
    el("div", {class: "cards"}, searches.map(card)),
  );
}

function card(entry) {
  const problems = entry.problems || [];
  const blocking = problems.filter((p) => p.severity === "problem");

  return el("div", {class: "card", dataset: {search: entry.name}},
    el("h3", {}, entry.name),
    entry.description ? el("p", {}, entry.description) : null,
    el("p", {class: "meta"},
      `${entry.areas || 0} areas · ${(entry.sources || []).join(", ") || "no sources"} · ` +
      `${entry.runs || 0} completed runs`),
    el("p", {class: "meta"},
      entry.running
        ? badge("a run is under way", "flag")
        : (entry.last_completed_at
            ? `last run ${entry.last_completed_at}`
            : "never run")),
    blocking.length
      ? el("p", {class: "notice notice-problem"},
          `${blocking.length} things to fix before this can run: ` +
          blocking.map((p) => `${p.location} ${p.message}`).join(" · "))
      : null,
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        disabled: blocking.length ? true : null,
        onclick: () => run(entry.name),
      }, "Run now"),
      link(`/results/${encodeURIComponent(entry.name)}`, "Results"),
      link(`/changes/${encodeURIComponent(entry.name)}`, "What changed"),
      link(`/search/${encodeURIComponent(entry.name)}`, "Edit"),
    ),
    el("div", {id: `progress-${entry.name}`}),
  );
}

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
