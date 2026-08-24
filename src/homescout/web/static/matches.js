"use strict";
/* The pairs the tool refused to guess at.
 *
 * Non-negotiable 6: an ambiguous merge is flagged for a human, never guessed. This is where the
 * human is. What each pair needs is not a prompt but the evidence: what lined up and what did not,
 * because "same street number, different city" and "same everything, different price" are not the
 * same question and do not get the same answer.
 *
 * A decision made here is durable and is honoured by every later run, which is what stops the same
 * pair coming back every night.
 */

whenReady(() => {
  nav("/matches");
  load().catch(fail);
});

async function load() {
  const found = await ask("/api/matches");
  draw(found.matches);
}

function draw(matches) {
  if (!matches.length) {
    shell("Matches",
      el("h1", {}, "Nothing to review"),
      el("p", {class: "lede"},
        "Every pair of records this tool compared was clear enough to decide on its own. " +
        "Pairs appear here only when the evidence points both ways."));
    return;
  }

  shell("Matches",
    el("h1", {}, `${matches.length} to review`),
    el("p", {class: "lede"},
      "Each of these is two records the tool could not tell apart or tell together. " +
      "Your answer is remembered and every later run respects it."),
    el("div", {class: "cards"}, matches.map(card)),
  );
}

function card(match) {
  return el("div", {class: "card", dataset: {match: match.id}},
    el("h3", {}, `${match.listing_ids.length} records`),
    el("p", {class: "meta"},
      match.listing_ids.map((id, index) =>
        el("span", {},
          index ? " · " : "",
          link(`/listing/${encodeURIComponent(id)}`, id.slice(0, 8)))),
    ),

    el("h4", {}, "What agrees"),
    match.agreed.length
      ? el("ul", {}, match.agreed.map((said) => el("li", {}, said)))
      : el("p", {class: "unknown"}, "nothing"),

    el("h4", {}, "What disagrees"),
    match.conflicted.length
      ? el("ul", {}, match.conflicted.map((said) => el("li", {}, said)))
      : el("p", {class: "unknown"}, "nothing"),

    el("div", {class: "actions"},
      el("button", {
        type: "button",
        onclick: () => decide(match.id, "same"),
      }, "One property: merge them"),
      el("button", {
        type: "button",
        onclick: () => decide(match.id, "different"),
      }, "Two properties: keep both"),
    ),
  );
}

async function decide(id, verdict) {
  try {
    const answered = await send(`/api/matches/${encodeURIComponent(id)}`, {verdict: verdict});
    say(
      verdict === "same"
        ? `Merged into ${answered.merged_listing_id}. The source rows are still there underneath.`
        : "Recorded as two different properties. This pair will not be asked about again.",
      "good");
  } catch (error) {
    fail(error);
    return;
  }
  await load();
}
