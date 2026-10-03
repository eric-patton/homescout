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
 * answers on its outline and never on its fill, exactly as a data centre's outline does, so a
 * house inside a warning still opens (feat-010/AC-101).
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
           warnings: [], reports: [], missing: [], stale: false, layer: null, renderer: null},
  dams: {on: false, asked: false, asking: false, dams: [], poor: 0, missing: [], stale: false,
         layer: null},
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

/* Everything in the window that touches the screen, drawn again. Emergencies last, so they sit on
 * top of the ordinary warnings they usually lie inside. */
function drawFloods() {
  const state = water.floods;
  if (!state.layer) return;
  state.layer.clearLayers();
  if (!state.on) {
    held.map.removeLayer(state.layer);
    floodCount();
    return;
  }
  state.layer.addTo(held.map);
  const bounds = held.map.getBounds();

  const ordered = [...state.warnings].sort((a, b) => Number(a.emergency) - Number(b.emergency));
  for (const one of ordered) {
    const shape = L.polygon(one.polygons, {
      pane: "floods", renderer: state.renderer,
      className: one.emergency ? "ff-warning ff-emergency" : "ff-warning",
      color: one.emergency ? EMERGENCY_INK : WARNING_INK,
      weight: one.emergency ? 3.5 : 1.5,
      opacity: 0.9,
      dashArray: one.emergency ? null : "5 4",
      fillColor: one.emergency ? EMERGENCY_INK : WARNING_INK,
      fillOpacity: one.emergency ? 0.12 : 0.04,
    });
    if (!bounds.intersects(shape.getBounds())) continue;
    shape.bindPopup(() => warningPopup(one), {maxWidth: 320});
    state.layer.addLayer(shape);
  }
  for (const report of state.reports) {
    if (!bounds.contains([report.latitude, report.longitude])) continue;
    state.layer.addLayer(new Drop([report.latitude, report.longitude], {
      pane: "floods", renderer: state.renderer, interactive: false,
      radius: 5.5, color: "#ffffff", weight: 5, opacity: 0.9, fill: false,
    }));
    const mark = new Drop([report.latitude, report.longitude], {
      pane: "floods", renderer: state.renderer, className: "ff-report",
      radius: 5.5, color: WARNING_INK, weight: 1.5, fillColor: REPORT_FILL, fillOpacity: 0.95,
    });
    mark.bindPopup(() => reportPopup(report), {maxWidth: 320});
    state.layer.addLayer(mark);
  }
  floodCount();
}

function warningPopup(one) {
  const threat = one.damage ? `damage threat: ${one.damage}` : null;
  return el("div", {class: "ffpopup"},
    el("strong", {}, one.emergency ? "Flash Flood Emergency" : "Flash-flood warning"),
    el("p", {class: "meta"},
      `Issued ${one.date}${one.time ? " at " + one.time : ""} (local standard time) by the ` +
      `${one.office} Weather Service office, ` +
      `number ${one.event}.`),
    threat ? el("p", {}, threat) : null,
    el("p", {class: "meta"},
      "Where flash flooding was expected, drawn wide. It does not say where water went."),
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

function drawDams() {
  const state = water.dams;
  if (!state.layer) return;
  state.layer.clearLayers();
  if (!state.on) {
    held.map.removeLayer(state.layer);
    damCount();
    return;
  }
  state.layer.addTo(held.map);
  const bounds = held.map.getBounds();
  for (const dam of state.dams) {
    if (!bounds.contains([dam.latitude, dam.longitude])) continue;
    const condition = DAM_CONDITIONS.includes(dam.condition) ? dam.condition : "not rated";
    /* The icon is nothing but class names: its look is in the stylesheet and it holds no text,
     * so nothing any source wrote can reach the page through it. */
    const mark = L.marker([dam.latitude, dam.longitude], {
      pane: "dams",
      icon: L.divIcon({className: `dam dam-${condition.replace(" ", "-")}`, iconSize: [16, 14]}),
      title: `${dam.name}, condition ${condition}`,
      keyboard: true,
    });
    mark.bindPopup(() => damPopup(dam), {maxWidth: 320});
    state.layer.addLayer(mark);
  }
  damCount();
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
   * gives it back to a warning's outline and a report's mark and nothing else, which is the answer
   * AC-93 found for the data centres and AC-101 asks of this layer. */
  map.createPane("floods");
  map.getPane("floods").style.zIndex = "446";
  map.getPane("floods").style.pointerEvents = "none";
  /* ONE renderer for the whole layer. A renderer per shape is how the data centre layer once put
   * eleven thousand svg elements in the page. */
  water.floods.renderer = L.svg({pane: "floods"});
  water.floods.layer = L.layerGroup();

  map.createPane("dams");
  map.getPane("dams").style.zIndex = "447";
  map.getPane("dams").style.pointerEvents = "none";
  water.dams.layer = L.layerGroup();

  map.on("zoomend", zonesNote);
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
      "warning does not say where water went. The dates open on the fortnight ending with the " +
      "latest Flash Flood Emergency on record."),
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
