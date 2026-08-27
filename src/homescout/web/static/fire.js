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

/* The ruler: a rod laid on the map, moved by dragging it, reading its own length.
 *
 * The scale bar in the corner answers "how big is this screen", which is the question at a glance.
 * It does not answer the one actually being asked, which is how far this house is from that red,
 * and no fixed bar in a corner ever will: the two things being compared are somewhere else on the
 * map and a scale bar cannot be held up against them. So the rod is the scale bar taken off the
 * corner and made movable, and once a thing is movable and has two ends it may as well say what is
 * between them. */
const rule = {on: false, line: null, a: null, b: null, middle: null, was: null};

/* Which way the wind pushes, station by station. `roses` is what has come back, `asking` is what
 * is on its way: a station's record takes a real query on somebody else's archive and this asks for
 * each one once, ever. */
const wind = {on: false, season: "april", stations: [], byKey: {}, roses: {}, asking: {},
              drawn: {}, layer: null, failed: 0};

const METRES_TO_A_MILE = 1609.344;
const FEET_TO_A_METRE = 3.28084;

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

  const ruler = el("input", {
    type: "checkbox",
    id: "ruler",
    onchange: (event) => showRule(event.target.checked),
  });

  const blowing = el("input", {
    type: "checkbox",
    id: "wind",
    onchange: (event) => showWind(event.target.checked),
  });

  const season = el("select", {
    id: "season",
    "aria-label": "Which months the wind is counted over",
    onchange: (event) => {
      wind.season = event.target.value;
      wind.roses = {};
      wind.asking = {};
      wind.drawn = {};
      wind.failed = 0;
      if (wind.layer) wind.layer.clearLayers();
      if (wind.on) blow();
    },
  },
    el("option", {value: "april"}, "in April"),
    el("option", {value: "year"}, "all year"),
  );

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
      el("label", {for: "ruler"}, ruler, " measure a distance"),
      el("label", {for: "wind"}, blowing, " which way the wind pushes ", season),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      el("span", {class: "counts", id: "windcount", role: "status"}, ""),
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
    el("p", {class: "meta"},
      "The wind is every hourly reading each airport weather station has on record, not a " +
      "forecast: Thursday\u2019s wind is a fact about Thursday, and a house is a longer question " +
      "than that. Those are anemometers in the open at airports tens of miles apart, so this " +
      "says which way weather moves through a region and cannot tell you about your own canyon."),
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
    /* Deliberately NOT drawn the way a wind rose is drawn, and this note is here because the
     * next person to read it will assume that is a bug and turn it back.
     *
     * A rose points into the wind, the way a weather vane does, and that convention is older than
     * anybody who will ever work on this. It is also the single easiest thing on this page to read
     * backwards, and backwards here is not a slightly worse answer: "from the west" and "toward
     * the west" name opposite sides of a house as the side to worry about. Nothing else on this
     * map fails that way.
     *
     * The reader is two people buying a house, not two meteorologists, and what they want to know
     * is which way a fire would run. So the arms are turned around to point downwind, the longest
     * one carries a head, and the word "from" appears nowhere near a direction. The archive still
     * records it the meteorological way and `enrich/wind.py` still stores it that way, which is
     * right for a store of facts; the turning around happens here, where the drawing is. */
    el("h2", {}, "Which way the wind pushes"),
    el("ul", {},
      el("li", {}, el("span", {class: "swatch wind any"}), "any speed"),
      el("li", {}, el("span", {class: "swatch wind strong"}), "15 mph and over"),
    ),
    el("p", {class: "meta"},
      "An arm points the way the wind ", el("strong", {}, "pushes"),
      ", and the head marks the way it pushes most often. That is the way a fire here would run, " +
      "so the red to worry about is the red the head points at."),
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

  /* How far a screen is, at whatever zoom this is. Miles only: everything else on this page that
   * talks about distance is in miles, and two bars in a corner is one more thing to read. */
  L.control.scale({position: "bottomleft", imperial: true, metric: false, maxWidth: 180})
    .addTo(map);

  /* A layer of its own for the wind, between the hazard raster and the properties.
   *
   * The obvious way, a large negative `zIndexOffset` on each rose, is wrong in a way that only a
   * real click finds: it gives the marker a negative z-index, which paints it behind the map's own
   * surface, so every click at a rose lands on the tile underneath it and the rose is decoration
   * that cannot be opened. A pointer test is the only thing that catches that. Leaflet numbers its
   * own layers 200 for tiles, 400 for overlays and 600 for markers, so 450 is under the properties
   * and over the fire, which is the order these things should be read in. */
  map.createPane("wind");
  map.getPane("wind").style.zIndex = "450";

  held.markers = L.layerGroup().addTo(map);
  wind.layer = L.layerGroup();
  /* Only what is on screen is asked about, nearest the middle first. Somebody looking at Taos gets
   * Taos in ten seconds rather than the whole state in four minutes. */
  map.on("moveend", () => { if (wind.on) blow(); });
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


/* ------------------------------------------------------------------ */
/* How far is that                                                     */
/* ------------------------------------------------------------------ */

/* Put the rod on the map or take it off. */
function showRule(on) {
  rule.on = Boolean(on);
  if (!rule.on) {
    for (const part of [rule.line, rule.a, rule.b, rule.middle]) {
      if (part) held.map.removeLayer(part);
    }
    rule.line = rule.a = rule.b = rule.middle = null;
    return;
  }
  if (rule.line) return;

  const [from, to] = across();
  rule.a = grip(from, "rule-end", "One end of the ruler", () => reread());
  rule.b = grip(to, "rule-end", "The other end of the ruler", () => reread());
  rule.middle = grip(between(from, to), "rule-middle", "The whole ruler, to move it", () => {});
  rule.line = L.polyline([from, to], {
    color: "#12263f", weight: 3, opacity: 0.9, dashArray: "7 5", interactive: false,
  });

  /* Dragging the middle carries both ends with it, which is what makes this a ruler rather than
   * two points: the length is set once and then held up against one thing after another. */
  rule.middle.on("dragstart", () => { rule.was = rule.middle.getLatLng(); });
  rule.middle.on("drag", () => {
    const now = rule.middle.getLatLng();
    const north = now.lat - rule.was.lat;
    const east = now.lng - rule.was.lng;
    rule.was = now;
    for (const end of [rule.a, rule.b]) {
      const at = end.getLatLng();
      end.setLatLng(L.latLng(at.lat + north, at.lng + east));
    }
    reread(false);
  });

  rule.line.addTo(held.map);
  for (const part of [rule.a, rule.b, rule.middle]) part.addTo(held.map);
  reread();
  say("Drag either end to set the length. Drag the reading in the middle to carry the whole ruler "
      + "somewhere else. The arrow keys move whichever end has the keyboard.");
}

/* Across the middle third of whatever is on screen, so it lands where somebody is looking and at a
 * length worth comparing rather than at a length nobody chose. */
function across() {
  const bounds = held.map.getBounds();
  const middle = bounds.getCenter();
  const span = (bounds.getEast() - bounds.getWest()) / 3;
  return [L.latLng(middle.lat, middle.lng - span / 2),
          L.latLng(middle.lat, middle.lng + span / 2)];
}

function between(from, to) {
  return L.latLng((from.lat + to.lat) / 2, (from.lng + to.lng) / 2);
}

/* One draggable handle. Focusable and nudgeable, because the pointer is not the only way anybody
 * uses this and AC-17 does not make an exception for a ruler. */
function grip(where, look, said, moved) {
  const pin = L.marker(where, {
    draggable: true,
    keyboard: true,
    title: said,
    alt: said,
    icon: L.divIcon({className: look, iconSize: [18, 18]}),
    zIndexOffset: 1200,
  });
  pin.on("drag", moved);
  pin.on("add", () => {
    const node = pin.getElement();
    if (!node) return;
    node.setAttribute("role", "slider");
    node.setAttribute("aria-label", said);
    node.addEventListener("keydown", (event) => nudge(event, pin, moved));
  });
  return pin;
}

/* The arrow keys, in units of what is on screen rather than in degrees. A step of a fixed number of
 * degrees is a jump off the map at one zoom and no movement at all at another. */
function nudge(event, pin, moved) {
  const step = {ArrowUp: [1, 0], ArrowDown: [-1, 0],
                ArrowLeft: [0, -1], ArrowRight: [0, 1]}[event.key];
  if (!step) return;
  event.preventDefault();
  event.stopPropagation();

  const bounds = held.map.getBounds();
  const part = event.shiftKey ? 12 : 60;
  const north = (bounds.getNorth() - bounds.getSouth()) / part;
  const east = (bounds.getEast() - bounds.getWest()) / part;
  const at = pin.getLatLng();

  if (pin === rule.middle) {
    rule.was = at;
    pin.setLatLng(L.latLng(at.lat + step[0] * north, at.lng + step[1] * east));
    pin.fire("drag");
    return;
  }
  pin.setLatLng(L.latLng(at.lat + step[0] * north, at.lng + step[1] * east));
  moved();
}

/* The rod redrawn, and what it now says. */
function reread(recentre = true) {
  if (!rule.line) return;
  const from = rule.a.getLatLng();
  const to = rule.b.getLatLng();
  rule.line.setLatLngs([from, to]);
  if (recentre) {
    rule.was = between(from, to);
    rule.middle.setLatLng(rule.was);
  }

  const reading = el("span", {}, howFar(from, to));
  if (rule.middle.getTooltip()) rule.middle.setTooltipContent(reading);
  else {
    rule.middle.bindTooltip(reading, {
      permanent: true, direction: "top", offset: [0, -10], className: "rule-said",
    });
  }
}

/* Miles, because everything else on this page that talks about distance is in miles, and feet
 * below the point where a mile stops being a useful unit: "0.03 miles" is a number nobody pictures
 * and a hundred and fifty feet is a house's own frontage. */
function howFar(from, to) {
  const metres = held.map.distance(from, to);
  const miles = metres / METRES_TO_A_MILE;
  if (miles < 0.2) {
    const feet = Math.round(metres * FEET_TO_A_METRE / 10) * 10;
    return `${feet.toLocaleString()} feet`;
  }
  return `${miles.toFixed(miles < 10 ? 2 : 1)} miles`;
}


/* ------------------------------------------------------------------ */
/* Which way the wind pushes                                           */
/* ------------------------------------------------------------------ */

/* How the rose is drawn. */
const ROSE_SIZE = 72;
const ROSE_FULL = 20;      /* The percent an arm at full length means. */
const ROSE_HEAD = 7;       /* How far past its arm the one head reaches. */
/* Violet, and violet for a reason: this page already spends red through green on the hazard model
 * and blue, gold and pink on what the person has decided about a house. A rose in any of those
 * would be read as one of those. Nothing else here is violet. */
const ROSE_ANY = "#a276cf";
const ROSE_STRONG = "#4c1d95";

/* Turn the overlay on or off. Off by default: this page is about the fire, and a second layer
 * nobody asked for over the top of it is a page that is about neither. */
async function showWind(on) {
  wind.on = Boolean(on);
  if (!wind.on) {
    held.map.removeLayer(wind.layer);
    return;
  }
  wind.layer.addTo(held.map);
  if (!wind.stations.length) {
    try {
      const found = await ask(`/api/wind/stations/${encodeURIComponent(held.name)}`);
      wind.stations = found.stations || [];
      for (const one of wind.stations) wind.byKey[`${one.network}/${one.station}`] = one;
      for (const said of found.unreachable || []) say(`No wind records for ${said}`, "problem");
    } catch (error) {
      say(`The weather stations could not be listed: ${error.message}`, "problem");
      return;
    }
  }
  if (!wind.stations.length) {
    say("No weather stations cover the states this run found properties in.");
    return;
  }
  blow();
}

/* Ask about the stations on screen, nearest the middle of it first, and draw whatever has come
 * back. Called again every time the map moves, which is what keeps the asking to what is being
 * looked at. */
function blow() {
  if (!wind.on) return;
  const bounds = held.map.getBounds().pad(0.15);
  const middle = held.map.getCenter();
  const near = wind.stations
    .filter((one) => bounds.contains([one.latitude, one.longitude]))
    .sort((a, b) => held.map.distance(middle, [a.latitude, a.longitude])
                  - held.map.distance(middle, [b.latitude, b.longitude]));

  for (const one of near) {
    const key = `${one.network}/${one.station}`;
    if (wind.roses[key] || wind.asking[key]) continue;
    wind.asking[key] = true;
    fetchRose(one, key);
  }
  drawWind(near.length);
}

async function fetchRose(station, key) {
  try {
    const found = await ask(
      `/api/wind/rose/${encodeURIComponent(station.network)}/` +
      `${encodeURIComponent(station.station)}?season=${encodeURIComponent(wind.season)}`);
    /* The season may have been changed while this was in flight, and an answer about April drawn
     * on a map now asking about the year is a wrong number nobody would ever catch. */
    if (found.rose.when === wind.season) wind.roses[key] = found.rose;
  } catch (error) {
    wind.failed += 1;
  } finally {
    delete wind.asking[key];
    if (wind.on) drawWind();
  }
}

/* What should be on the map, put on the map, WITHOUT touching whatever is already right.
 *
 * The obvious version of this clears the layer and rebuilds it, and the obvious version has a bug
 * that only a real pointer finds. Opening a rose near the edge of the screen makes the map pan to
 * fit the bubble; panning fires a move; a move is what calls this; and clearing the layer removes
 * the very marker the bubble belongs to, which closes it. So the rose nearest the middle opened
 * and every other one flickered and shut, which is worse than a bug that never works because it
 * looks like the person mis-clicked.
 */
function drawWind(inView) {
  const wanted = {};
  for (const one of wind.stations) {
    const key = `${one.network}/${one.station}`;
    if (wind.roses[key]) wanted[key] = "rose";
    else if (wind.asking[key]) wanted[key] = "waiting";
  }

  for (const [key, held_] of Object.entries(wind.drawn)) {
    if (wanted[key] === held_.kind) continue;
    wind.layer.removeLayer(held_.layer);
    delete wind.drawn[key];
  }
  for (const [key, kind] of Object.entries(wanted)) {
    if (wind.drawn[key]) continue;
    const one = wind.byKey[key];
    if (!one) continue;
    const layer = kind === "rose" ? roseAt(one, wind.roses[key]) : waitingAt(one);
    layer.addTo(wind.layer);
    wind.drawn[key] = {kind: kind, layer: layer};
  }

  if (inView !== undefined) wind.inView = inView;
  windCount(Object.values(wind.drawn).filter((held_) => held_.kind === "rose").length);
}

function windCount(drawn) {
  const waiting = Object.keys(wind.asking).length;
  const where = document.getElementById("windcount");
  if (!where) return;
  const parts = [];
  if (waiting) {
    parts.push(count(waiting, "station", "stations") + " still being read");
  } else if (drawn) {
    parts.push(count(drawn, "weather station", "weather stations"));
  }
  if (wind.failed) parts.push(`${wind.failed} would not answer`);
  where.replaceChildren(document.createTextNode(parts.join(" \u00b7 ")));
}

/* A station whose record is on its way. Drawn rather than left blank, so it is plain that there is
 * more coming and where it will be: the first read of a station takes about ten seconds, and an
 * empty patch of map says nothing about whether anything is happening. */
function waitingAt(station) {
  return L.circleMarker([station.latitude, station.longitude], {
    pane: "wind",
    radius: 5, color: ROSE_STRONG, weight: 1.5, opacity: 0.7,
    fillColor: ROSE_ANY, fillOpacity: 0.5,
  }).bindTooltip(`${station.name}: reading its record\u2026`);
}

/* One station's rose, as a fixed number of pixels rather than a shape on the ground.
 *
 * A rose drawn in degrees would be a speck at one zoom and cover a county at the next, and it is
 * not a thing that is anywhere: it is a summary of a place, drawn at the place. So it is an icon,
 * and its size is the same at every zoom.
 */
function roseAt(station, rose) {
  const pin = L.marker([station.latitude, station.longitude], {
    pane: "wind",
    icon: L.divIcon({className: "rose", iconSize: [ROSE_SIZE, ROSE_SIZE]}),
    keyboard: true,
    title: whatItSays(rose),
    alt: whatItSays(rose),
  });
  pin.on("add", () => {
    const node = pin.getElement();
    if (node && !node.firstChild) node.append(arms(rose));
  });
  pin.bindPopup(() => aboutTheWind(rose), {minWidth: 250, maxWidth: 320});
  return pin;
}

/* The one line that turns the archive's answer into the page's question.
 *
 * A weather archive records a direction the way meteorology has always recorded it, which is where
 * the air came out of, and that is the right thing for a record of facts to hold. It is the wrong
 * thing to draw on a fire map, because the question here is where a fire goes. Every direction that
 * reaches a reader goes through this, and nothing on this page ever shows `degrees` raw. */
function pushes(degrees) {
  return (degrees + 180) % 360;
}

function whatItSays(rose) {
  const best = rose.prevailing;
  if (!best) return `${rose.name}: no wind on record`;
  return `${rose.name}: the wind pushes toward the ${compassOf(pushes(best.degrees))} more than ` +
         `any other direction, ${best.percent.toFixed(1)}% of the time`;
}

/* The glyph. Built with `createElementNS` rather than from a string of markup, which is the same
 * rule every other thing this product draws follows and the reason there is no way to put markup
 * on a page here at all.
 *
 * Every arm is drawn at `pushes(degrees)`, which is a half turn from where the archive put it. The
 * long note in `legend()` is why. */
function arms(rose) {
  const where = "http://www.w3.org/2000/svg";
  const box = document.createElementNS(where, "svg");
  box.setAttribute("viewBox", `0 0 ${ROSE_SIZE} ${ROSE_SIZE}`);
  box.setAttribute("width", String(ROSE_SIZE));
  box.setAttribute("height", String(ROSE_SIZE));
  box.setAttribute("aria-hidden", "true");

  const middle = ROSE_SIZE / 2;
  const most = middle - ROSE_HEAD - 3;
  const half = 360 / (rose.sectors.length * 2);

  const at = (turn, out) => {
    const radians = (turn * Math.PI) / 180;
    return [middle + out * Math.sin(radians), middle - out * Math.cos(radians)];
  };

  /* Every shape here gets the same white edge, because this lies over a raster that is red in some
   * places and green in others, and a shape with no outline reads on one and disappears on the
   * other. */
  const drawn = (d, fill, alpha) => {
    const path = document.createElementNS(where, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", fill);
    path.setAttribute("fill-opacity", String(alpha));
    path.setAttribute("stroke", "#ffffff");
    path.setAttribute("stroke-width", "0.7");
    path.setAttribute("stroke-opacity", "0.85");
    box.append(path);
  };

  const wedge = (degrees, length, fill, alpha) => {
    if (length <= 0.4) return;
    const [x1, y1] = at(degrees - half, length);
    const [x2, y2] = at(degrees + half, length);
    drawn(
      `M ${middle} ${middle} L ${x1.toFixed(2)} ${y1.toFixed(2)} ` +
      `A ${length.toFixed(2)} ${length.toFixed(2)} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`,
      fill, alpha);
  };

  const outTo = (percent) => Math.min(percent / ROSE_FULL, 1) * most;
  /* Every direction first, then the hard wind inside it, so one glyph says both "which way does it
   * push" and "which way does it push when it is pushing hard enough to matter". */
  for (const one of rose.sectors) wedge(pushes(one.degrees), outTo(one.percent), ROSE_ANY, 0.85);
  for (const one of rose.sectors) wedge(pushes(one.degrees), outTo(one.strong), ROSE_STRONG, 0.9);

  /* One head, on the arm that matters, and one is the point. Sixteen heads at this size is a
   * smudge, and what a head has to do here is answer "which end of this thing is the pointed end"
   * once. Answered for the longest arm, it is answered for all of them.
   *
   * Its colour is the arm's own rather than the hard-wind violet: a head in the darker colour reads
   * as another quantity, and it is not a quantity, it is a direction. */
  const best = rose.prevailing;
  if (best) {
    const turn = pushes(best.degrees);
    const along = outTo(best.percent);
    const [tipX, tipY] = at(turn, along + ROSE_HEAD);
    const [leftX, leftY] = at(turn - half * 1.2, along - 0.5);
    const [rightX, rightY] = at(turn + half * 1.2, along - 0.5);
    drawn(
      `M ${tipX.toFixed(2)} ${tipY.toFixed(2)} L ${leftX.toFixed(2)} ${leftY.toFixed(2)} ` +
      `L ${rightX.toFixed(2)} ${rightY.toFixed(2)} Z`,
      ROSE_ANY, 1);
  }

  const middleDot = document.createElementNS(where, "circle");
  middleDot.setAttribute("cx", String(middle));
  middleDot.setAttribute("cy", String(middle));
  middleDot.setAttribute("r", "2.5");
  middleDot.setAttribute("fill", ROSE_STRONG);
  middleDot.setAttribute("stroke", "#ffffff");
  middleDot.setAttribute("stroke-width", "1");
  box.append(middleDot);
  return box;
}

/* What one station has to say, in words and numbers. */
function aboutTheWind(rose) {
  const best = rose.prevailing;
  const ranked = rose.sectors.slice().sort((a, b) => b.percent - a.percent).slice(0, 3);
  const strongest = rose.sectors.slice().sort((a, b) => b.strong - a.strong)[0];

  return el("div", {class: "pin wind"},
    el("p", {class: "what"}, rose.name),
    el("p", {class: "facts"},
      best
        ? el("span", {}, "Most often pushes toward the ",
             el("strong", {}, compassOf(pushes(best.degrees))),
             `, ${best.percent.toFixed(1)}% of the time`)
        : "No wind on record here"),
    strongest && strongest.strong > 0
      ? el("p", {class: "facts"},
          "Hard wind, 15 mph and over, most often pushes toward the ",
          el("strong", {}, compassOf(pushes(strongest.degrees))),
          `, ${strongest.strong.toFixed(1)}% of the time`)
      : null,
    el("p", {class: "facts"},
      "Then ", ranked.slice(1).map((one, at) =>
        el("span", {}, at ? " and " : "", compassOf(pushes(one.degrees)),
           ` (${one.percent.toFixed(1)}%)`))),
    el("p", {class: "facts"}, `Calm ${rose.calm.toFixed(1)}% of the time`),
    el("p", {class: "hint"},
      "Every direction here is the way the wind ", el("strong", {}, "pushes"),
      ", which is the way a fire here would run."),
    el("p", {class: "meta"},
      `${(rose.observations || 0).toLocaleString()} hourly readings` +
      (rose.period ? `, ${rose.period.replace(/ America\/\w+$/, "")}` : "") +
      (rose.when === "april" ? ", April only" : ", every month")),
  );
}

/* The same sixteen points the archive is read into, so a page and a parser cannot come to disagree
 * about which way "southwest" is. */
const POINTS = [
  "north", "north-northeast", "northeast", "east-northeast",
  "east", "east-southeast", "southeast", "south-southeast",
  "south", "south-southwest", "southwest", "west-southwest",
  "west", "west-northwest", "northwest", "north-northwest",
];

function compassOf(degrees) {
  return POINTS[Math.round(degrees / 22.5) % 16];
}
