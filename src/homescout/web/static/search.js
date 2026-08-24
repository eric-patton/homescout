"use strict";
/* The map and search builder.
 *
 * Two things about it are decisions rather than mechanics.
 *
 * THE FILE IS NEVER WRITTEN HERE. Every change goes through the core's own edit operation, and the
 * round-tripping document layer that saved searches already have does the writing, keeping comments
 * and ordering exactly as somebody typed them. The consequence is stated rather than hidden: a part
 * of a definition this interface cannot edit is shown read-only, not rewritten around.
 *
 * THERE IS NO MAP BACKGROUND BY DEFAULT. Asking a tile server for tiles tells it which part of the
 * world is being looked at, and this product's own privacy statement lists four kinds of outbound
 * traffic, none of which is that. Set HOMESCOUT_MAP_TILES to turn one on, having read what it
 * means.
 */

const held = {name: "", search: null, settings: null, map: null, drawn: null};

whenReady(() => {
  nav("/");
  held.name = pathParts()[1] || "";
  load().catch(fail);
});

async function load() {
  const [search, settings] = await Promise.all([
    ask(`/api/searches/${encodeURIComponent(held.name)}`),
    ask("/api/settings"),
  ]);
  held.search = search.search;
  held.settings = settings;
  draw();
}

function draw() {
  const search = held.search;
  shell(`${held.name}`,
    el("h1", {}, held.name),
    el("p", {class: "lede"},
      "This is the same file you can edit by hand. Anything changed here is written through the " +
      "core, so comments and ordering survive."),
    problems(search),
    el("div", {class: "detail"},
      el("div", {}, mapPanel(), areaList()),
      el("div", {}, settingsPanel(), notesPanel()),
    ),
  );
  startMap();
}

function problems(search) {
  const found = search.problems || [];
  if (!found.length) return null;
  return el("div", {},
    found.map((problem) =>
      el("p", {class: "notice notice-" + (problem.severity === "problem" ? "problem" : "plain")},
        `${problem.location}: ${problem.message}`)));
}

function mapPanel() {
  return el("section", {},
    el("h2", {}, "Areas"),
    el("div", {id: "map", role: "application",
               "aria-label": "Map for drawing the areas this search covers"}),
    el("div", {class: "controls"},
      el("label", {for: "drawkind"}, "New shapes are "),
      el("select", {id: "drawkind", "aria-label": "Whether a new shape is included or excluded"},
        el("option", {value: "include"}, "areas to search"),
        el("option", {value: "exclude"}, "areas to leave out")),
    ),
    el("p", {class: "meta", id: "maphint"}),
  );
}

/* Writing a drawn shape back into the saved search.
 *
 * The file is never written here. This hands the core the whole `areas` and `exclude_areas` lists,
 * and the round-tripping document layer that saved searches already have does the writing, keeping
 * comments and ordering exactly as somebody typed them. That is AC-3, and it is the reason this
 * interface can only change what the core's edit operation can change.
 */
async function saveAreas() {
  const areas = [];
  const exclusions = [];

  /* The named areas: a town or a county, with whatever the table's name and in-or-out fields now
   * say. These have no geometry to draw and must survive a save that is mostly about shapes. */
  for (const area of held.named || []) {
    (area.excluded ? exclusions : areas).push(namedArea(area));
  }

  if (held.drawn) {
    held.drawn.eachLayer((layer) => {
      if (!layer.toGeoJSON) return;
      const entry = {type: "polygon", geometry: layer.toGeoJSON().geometry};
      if (layer.__name) entry.name = layer.__name;
      (layer.__excluded ? exclusions : areas).push(entry);
    });
  }

  if (!areas.length) {
    say("A saved search needs at least one area to look in, so this was not saved.", "problem");
    return;
  }

  try {
    await send(`/api/searches/${encodeURIComponent(held.name)}`,
      {set: {areas: areas, exclude_areas: exclusions}});
    say(
      `Saved ${count(areas.length, "area")}` +
      (exclusions.length ? ` and ${count(exclusions.length, "exclusion")}.` : "."),
      "good");
    await load();
  } catch (error) {
    fail(error);
  }
}

function namedArea(area) {
  const entry = {type: area.kind, value: area.value};
  if (area.name) entry.name = area.name;
  return entry;
}

/* The areas, editable.
 *
 * A drawn shape's name and its included-or-excluded sense are edited here rather than by deleting
 * the shape and drawing it again, which is what this table used to require. The two kinds of row
 * differ in exactly one way: a named area (a city, a county) keeps its value in the file, so its
 * row edits a copy of the file's entry; a drawn one has no value to keep, so its row edits the map
 * layer that holds its geometry. Both are read back by `saveAreas`.
 */
function areaList() {
  const search = held.search;
  const named = [
    ...(search.areas || []).filter((a) => !a.geometry).map((a) => ({...a, excluded: false})),
    ...(search.exclusions || []).filter((a) => !a.geometry).map((a) => ({...a, excluded: true})),
  ];
  held.named = named;

  const shapes = [];
  if (held.drawn) held.drawn.eachLayer((layer) => { if (layer.toGeoJSON) shapes.push(layer); });

  if (!named.length && !shapes.length) {
    return el("section", {id: "arealist"},
      el("p", {class: "unknown"},
        "this search names no areas yet. Add a town below, or draw one on the map."));
  }

  return el("section", {id: "arealist"},
    el("table", {class: "plain"},
      el("thead", {}, el("tr", {},
        el("th", {scope: "col"}, "Kind"),
        el("th", {scope: "col"}, "Which"),
        el("th", {scope: "col"}, "Called"),
        el("th", {scope: "col"}, "In or out"),
        el("th", {scope: "col"}, "Remove"),
      )),
      el("tbody", {},
        named.map((area, index) => areaRow(
          area.kind,
          el("input", {
            type: "text", value: area.value || "",
            "aria-label": `Which place row ${index + 1} names`,
            onchange: (e) => { area.value = e.target.value.trim(); },
          }),
          area,
          () => { named.splice(named.indexOf(area), 1); redrawAreaList(); },
          index + 1)),
        shapes.map((layer, index) => areaRow(
          "polygon",
          el("span", {}, "a drawn shape"),
          layer,
          () => { held.drawn.removeLayer(layer); redrawAreaList(); },
          named.length + index + 1,
          layer)),
      ),
    ),
    el("p", {class: "meta"},
      "A name is yours, for reading the file and the exported sheet. Nothing is written until you " +
      "save."),
    addPlace(),
    el("button", {type: "button", onclick: saveAreas}, "Save the areas"),
  );
}

/* Adding a town, a county, a postal code. The other half of "draw one": most searches start with a
 * place that has a name, and typing one should not mean opening the file. */
function addPlace() {
  const kinds = (held.settings.area_kinds || ["city", "county", "zip", "state"])
    .filter((k) => k !== "polygon" && k !== "radius");
  const kind = el("select", {id: "newkind", "aria-label": "What kind of place to add"},
    kinds.map((k) => el("option", {value: k}, k)));
  const value_ = el("input", {
    type: "text", id: "newplace", placeholder: "Portales, NM",
    "aria-label": "The place to add",
  });

  return el("div", {class: "controls"},
    el("label", {for: "newkind"}, "Add a place "), kind,
    el("label", {for: "newplace"}, " called "), value_,
    el("button", {
      type: "button",
      onclick: () => {
        const given = value_.value.trim();
        if (!given) { say("Type a place first.", "problem"); return; }
        held.named.push({kind: kind.value, value: given, name: "", excluded: false});
        redrawAreaList();
        say(`Added ${given}. Save the areas to write it into the file.`, "good");
      },
    }, "Add"),
  );
}

/* One row. `holder` is the thing the row edits: a copy of a file entry, or a map layer. Both carry
 * a name and an excluded flag, which is the whole of what this row changes. */
function areaRow(kind, which, holder, remove, position, layer) {
  const isLayer = !!layer;
  const naming = el("input", {
    type: "text",
    value: (isLayer ? holder.__name : holder.name) || "",
    placeholder: "east side, the flats…",
    "aria-label": `What to call area ${position}`,
    onchange: (e) => {
      const given = e.target.value.trim();
      if (isLayer) holder.__name = given; else holder.name = given;
    },
  });
  const sense = el("select", {
    "aria-label": `Whether area ${position} is searched or left out`,
    onchange: (e) => {
      const out = e.target.value === "excluded";
      if (isLayer) {
        holder.__excluded = out;
        if (holder.setStyle) {
          holder.setStyle({color: out ? "#a02020" : "#14508c", dashArray: out ? "5,5" : null});
        }
      } else {
        holder.excluded = out;
      }
    },
  },
    el("option", {value: "included"}, "searched"),
    el("option", {value: "excluded"}, "left out"));
  sense.value = (isLayer ? holder.__excluded : holder.excluded) ? "excluded" : "included";

  return el("tr", {},
    el("td", {}, value(kind)),
    el("td", {}, which),
    el("td", {}, naming),
    el("td", {}, sense),
    el("td", {}, el("button", {
      type: "button",
      onclick: remove,
      "aria-label": `Remove area ${position}`,
    }, "Remove")),
  );
}

function redrawAreaList() {
  const where = document.getElementById("arealist");
  if (where) where.replaceWith(areaList());
}

/* Everything about a search that is not geometry.
 *
 * Nothing here writes YAML. Each field sends one dotted path to the core's own edit operation, and
 * the round-tripping document layer does the writing, so the file keeps its comments and its
 * ordering. That is also why the set of fields here is exactly the set that operation can change:
 * what it cannot change is shown as it was found rather than rewritten around.
 */
function settingsPanel() {
  const search = held.search;
  const filters = search.filters || {};

  return el("section", {},
    el("h2", {}, "What it looks for"),

    text("description", "Description", search.description,
      (v) => save({description: v})),

    text("sources", "Sources, comma separated", (search.sources || []).join(", "),
      (v) => save({sources: v.split(",").map((s) => s.trim()).filter(Boolean)}),
      `known: ${(held.settings.sources || []).join(", ") || "none registered"}`),

    el("h3", {}, "Filters"),
    el("p", {class: "meta"},
      "Leave one empty to remove it. A property whose value is unknown is never removed by a " +
      "filter, so an empty field and a filter that cannot be answered are different things."),
    range_("price", "Price", filters.price),
    range_("beds", "Beds", filters.beds),
    range_("baths", "Baths", filters.baths),
    range_("sqft", "Square feet", filters.sqft),
    range_("lot_acres", "Acres", filters.lot_acres),
    range_("year_built", "Year built", filters.year_built),
    text("listing_type", "Listing status, comma separated",
      (filters.listing_type || []).join(", "),
      (v) => save({"filters.listing_type": listOrNothing(v)}),
      "for_sale, pending, contingent, sold, off_market"),
    text("property_type", "Property type, comma separated",
      (filters.property_type || []).join(", "),
      (v) => save({"filters.property_type": listOrNothing(v)})),

    el("h3", {}, "Reading descriptions with a model"),
    el("p", {class: "meta"},
      "Off unless this search asks for it. The six fields recovered from prose are filled by " +
      "patterns that need nothing; this adds a model for the ones they could not settle."),
    el("div", {class: "field"},
      el("label", {for: "usemodel"},
        el("input", {
          type: "checkbox",
          id: "usemodel",
          checked: search.model_extraction ? true : null,
          onchange: (event) => save({"extract.model": event.target.checked}),
        }),
        " ask a model about this search's descriptions")),
    modelReadiness(),

    el("h3", {}, "Criteria"),
    criteriaPanel(),
  );
}

function modelReadiness() {
  const model = (held.settings || {}).model || {};
  if (model.configured) {
    return el("p", {class: "notice notice-good"},
      `A model is ready: ${model.model} at ${model.base_url}.`);
  }
  return el("p", {class: "notice"},
    "No model is configured yet, so turning this on does nothing until one is. ",
    link("/settings", "Set one up"),
    ". The rest of extraction works without it.");
}

function criteriaPanel() {
  const rules = held.search.rules || [];
  const box = el("textarea", {
    rows: String(Math.max(4, rules.length * 3 + 2)),
    id: "rules",
    "aria-label": "Criteria, one per line, as id | severity | expression",
    value: rules.map((r) => `${r.id} | ${r.severity} | ${r.when}`).join("\n"),
  });
  return el("div", {},
    el("p", {class: "meta"},
      "One per line: an id, what it does (drop, flag, boost or demote), and the condition. " +
      "A condition is checked before it is saved, and a bad one is refused with its position."),
    el("div", {class: "field"}, box),
    el("button", {
      type: "button",
      onclick: () => save({rules: parseRules(box.value)}),
    }, "Save the criteria"),
    el("p", {class: "meta"},
      "Fields a condition may name: " +
      ((held.settings || {}).rule_fields || []).join(", ")),
  );
}

function parseRules(text) {
  const made = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const parts = trimmed.split("|").map((p) => p.trim());
    if (parts.length < 3) {
      throw new Error(`"${trimmed}" is not id | severity | condition`);
    }
    made.push({id: parts[0], severity: parts[1], when: parts.slice(2).join("|").trim()});
  }
  return made;
}

function listOrNothing(raw) {
  const made = raw.split(",").map((s) => s.trim()).filter(Boolean);
  return made.length ? made : null;
}

/* One labelled field that saves when you leave it or press Enter. */
function text(id, label, current, onSave, hint) {
  const input = el("input", {
    type: "text",
    id: id,
    value: current === null || current === undefined ? "" : String(current),
    "aria-label": label,
  });
  const commit = () => {
    const wanted = input.value.trim();
    if (wanted === (current === null || current === undefined ? "" : String(current))) return;
    try { onSave(wanted); } catch (error) { fail(error); }
  };
  input.addEventListener("keydown", (event) => { if (event.key === "Enter") commit(); });
  input.addEventListener("blur", commit);
  return el("div", {class: "field"},
    el("label", {for: id}, label),
    input,
    hint ? el("span", {class: "meta"}, hint) : null);
}

/* A minimum and a maximum, which is the shape every numeric filter takes. */
function range_(name, label, current) {
  const held_ = current || {};
  const low = el("input", {
    type: "number", id: `${name}-min`, value: held_.min ?? "",
    "aria-label": `${label}, minimum`, placeholder: "no minimum",
  });
  const high = el("input", {
    type: "number", id: `${name}-max`, value: held_.max ?? "",
    "aria-label": `${label}, maximum`, placeholder: "no maximum",
  });
  const commit = () => {
    const wanted = {};
    if (low.value.trim() !== "") wanted.min = Number(low.value);
    if (high.value.trim() !== "") wanted.max = Number(high.value);
    save({[`filters.${name}`]: Object.keys(wanted).length ? wanted : null});
  };
  for (const box of [low, high]) {
    box.addEventListener("keydown", (event) => { if (event.key === "Enter") commit(); });
    box.addEventListener("blur", commit);
  }
  return el("div", {class: "field"},
    el("label", {for: `${name}-min`}, label),
    el("span", {}, low, " to ", high));
}

async function save(changes) {
  try {
    const answered = await send(`/api/searches/${encodeURIComponent(held.name)}`, {set: changes});
    held.search = answered.search;
    say("Saved. The file keeps its comments and everything you did not change.", "good");
    draw();
  } catch (error) {
    fail(error);
  }
}

function notesPanel() {
  const box = el("textarea", {rows: "4", id: "note",
                              "aria-label": "A note about this town or region"});
  const kind = el("select", {id: "notekind", "aria-label": "What kind of place"},
    (held.settings.area_kinds || []).map((k) => el("option", {value: k}, k)));
  const place = el("input", {type: "text", id: "noteplace", "aria-label": "Which place"});

  return el("section", {},
    el("h2", {}, "Notes about a place"),
    el("p", {class: "lede"},
      "About a town or a region rather than about a property. These are the notes the " +
      "spreadsheet's second sheet carries."),
    el("div", {class: "field"}, el("label", {for: "notekind"}, "Kind"), kind),
    el("div", {class: "field"}, el("label", {for: "noteplace"}, "Place"), place),
    el("div", {class: "field"}, el("label", {for: "note"}, "Note"), box),
    el("button", {type: "button", onclick: () => saveNote(kind.value, place.value, box.value)},
      "Save this note"),
    el("div", {id: "notes"}),
  );
}

async function saveNote(kind, place, notes) {
  try {
    const answered = await send("/api/areas",
      {area_type: kind, area_value: place, notes: notes});
    say(`Saved a note about ${place}.`, "good");
    document.getElementById("notes").replaceChildren(
      el("table", {class: "plain"},
        el("tbody", {}, (answered.areas || []).map((note) => el("tr", {},
          el("td", {}, `${note.area_type} ${note.area_value}`),
          el("td", {}, value(note.notes)))))));
  } catch (error) {
    fail(error);
  }
}

/* ------------------------------------------------------------------ */
/* The map                                                             */
/* ------------------------------------------------------------------ */

function startMap() {
  const where = document.getElementById("map");
  const hint = document.getElementById("maphint");

  if (typeof L === "undefined" || typeof L.Control === "undefined" || !L.Control.Draw) {
    where.classList.add("plain");
    where.replaceChildren(
      el("p", {},
        "The map library is not there. It lives in web/vendor and is committed with the tool; " +
        "if it has been removed, restore it from the repository."));
    return;
  }

  const map = L.map(where, {center: [34.19, -103.34], zoom: 11});
  held.map = map;

  const tiles = held.settings.map && held.settings.map.tiles;
  if (tiles) {
    L.tileLayer(tiles, {
      attribution: (held.settings.map && held.settings.map.attribution) || "",
      maxZoom: 19,
    }).addTo(map);
    hint.replaceChildren(
      el("span", {},
        "A background is on, so this map asks that server for the part of the world you are " +
        "looking at. "),
      el("button", {type: "button", onclick: turnTilesOff}, "Turn it off"));
  } else {
    /* A grey rectangle with a toolbar on it is not a map. Rather than leave somebody looking at
     * one, say what is missing and offer the one click that fixes it, with what it costs stated
     * where the choice is made rather than in a file they would have to go and find. */
    hint.replaceChildren(
      el("strong", {}, "There is no map background. "),
      el("span", {},
        "Drawing works without one, over the coordinate grid below, and is much easier with one. " +
        "Turning it on means this map asks OpenStreetMap for tiles, which tells them which part " +
        "of the world you are looking at. Nothing else about this tool talks to them. "),
      el("button", {type: "button", onclick: turnTilesOn}, "Turn on the map background"),
      el("span", {}, " "),
      link("/settings", "or use a different tile server"));
    grid(map);
  }

  const drawn = new L.FeatureGroup();
  map.addLayer(drawn);
  held.drawn = drawn;

  for (const area of (held.search.areas || []).concat(held.search.exclusions || [])) {
    if (!area.geometry) continue;
    L.geoJSON(area.geometry, {
      style: {color: area.excluded ? "#a02020" : "#14508c",
              dashArray: area.excluded ? "5,5" : null},
    }).eachLayer((layer) => {
      layer.__excluded = !!area.excluded;
      /* The name and the in-or-out sense live on the layer, not on the row that shows them. That
       * is what lets both be changed without redrawing the shape: the table edits the layer, and
       * saving reads every layer back out. */
      layer.__name = area.name || "";
      drawn.addLayer(layer);
    });
  }

  map.addControl(new L.Control.Draw({
    edit: {featureGroup: drawn},
    draw: {polyline: false, circle: false, marker: false, circlemarker: false, rectangle: true},
  }));

  /* The table is built before this runs, so the shapes it should list did not exist yet. Now they
   * do, and each one gets its row with its name and its in-or-out control. */
  redrawAreaList();

  map.on(L.Draw.Event.DELETED, redrawAreaList);

  map.on(L.Draw.Event.CREATED, (event) => {
    const shape = event.layer.toGeoJSON();
    if (crossesItself(shape)) {
      /* Refused as it is drawn, with the reason, rather than saved and failed at run time. */
      say("That shape crosses itself, so it does not enclose one area. Draw it again.", "problem");
      return;
    }
    const kind = (document.getElementById("drawkind") || {}).value;
    event.layer.__excluded = kind === "exclude";
    event.layer.__name = "";
    if (event.layer.__excluded && event.layer.setStyle) {
      event.layer.setStyle({color: "#a02020", dashArray: "5,5"});
    }
    drawn.addLayer(event.layer);
    say(
      event.layer.__excluded
        ? "Shape drawn as an area to leave out. Name it in the table below, then save."
        : "Shape drawn. Name it in the table below, then save.",
      "good");
    redrawAreaList();
  });
}

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_CREDIT = "© OpenStreetMap contributors";

async function turnTilesOn() {
  try {
    await send("/api/configuration",
      {set: {HOMESCOUT_MAP_TILES: OSM, HOMESCOUT_MAP_ATTRIBUTION: OSM_CREDIT}});
  } catch (error) {
    fail(error);
    return;
  }
  say("Map background on. It can be turned off again here or on the settings page.", "good");
  await load();
}

async function turnTilesOff() {
  try {
    await send("/api/configuration", {set: {HOMESCOUT_MAP_TILES: "", HOMESCOUT_MAP_ATTRIBUTION: ""}});
  } catch (error) {
    fail(error);
    return;
  }
  say("Map background off. Nothing outside this machine is asked about the map now.", "good");
  await load();
}

/* Something to draw over when there is no background.
 *
 * A grid of degrees with its lines labelled, so a shape drawn on it can be placed and checked
 * against a coordinate rather than against nothing at all. Not a substitute for a map, and it is
 * not offered as one: the sentence above it says what is missing.
 */
function grid(map) {
  const lines = L.layerGroup().addTo(map);
  const redraw = () => {
    lines.clearLayers();
    const bounds = map.getBounds();
    const span = Math.max(bounds.getNorth() - bounds.getSouth(),
                          bounds.getEast() - bounds.getWest());
    const step = span > 4 ? 1 : span > 1 ? 0.25 : span > 0.4 ? 0.1 : 0.025;
    const style = {color: "#b9b9b4", weight: 1, interactive: false};

    for (let lat = Math.floor(bounds.getSouth() / step) * step;
         lat <= bounds.getNorth(); lat += step) {
      L.polyline([[lat, bounds.getWest()], [lat, bounds.getEast()]], style).addTo(lines);
      L.marker([lat, bounds.getWest()], {
        interactive: false,
        icon: L.divIcon({className: "gridlabel", html: null}),
      }).addTo(lines).bindTooltip(lat.toFixed(3), {permanent: true, direction: "right"});
    }
    for (let lon = Math.floor(bounds.getWest() / step) * step;
         lon <= bounds.getEast(); lon += step) {
      L.polyline([[bounds.getSouth(), lon], [bounds.getNorth(), lon]], style).addTo(lines);
    }
  };
  redraw();
  map.on("moveend zoomend", redraw);
}

/* A cheap self-intersection test for the shape somebody just drew, so the refusal happens while
 * their hand is still on the mouse. The authoritative check is the core's own, at validation. */
function crossesItself(shape) {
  const ring = ((shape.geometry || {}).coordinates || [])[0] || [];
  for (let i = 0; i < ring.length - 1; i++) {
    for (let j = i + 2; j < ring.length - 1; j++) {
      if (i === 0 && j === ring.length - 2) continue;
      if (cross(ring[i], ring[i + 1], ring[j], ring[j + 1])) return true;
    }
  }
  return false;
}

function cross(a, b, c, d) {
  const side = (p, q, r) =>
    Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return side(a, b, c) !== side(a, b, d) && side(c, d, a) !== side(c, d, b);
}
