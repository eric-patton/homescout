"use strict";
/* Every property in a run, on top of the fire.
 *
 * This exists because of a house near Taos that every rule in the search was happy with. It stands
 * on ground the model calls very low hazard, so `wildfire_hazard` is "very low" and nothing objects,
 * and it is a few hundred metres from a solid wall of red. A criterion asks about the point a house
 * stands on. A person looking at a map asks a different question, one no value in this tool answers:
 * what is it *next to*.
 *
 * So this draws the same layer the enrichment pass reads, at the same address, and puts the
 * properties on top of it. It works out nothing and decides nothing. It is a way of looking, and the
 * looking is the point: the eye reads "a mile from that" in a moment and no column here can.
 *
 * ONE THING IS WORTH KNOWING BEFORE OPENING IT. The hazard layer is drawn by a federal server, so
 * this page asks that server for the part of the country on screen, the way any map does. Nothing
 * else in this tool does that unless a map background has been turned on. It is said on the page,
 * not only here.
 */

const held = {name: "", rows: [], settings: null, map: null, markers: null,
              showPassed: false, opacity: 0.55};

/* The classified layer's own legend, in the words the rest of this tool uses for it. Written out
 * rather than fetched: a legend that arrives over the network is a legend that is missing exactly
 * when the map is hardest to read. */
const HAZARD = [
  ["very high", "#e03020"],
  ["high", "#f08a20"],
  ["moderate", "#f5d949"],
  ["low", "#a8e05a"],
  ["very low", "#2f8f3f"],
  ["non-burnable", "#c8c8c8"],
  ["water", "#5aa8e0"],
];

/* What a pin says about itself before it is opened. Judgment first, because on this page the whole
 * job is telling apart the houses already dealt with from the ones still to look at. */
const PINS = {
  keep: {colour: "#8a6d00", fill: "#ffd75e", size: 9},
  pass: {colour: "#8c2b2b", fill: "#e8b6b6", size: 5},
  none: {colour: "#0f3f7a", fill: "#5b9bd5", size: 7},
};

whenReady(() => {
  document.body.classList.add("wide");
  nav("/");
  held.name = pathParts()[1] || "";
  load().catch(fail);
});

async function load() {
  const [found, settings] = await Promise.all([
    ask(`/api/results/${encodeURIComponent(held.name)}?include_passed=true`),
    ask("/api/settings"),
  ]);
  held.rows = found.rows.filter((row) => row.latitude !== null && row.longitude !== null);
  held.without = found.rows.length - held.rows.length;
  held.settings = settings;
  draw();
}

/* ------------------------------------------------------------------ */
/* The page                                                            */
/* ------------------------------------------------------------------ */

function draw() {
  const passed = el("input", {
    type: "checkbox",
    id: "showpassed",
    onchange: (event) => { held.showPassed = event.target.checked; plot(); },
  });

  const fade = el("input", {
    type: "range", id: "fade", min: "0", max: "100", value: String(held.opacity * 100),
    "aria-label": "How strongly the fire layer is drawn",
    oninput: (event) => {
      held.opacity = Number(event.target.value) / 100;
      if (held.hazard) held.hazard.setOpacity(held.opacity);
    },
  });

  shell(
    `${held.name} on the fire map`,
    el("h1", {}, "Where the fire is"),
    el("p", {class: "lede"},
      "Every property this run kept, on the wildfire hazard model the criteria read. A rule asks " +
      "about the ground a house stands on; this is for the other question, which is what it is " +
      "next to. Click a pin to keep the house or pass on it, and say why."),
    el("div", {class: "controls"},
      el("label", {for: "showpassed"}, passed, " show properties you passed on"),
      el("label", {for: "fade"}, "fire layer ", fade),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      link(`/results/${encodeURIComponent(held.name)}`, "back to the table"),
    ),
    el("div", {class: "firemap"},
      el("div", {id: "map", role: "application", "aria-label": "Properties on the fire map"}),
      legend(),
    ),
    el("p", {class: "meta"},
      "The fire layer is the same one the enrichment pass reads, fetched by this machine rather " +
      "than by your browser and kept once fetched, so looking at the same part of the state twice " +
      "costs nothing and nothing new talks to the outside world."),
  );

  build();
}

function legend() {
  return el("div", {class: "legend"},
    el("h2", {}, "Wildfire hazard potential"),
    el("ul", {},
      HAZARD.map(([word, colour]) =>
        el("li", {}, el("span", {class: "swatch", style: `background:${colour}`}), word))),
    el("h2", {}, "Your judgment"),
    el("ul", {},
      el("li", {}, el("span", {class: "swatch round kept"}), "kept"),
      el("li", {}, el("span", {class: "swatch round"}), "not decided"),
      el("li", {}, el("span", {class: "swatch round passed"}), "passed on"),
    ),
    el("p", {class: "meta"},
      "Colours are the model's own, redrawn here so the map reads without asking anybody for a " +
      "picture of its legend."),
  );
}

/* ------------------------------------------------------------------ */
/* The map                                                             */
/* ------------------------------------------------------------------ */

function build() {
  const where = document.getElementById("map");
  if (typeof L === "undefined") {
    where.replaceChildren(
      el("p", {class: "notice"},
        "The map library is not there. It lives in web/vendor and is committed with the tool."));
    return;
  }

  const map = L.map(where, {center: [34.5, -106.0], zoom: 7, preferCanvas: true});
  held.map = map;

  const tiles = held.settings.map && held.settings.map.tiles;
  if (tiles) {
    L.tileLayer(tiles, {attribution: held.settings.map.attribution || "", maxZoom: 19}).addTo(map);
  }

  if ((held.settings.hazards || {}).wildfire) {
    held.hazard = arcgisLayer("wildfire", {opacity: held.opacity}).addTo(map);
  } else {
    say("No wildfire layer is configured, so the map has nothing to draw behind the properties.");
  }

  held.markers = L.layerGroup().addTo(map);
  plot();
  const bounds = held.rows.map((row) => [row.latitude, row.longitude]);
  if (bounds.length) map.fitBounds(bounds, {padding: [24, 24]});
}

/* A hazard layer, drawn as map tiles.
 *
 * Leaflet asks for a tile by its column, row and zoom; the service answers about a rectangle in
 * metres. So the tile's own corners are projected to web mercator and handed over as the rectangle,
 * which is the whole of the translation between the two.
 *
 * Asked of this tool rather than of the federal server directly, which is not a detour: a browser
 * refuses a cross-origin image it was not clearly offered, so asking directly draws nothing at all,
 * and this way the only machine talking to that server is the one that already does.
 */
function arcgisLayer(layer, options) {
  const Layer = L.TileLayer.extend({
    getTileUrl(coords) {
      const size = this.getTileSize();
      const map = this._map;
      const topLeft = map.unproject(coords.scaleBy(size), coords.z);
      const bottomRight = map.unproject(coords.add([1, 1]).scaleBy(size), coords.z);
      const a = L.Projection.SphericalMercator.project(topLeft);
      const b = L.Projection.SphericalMercator.project(bottomRight);
      const query = new URLSearchParams({
        bbox: `${a.x},${b.y},${b.x},${a.y}`,
        size: `${size.x},${size.y}`,
      });
      return `/api/hazard/${encodeURIComponent(layer)}?${query}`;
    },
  });
  return new Layer("", Object.assign({maxZoom: 16, maxNativeZoom: 16}, options || {}));
}

function plot() {
  if (!held.markers) return;
  held.markers.clearLayers();
  let drawn = 0;
  for (const row of held.rows) {
    if (row.judgment === "pass" && !held.showPassed) continue;
    const look = PINS[row.judgment || "none"];
    const pin = L.circleMarker([row.latitude, row.longitude], {
      radius: look.size,
      color: look.colour,
      weight: 1.5,
      fillColor: look.fill,
      fillOpacity: 0.95,
    });
    pin.bindPopup(() => popup(row, pin), {minWidth: 260, maxWidth: 320});
    pin.addTo(held.markers);
    drawn += 1;
  }
  counts(drawn);
}

function counts(drawn) {
  const kept = held.rows.filter((row) => row.judgment === "keep").length;
  const passed = held.rows.filter((row) => row.judgment === "pass").length;
  const parts = [`${drawn} on the map`];
  if (kept) parts.push(`${kept} kept`);
  if (!held.showPassed && passed) parts.push(`${passed} passed and hidden`);
  if (held.without) {
    parts.push(count(held.without, "property", "properties") + " with no location, not shown");
  }
  const where = document.getElementById("counts");
  if (where) where.replaceChildren(document.createTextNode(parts.join(" · ")));
}

/* ------------------------------------------------------------------ */
/* One property, on the map                                            */
/* ------------------------------------------------------------------ */

function popup(row, pin) {
  const values = row.values;
  const facts = [
    values["Price"] === null || values["Price"] === undefined
      ? null : `$${Number(values["Price"]).toLocaleString()}`,
    values["Beds"] ? `${values["Beds"]} bed` : null,
    values["Acres"] ? `${values["Acres"]} acres` : null,
    values["Year Built"] ? `built ${values["Year Built"]}` : null,
  ].filter(Boolean).join(" · ");

  const held_ = el("div", {class: "pin"},
    el("p", {class: "what"},
      link(`/listing/${encodeURIComponent(row.listing_id)}`, values["Property"] || "this property")),
    facts ? el("p", {class: "facts"}, facts) : null,
    el("p", {class: "facts"},
      "hazard here: ", el("strong", {}, values["Wildfire Hazard"] || "not known")),
    values["Wildland-Urban Interface"]
      ? el("p", {class: "facts"}, values["Wildland-Urban Interface"]) : null,
    el("p", {class: "elsewhere"},
      (row.links || []).map((entry) =>
        link(entry.url, {realtor: "Realtor", zillow: "Zillow", redfin: "Redfin"}[entry.source]
                        || entry.source))),
  );

  const say_ = el("p", {class: "rowstate", role: "status"}, "");
  const keep = el("button", {
    type: "button",
    class: row.judgment === "keep" ? "keep on" : "keep",
    onclick: () => decide(row, pin, row.judgment === "keep" ? null : "keep", say_),
  }, row.judgment === "keep" ? "★ kept" : "☆ keep");
  const pass = el("button", {
    type: "button",
    class: row.judgment === "pass" ? "pass on" : "pass",
    onclick: () => decide(row, pin, row.judgment === "pass" ? null : "pass", say_),
  }, row.judgment === "pass" ? "undo" : "✕ pass");

  held_.append(el("div", {class: "actions"}, keep, pass), say_);
  return held_;
}

/* The same decision the table records, from the map, with the same question asked about it.
 *
 * Why here as well: this page is where the answer is obvious. "Too close to the red" is a thing
 * somebody can see and cannot easily say from a table of numbers, and it is exactly the reason
 * worth having in writing.
 */
async function decide(row, pin, wanted, where) {
  let reason = null;
  if (wanted !== null) {
    const asked = await askWhy(row, wanted);
    if (!asked.yes) return;
    reason = asked.reason;
  }
  where.replaceChildren(document.createTextNode("saving…"));
  try {
    const body = {judgment: wanted};
    if (reason !== null && reason.trim() !== "") body.verdict = reason;
    const answered = await send(
      `/api/listings/${encodeURIComponent(row.listing_id)}/annotation`, body);
    row.judgment = answered.judgment ?? null;
    row.values["Verdict"] = answered.verdict ?? row.values["Verdict"];
    held.map.closePopup();
    plot();
  } catch (error) {
    where.replaceChildren(document.createTextNode(`not saved: ${error.message}`));
    where.className = "rowstate problem";
  }
}

function askWhy(row, wanted) {
  return new Promise((resolve) => {
    let answered = false;
    const done = (yes) => {
      if (answered) return;
      answered = true;
      resolve({yes, reason: yes ? why.value : null});
      dialog.close();
      dialog.remove();
    };

    const why = el("textarea", {
      rows: "3",
      value: row.values["Verdict"] || "",
      placeholder: wanted === "pass"
        ? "Why? \"Half a mile from the red\" is exactly the kind of reason worth keeping."
        : "Why? Optional, and worth having.",
      "aria-label": "Why",
      onkeydown: (event) => {
        if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); done(true); }
        event.stopPropagation();
      },
    });

    const dialog = el("dialog", {
      class: "ask",
      "aria-labelledby": "askwhat",
      onclose: () => done(false),
      oncancel: () => done(false),
      onclick: (event) => { if (event.target === dialog) done(false); },
    },
      el("h2", {id: "askwhat"},
        wanted === "pass" ? "Pass on this property?" : "Keep this one?"),
      el("p", {}, row.values["Property"] || row.listing_id),
      why,
      el("p", {class: "hint"},
        wanted === "pass"
          ? "It leaves the table and this map, and stays out of both until you ask for it back."
          : "It goes on your shortlist. Nothing is hidden."),
      el("div", {class: "actions"},
        el("button", {type: "button", class: "quiet", onclick: () => done(false)}, "Cancel"),
        el("button", {type: "button", class: "primary", onclick: () => done(true)},
           wanted === "pass" ? "Pass on it" : "Keep it"),
      ),
    );
    document.body.append(dialog);
    dialog.showModal();
    why.focus();
  });
}
