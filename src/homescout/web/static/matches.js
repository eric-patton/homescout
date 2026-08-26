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
    el("div", {class: "pair"}, (match.properties || []).map(side)),

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

/* One of the two properties, as much of it as fits: the photograph first, because that is what
 * settles most of these at a glance, then the address, the price and which sites it came from.
 * Two records from two different sites at the same address is the shape of a house seen twice;
 * "Mimbres Rd" against "Mimbres Ct" at a different price is the shape of two houses. */
function side(property) {
  const where = [property.address_line, property.city].filter(Boolean).join(", ");
  const facts = [
    property.beds ? `${property.beds} bed` : null,
    property.baths ? `${property.baths} bath` : null,
    property.sqft ? `${property.sqft.toLocaleString()} sq ft` : null,
    property.year_built ? String(property.year_built) : null,
  ].filter(Boolean).join(" · ");

  return el("div", {class: "side"},
    property.has_image
      ? el("img", {
          class: "shot",
          src: `/api/listings/${encodeURIComponent(property.listing_id)}/image`,
          alt: where ? `Photograph of ${where}` : "Photograph of this property",
          loading: "lazy",
        })
      : el("div", {class: "shot none", role: "img", "aria-label": "No photograph stored"},
          "no photograph"),
    el("p", {class: "who"},
      el("strong", {}, link(`/listing/${encodeURIComponent(property.listing_id)}`,
                            where || property.listing_id.slice(0, 8))),
      el("br", {}),
      el("span", {class: "cost"}, money(property.price)),
      facts ? el("span", {}, ` · ${facts}`) : "",
      el("br", {}),
      el("span", {class: "from"},
        (property.sources || []).length
          ? `seen by ${property.sources.join(" and ")}`
          : "no source recorded"),
    ),
  );
}
