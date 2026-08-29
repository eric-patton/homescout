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

const held = {name: "", rows: [], settings: null, map: null, markers: null, pins: {},
              showPassed: false, opacity: 0.55,
              /* How the list under the map is arranged. Cheapest first, because that is the
               * question everybody asks of a screenful of houses before any other one. */
              list: {by: "Price", down: false}};

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

/* Names on the map, and how wet the ground under them is.
 *
 * The hazard layer is a wall of colour with no words on it, and the basemap's own names are
 * underneath it: the moment the map becomes useful it also becomes anonymous. `lines` is what puts
 * the names back on top. `rain` is the other half of the same question, asked about the ground
 * rather than about the map: fire hazard is modelled from fuel and terrain and says nothing at all
 * about how dry a place is, and nine inches a year and twenty inches a year are different
 * countries. */
const land = {lines: false, rain: false, counties: [], towns: [], byCounty: {},
              years: 30, asked: false, asking: false, raining: false, rainAsked: false,
              shapes: null, labels: null};

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

  const named = el("input", {
    type: "checkbox",
    id: "names",
    onchange: (event) => showLand(event.target.checked),
  });

  /* Turning the rain on turns the names on, because the number is written under a county's name
   * and a number floating on an unnamed patch of map is a number about nothing. The box ticks
   * itself when that happens, so the page never holds a state it is not showing. */
  const wet = el("input", {
    type: "checkbox",
    id: "rain",
    onchange: (event) => showRain(event.target.checked),
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
      el("label", {for: "names"}, named, " counties and towns"),
      el("label", {for: "rain"}, wet, " rain and snow a year"),
      el("span", {class: "counts", id: "counts", role: "status"}, ""),
      el("span", {class: "counts", id: "windcount", role: "status"}, ""),
      el("span", {class: "counts", id: "landcount", role: "status"}, ""),
      link(`/results/${encodeURIComponent(held.name)}`, "back to the table"),
    ),
    el("div", {class: "firemap"},
      el("div", {id: "map", role: "application", "aria-label": "Properties on the fire map"}),
      legend(),
    ),
    /* The same properties, as a list, under the map they are pinned on.
     *
     * A pin is very good at "where" and says nothing at all until it is opened, so reading a
     * screenful of them means clicking every one. The list is the other half of the same look:
     * what is on this screen, with the numbers, in one read. It is not a second table with its own
     * idea of what is going on - it holds exactly the pins the map is drawing, hides what the map
     * hides, and re-reads itself whenever the map moves. */
    el("section", {class: "onmap"},
      el("h2", {}, el("span", {id: "listcount"}, "What is on the map")),
      el("div", {id: "list"}),
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
     * next person to read it will assume that is a bug and put the rose back.
     *
     * A rose points into the wind, the way a weather vane does, and that convention is older than
     * anybody who will ever work on this. It is also the single easiest thing on this page to read
     * backwards, and backwards here is not a slightly worse answer: "from the west" and "toward
     * the west" name opposite sides of a house as the side to worry about. Nothing else on this
     * map fails that way.
     *
     * So it is not a rose at all now, and it points downwind. The reader is two people buying a
     * house, not two meteorologists, the question they are asking has one direction in the answer,
     * and the drawing of one direction is an arrow. The word "from" appears nowhere near a
     * direction on this page. The archive still records it the meteorological way and
     * `enrich/wind.py` still stores it that way, which is right for a store of facts; the turning
     * around happens here, where the drawing is. */
    el("h2", {}, "Which way the wind pushes"),
    el("ul", {},
      el("li", {}, el("span", {class: "swatch wind any"}), "any speed"),
      el("li", {}, el("span", {class: "swatch wind strong"}), "15 mph and over"),
    ),
    el("p", {class: "meta"},
      "An arrow points the way the wind ", el("strong", {}, "pushes"),
      ", which is the way a fire would run, so the red to worry about is the red the arrow " +
      "points at. It is longer where the wind more often does the same thing. The dark arrow " +
      "appears only where hard wind pushes somewhere else than the everyday wind does."),
    el("h2", {}, "Where this is"),
    el("p", {class: "meta"},
      "County lines and town names are drawn on top of the fire layer rather than under it, "
      + "because underneath is where the map\u2019s own names already are and they cannot be read "
      + "there. More town names appear as you zoom in."),
    /* "Rain" was the word here and it was wrong, and the person the page is for found it by
     * asking whether snow counted. It does, and the way it counts is the part worth spelling out:
     * the national record measures snow by melting it, so a mountain county's figure is a real
     * winter written down as a small number. Taos and San Juan are eighteen and nine, and reading
     * that as "twice the rain" misses that most of the difference is snow. */
    el("p", {class: "meta"},
      "Rain and snow together, averaged over the last thirty years, per county, which is the "
      + "finest grain the national record publishes. Snow is counted as the water it melts down "
      + "to, so an inch on this map is an inch of water and roughly a foot of snow. It is a fact "
      + "about the county and not about the house: fire hazard says how a place would burn and "
      + "says nothing about how wet it is."),
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
  /* The pane takes no pointer, and the arrows put it back on their own ink, in the stylesheet.
   *
   * Same trap as the county lines below, arrived at from the other side. This pane holds one thing
   * that is meant to be opened, the arrows, and one thing that is not: the dot marking a station
   * whose record is still being read. That dot is a shape on a canvas, and a canvas is one element
   * over the whole pane whatever is painted on it, so leaving this pane able to take the pointer
   * meant a canvas over the properties answering for every pixel of the map. Measured with the
   * wind on: a hundred and sixty-seven of the hundred and seventy-six pins on screen could not be
   * reached.
   *
   * The dot loses the tooltip that named its station. That is the price and it is the right way
   * round: the dot's job is to say that more is coming, the line above the map says how many are
   * still being read, and neither of those is worth a screenful of houses that cannot be opened. */
  map.getPane("wind").style.pointerEvents = "none";

  /* County lines under the wind and over the fire, so an outline never hides an arrow.
   *
   * The names go over everything, properties included, and take no pointer at all. A label is
   * read, never clicked, and one that can be clicked is a label that swallows the pin underneath
   * it: on this map that would mean a name over a town quietly making the houses in that town
   * unopenable, which is the sort of fault nobody reports because it looks like a mis-click. */
  map.createPane("lines");
  map.getPane("lines").style.zIndex = "440";
  /* And takes no pointer either, for a reason that is not obvious and cost the properties on this
   * map every click they had.
   *
   * A county outline is not a thing anybody clicks, so every one of them is drawn as
   * non-interactive, and that would be the end of it if these were shapes in the page. They are
   * not: this map draws its shapes on a canvas, and a canvas is one element covering the whole
   * pane whatever is or is not painted on it. A canvas over the properties answers for every
   * pixel of the map, finds nothing of its own under the pointer, and hands the click to the map
   * itself. So with county lines on, which is a checkbox somebody ticks once and leaves ticked,
   * not one house on the screen could be opened and the pointer never even said one was there.
   * Measured on the state at zoom seven: a hundred and seventy-six of a hundred and seventy-six.
   *
   * The pane is what has to say this rather than the layers in it, because the element that was
   * swallowing the clicks belongs to the pane and not to any layer. */
  map.getPane("lines").style.pointerEvents = "none";
  map.createPane("labels");
  map.getPane("labels").style.zIndex = "640";
  map.getPane("labels").style.pointerEvents = "none";

  held.markers = L.layerGroup().addTo(map);
  wind.layer = L.layerGroup();
  land.shapes = L.layerGroup();
  land.labels = L.layerGroup();
  /* Only what is on screen is asked about, nearest the middle first. Somebody looking at Taos gets
   * Taos in ten seconds rather than the whole state in four minutes. */
  map.on("moveend", () => {
    if (wind.on) blow();
    /* The list is "what is on this screen", so the screen changing is the whole of its news. */
    listWhatIsOnScreen();
    /* Which names fit depends on how far out this is, so they are worked out again every move. */
    if (land.lines) drawLand();
  });
  plot();
  const bounds = held.rows.map((row) => [row.latitude, row.longitude]);
  if (bounds.length) map.fitBounds(bounds, {padding: [24, 24]});
}

function plot() {
  if (!held.markers) return;
  held.markers.clearLayers();
  held.pins = {};
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
    held.pins[row.listing_id] = {pin: pin, look: look};
    drawn += 1;
  }
  counts(drawn);
  listWhatIsOnScreen();
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
/* The list under the map                                              */
/* ------------------------------------------------------------------ */

/* What the list shows, and how each column is compared.
 *
 * Not the whole table. The table has every column this tool knows and a way to choose between
 * them, and it is one click away at the top of this page; putting it here as well would be two
 * tables that disagree about what is filtered. These are the six things somebody reads off a pin
 * before deciding whether to open it. */
const LIST = [
  {name: "Property", kind: "text", of: (row) => row.values["Property"]},
  {name: "Price", kind: "money", of: (row) => row.values["Price"]},
  {name: "Beds", kind: "number", of: (row) => row.values["Beds"]},
  {name: "Acres", kind: "number", of: (row) => row.values["Acres"]},
  {name: "Built", kind: "number", of: (row) => row.values["Year Built"]},
  {name: "Hazard here", kind: "hazard", of: (row) => row.values["Wildfire Hazard"]},
];

/* Worst first, which is the order the legend is written in, so the eye reads the same ranking in
 * both places. Anything the model has no word for sorts after everything it does. */
const HAZARD_ORDER = {};
HAZARD.forEach(([word], at) => { HAZARD_ORDER[word] = at; });

/* Above this many, the list stops being a list. A run at full zoom-out is the whole state, and a
 * thousand rows under a map is neither readable nor quick; the honest thing is to draw what can be
 * read and say plainly that there is more, because the fix is to zoom in and that is the thing
 * somebody is about to do anyway. */
const LIST_MOST = 400;

function listWhatIsOnScreen() {
  const where = document.getElementById("list");
  const heading = document.getElementById("listcount");
  if (!where || !held.map) return;

  const bounds = held.map.getBounds();
  const on = held.rows.filter((row) =>
    (row.judgment !== "pass" || held.showPassed)
    && bounds.contains([row.latitude, row.longitude]));

  const column = LIST.find((one) => one.name === held.list.by) || LIST[1];
  on.sort((a, b) => rank(column, a, b) * (held.list.down ? -1 : 1));
  const shown = on.slice(0, LIST_MOST);

  if (heading) {
    heading.replaceChildren(document.createTextNode(
      on.length
        ? (shown.length < on.length
            ? `The first ${LIST_MOST} of ${on.length} properties on the map: zoom in for the rest`
            : count(on.length, "property", "properties") + " on the map")
        : "Nothing on this part of the map"));
  }

  if (!on.length) {
    where.replaceChildren(
      el("p", {class: "notice"},
        "No properties are on this part of the map. Zoom out, or move to where the pins are."));
    return;
  }

  where.replaceChildren(
    el("table", {class: "onscreen"},
      el("thead", {}, el("tr", {}, LIST.map((one) => listHead(one)))),
      el("tbody", {}, shown.map((row) => listRow(row)))));
}

function rank(column, a, b) {
  const left = column.of(a);
  const right = column.of(b);
  if (column.kind === "hazard") {
    const at = (value) => (value in HAZARD_ORDER ? HAZARD_ORDER[value] : HAZARD.length + 1);
    return at(left) - at(right);
  }
  /* Nothing known sorts last whichever way round the column is, because a blank is not a small
   * number and a page that says so puts every unpriced house at the top of "cheapest first". */
  const missing = (value) => value === null || value === undefined || value === "";
  if (missing(left) && missing(right)) return 0;
  if (missing(left)) return 1 * (held.list.down ? -1 : 1);
  if (missing(right)) return -1 * (held.list.down ? -1 : 1);
  if (column.kind === "text") return String(left).localeCompare(String(right));
  return Number(left) - Number(right);
}

function listHead(column) {
  const sorted = held.list.by === column.name;
  return el("th", {
    scope: "col",
    class: column.kind === "money" || column.kind === "number" ? "numeric" : "",
    "aria-sort": sorted ? (held.list.down ? "descending" : "ascending") : "none",
  },
    el("button", {
      type: "button",
      onclick: () => {
        held.list.down = held.list.by === column.name ? !held.list.down : false;
        held.list.by = column.name;
        listWhatIsOnScreen();
      },
    }, column.name, sorted ? el("span", {class: "way"}, held.list.down ? " ▾" : " ▴") : null),
  );
}

/* One row, and the button on it is the point of the whole list.
 *
 * The pin is already on screen: that is what being in this list means. So this opens it where it
 * stands rather than flying to it, because a map that jumps every time somebody reads a row is a
 * map that loses the place they were looking at. */
function listRow(row) {
  const on = held.pins[row.listing_id];
  const judged = row.judgment === "keep" ? "kept"
               : row.judgment === "pass" ? "passed on" : "not decided";

  const lift = (bigger) => {
    if (!on) return;
    on.pin.setStyle({radius: bigger ? on.look.size + 5 : on.look.size,
                     weight: bigger ? 3 : 1.5});
    if (bigger) on.pin.bringToFront();
  };

  const what = row.values["Property"] || "this property";
  const open = el("button", {
    type: "button",
    class: "address",
    /* The dot says which of the three this is, and a dot says nothing to a screen reader, so the
     * word goes in the name rather than in a title nobody hears. */
    "aria-label": `${what}, ${judged}. Opens its pin on the map.`,
    title: `${what} - ${judged}`,
    onclick: () => { if (on) on.pin.openPopup(); },
    onmouseenter: () => lift(true),
    onmouseleave: () => lift(false),
    onfocus: () => lift(true),
    onblur: () => lift(false),
  },
    el("span", {class: `dot ${row.judgment || "none"}`, "aria-hidden": "true"}),
    what);

  const money = row.values["Price"];
  return el("tr", {class: row.judgment === "pass" ? "passed"
                        : row.judgment === "keep" ? "kept" : ""},
    el("td", {class: "address"}, open),
    el("td", {class: "numeric"},
      money === null || money === undefined ? "" : `$${Number(money).toLocaleString()}`),
    el("td", {class: "numeric"}, blank(row.values["Beds"])),
    el("td", {class: "numeric"}, blank(row.values["Acres"])),
    el("td", {class: "numeric"}, blank(row.values["Year Built"])),
    el("td", {class: "hazard"},
      row.values["Wildfire Hazard"]
        ? el("span", {},
             el("span", {class: "swatch",
                         style: `background:${(HAZARD.find(
                           ([word]) => word === row.values["Wildfire Hazard"]) || [])[1]
                           || "transparent"}`,
                         "aria-hidden": "true"}),
             row.values["Wildfire Hazard"])
        : ""),
  );
}

function blank(value) {
  return value === null || value === undefined ? "" : String(value);
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

  /* Built before the bubble, because the picture writes into it when a listing turns out to
   * carry nothing beyond the one photograph stored here. */
  const say_ = el("p", {class: "rowstate", role: "status"}, "");

  const held_ = el("div", {class: "pin"},
    picture(row, say_),
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

/* The photograph this tool stored, at the top of the bubble.
 *
 * A pin is very good at where and the facts under it are good at what, and neither of them says
 * what the house looks like, which is the first thing anybody wants from a listing and the reason
 * the results table carries one as well. This is the stored copy served from this machine, so
 * opening a pin still tells the listing site nothing; pressing it opens every photograph the
 * listing carried, which is the one thing on this page that does, and it says so when it does it.
 *
 * A property with no stored picture gets no frame at all. The table does the opposite and keeps an
 * empty box, for a reason that does not hold here: there, a column of addresses has to stay in a
 * straight line to run an eye down, and here there is one bubble on its own.
 */
function picture(row, where) {
  if (!row.has_image) return null;
  /* Not lazy, unlike the table's. There are sixty of those on a screen and there is one of this,
   * and it is in a bubble somebody has just opened on purpose. */
  const shot = el("img", {
    class: "shot",
    decoding: "async",
    alt: "",
    src: `/api/listings/${encodeURIComponent(row.listing_id)}/image`,
  });
  /* A button rather than a picture with a handler on it, so the keyboard reaches it. */
  return el("button", {
    type: "button",
    class: "pinshot",
    title: "See every photograph of this property",
    "aria-label": `Photographs of ${row.values["Property"] || "this property"}`,
    onclick: (event) => {
      event.preventDefault();
      event.stopPropagation();
      photographs(row, where);
    },
  }, shot);
}

/* The rest of them, asked for at the moment somebody asks for them and never before: they are the
 * listing site's own addresses rather than pictures this tool holds. */
async function photographs(row, where) {
  try {
    const found = await ask(`/api/listings/${encodeURIComponent(row.listing_id)}`);
    if (gallery((found.listing || {}).photo_urls, row.values["Property"])) return;
    where.replaceChildren(
      document.createTextNode("This listing carried no photographs beyond the one stored."));
  } catch (error) {
    where.replaceChildren(document.createTextNode(`could not read them: ${error.message}`));
    where.className = "rowstate problem";
  }
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
/* Where this is, and how much rain falls on it                        */
/* ------------------------------------------------------------------ */

/* How many town names to draw at each zoom, biggest first.
 *
 * A cap and not a threshold, because the right number of labels is a property of the screen rather
 * than of the towns: forty names on a map of the whole state is a smudge whether or not every one
 * of them is a real town. Biggest first means the ones that survive the cap are the ones somebody
 * navigates by, and zooming in is what asks for the rest.
 */
const TOWNS_AT = [[6, 5], [7, 10], [8, 18], [9, 30], [10, 50]];

/* Roughly how much room a drawn name takes, in pixels either side of its point. Measured off the
 * real thing rather than computed from the text, because a label's box is the same order of size
 * whatever is in it and measuring every one would mean laying them all out to find out which ones
 * not to lay out. */
const LABEL_ROOM = {county: [58, 17], town: [42, 9]};

function townsHere(zoom) {
  for (const [out, many] of TOWNS_AT) {
    if (zoom <= out) return many;
  }
  return 400;
}

async function showLand(on) {
  land.lines = Boolean(on);
  const box = document.getElementById("names");
  if (box) box.checked = land.lines;
  if (!land.lines) {
    if (land.shapes) held.map.removeLayer(land.shapes);
    if (land.labels) held.map.removeLayer(land.labels);
    landCount();
    return;
  }
  land.shapes.addTo(held.map);
  land.labels.addTo(held.map);
  if (!land.asked) {
    land.asking = true;
    landCount();
    try {
      const found = await ask(`/api/ground/${encodeURIComponent(held.name)}`);
      land.counties = found.counties || [];
      land.towns = found.towns || [];
      land.asked = true;
      for (const said of found.unreachable || []) say(said, "problem");
    } catch (error) {
      say(`The county lines could not be read: ${error.message}`, "problem");
    } finally {
      land.asking = false;
    }
  }
  drawLand();
}

/* The rain is a second request and a slower one, so it is a second switch. The names are on the
 * map in a moment; the numbers take a few seconds the first time and never again. */
async function showRain(on) {
  land.rain = Boolean(on);
  if (land.rain && !land.lines) await showLand(true);
  if (!land.rain) {
    drawLand();
    return;
  }
  if (!land.rainAsked) {
    land.raining = true;
    landCount();
    try {
      const found = await ask(`/api/rain/${encodeURIComponent(held.name)}`);
      land.byCounty = {};
      for (const one of found.counties || []) land.byCounty[`${one.state}/${one.fips}`] = one;
      land.years = found.years || land.years;
      land.rainAsked = true;
      for (const said of found.unreachable || []) say(said, "problem");
    } catch (error) {
      say(`The rainfall record could not be read: ${error.message}`, "problem");
      land.rain = false;
      const box = document.getElementById("rain");
      if (box) box.checked = false;
    } finally {
      land.raining = false;
    }
  }
  drawLand();
}

function landCount() {
  const where = document.getElementById("landcount");
  if (!where) return;
  const parts = [];
  if (land.asking) parts.push("reading the county lines\u2026");
  else if (land.raining) parts.push("reading thirty years of rainfall\u2026");
  else if (land.lines && land.counties.length) {
    parts.push(count(land.counties.length, "county", "counties"));
    if (land.rain && land.rainAsked) {
      parts.push(`rain and snow averaged over ${land.years} years`);
    }
  }
  where.replaceChildren(document.createTextNode(parts.join(" \u00b7 ")));
}

/* Everything drawn again from what is on screen now.
 *
 * Cleared and rebuilt, unlike the wind, and the difference is worth knowing: nothing here opens a
 * bubble, so there is no popup for a redraw to close. The wind cannot do this and the note above
 * `drawWind` says why.
 */
function drawLand() {
  if (!land.shapes || !land.labels) return;
  land.shapes.clearLayers();
  land.labels.clearLayers();
  if (!land.lines) return;

  const bounds = held.map.getBounds();
  /* Where a name has already been written, so the next one does not go on top of it.
   *
   * Counties go down first and towns give way, which is the right order because a county name is
   * the coarse answer: somebody who cannot read "Albuquerque" can still see they are in
   * Bernalillo, and somebody who cannot read "Bernalillo" is looking at an unlabelled county.
   * Zooming in is what separates them, and by then both fit. */
  const taken = [];
  const roomFor = (where, kind) => {
    const at = held.map.latLngToContainerPoint(where);
    const [wide, tall] = LABEL_ROOM[kind];
    for (const held_ of taken) {
      if (Math.abs(held_.x - at.x) < held_.wide + wide
       && Math.abs(held_.y - at.y) < held_.tall + tall) return null;
    }
    return {x: at.x, y: at.y, wide: wide, tall: tall};
  };

  for (const one of land.counties) {
    for (const ring of one.outline || []) {
      L.polygon(ring, {
        pane: "lines",
        color: "#1f2933",
        weight: 1.1,
        opacity: 0.55,
        fill: false,
        interactive: false,
      }).addTo(land.shapes);
    }
    if (one.latitude === null || one.longitude === null) continue;
    if (!bounds.contains([one.latitude, one.longitude])) continue;
    const room = roomFor([one.latitude, one.longitude], "county");
    if (!room) continue;
    taken.push(room);
    label([one.latitude, one.longitude], "county", countyLabel(one)).addTo(land.labels);
  }

  const many = townsHere(held.map.getZoom());
  let drawn = 0;
  for (const one of land.towns) {
    if (drawn >= many) break;
    if (!bounds.contains([one.latitude, one.longitude])) continue;
    const room = roomFor([one.latitude, one.longitude], "town");
    /* Not counted against the cap: a name that could not be drawn should cost the next town its
     * turn, not its own. Otherwise a screen with one crowded corner draws five names instead of
     * the ten it has room for. */
    if (!room) continue;
    taken.push(room);
    label([one.latitude, one.longitude], "town", [el("span", {class: "dot"}), one.name])
      .addTo(land.labels);
    drawn += 1;
  }
  landCount();
}

function countyLabel(one) {
  const wet = land.rain ? land.byCounty[`${one.state}/${one.fips}`] : null;
  return [
    el("span", {class: "name"}, one.name),
    /* The unit is on every one of them on purpose. "17.7" over a county is a number somebody has
     * to go and look up; "17.7 in" is an answer. */
    wet ? el("span", {class: "rain"}, `${wet.inches.toFixed(1)} in`) : null,
    land.rain && !wet && land.rainAsked
      ? el("span", {class: "rain none"}, "no record") : null,
  ];
}

function label(where, kind, what) {
  const icon = L.divIcon({
    className: `mapname ${kind}`,
    /* Zero, so the box is the text and the text is centred on the place. A divIcon with a size
     * gets a box that big whatever is in it, and a hundred invisible boxes over a map is a
     * hundred things for the eye to line up against nothing. */
    iconSize: [0, 0],
    html: "",
  });
  const pin = L.marker(where, {pane: "labels", icon: icon, interactive: false, keyboard: false});
  pin.on("add", () => {
    const node = pin.getElement();
    if (node && !node.firstChild) node.append(el("span", {}, what));
  });
  return pin;
}

/* ------------------------------------------------------------------ */
/* Which way the wind pushes                                           */
/* ------------------------------------------------------------------ */

/* How the arrow is drawn.
 *
 * THIS WAS A WIND ROSE, AND THE NOTE IS HERE SO NOBODY PUTS IT BACK. Sixteen arms, one per
 * direction, each as long as that direction was common. The arms were turned around to point
 * downwind, which fixed the half of the problem that was about which way, and the person the page
 * is drawn for read it and asked for an arrow instead.
 *
 * She is right, and the reason is that a rose and an arrow answer different questions. A rose
 * answers "what is the distribution of wind direction at this station", which is a question with
 * sixteen numbers in the answer and is asked by somebody studying the wind. What she is asking is
 * "which way would a fire here run", which has one direction in the answer, and the drawing of one
 * direction is an arrow. Sixteen arms was the right shape for the wrong question.
 *
 * The sixteen numbers did not go anywhere. They are in the bubble, where a second question belongs.
 */
const WIND_SIZE = 112;     /* The icon's box. The station sits at the middle of it. */
const WIND_FULL = 20;      /* The percent an arrow at full length means. */
const WIND_LEAST = 0.5;    /* Never shorter than half of it: a stub does not point anywhere. */
const WIND_HEAD = 12;      /* How long the head is, along the arrow. */
const WIND_HEAD_WIDE = 5.5;
const WIND_SHAFT = 1.4;    /* Half the shaft's width. Thin, because thin is what was asked for. */
/* Violet, and violet for a reason: this page already spends red through green on the hazard model
 * and blue, gold and pink on what the person has decided about a house. An arrow in any of those
 * would be read as one of those. Nothing else here is violet. */
const WIND_ANY = "#a276cf";
const WIND_STRONG = "#4c1d95";

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
    const layer = kind === "rose" ? arrowAt(one, wind.roses[key]) : waitingAt(one);
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
    /* Nothing in this pane takes the pointer; see the note where the pane is made. A dot that
     * cannot be hovered is a dot that is read rather than asked, which is all this one is for. */
    interactive: false,
    radius: 5, color: WIND_STRONG, weight: 1.5, opacity: 0.7,
    fillColor: WIND_ANY, fillOpacity: 0.5,
  });
}

/* One station's arrow, as a fixed number of pixels rather than a shape on the ground.
 *
 * An arrow drawn in degrees would be a speck at one zoom and cover a county at the next, and it is
 * not a thing that is anywhere: it is a summary of a place, drawn at the place. So it is an icon,
 * and its size is the same at every zoom.
 */
function arrowAt(station, rose) {
  const pin = L.marker([station.latitude, station.longitude], {
    pane: "wind",
    icon: L.divIcon({className: "windarrow", iconSize: [WIND_SIZE, WIND_SIZE]}),
    keyboard: true,
    title: whatItSays(rose),
    alt: whatItSays(rose),
  });
  pin.on("add", () => {
    const node = pin.getElement();
    if (node && !node.firstChild) node.append(arrowsFor(rose));
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
 * Every arrow is drawn at `pushes(degrees)`, which is a half turn from where the archive put it.
 * The long note in `legend()` is why. */
function arrowsFor(rose) {
  const where = "http://www.w3.org/2000/svg";
  const box = document.createElementNS(where, "svg");
  box.setAttribute("viewBox", `0 0 ${WIND_SIZE} ${WIND_SIZE}`);
  box.setAttribute("width", String(WIND_SIZE));
  box.setAttribute("height", String(WIND_SIZE));
  box.setAttribute("aria-hidden", "true");

  const middle = WIND_SIZE / 2;
  const most = middle - 4;

  const at = (turn, along, across) => {
    const radians = (turn * Math.PI) / 180;
    const ahead = [Math.sin(radians), -Math.cos(radians)];
    return [
      middle + along * ahead[0] + across * -ahead[1],
      middle + along * ahead[1] + across * ahead[0],
    ];
  };

  /* Long enough to read as a direction, and longer the more of the time the wind actually does
   * this. A station where every direction is about as likely gets a short arrow, and that is the
   * truth about that station: it is worth being able to see at a glance that an arrow is a strong
   * claim in one place and a weak one in another. Never shorter than half, because below that an
   * arrow stops being a thing with a direction and becomes a smudge with a point on it. */
  const outTo = (percent) =>
    (WIND_LEAST + (1 - WIND_LEAST) * Math.min((percent || 0) / WIND_FULL, 1)) * most;

  /* One arrow, as one closed outline: down one side of the shaft, out to the point, back down the
   * other. Drawn as a single shape rather than a stroked line with a triangle on the end because
   * of what it lies over. This sits on a raster that is red in some places, green in others and
   * grey in the rest, and a shape with no edge reads on one and vanishes on the next. One shape
   * takes one white edge, all the way round, with `paint-order` putting that edge outside the
   * colour rather than half over it. Two shapes would take two, and show the seam where they
   * meet. */
  const arrow = (turn, out, colour) => {
    const s = WIND_SHAFT;
    const neck = Math.max(out - WIND_HEAD, 4);
    const corners = [
      at(turn, 2, s), at(turn, neck, s), at(turn, neck, WIND_HEAD_WIDE),
      at(turn, out, 0),
      at(turn, neck, -WIND_HEAD_WIDE), at(turn, neck, -s), at(turn, 2, -s),
    ];
    const path = document.createElementNS(where, "path");
    path.setAttribute(
      "d",
      corners.map(([x, y], at_) => `${at_ ? "L" : "M"} ${x.toFixed(2)} ${y.toFixed(2)}`)
             .join(" ") + " Z");
    path.setAttribute("fill", colour);
    path.setAttribute("stroke", "#ffffff");
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("stroke-opacity", "0.9");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("paint-order", "stroke");
    box.append(path);
  };

  const best = rose.prevailing;
  if (best) arrow(pushes(best.degrees), outTo(best.percent), WIND_ANY);

  /* The hard wind gets its own arrow ONLY when it pushes somewhere else, because that is the only
   * time it is news. "It normally pushes east, and when it blows hard enough to move a fire it
   * pushes north" is worth a second arrow on the map. "It pushes east, and hard wind pushes east"
   * is one arrow and a line in the bubble, and drawing it twice would say there are two answers
   * here when there is one. */
  const strongest = rose.sectors.slice().sort((a, b) => b.strong - a.strong)[0];
  if (strongest && strongest.strong > 0 && (!best || strongest.degrees !== best.degrees)) {
    arrow(pushes(strongest.degrees), outTo(strongest.strong), WIND_STRONG);
  }

  /* The station itself. The arrow says which way from here, and this is the here. */
  const middleDot = document.createElementNS(where, "circle");
  middleDot.setAttribute("cx", String(middle));
  middleDot.setAttribute("cy", String(middle));
  middleDot.setAttribute("r", "2.6");
  middleDot.setAttribute("fill", WIND_STRONG);
  middleDot.setAttribute("stroke", "#ffffff");
  middleDot.setAttribute("stroke-width", "1.2");
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
