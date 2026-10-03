"use strict";
/* Water on the map: FEMA's zones under the properties, flash floods over a window of dates, and the
 * high-hazard dams.
 *
 * Asked for the week after the remnants of Hurricane Polo crossed New Mexico, by a household that
 * is mold sensitive: "show us areas that flooded with this recent event and areas that this could
 * happen in so we can avoid getting houses in those areas."
 *
 * Its own file rather than more of fire.js, which is long enough that its layering faults are hard
 * to find already. fire.js builds the page and calls into this for the controls, the legend and the
 * drawing; everything here reads `held` and the panes that file sets up.
 *
 * THREE THINGS THIS LAYER IS CAREFUL ABOUT.
 *
 * A warning says where the Weather Service expected flash flooding, drawn wide. It does not say
 * where water went, and nothing public does yet for this storm. So the word on this layer is
 * "warned", and never "flooded".
 *
 * A warning is a large polygon over the houses. That is the case the pointer rule exists for: it
 * takes no pointer at all, so a house inside a warning still opens, and a press on the map that no
 * house, report or dam took lists every warning at that spot (feat-010/AC-101).
 *
 * Every word in a storm report was written by a spotter or a member of the public. It goes into
 * the page through `el` as text and nowhere else, and the one link on a warning is built by the
 * server from three checked numbers rather than taken from the archive (feat-010/AC-99).
 */

const water = {
  /* What is drawn under the properties: the wildfire model, FEMA's flood zones, or neither. */
  under: "wildfire",
  zones: null,
  floods: {on: false, asked: false, asking: false, from: "", to: "", latest: null,
           warnings: [], reports: [], missing: [], stale: false, layer: null, renderer: null,
           drawn: new Map(), bubble: null},
  dams: {on: false, asked: false, asking: false, dams: [], poor: 0, missing: [], stale: false,
         layer: null, renderer: null, drawn: new Map()},
};

/* FEMA's map service draws its zones from about this zoom in, and sends an empty picture further
 * out. Asking for those would be hundreds of requests for nothing, so nothing is asked. */
const FEMA_ZOOM = 14;

/* FEMA's own colours for its zones, read from the service's renderer. Plain Zone X is not drawn by
 * FEMA at all, which the legend says, because an undrawn place could be either outside every
 * mapped zone or not mapped at all. */
const FEMA_LEGEND = [
  ["1% annual chance: the A and V zones", "fema-sfha"],
  ["floodway", "fema-floodway"],
  ["0.2% annual chance (the 500-year)", "fema-shaded"],
  ["Zone D: possible, never studied", "fema-d"],
];

/* Ink for warnings, deliberately unlike anything else here: underneath is a green-to-red or a
 * cyan-and-orange scale, and the pins are gold, blue and pink. */
const WARNING_INK = "#1e3a8a";
const EMERGENCY_INK = "#4c0519";

/* Dams by condition, worst darkest. No green anywhere: "nothing wrong found" is not a colour. */
const DAM_CONDITIONS = ["unsatisfactory", "poor", "fair", "satisfactory", "not rated"];

/* A report is a drop of water rather than a dot, because the properties are blue dots and a report
 * drawn as one was taken for a house. Its point sits at the centre of the round part, where the
 * dot's was, and the tip rises above it.
 *
 * It is a circle marker with its outline changed and nothing else, so it stays a path on the
 * layer's one renderer (feat-010/AC-101). That leans on two names inside Leaflet, `_updatePath`
 * and the renderer's `_setPath`, which hold for the 1.9.4 this page pins in its vendor manifest. */
const DROP_TIP = 2.2;
const Drop = L.CircleMarker.extend({
  _updateBounds() {
    const r = this._radius;
    const w = this._clickTolerance();
    this._pxBounds = L.bounds(this._point.subtract([r + w, DROP_TIP * r + w]),
                              this._point.add([r + w, r + w]));
  },
  _updatePath() {
    const {x, y} = this._point;
    const r = this._radius;
    const tip = y - DROP_TIP * r;
    this._renderer._setPath(this, this._empty() ? "M0 0" :
      `M${x} ${tip}C${x + 0.3 * r} ${y - 1.6 * r} ${x + r} ${y - 0.9 * r} ${x + r} ${y}` +
      `A${r} ${r} 0 0 1 ${x - r} ${y}` +
      `C${x - r} ${y - 0.9 * r} ${x - 0.3 * r} ${y - 1.6 * r} ${x} ${tip}Z`);
  },
});
const REPORT_FILL = "#38bdf8";

/* A dam is a triangle standing on its point's place, the same shape and size the marker it replaced
 * drew: sixteen pixels across and fourteen high at a radius of seven. The same two names inside
 * Leaflet as the drop. */
const DAM_WIDTH = 8 / 7;
const Triangle = L.CircleMarker.extend({
  _updateBounds() {
    const r = this._radius;
    const w = this._clickTolerance();
    this._pxBounds = L.bounds(this._point.subtract([DAM_WIDTH * r + w, r + w]),
                              this._point.add([DAM_WIDTH * r + w, r + w]));
  },
  _updatePath() {
    const {x, y} = this._point;
    const r = this._radius;
    this._renderer._setPath(this, this._empty() ? "M0 0" :
      `M${x} ${y - r}L${x + DAM_WIDTH * r} ${y + r}L${x - DAM_WIDTH * r} ${y + r}Z`);
  },
});

/* Darker the worse the condition, and an unrated dam white rather than reassuring. The legend's
 * swatches carry the same colours in app.css; change them together. */
const DAM_INK = {
  "unsatisfactory": "#3f0a0a",
  "poor": "#b91c1c",
  "fair": "#d97706",
  "satisfactory": "#6b7280",
  "not rated": "#ffffff",
};

/* ------------------------------------------------------------------ */
/* Controls                                                            */
/* ------------------------------------------------------------------ */

/** The choice of what is drawn under the properties, to sit beside the opacity slider. */
function underChoice() {
  return el("select", {
    id: "under",
    "aria-label": "What is drawn under the properties",
    onchange: (event) => chooseUnder(event.target.value),
  },
    el("option", {value: "wildfire"}, "wildfire hazard"),
    el("option", {value: "flood"}, "FEMA flood zones"),
    el("option", {value: "none"}, "neither"),
  );
}

function floodControls() {
  const box = el("input", {
    type: "checkbox", id: "floods",
    onchange: (event) => showFloods(event.target.checked),
  });
  const from = el("input", {
    type: "date", id: "floodfrom", "aria-label": "Flash floods from",
    onchange: (event) => { water.floods.from = event.target.value; askFloods(); },
  });
  const to = el("input", {
    type: "date", id: "floodto", "aria-label": "Flash floods to",
    onchange: (event) => { water.floods.to = event.target.value; askFloods(); },
  });
  const dams = el("input", {
    type: "checkbox", id: "dams",
    onchange: (event) => showDams(event.target.checked),
  });
  return [
    el("label", {for: "floods"}, box, " flash-flood warnings from "),
    from, el("span", {}, " to "), to,
    el("label", {for: "dams"}, dams, " high-hazard dams"),
  ];
}

/* ------------------------------------------------------------------ */
/* Under the properties                                                */
/* ------------------------------------------------------------------ */

function chooseUnder(which) {
  water.under = which;
  if (!held.map) return;
  if (held.hazard && held.map.hasLayer(held.hazard)) held.map.removeLayer(held.hazard);
  if (water.zones && held.map.hasLayer(water.zones)) held.map.removeLayer(water.zones);

  if (which === "wildfire" && held.hazard) {
    held.hazard.setOpacity(held.opacity);
    held.hazard.addTo(held.map);
  } else if (which === "flood") {
    if (!water.zones && (held.settings.hazards || {}).flood) {
      water.zones = arcgisLayer("flood", {opacity: held.opacity, minZoom: FEMA_ZOOM});
    }
    if (water.zones) {
      water.zones.setOpacity(held.opacity);
      water.zones.addTo(held.map);
    } else {
      say("No FEMA flood layer is configured, so there is nothing to draw under the properties.");
    }
  }
  for (const [key, id] of [["wildfire", "legend-wildfire"], ["flood", "legend-fema"]]) {
    const part = document.getElementById(id);
    if (part) part.hidden = which !== key;
  }
  zonesNote();
}

/** The layer the opacity slider moves, whichever one is drawn. */
function underneath() {
  return water.under === "flood" ? water.zones : water.under === "wildfire" ? held.hazard : null;
}

function zonesNote() {
  const where = document.getElementById("zonesnote");
  if (!where) return;
  const far = held.map && held.map.getZoom() < FEMA_ZOOM;
  where.replaceChildren(document.createTextNode(
    water.under === "flood" && far
      ? "Zoom in to see FEMA's zones: its map service draws them only a few miles across. "
      : ""));
}

/** FEMA's legend, hidden until FEMA's zones are what is drawn. */
function zonesLegend() {
  return el("div", {id: "legend-fema", hidden: true},
    el("h2", {}, "FEMA flood zones"),
    el("ul", {},
      FEMA_LEGEND.map(([said, kind]) =>
        el("li", {}, el("span", {class: `swatch ${kind}`, "aria-hidden": "true"}), said))),
    el("p", {class: "meta"},
      "FEMA draws nothing over plain Zone X, so an empty patch is either plain Zone X or a place " +
      "FEMA has never mapped at all, and the properties' own values say which. FEMA maps rivers, " +
      "not most arroyos, and assumes its dams and levees hold."),
  );
}

/* ------------------------------------------------------------------ */
/* Flash floods                                                        */
/* ------------------------------------------------------------------ */

async function showFloods(on) {
  water.floods.on = Boolean(on);
  if (water.floods.on && !water.floods.asked) {
    await askFloods();
    return;
  }
  drawFloods();
}

async function askFloods() {
  const state = water.floods;
  state.asking = true;
  floodCount();
  const query = new URLSearchParams();
  if (state.from) query.set("from", state.from);
  if (state.to) query.set("to", state.to);
  try {
    const found = await ask(
      `/api/flash-floods/${encodeURIComponent(held.name)}${String(query) ? "?" + query : ""}`);
    state.warnings = found.warnings || [];
    state.reports = found.reports || [];
    state.missing = found.missing || [];
    state.stale = Boolean(found.stale);
    state.latest = found.latest_emergency;
    state.from = found.from;
    state.to = found.to;
    state.asked = true;
    const from = document.getElementById("floodfrom");
    const to = document.getElementById("floodto");
    if (from) from.value = state.from;
    if (to) to.value = state.to;
    if (!state.on) {
      state.on = true;
      const box = document.getElementById("floods");
      if (box) box.checked = true;
    }
  } catch (error) {
    say(`The flash-flood record could not be read: ${error.message}`, "problem");
  } finally {
    state.asking = false;
  }
  drawFloods();
}

function floodCount() {
  const where = document.getElementById("floodcount");
  if (!where) return;
  const state = water.floods;
  let said = "";
  if (state.asking) {
    said = "reading the flash-flood record…";
  } else if (state.on && state.missing.length) {
    /* Never an empty map that reads as "no floods". */
    said = `No flash-flood record is held yet for ${state.missing.join(", ")}: ` +
      "the enrichment pass fetches it (Settings and tools, Attach public data).";
  } else if (state.on) {
    const emergencies = state.warnings.filter((one) => one.emergency).length;
    said = `${count(state.warnings.length, "flash-flood warning")}` +
      (emergencies ? `, ${count(emergencies, "emergency", "emergencies")}` : "") +
      ` and ${count(state.reports.length, "flood report")} from ${state.from} to ${state.to}` +
      (state.stale ? " (the record is more than a week old)" : "");
  }
  where.replaceChildren(document.createTextNode(said));
}

/* Everything in the window that touches the screen. Emergencies after ordinary warnings, so they
 * sit on top of the ones they usually lie inside, and the reports over both.
 *
 * A warning takes no pointer at all. It used to answer on its outline, which is a dashed line a
 * pixel and a half wide, and it was reported as hard to press. A press on the map that nothing else
 * took opens every warning at that spot instead (`warningsHere`), which a house inside a warning
 * never loses to, because the house takes the press first (feat-010/AC-101, feat-010/AC-60). */
function drawFloods() {
  const state = water.floods;
  if (!state.layer) return;
  if (!state.on) {
    forget(state);
    if (state.bubble) held.map.closePopup(state.bubble);
    held.map.removeLayer(state.layer);
    floodCount();
    return;
  }
  state.layer.addTo(held.map);
  const view = held.map.getBounds().pad(0.1);
  const shown = (one) => view.intersects(boxOf(one));
  const wanted = new Set([
    ...state.warnings.filter((one) => !one.emergency && shown(one)),
    ...state.warnings.filter((one) => one.emergency && shown(one)),
    ...state.reports.filter((one) => view.contains([one.latitude, one.longitude])),
  ]);
  if (keepInView(state, wanted, drawFlood)) {
    /* What was added went on top of what was kept, so the order is put back: emergencies over
     * ordinary warnings, then the reports over everything. */
    for (const [record, layers] of state.drawn) {
      if (record.emergency) for (const one of layers) one.bringToFront();
    }
    for (const [record, layers] of state.drawn) {
      if (!record.polygons) for (const one of layers) one.bringToFront();
    }
  }
  floodCount();
}

/* The shapes for one record: a warning's polygon, or a report's drop with its white casing. */
function drawFlood(record) {
  const renderer = water.floods.renderer;
  if (record.polygons) {
    const shape = L.polygon(record.polygons, {
      pane: "floods", renderer, interactive: false,
      className: record.emergency ? "ff-warning ff-emergency" : "ff-warning",
      color: record.emergency ? EMERGENCY_INK : WARNING_INK,
      weight: record.emergency ? 3.5 : 1.5,
      opacity: 0.9,
      dashArray: record.emergency ? null : "5 4",
      fillColor: record.emergency ? EMERGENCY_INK : WARNING_INK,
      fillOpacity: record.emergency ? 0.12 : 0.04,
    });
    return [shape];
  }
  const at = [record.latitude, record.longitude];
  const casing = new Drop(at, {
    pane: "floods", renderer, interactive: false,
    radius: 5.5, color: "#ffffff", weight: 5, opacity: 0.9, fill: false,
  });
  const mark = new Drop(at, {
    pane: "floods", renderer, className: "ff-report",
    radius: 5.5, color: WARNING_INK, weight: 1.5, fillColor: REPORT_FILL, fillOpacity: 0.95,
  });
  mark.bindPopup(() => reportPopup(record), {maxWidth: 320});
  return [casing, mark];
}

/* A warning's extent, worked out once rather than on every move. */
const BOXES = new WeakMap();
function boxOf(one) {
  if (!BOXES.has(one)) BOXES.set(one, L.latLngBounds(one.polygons.flat(2)));
  return BOXES.get(one);
}

/* How close to a warning's edge, in pixels, a press still counts as on it. */
const NEAR_AN_EDGE = 6;

/** A press on the map that no property, report or dam took: every drawn warning at that spot.
 *
 * The statewide view is warnings over warnings, so what a press here is asking is "what was this
 * spot warned for", and the answer is a list. It is one bubble belonging to the map rather than to
 * a shape, so no redraw can take it away. */
function warningsHere(event) {
  const state = water.floods;
  if (!state.on || !state.layer) return;
  const here = [];
  for (const [record, layers] of state.drawn) {
    if (record.polygons && covers(layers[0], event.layerPoint)) here.push(record);
  }
  if (!here.length) return;
  here.sort((a, b) =>
    Number(b.emergency) - Number(a.emergency) || String(b.issued).localeCompare(String(a.issued)));
  state.bubble = L.popup({maxWidth: 340, maxHeight: 360})
    .setLatLng(event.latlng)
    .setContent(warningsPopup(here))
    .openOn(held.map);
}

/* Whether a drawn warning covers a point, or passes within a few pixels of it. Every ring of every
 * part is counted, so a hole in a warning is not inside it. */
function covers(shape, point) {
  let inside = false;
  for (const ring of ringsOf(shape.getLatLngs())) {
    const drawn = ring.map((one) => held.map.latLngToLayerPoint(one));
    for (let i = 0, j = drawn.length - 1; i < drawn.length; j = i++) {
      const a = drawn[i];
      const b = drawn[j];
      if (L.LineUtil.pointToSegmentDistance(point, a, b) <= NEAR_AN_EDGE) return true;
      if ((a.y > point.y) !== (b.y > point.y)
          && point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x) inside = !inside;
    }
  }
  return inside;
}

function ringsOf(latlngs) {
  return latlngs.length && latlngs[0] instanceof L.LatLng ? [latlngs] : latlngs.flatMap(ringsOf);
}

function warningsPopup(list) {
  const emergencies = list.filter((one) => one.emergency).length;
  return el("div", {class: "ffpopup"},
    list.length > 1
      ? el("p", {class: "meta"},
        `${count(list.length, "flash-flood warning")} issued for this spot` +
        (emergencies
          ? `, ${emergencies} of them ${emergencies === 1 ? "an emergency" : "emergencies"}`
          : "") + ".")
      : null,
    list.map(warningEntry),
    el("p", {class: "meta"},
      "Where flash flooding was expected, drawn wide. A warning does not say where water went."),
  );
}

function warningEntry(one) {
  const threat = one.damage ? `damage threat: ${one.damage}` : null;
  return el("div", {class: "ffwarning"},
    el("strong", {}, one.emergency ? "Flash Flood Emergency" : "Flash-flood warning"),
    el("p", {class: "meta"},
      `Issued ${one.date}${one.time ? " at " + one.time : ""} (local standard time) by the ` +
      `${one.office} Weather Service office, ` +
      `number ${one.event}.`),
    threat ? el("p", {}, threat) : null,
    el("p", {class: "meta"},
      link(one.link, "Read the warning itself at Iowa State"), " (leaves this page). " +
      "A cause such as a dam failure is stated there."),
  );
}

function reportPopup(report) {
  return el("div", {class: "ffpopup"},
    el("strong", {}, `${report.kind} reported`),
    el("p", {class: "meta"},
      `${report.date}, ${report.place || "no place given"}` +
      (report.county ? `, ${report.county} County` : "") +
      (report.source ? `. Filed by: ${report.source}.` : ".")),
    /* Written by a spotter or a member of the public, and shown as exactly that: text. */
    report.remark ? el("p", {}, report.remark) : null,
    el("p", {class: "meta"}, "Placed to about a kilometre, usually from a named town or road."),
  );
}

/* ------------------------------------------------------------------ */
/* Dams                                                                */
/* ------------------------------------------------------------------ */

async function showDams(on) {
  const state = water.dams;
  state.on = Boolean(on);
  if (state.on && !state.asked) {
    state.asking = true;
    damCount();
    try {
      const found = await ask(`/api/dams/${encodeURIComponent(held.name)}`);
      state.dams = found.dams || [];
      state.missing = found.missing || [];
      state.stale = Boolean(found.stale);
      state.poor = Number(found.poor) || 0;
      state.asked = true;
    } catch (error) {
      say(`The dam inventory could not be read: ${error.message}`, "problem");
      state.on = false;
      const box = document.getElementById("dams");
      if (box) box.checked = false;
    } finally {
      state.asking = false;
    }
  }
  drawDams();
}

function damCount() {
  const where = document.getElementById("damcount");
  if (!where) return;
  const state = water.dams;
  let said = "";
  if (state.asking) said = "reading the dam inventory…";
  else if (state.on && state.missing.length) {
    said = `No dam inventory is held yet for ${state.missing.join(", ")}: ` +
      "the enrichment pass fetches it.";
  } else if (state.on) {
    said = `${count(state.dams.length, "high-hazard dam")}, ` +
      `${state.poor} rated poor or unsatisfactory`;
  }
  where.replaceChildren(document.createTextNode(said));
}

/* The dams on screen, as triangles on the layer's one renderer.
 *
 * They were markers: an element each, with two drop-shadow filters and two clip paths, every one of
 * them built again after every move and moved separately through every frame of a zoom. Zoomed out
 * over the region that is 3,274 of them, and it was measured as frames of a third of a second and
 * more, against a thirtieth with the dams off. As paths on one renderer a zoom scales one drawing,
 * and a move only adds what came into view. */
function drawDams() {
  const state = water.dams;
  if (!state.layer) return;
  if (!state.on) {
    forget(state);
    held.map.removeLayer(state.layer);
    damCount();
    return;
  }
  state.layer.addTo(held.map);
  const view = held.map.getBounds().pad(0.1);
  keepInView(state,
    new Set(state.dams.filter((dam) => view.contains([dam.latitude, dam.longitude]))), drawDam);
  damCount();
}

function drawDam(dam) {
  const condition = DAM_CONDITIONS.includes(dam.condition) ? dam.condition : "not rated";
  const rated = condition !== "not rated";
  const mark = new Triangle([dam.latitude, dam.longitude], {
    pane: "dams", renderer: water.dams.renderer, className: "dam-mark",
    radius: 7, color: rated ? "#ffffff" : "#111111", weight: rated ? 2 : 1.5, opacity: 1,
    fillColor: DAM_INK[condition], fillOpacity: 1,
  });
  reachable(mark, `${dam.name}, condition ${condition}`);
  mark.bindPopup(() => damPopup(dam), {maxWidth: 320});
  return [mark];
}

/* A path is not a marker, so the keyboard reaches it only by being told to. The name goes in as an
 * attribute's value and nowhere else, so nothing a source wrote is ever read as markup. */
function reachable(mark, name) {
  mark.on("add", () => {
    const path = mark.getElement();
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "button");
    path.setAttribute("aria-label", name);
    L.DomEvent.on(path, "keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      L.DomEvent.preventDefault(event);
      mark.openPopup();
    });
  });
}

function damPopup(dam) {
  const rows = [];
  const add = (said) => { if (said) rows.push(el("li", {}, said)); };
  add(dam.built ? `Built ${dam.built}` : null);
  add(`Condition: ${dam.condition}` + (dam.assessed ? `, assessed ${dam.assessed}` : ""));
  add(dam.plan ? dam.plan.charAt(0).toUpperCase() + dam.plan.slice(1) : null);
  add(dam.purpose ? `Built for ${dam.purpose}` : null);
  add(dam.owner ? `Owner: ${dam.owner}` : null);
  return el("div", {class: "dampopup"},
    el("strong", {}, dam.name),
    el("p", {class: "meta"}, `High hazard. National Inventory of Dams ${dam.id}.`),
    el("ul", {}, rows),
    el("p", {class: "meta"},
      "Near is all this can say. The inventory places a dam as one point and does not say which " +
      "way it drains."),
  );
}

/* ------------------------------------------------------------------ */
/* Shared with fire.js                                                 */
/* ------------------------------------------------------------------ */

/** The panes and renderers, made once when the map is built. */
function waterPanes(map) {
  /* Warnings over the data centres and under the wind. The pane takes no pointer; the stylesheet
   * gives it back to a report's mark and nothing else. A warning is opened by a press on the map
   * (`warningsHere`), so a house inside one keeps its own press (feat-010/AC-101). */
  map.createPane("floods");
  map.getPane("floods").style.zIndex = "446";
  map.getPane("floods").style.pointerEvents = "none";
  /* ONE renderer for the whole layer. A renderer per shape is how the data centre layer once put
   * eleven thousand svg elements in the page. */
  water.floods.renderer = L.svg({pane: "floods"});
  water.floods.layer = L.layerGroup();

  /* The dams the same way, on a renderer of their own so they sit over the warnings. A triangle
   * takes the pointer on itself (Leaflet's own rule for an interactive path) and nowhere else. */
  map.createPane("dams");
  map.getPane("dams").style.zIndex = "447";
  map.getPane("dams").style.pointerEvents = "none";
  water.dams.renderer = L.svg({pane: "dams"});
  water.dams.layer = L.layerGroup();

  map.on("zoomend", zonesNote);
  map.on("click", warningsHere);
  /* The keyboard's way to the same bubble: Enter on the map itself, which the arrow keys already
   * move, asks about the middle of what is on screen (AC-17). Only on the map, so Enter on a
   * focused dam or a link in a bubble keeps meaning what it meant. */
  L.DomEvent.on(map.getContainer(), "keydown", (event) => {
    if (event.key !== "Enter" || event.target !== map.getContainer()) return;
    const middle = map.getCenter();
    warningsHere({latlng: middle, layerPoint: map.latLngToLayerPoint(middle)});
  });
}

/** Bring a layer's drawing into line with the view: add what came into it, take away what left
 * it, and leave alone what is still there. Says whether anything was added.
 *
 * Both water layers used to be emptied and built again at the end of every move, which zoomed out
 * over the region was three thousand dams built from nothing after every pan. It also closed
 * bubbles: opening one near the edge pans the map to fit it, the pan redrew the layer, and the
 * shape that owned the bubble went with everything else. So a shape whose bubble is open is never
 * taken away here; it goes on a later move, once the bubble has closed (feat-010/AC-105). */
function keepInView(state, wanted, draw) {
  for (const [record, layers] of state.drawn) {
    if (wanted.has(record) || layers.some((one) => one.isPopupOpen())) continue;
    for (const one of layers) state.layer.removeLayer(one);
    state.drawn.delete(record);
  }
  let added = false;
  for (const record of wanted) {
    if (state.drawn.has(record)) continue;
    const layers = draw(record);
    for (const one of layers) state.layer.addLayer(one);
    state.drawn.set(record, layers);
    added = true;
  }
  return added;
}

/** Everything off a layer, for when it is turned off. */
function forget(state) {
  state.layer.clearLayers();
  state.drawn.clear();
}

/** Called by fire.js whenever the map has moved. */
function waterMoved() {
  if (water.floods.on) drawFloods();
  if (water.dams.on) drawDams();
  zonesNote();
}

/** The legend's flash-flood and dam sections. */
function waterLegend() {
  return [
    el("h2", {}, "Flash floods"),
    el("ul", {},
      el("li", {}, el("span", {class: "swatch ff-warning", "aria-hidden": "true"}),
         "a flash-flood warning"),
      el("li", {}, el("span", {class: "swatch ff-emergency", "aria-hidden": "true"}),
         "a Flash Flood Emergency"),
      el("li", {}, el("span", {class: "swatch ff-report", "aria-hidden": "true"}),
         "a flood report"),
    ),
    el("p", {class: "meta"},
      "Where the Weather Service warned, drawn wide, and where somebody reported flooding. A " +
      "warning does not say where water went. Press anywhere inside one for every warning issued " +
      "for that spot, or press Enter on the map for the middle of it. The dates open on the " +
      "fortnight ending with the latest Flash Flood Emergency on record."),
    el("h2", {}, "High-hazard dams"),
    el("ul", {},
      DAM_CONDITIONS.map((condition) =>
        el("li", {},
          el("span", {class: `swatch dam dam-${condition.replace(" ", "-")}`,
                      "aria-hidden": "true"}),
          condition))),
    el("p", {class: "meta"},
      "Dams whose failure would probably cost a life, by the condition last assessed. Near is all " +
      "this can say: nothing public says which way a local dam drains."),
  ];
}

/** What the page says about where these come from, under the map. */
function waterCredits() {
  return el("p", {class: "meta"},
    "FEMA's flood zones are fetched by this machine from FEMA's map service for the part of the " +
    "map on screen, and kept, like the fire layer. Turning on the flash floods or the dams asks " +
    "nobody: they are read from records the enrichment pass already fetched, a state at a time, " +
    "which tells those hosts only which states. Flash-flood warnings and storm " +
    "reports are the National Weather Service's, as archived by the Iowa Environmental Mesonet at " +
    "Iowa State University; the dams are the U.S. Army Corps of Engineers' National Inventory of " +
    "Dams.");
}
