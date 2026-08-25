"use strict";
/* One property's full picture, including how the record was assembled.
 *
 * The last part is the point of the surface. A merged record is two or three source rows joined by
 * a signal, and the only way to tell a real record from a bad merge is to see the rows and the
 * signal that joined them. So they are shown, with what each source called the property, rather
 * than hidden behind the canonical values.
 */

whenReady(() => {
  nav("");
  const id = pathParts()[1];
  load(id).catch(fail);
});

async function load(id) {
  const found = await ask(`/api/listings/${encodeURIComponent(id)}`);
  draw(found.listing);
}

function draw(held) {
  const fields = held.fields || {};
  const address = [fields.address_line, fields.unit, fields.city, fields.state, fields.postal_code]
    .filter(Boolean).join(", ");

  shell(address || held.listing_id,
    el("h1", {}, address || "This property has no address"),
    el("p", {class: "lede"},
      held.presence === "disappeared"
        ? "This property stopped appearing in results without being seen sold."
        : "Observed in the most recent run."),
    el("div", {class: "detail"},
      el("div", {},
        facts(held, fields),
        description(fields),
        timeline(held),
        provenance(held),
      ),
      el("div", {},
        picture(held),
        recovered(held),
        enrichment(held),
        judgment(held),
      ),
    ),
  );
}

function picture(held) {
  if (!held.has_image) {
    return el("section", {}, el("h2", {}, "Photograph"),
      el("p", {class: "unknown"}, "none stored"));
  }
  return el("section", {},
    el("h2", {}, "Photograph"),
    el("img", {
      class: "preview",
      src: `/api/listings/${encodeURIComponent(held.listing_id)}/image`,
      alt: "The preview image this tool stored when it first saw this property",
    }),
    el("p", {class: "meta"},
      "Stored by this tool, so it still shows for a property that has since disappeared, " +
      "and opening it tells the listing site nothing."),
  );
}

function facts(held, fields) {
  const rows = [
    ["Price", money(fields.price)],
    ["Status", value(fields.listing_status)],
    ["Beds", value(fields.beds)],
    ["Baths", value(fields.baths)],
    ["Square feet", value(fields.sqft)],
    ["Lot", value(fields.lot_sqft ? (fields.lot_sqft / 43560).toFixed(2) + " acres" : null)],
    ["Year built", value(fields.year_built)],
    ["Type", value(fields.property_type)],
    ["County", value(fields.county)],
    ["Days on market", value(held.days_on_market)],
    ["First seen", moment(held.first_observed_at)],
  ];
  return el("section", {},
    el("h2", {}, "What the listing says"),
    el("dl", {class: "facts"},
      rows.flatMap(([label, node]) => [el("dt", {}, label), el("dd", {}, node)])),
    fields.listing_url ? el("p", {}, link(fields.listing_url, "Open the listing")) : null,
  );
}

function description(fields) {
  if (!fields.description) {
    return el("section", {}, el("h2", {}, "Description"),
      el("p", {class: "unknown"}, "this source returned none"));
  }
  /* `pre` with textContent: the description is somebody else's text and never becomes markup. */
  return el("section", {},
    el("h2", {}, "Description"),
    el("pre", {class: "prose"}, fields.description),
  );
}

function timeline(held) {
  const prices = held.prices || [];
  const events = held.events || [];
  if (!prices.length && !events.length) {
    return el("section", {}, el("h2", {}, "History"),
      el("p", {class: "unknown"}, "nothing recorded yet"));
  }
  return el("section", {},
    el("h2", {}, "History"),
    el("table", {class: "plain"},
      el("thead", {}, el("tr", {},
        el("th", {scope: "col"}, "When"),
        el("th", {scope: "col"}, "What"),
      )),
      el("tbody", {},
        prices.map((entry) => el("tr", {},
          el("td", {}, moment(entry.observed_at)),
          el("td", {}, entry.price === null ? value(null) : money(entry.price)))),
        events.map((event) => el("tr", {},
          el("td", {}, moment(event.occurred_at)),
          el("td", {},
            badge(event.kind, "plain"), " ",
            detailOf(event.detail)))),
      ),
    ),
  );
}

/* An event's detail is whatever that kind of event recorded. Rendered as plain key-and-value text
 * rather than interpreted, because a surface that knows what each kind means is a surface that has
 * to be edited every time one is added. */
function detailOf(detail) {
  if (!detail || typeof detail !== "object") return value(detail);
  return Object.entries(detail)
    .map(([name, held]) => el("span", {}, `${name}: `, value(held), " "));
}

function provenance(held) {
  const sources = held.sources || [];
  return el("section", {},
    el("h2", {}, "How this record was assembled"),
    el("p", {class: "lede"},
      sources.length > 1
        ? "This record is more than one source row joined together. The signal that justified " +
          "each join is below; if one looks wrong, the source rows are still there underneath."
        : "One source row. Nothing has been merged into this record."),
    el("table", {class: "plain"},
      el("thead", {}, el("tr", {},
        el("th", {scope: "col"}, "Source"),
        el("th", {scope: "col"}, "Their identifier"),
        el("th", {scope: "col"}, "Why it was joined"),
        el("th", {scope: "col"}, "When"),
      )),
      el("tbody", {}, sources.map((link_) => el("tr", {},
        el("td", {}, link_.source),
        el("td", {}, value(link_.source_listing_id)),
        el("td", {}, value(link_.join_signal)),
        el("td", {},
          moment(link_.linked_at),
          link_.times_seen > 1
            ? el("span", {class: "rowstate"}, ` seen in ${link_.times_seen} runs`)
            : null),
      ))),
    ),
    held.superseded_by
      ? el("p", {class: "notice"},
          "This record was merged into another one. ",
          link(`/listing/${encodeURIComponent(held.superseded_by)}`, "Open that one"))
      : null,
  );
}

function recovered(held) {
  const extracted = held.extracted || {};
  const names = Object.keys(extracted);
  if (!names.length) return null;
  return el("section", {},
    el("h2", {}, "Read out of the description"),
    el("table", {class: "plain"},
      el("tbody", {}, names.map((name) => {
        const entry = extracted[name];
        return el("tr", {},
          el("th", {scope: "row"}, name.replace(/_/g, " ")),
          el("td", {},
            entry.conflicted
              ? el("span", {class: "unknown"}, "the description says two different things")
              : value(entry.value),
            entry.provenance ? el("span", {class: "rowstate"}, ` (${entry.provenance})`) : null,
            (entry.evidence || []).map((quote) =>
              el("p", {class: "rowstate"}, quote))),
        );
      })),
    ),
  );
}

function enrichment(held) {
  const found = held.enrichment || {};
  const names = Object.keys(found);
  if (!names.length) {
    return el("section", {}, el("h2", {}, "Where it is"),
      el("p", {class: "unknown"},
        "nothing looked up yet. Run homescout enrich to fill these."));
  }
  const internet = names.some((name) =>
    name === "download_mbps" || name === "upload_mbps" || name === "broadband_provider");

  return el("section", {},
    el("h2", {}, "Where it is"),
    el("dl", {class: "facts"},
      names.sort().flatMap((name) => [
        el("dt", {}, name.replace(/_/g, " ")),
        el("dd", {}, value(found[name])),
      ])),
    /* The speeds need a sentence the others do not. Every other value here is about this point:
     * the flood zone, the elevation, the aquifer under it. The speeds are about the census block,
     * which outside a town can be square miles, and they are what a provider filed rather than
     * what anybody measured. A number without that reads as a promise about this address. */
    internet
      ? el("p", {class: "meta"},
          "The speeds are the best advertised residential service the FCC records in this " +
          "property's census block. Not a measurement, and not this property's own line: a block " +
          "is a few houses in town and a few square miles outside it. Satellite is left out, " +
          "because it is available almost everywhere and would tell you nothing.")
      : null,
  );
}

function judgment(held) {
  const held_ = held.annotation || {};
  const rows = ["rank", "verdict", "red_flags", "summary", "next_step", "notes"];
  return el("section", {},
    el("h2", {}, "Your own judgment"),
    el("p", {class: "lede"},
      "Edit these in the results table, on the row you are reading. They survive every later run."),
    el("dl", {class: "facts"},
      rows.flatMap((name) => [
        el("dt", {}, name.replace(/_/g, " ")),
        el("dd", {}, value(held_[name])),
      ])),
    held.annotation_updated_at
      ? el("p", {class: "meta"}, `last written ${held.annotation_updated_at}`)
      : null,
  );
}

/* A stored timestamp, said readably and keeping the exact one where a pointer can find it.
 *
 * The store keeps UTC to the microsecond, which is right for the store and is not what somebody
 * reading a history wants. The precise value is still there, in the title, because on this surface
 * the difference between two runs a minute apart is sometimes the whole question.
 */
function moment(text) {
  if (!text) return value(null);
  return el("span", {title: text}, when(text));
}
