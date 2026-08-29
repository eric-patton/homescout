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

/* What to call each field on this page. The core knows: it declares every field a criterion can
 * name along with the words to put in front of a person, and this reads the same table rather than
 * turning `over_principal_aquifer` into "over principal aquifer" and calling that a label. */
let labels = {};

function labelFor(name) {
  return labels[name] || name.replace(/_/g, " ");
}

async function load(id) {
  const [found, settings] = await Promise.all([
    ask(`/api/listings/${encodeURIComponent(id)}`),
    ask("/api/settings"),
  ]);
  for (const field of settings.rule_vocabulary || []) labels[field.name] = field.label;
  draw(found.listing, settings);
}

function draw(held, settings) {
  const fields = held.fields || {};
  const address = propertyName(fields, held.listing_id);

  const from = fromSearch();
  shell(address,
    /* The way back to the table this was read from, which is a fact about this visit rather than
     * about the property: a house can be in several saved searches, so "back to the search" has no
     * single answer. Opened without one, this page simply offers no trail rather than guessing. */
    from
      ? el("p", {class: "crumbs"},
          link("/", "Searches"), " / ",
          link(`/results/${encodeURIComponent(from)}`, from), " / ",
          el("span", {}, "This property"))
      : el("p", {class: "crumbs"}, link("/", "Searches"), " / ", el("span", {}, "This property")),
    el("h1", {}, address),
    /* Kept, and not the thing anybody is asked to read: it is exact, it is how this property is
     * asked for again, and it is what to quote when something about it is wrong. */
    el("p", {class: "meta recordid"}, "record ", held.listing_id),
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
        whereItIs(held, settings),
        picture(held),
        recovered(held),
        enrichment(held),
        judgment(held),
      ),
    ),
  );
}

/* This one house on the fire, small, on its own page.
 *
 * Asked for in one sentence: "on the individual property pages, it would be nice if it showed a
 * small firemap so you could quickly see where that one was." The full map answers "which of these
 * hundred is near the red" and this answers the other half of the same question, which is the one
 * somebody has while reading a single listing: what is *this* one next to.
 *
 * The same layer at the same address as the big map and the enrichment pass, through the same
 * cached route, so opening a property twice costs nothing and nothing new talks to the outside
 * world. Drawn after the page is on screen, because a map built into a detached element measures
 * itself as zero by zero and comes out grey.
 */
function whereItIs(held, settings) {
  const fields = held.fields || {};
  if (fields.latitude === null || fields.latitude === undefined
      || fields.longitude === null || fields.longitude === undefined) {
    return el("section", {},
      el("h2", {}, "Where it is"),
      el("p", {class: "notice"},
        "No source gave this property a location, so it cannot be drawn on the map. It is "
        + "counted as unplaced there rather than quietly left out."),
    );
  }
  if (typeof L === "undefined") return null;

  const where = el("div", {id: "minimap", role: "application",
                           "aria-label": "This property on the wildfire hazard map"});
  /* After the shell has put this in the document. A map measures the element it is given, and an
   * element that is not on the page yet is zero pixels tall. */
  setTimeout(() => drawWhereItIs(where, fields, settings), 0);

  return el("section", {},
    el("h2", {}, "Where it is"),
    el("div", {class: "minimap"}, where),
    el("p", {class: "meta"},
      "Wildfire hazard potential, the same layer the criteria read. A rule asks about the ground "
      + "this house stands on; the map is for what it is next to. Drag and zoom it."),
  );
}

function drawWhereItIs(where, fields, settings) {
  if (!where.isConnected) return;
  const at = [fields.latitude, fields.longitude];
  const map = L.map(where, {center: at, zoom: 12, preferCanvas: true, scrollWheelZoom: false});

  const tiles = settings.map && settings.map.tiles;
  if (tiles) {
    L.tileLayer(tiles, {attribution: settings.map.attribution || "", maxZoom: 19}).addTo(map);
  }
  if ((settings.hazards || {}).wildfire) {
    arcgisLayer("wildfire", {opacity: 0.55}).addTo(map);
  }
  L.control.scale({position: "bottomleft", imperial: true, metric: false, maxWidth: 140})
    .addTo(map);

  /* The same blue as an undecided pin on the big map, because it is the same thing: this page
   * shows a judgment and does not make one, so the pin says nothing about what was decided. */
  L.circleMarker(at, {
    radius: 8, color: "#0f3f7a", weight: 2, fillColor: "#5b9bd5", fillOpacity: 0.95,
  }).addTo(map);
}

function picture(held) {
  const photos = (held.photo_urls || []).filter(Boolean);
  if (!held.has_image) {
    return el("section", {}, el("h2", {}, "Photograph"),
      el("p", {class: "unknown"}, "none stored"),
      photos.length ? seeThemAll(held, photos) : null);
  }
  const stored = el("img", {
    class: "preview",
    src: `/api/listings/${encodeURIComponent(held.listing_id)}/image`,
    alt: "The preview image this tool stored when it first saw this property",
  });
  return el("section", {},
    el("h2", {}, "Photograph"),
    photos.length
      ? el("button", {
          type: "button",
          class: "shownall",
          "aria-label": `See all ${photos.length} photographs`,
          onclick: () => gallery(photos, address(held)),
        }, stored)
      : stored,
    el("p", {class: "meta"},
      "Stored by this tool, so it still shows for a property that has since disappeared, " +
      "and opening it tells the listing site nothing."),
    photos.length ? seeThemAll(held, photos) : null,
  );
}

/* The rest of the listing's photographs, which this tool does not hold and does not fetch until
 * somebody asks. Said in the sentence rather than left to be discovered: everywhere else on this
 * page, looking costs the listing site nothing, and this is the one place that is not true. */
function seeThemAll(held, photos) {
  return el("p", {},
    el("button", {type: "button", class: "quiet",
                  onclick: () => gallery(photos, address(held))},
       `See all ${photos.length} photographs`),
    el("span", {class: "meta"},
      " These come from the listing site when you open them, not from this machine."),
  );
}

function address(held) {
  return propertyName(held.fields || {}, held.listing_id);
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
    .map(([name, held]) => el("span", {class: "eventdetail"}, `${name}: `, ids(held), " "));
}

/* A value that is a comma-joined list of record identifiers, said as what it is.
 *
 * A merge event records which records were folded in, and printed straight it is a run of
 * thirty-two-character strings that overflows the column and is clipped mid-identifier, which is
 * neither readable nor complete. The count is the part somebody wants; the identifiers are there
 * underneath for whoever is chasing one, wrapping rather than running off the edge. */
function ids(held) {
  if (typeof held !== "string" || !/^[0-9a-f]{32}(,[0-9a-f]{32})*$/.test(held.trim())) {
    return value(held);
  }
  const many = held.trim().split(",");
  return el("span", {},
    count(many.length, "record"), " ",
    el("span", {class: "rowstate ids"}, many.join(" ")));
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
        /* The site's own name, and its own page. A merged record has one page per site and they
         * are not interchangeable: a person keeping a list on one site needs that site's page. */
        el("td", {}, link_.listing_url
          ? link(link_.listing_url, link_.source, {title: `Open this on ${link_.source}`})
          : link_.source),
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
          el("th", {scope: "row"}, labelFor(name)),
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

/* The three readings of the interface value, kept apart in the browser exactly as the spreadsheet
 * keeps them apart. `in` rather than a truthiness test, because the known negative IS null and the
 * only thing that separates it from "nobody asked" is whether the key is there at all. */
function interfaceValue(held) {
  if (held === null || held === undefined) {
    return el("span", {class: "negative", title: "asked, and this place is in neither kind"},
      "not in the wildland-urban interface");
  }
  if (held === "outside coverage") {
    return el("span", {class: "unknown", title: "this source covers New Mexico only"},
      "outside coverage");
  }
  return el("span", {}, "in the wildland-urban interface: " + String(held));
}

function enrichment(held) {
  const found = held.enrichment || {};
  const names = Object.keys(found);
  if (!names.length) {
    return el("section", {}, el("h2", {}, "What is around it"),
      el("p", {class: "unknown"},
        "nothing looked up yet. Settings and tools has a button that fills these in."));
  }
  const internet = names.some((name) =>
    name === "download_mbps" || name === "upload_mbps" || name === "broadband_provider");

  const interfaceHeld = "wildland_urban_interface" in found;

  /* "What is around it", not "Where it is", which is what the map section above is called and
   * what this one was called as well: every listing page carried two sections with the same
   * heading, one holding a map and one holding the flood zone, the aquifer and the speeds. This is
   * the public record about the place rather than the place. */
  return el("section", {},
    el("h2", {}, "What is around it"),
    el("dl", {class: "facts"},
      names.sort().flatMap((name) => [
        el("dt", {}, labelFor(name)),
        el("dd", {}, name === "wildland_urban_interface"
          ? interfaceValue(found[name])
          : value(found[name])),
      ])),
    /* The speeds need a sentence the others do not. Every other value here is about this point:
     * the flood zone, the elevation, the aquifer under it. The speeds are about the census block,
     * which outside a town can be square miles, and they are what a provider filed rather than
     * what anybody measured. A number without that reads as a promise about this address. */
    /* The one value here whose "no" is a real answer. Left to the shared renderer, `null` comes out
     * as "not known / nobody determined this", which is the exact sentence this field must never
     * say: somebody did determine it, and what they determined is that this house is not standing
     * in the vegetation. The other direction matters just as much, which is why `outside coverage`
     * is spelled out rather than shown as a bare phrase nobody can interpret. */
    interfaceHeld
      ? el("p", {class: "meta"},
          "The wildland-urban interface says whether houses here stand in the vegetation, which " +
          "is a different question from wildfire hazard: hazard describes how the vegetation " +
          "would burn, the interface describes whether homes are in it. This one covers New " +
          "Mexico only, so a property anywhere else reads as outside coverage rather than as a no.")
      : null,
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
  /* Yours, so they are labelled the way you would say them rather than the way they are stored. */
  const rows = [
    ["rank", "Your rank"],
    ["verdict", "Your verdict"],
    ["red_flags", "Red flags"],
    ["summary", "Summary"],
    ["next_step", "Next step"],
    ["notes", "Notes"],
  ];
  const carried = held.tags || [];
  return el("section", {},
    el("h2", {}, "Your own judgment"),
    el("p", {class: "lede"},
      "Edit these in the results table, on the row you are reading. They survive every later run."),
    /* Shown here and set in the table, like everything else on this panel. This page is for
     * reading one property; the table is where a decision is made about it against the others. */
    el("div", {class: "tagstrip"},
      carried.length
        ? carried.map((one) => el("span", {class: "tag"}, one))
        : el("span", {class: "none"}, "no tags")),
    el("dl", {class: "facts"},
      rows.flatMap(([name, said]) => [
        el("dt", {}, said),
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
