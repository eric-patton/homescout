"use strict";
/* Everything set aside, and the only place a definition can finally be discarded.
 *
 * This surface exists because the list of searches was doing two jobs. Its job is "what happened
 * overnight", and it was also carrying every search nobody is watching: archived ones as greyed
 * cards behind a checkbox that had to stay on screen even at a count of zero, and deleted ones as a
 * strip of "bring back X" buttons at the foot of the page that never shrank and never said what any
 * of them were. A name six months old is not enough to decide whether you want a search back, and a
 * page that can only accumulate gets worse the longer it is used.
 *
 * So: two lists, each entry saying what the search actually was, and one operation that is not
 * offered anywhere else.
 *
 * ARCHIVED AND DELETED ARE NOT THE SAME THING and are not merged here. An archived search is still a
 * saved search that nobody is watching, and it still runs when asked for by name. A deleted one has
 * stopped being a saved search. Both are still files with everything in them, which is why both are
 * on this page rather than in a bin.
 */

let held = {archived: [], deleted: []};
/* Which card has its discard open. One at a time, and it closes when another opens: two open
 * confirmations for two irreversible actions is how the wrong one gets confirmed. */
let discarding = null;

whenReady(() => {
  nav("/");
  load().catch(fail);
});

async function load() {
  held = await ask("/api/set-aside");
  draw();
}

function draw() {
  const archived = held.archived || [];
  const deleted = held.deleted || [];

  shell("Set aside",
    el("p", {class: "crumbs"}, link("/", "Searches"), " / ", el("span", {}, "Set aside")),
    el("h1", {}, "Set aside"),
    el("p", {class: "lede"},
      archived.length || deleted.length
        ? "Searches nobody is watching. Nothing here has been thrown away: every one is still a " +
          "file with its areas and its comments in it, and everything their runs found is still " +
          "in the store."
        : "Nothing is set aside. Archived and deleted searches would be here."),

    el("section", {},
      el("h2", {}, "Archived", " ", badge(String(archived.length), "plain")),
      el("p", {class: "meta"},
        "Still saved searches. Skipped by a run of everything, and still run when you ask for one " +
        "by name."),
      archived.length
        ? el("div", {class: "cards"}, archived.map((entry) => card(entry, "archived")))
        : el("p", {class: "unknown"}, "none"),
    ),

    el("section", {},
      el("h2", {}, "Deleted", " ", badge(String(deleted.length), "plain")),
      el("p", {class: "meta"},
        deleted.length
          ? "No longer saved searches. The file was kept rather than removed, so any of these " +
            "can be brought back exactly as it was, or discarded for good."
          : "No longer saved searches. Deleting one keeps its file, so anything here could be " +
            "brought back or discarded for good."),
      deleted.length
        ? el("div", {class: "cards"}, deleted.map((entry) => card(entry, "deleted")))
        : el("p", {class: "unknown"}, "none"),
    ),
  );
}

/* One set-aside search, saying what it was rather than only what it was called. */
function card(entry, kind) {
  const name = entry.name;
  return el("div", {class: "card set-aside", dataset: {search: name}},
    el("h3", {}, name),
    entry.description ? el("p", {}, entry.description) : null,
    el("p", {class: "meta"},
      `${count(entry.areas || 0, "area")}` +
      (entry.exclusions ? ` · ${count(entry.exclusions, "exclusion")}` : "") +
      ` · ${(entry.sources || []).join(", ") || "no sources"}` +
      ` · ${count(entry.runs || 0, "completed run")}`),
    el("p", {class: "meta"},
      entry.last_completed_at
        ? el("span", {title: entry.last_completed_at}, `last run ${when(entry.last_completed_at)}`)
        : "never run",
      entry.deleted_at
        ? el("span", {title: entry.deleted_at}, ` · deleted ${when(entry.deleted_at)}`)
        : null),

    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "primary",
        onclick: () => (kind === "deleted" ? restore(name) : bringBack(name)),
      }, "Bring it back"),
      link(`/results/${encodeURIComponent(name)}`, "Results"),
      kind === "deleted"
        ? el("button", {
            type: "button",
            class: "quiet",
            onclick: () => { discarding = discarding === name ? null : name; draw(); },
          }, "Discard for good")
        : null,
    ),
    kind === "deleted" && discarding === name ? discardBox(entry) : null,
  );
}

/* The one irreversible thing in this interface, and the only one that asks you to type.
 *
 * Not a second button and not a browser dialog. Both of those are got through by reflex, and this
 * is the one action where a reflex costs something nobody can give back. What it does not reach is
 * said above the buttons rather than below them: a reassurance somebody reads after deciding
 * arrived too late to be one.
 */
function discardBox(entry) {
  const name = entry.name;
  const typed = el("input", {
    type: "text",
    id: `confirm-${name}`,
    autocomplete: "off",
    placeholder: name,
    "aria-label": `Type ${name} to confirm discarding it`,
    oninput: () => { go.disabled = typed.value.trim() !== name; },
    onkeydown: (event) => {
      if (event.key === "Enter" && typed.value.trim() === name) {
        event.preventDefault();
        discard(name);
      }
    },
  });
  const go = el("button", {
    type: "button",
    class: "danger",
    disabled: true,
    onclick: () => discard(name),
  }, "Discard it");

  return el("div", {class: "notice notice-problem"},
    el("p", {},
      el("strong", {}, "This removes the file. "),
      "The areas drawn on it and the comments written in it go with it, and nothing brings them " +
      "back."),
    el("p", {},
      "What stays: every property this search ever found, their price history, and every " +
      "judgment written on them. " +
      (entry.runs
        ? `Its ${count(entry.runs, "run")} and everything they recorded are untouched, and you ` +
          "will be told how many properties that was."
        : "Recorded history is never deleted.")),
    el("p", {class: "hint"}, `Type ${name} to confirm.`),
    el("div", {class: "actions"},
      typed,
      go,
      el("button", {type: "button", class: "quiet",
                    onclick: () => { discarding = null; draw(); }}, "Cancel"),
    ),
  );
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

/* Bringing an archived one back is a change of standing, not a restore: it never stopped being a
 * saved search. Different call, same words on the button, because to a person it is the same act. */
async function bringBack(name) {
  try {
    await send(`/api/searches/${encodeURIComponent(name)}/standing`, {archived: false});
  } catch (error) {
    fail(error);
    return;
  }
  say(`${name} is back on the list of searches.`, "good");
  await load();
}

async function discard(name) {
  let answered;
  try {
    answered = await send(`/api/searches/${encodeURIComponent(name)}/discard`, {});
  } catch (error) {
    fail(error);
    return;
  }
  discarding = null;
  say(
    `${name} is gone. ` +
    (answered.properties_kept
      ? `The ${answered.properties_kept} properties its ${answered.runs_kept} runs found are ` +
        "still in the store, with their history and anything you wrote on them."
      : "Nothing its runs recorded was touched."),
    "good");
  await load();
}
