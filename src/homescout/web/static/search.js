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
      el("button", {type: "button", id: "savedrawn", onclick: saveDrawn},
        "Save the shapes to the file"),
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
async function saveDrawn() {
  if (!held.drawn) { say("There is no map, so there is nothing drawn.", "problem"); return; }

  const areas = [];
  const exclusions = [];
  /* The named areas the file already had, unchanged. A city or a county has no geometry to draw
   * and must survive a save that is about shapes. */
  for (const area of held.search.areas || []) if (!area.geometry) areas.push(namedArea(area));
  for (const area of held.search.exclusions || []) if (!area.geometry) {
    exclusions.push(namedArea(area));
  }

  held.drawn.eachLayer((layer) => {
    if (!layer.toGeoJSON) return;
    const shape = layer.toGeoJSON();
    const entry = {type: "polygon", geometry: shape.geometry};
    if (layer.__excluded) exclusions.push(entry); else areas.push(entry);
  });

  if (!areas.length) {
    say("A saved search needs at least one area to look in, so this was not saved.", "problem");
    return;
  }

  try {
    await send(`/api/searches/${encodeURIComponent(held.name)}`,
      {set: {areas: areas, exclude_areas: exclusions}});
    say(`Saved ${areas.length} areas and ${exclusions.length} exclusions.`, "good");
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

function areaList() {
  const search = held.search;
  const rows = [
    ...(search.areas || []).map((area) => [area, false]),
    ...(search.exclusions || []).map((area) => [area, true]),
  ];
  if (!rows.length) {
    return el("section", {}, el("p", {class: "unknown"}, "this search names no areas yet"));
  }
  return el("section", {},
    el("table", {class: "plain"},
      el("thead", {}, el("tr", {},
        el("th", {scope: "col"}, "Kind"),
        el("th", {scope: "col"}, "Which"),
        el("th", {scope: "col"}, "In or out"),
      )),
      el("tbody", {}, rows.map(([area, excluded]) => el("tr", {},
        el("td", {}, value(area.kind)),
        el("td", {}, value(area.name || area.value || (area.geometry ? "a drawn shape" : null))),
        el("td", {}, badge(excluded ? "excluded" : "included", excluded ? "bad" : "good")),
      ))),
    ),
  );
}

function settingsPanel() {
  const search = held.search;
  return el("section", {},
    el("h2", {}, "Settings"),
    el("dl", {class: "facts"},
      el("dt", {}, "sources"), el("dd", {}, value((search.sources || []).join(", "))),
      el("dt", {}, "description"), el("dd", {}, value(search.description)),
      el("dt", {}, "model extraction"), el("dd", {},
        badge(search.model_extraction ? "on" : "off",
              search.model_extraction ? "flag" : "plain")),
    ),
    el("p", {class: "meta"},
      "Filters and criteria are edited in the file. This interface changes what the core's edit " +
      "operation can change, and shows the rest as it found it."),
  );
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
    hint.replaceChildren(document.createTextNode(
      "A tile background is configured, so this map asks that server for the part of the world " +
      "you are looking at."));
  } else {
    hint.replaceChildren(document.createTextNode(
      "No map background. Drawing works without one. Setting " +
      ((held.settings.map && held.settings.map.variable) || "HOMESCOUT_MAP_TILES") +
      " to a tile URL adds one, and means this map tells that server which part of the world " +
      "you are looking at."));
  }

  const drawn = new L.FeatureGroup();
  map.addLayer(drawn);
  held.drawn = drawn;

  for (const area of (held.search.areas || []).concat(held.search.exclusions || [])) {
    if (!area.geometry) continue;
    L.geoJSON(area.geometry, {
      style: {color: area.excluded ? "#a02020" : "#14508c",
              dashArray: area.excluded ? "5,5" : null},
    }).eachLayer((layer) => { layer.__excluded = !!area.excluded; drawn.addLayer(layer); });
  }

  map.addControl(new L.Control.Draw({
    edit: {featureGroup: drawn},
    draw: {polyline: false, circle: false, marker: false, circlemarker: false, rectangle: true},
  }));

  map.on(L.Draw.Event.CREATED, (event) => {
    const shape = event.layer.toGeoJSON();
    if (crossesItself(shape)) {
      /* Refused as it is drawn, with the reason, rather than saved and failed at run time. */
      say("That shape crosses itself, so it does not enclose one area. Draw it again.", "problem");
      return;
    }
    const kind = (document.getElementById("drawkind") || {}).value;
    event.layer.__excluded = kind === "exclude";
    if (event.layer.__excluded && event.layer.setStyle) {
      event.layer.setStyle({color: "#a02020", dashArray: "5,5"});
    }
    drawn.addLayer(event.layer);
    say(
      event.layer.__excluded
        ? "Shape drawn as an area to leave out. Save it to write it into the file."
        : "Shape drawn. Save it to write it into the file.",
      "good");
  });
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
