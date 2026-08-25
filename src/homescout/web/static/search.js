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
  const [search, settings, areas] = await Promise.all([
    ask(`/api/searches/${encodeURIComponent(held.name)}`),
    ask("/api/settings"),
    ask("/api/areas"),
  ]);
  held.search = search.search;
  held.settings = settings;
  /* The places this store has properties in, and what is already written about them. Fetched here
   * rather than typed into a blank box: a note only reaches a property's row when it matches that
   * property's own town, spelled the way the listing site spells it, and "Portales, NM" is the
   * obvious thing to write and matches nothing. */
  held.places = areas.places || [];
  held.areaNotes = areas.areas || [];
  held.matchingKinds = areas.matching_kinds || ["city"];
  draw();
}

function draw() {
  const search = held.search;
  shell(`${held.name}`,
    el("h1", {}, held.name),
    el("p", {class: "lede"},
      "Where to look, what to look for, and what matters to you about what turns up. Nothing is " +
      "saved until you press a save button, and each panel saves only itself."),
    problems(search),
    el("div", {class: "detail"},
      el("div", {}, mapPanel(), areaList()),
      el("div", {}, settingsPanel()),
    ),
    /* Full width, below the two columns. A criterion is four controls in a row and a place note is
     * a paragraph, and both were unreadable squeezed into a third of the window. */
    criteriaPanel(),
    placeNotesPanel(),
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
    el("button", {type: "button", class: "primary", onclick: saveAreas}, "Save the areas"),
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
    searchNotes(),
  );
}

/* What this search wants the model told, on top of whatever the installation says on the settings
 * page. Both are sent, the general one first. This is where the local knowledge goes: the phrase
 * that means something different in this county than it does two counties over. */
function searchNotes() {
  const limit = 2000;
  const box = el("textarea", {
    id: "searchnotes", rows: 4, maxlength: limit,
    "aria-label": "What you want the model told about listings this search finds",
    placeholder: "Anything specific to this market. Left empty, only the installation's note is " +
      "sent.",
  });
  box.value = held.search.extract_notes || "";

  return el("div", {},
    el("div", {class: "field"},
      el("label", {for: "searchnotes"}, "Notes for the model, for this search"), box,
      el("span", {class: "hint"},
        "Added to the note on the settings page, which is sent as well. Sent to the model with " +
        "every description this search finds, so keep anything private out of it. It cannot add a " +
        "field or a new answer.")),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "quiet",
        onclick: () => save({"extract.notes": box.value.trim()}),
      }, "Save the note")));
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

/* Criteria, built rather than typed.
 *
 * A criterion is stored as an expression, and it stays that way: the file still says
 * `when: water_source == "well"`, still readable and editable by hand. What changed is that nobody
 * has to write that to make one. Each criterion is a card with a name, what firing does, and one or
 * more conditions, each of which is three dropdowns.
 *
 * Three things this has to get right, and they are the reasons it is not simply a form.
 *
 * THE VALUE BOX FOLLOWS THE FIELD. Picking "Water source" gives a list of the six words that field
 * can hold; picking "Price" gives a number box; picking "Price has come down" gives yes and no.
 * Offering a text box for a field with six possible values is how somebody types "swamp cooler" and
 * gets a criterion that can never be true.
 *
 * A CRITERION THE BUILDER CANNOT SHOW IS SHOWN AS TEXT, NOT MANGLED. `(a or b) and c` is a
 * perfectly good criterion and is not a flat list of rows. The core answers `parts: null` for one of
 * those and this shows the expression read-only with a note, rather than rows that would quietly
 * mean something else.
 *
 * NOTHING IS SAVED UNTIL SAVE IS PRESSED, and everything is saved together. Editing one card and
 * navigating away loses that edit, which is the ordinary bargain; editing one card and having it
 * save while another is half-finished is not.
 */

/* The criteria panel: every rule as a card, plus the two ways to add one. */
function criteriaPanel() {
  /* Working copy. The saved search is not touched until Save. */
  held.rules = (held.search.rules || []).map(asDraft);

  return el("section", {},
    el("h2", {}, "Criteria"),
    el("p", {class: "lede"},
      "Rules about what matters to you. Each one watches for something and then points it out, " +
      "moves it up or down the list, or hides it. Nothing here changes what is searched for: " +
      "criteria decide how what was found is shown to you."),
    el("div", {id: "criteria"}, criteriaCards()),
    el("div", {class: "actions"},
      el("button", {type: "button", onclick: addRule}, "Add a criterion"),
      el("button", {type: "button", class: "primary", onclick: saveRules}, "Save the criteria")),
    startFrom(),
  );
}

function asDraft(rule) {
  return {
    id: rule.id,
    severity: rule.severity,
    when: rule.when,
    /* Null means the core could not read this one as rows. It stays as text. */
    parts: rule.parts ? rule.parts.map((p) => ({...p})) : null,
  };
}

function redrawCriteria() {
  const where = document.getElementById("criteria");
  if (where) where.replaceChildren(criteriaCards());
}

function criteriaCards() {
  if (!held.rules.length) {
    return el("p", {class: "empty"},
      "No criteria yet. Everything this search finds is shown, in the order it was found. " +
      "Add one below, or start from one of the suggestions.");
  }
  return el("div", {}, held.rules.map((rule, index) => criterionCard(rule, index)));
}

function criterionCard(rule, index) {
  const name = el("input", {
    type: "text", value: rule.id || "", size: 18,
    "aria-label": "What to call this criterion",
    placeholder: "a name for it",
    onchange: (e) => { rule.id = e.target.value.trim(); },
  });

  const labels = (held.settings.severity_labels || []);
  const does = el("select", {"aria-label": "What happens when this is true"},
    labels.map((s) => el("option", {value: s.severity}, s.label)));
  does.value = rule.severity || "flag";
  does.addEventListener("change", () => {
    rule.severity = does.value;
    redrawCriteria();
  });
  const said = (labels.find((s) => s.severity === (rule.severity || "flag")) || {}).does || "";

  return el("div", {class: "criterion"},
    /* Reads as a sentence: "Call it on-a-well and point it out, when water source is well." A form
     * whose labels are above its boxes would need the same words and would not read as anything. */
    el("div", {class: "criterion-head"},
      el("span", {class: "criterion-when"}, "Call it"),
      name,
      el("span", {class: "criterion-when"}, "and"),
      does,
      el("button", {
        type: "button", class: "quiet danger",
        "aria-label": `Remove the criterion ${rule.id || index + 1}`,
        onclick: () => { held.rules.splice(index, 1); redrawCriteria(); },
      }, "Remove")),

    rule.parts
      ? el("div", {class: "conditions"},
          rule.parts.map((part, at) => conditionRow(rule, part, at)),
          el("button", {
            type: "button", class: "quiet",
            onclick: () => {
              rule.parts.push({field: "price", comparison: "<", value: "", join: "and"});
              redrawCriteria();
            },
          }, "Add another condition"))
      : el("div", {},
          el("p", {class: "notice"},
            "This one was written by hand and is more than a list of conditions, so it is shown " +
            "as it was written."),
          el("code", {class: "expression"}, rule.when)),

    el("p", {class: "meta"}, said),
  );
}

/* One condition: how it joins the one above, the field, the comparison, and the value.
 *
 * The value control is rebuilt whenever the field changes, because what a value may be is a
 * property of the field. A list of six words is a dropdown; a price is a number box; a yes-or-no is
 * a yes-or-no. */
function conditionRow(rule, part, at) {
  const vocabulary = held.settings.rule_vocabulary || [];
  const comparisons = held.settings.rule_comparisons || [];
  const field = vocabulary.find((f) => f.name === part.field) || vocabulary[0] || {};

  const join = at === 0
    ? el("span", {class: "join"}, "when")
    : el("select", {class: "join", "aria-label": "How this joins the condition above"},
        el("option", {value: "and"}, "and also"),
        el("option", {value: "or"}, "or else"));
  if (at > 0) {
    join.value = part.join || "and";
    join.addEventListener("change", () => { part.join = join.value; });
  }

  const which = el("select", {"aria-label": "What to look at"},
    groupedFields(vocabulary));
  which.value = part.field;
  which.addEventListener("change", () => {
    part.field = which.value;
    /* A value carried over from the old field is almost always wrong for the new one, and a wrong
     * value that looks deliberate is worse than an empty one. */
    part.value = defaultValueFor(vocabulary.find((f) => f.name === which.value));
    redrawCriteria();
  });

  const how = el("select", {"aria-label": "How to compare it"},
    comparisons.filter((c) => suitable(c, field)).map((c) =>
      el("option", {value: c.comparison}, c.label)));
  how.value = part.comparison;
  how.addEventListener("change", () => {
    part.comparison = how.value;
    redrawCriteria();
  });

  const takes = (comparisons.find((c) => c.comparison === part.comparison) || {}).takes || "one";

  return el("div", {class: "condition"},
    join, which, how,
    takes === "nothing" ? el("span", {class: "meta"}, "") : valueControl(field, part, takes),
    rule.parts.length > 1
      ? el("button", {
          type: "button", class: "quiet",
          "aria-label": "Remove this condition",
          onclick: () => { rule.parts.splice(at, 1); redrawCriteria(); },
        }, "×")
      : null,
  );
}

/* The fields, grouped by where they come from, because "Water source" and "Price" are different
 * kinds of thing and a flat list of forty is a list nobody reads. */
function groupedFields(vocabulary) {
  const groups = [
    ["listing", "From the listing"],
    ["extracted", "Read out of the description"],
    ["enriched", "About where it is"],
    ["derived", "From your own history"],
  ];
  return groups.map(([origin, title]) => {
    const fields = vocabulary.filter((f) => f.origin === origin && f.type !== "list");
    if (!fields.length) return null;
    return el("optgroup", {label: title},
      fields.map((f) => el("option", {value: f.name}, f.label)));
  });
}

/* Which comparisons make sense for this field. Offering "is more than" for a word, or "is any of"
 * for a yes-or-no, is offering somebody a way to write a condition that cannot be true. */
function suitable(comparison, field) {
  const name = comparison.comparison;
  if (name === "is null" || name === "is not null") return true;
  if (field.type === "boolean") return name === "==" || name === "!=";
  if (field.type === "number") return name !== "in" && name !== "not in";
  if (field.values && field.values.length) return true;
  return name === "==" || name === "!=" || name === "in" || name === "not in";
}

function defaultValueFor(field) {
  if (!field) return "";
  if (field.type === "boolean") return true;
  if (field.values && field.values.length) return field.values[0].value;
  return "";
}

function valueControl(field, part, takes) {
  if (field.type === "boolean") {
    const box = el("select", {"aria-label": "Yes or no"},
      el("option", {value: "true"}, "yes"),
      el("option", {value: "false"}, "no"));
    box.value = part.value === false ? "false" : "true";
    box.addEventListener("change", () => { part.value = box.value === "true"; });
    return box;
  }

  if (field.values && field.values.length && takes === "one") {
    const box = el("select", {"aria-label": "Which value"},
      field.values.map((v) => el("option", {value: v.value}, v.label)));
    box.value = part.value != null && part.value !== "" ? String(part.value) : field.values[0].value;
    part.value = box.value;
    box.addEventListener("change", () => { part.value = box.value; });
    return box;
  }

  if (field.values && field.values.length && takes === "many") {
    /* Tick boxes rather than a multi-select, which nobody knows to ctrl-click. */
    const chosen = new Set(Array.isArray(part.value) ? part.value.map(String) : []);
    part.value = [...chosen];
    return el("span", {class: "choices"},
      field.values.map((v) => el("label", {class: "choice"},
        el("input", {
          type: "checkbox",
          checked: chosen.has(v.value) ? true : null,
          onchange: (e) => {
            if (e.target.checked) chosen.add(v.value); else chosen.delete(v.value);
            part.value = [...chosen];
          },
        }),
        " " + v.label)));
  }

  /* "is any of" on a field whose values are not a fixed list. A comma-separated box, because the
   * alternative is a row of empty text inputs with an add button, and a person comparing a flood
   * zone against two letters should not have to build a list to do it. */
  if (takes === "many") {
    const held_ = Array.isArray(part.value) ? part.value : (part.value ? [part.value] : []);
    part.value = held_;
    const box = el("input", {
      type: "text", value: held_.join(", "), size: 20,
      "aria-label": "The values to compare against, separated by commas",
      placeholder: (field.examples || []).slice(0, 2).join(", ") || "one, another",
    });
    box.addEventListener("change", () => {
      part.value = box.value.split(",").map((v) => v.trim()).filter(Boolean);
    });
    return el("span", {class: "many"}, box,
      el("span", {class: "hint"}, "separate them with commas"));
  }

  if (field.type === "number") {
    const box = el("input", {
      type: "number", value: part.value == null ? "" : String(part.value), size: 10,
      "aria-label": "The number to compare against",
      placeholder: field.name === "price" ? "300000" : "",
    });
    box.addEventListener("change", () => {
      const held_ = box.value.trim();
      part.value = held_ === "" ? "" : Number(held_);
    });
    return box;
  }

  const box = el("input", {
    type: "text", value: part.value == null ? "" : String(part.value), size: 18,
    "aria-label": "The value to compare against",
    placeholder: (field.examples && field.examples[0]) || "",
  });
  box.addEventListener("change", () => { part.value = box.value.trim(); });
  return box;
}

function addRule() {
  held.rules.push({
    id: "",
    severity: "flag",
    when: "",
    parts: [{field: "water_source", comparison: "==", value: "well", join: ""}],
  });
  redrawCriteria();
}

/* A few criteria worth having, offered as one click each, because a blank builder is still a blank
 * page. Every one of these is a thing a person looking at rural property actually wants. */
const SUGGESTIONS = [
  ["on-a-well", "flag", [["water_source", "==", "well"]],
   "Point out the ones on a private well"],
  ["septic", "flag", [["sewer", "==", "septic"]],
   "Point out the ones on septic"],
  ["swamp-cooler", "demote", [["cooling", "==", "evaporative"]],
   "Push down the ones with only an evaporative cooler"],
  ["in-a-flood-zone", "flag", [["flood_zone", "in", ["A", "AE"]]],
   "Point out the ones in a real FEMA flood zone"],
  ["fire-risk", "demote", [["wildfire_hazard", "in", ["high", "very high"]]],
   "Push down the ones the Forest Service rates high for wildfire"],
  ["slow-internet", "flag", [["download_mbps", "<", 25]],
   "Point out the ones with under 25 Mbps in their census block"],
  ["price-came-down", "boost", [["price_cut", "==", true]],
   "Lift the ones whose price has dropped"],
  ["been-sitting", "flag", [["dom", ">", 120]],
   "Point out the ones on the market over four months"],
];

function startFrom() {
  return el("details", {class: "reference"},
    el("summary", {}, "Start from one of these"),
    el("p", {class: "meta"},
      "One click adds it. Change anything about it afterwards, or remove it again."),
    el("table", {class: "plain"},
      el("tbody", {}, SUGGESTIONS.map(([id, severity, conditions, said]) => el("tr", {},
        el("td", {}, said),
        el("td", {},
          el("button", {
            type: "button",
            class: "quiet",
            disabled: held.rules.some((r) => r.id === id) ? true : null,
            onclick: () => {
              held.rules.push({
                id: id,
                severity: severity,
                when: "",
                parts: conditions.map(([f, c, v], at) => ({
                  field: f, comparison: c, value: v, join: at ? "and" : "",
                })),
              });
              redrawCriteria();
            },
          }, held.rules.some((r) => r.id === id) ? "added" : "Add"))))))
  );
}

async function saveRules() {
  const named = held.rules.filter((r) => (r.id || "").trim());
  if (named.length !== held.rules.length) {
    say("Every criterion needs a name. It is what the badge says.", "problem");
    return;
  }
  const payload = held.rules.map((rule) =>
    rule.parts
      ? {id: rule.id, severity: rule.severity, parts: rule.parts}
      : {id: rule.id, severity: rule.severity, when: rule.when});
  await save({rules: payload});
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
  /* What the file says right now, so leaving a box without having touched it saves nothing. A blur
   * handler that commits unconditionally writes the file every time somebody tabs through the page,
   * which is how an empty `sqft:` appears in a search nobody edited. */
  const asLoaded = JSON.stringify({
    ...(held_.min != null ? {min: held_.min} : {}),
    ...(held_.max != null ? {max: held_.max} : {}),
  });
  const commit = () => {
    const wanted = {};
    if (low.value.trim() !== "") wanted.min = Number(low.value);
    if (high.value.trim() !== "") wanted.max = Number(high.value);
    if (JSON.stringify(wanted) === asLoaded) return;
    save({[`filters.${name}`]: Object.keys(wanted).length ? wanted : null});
  };
  for (const box of [low, high]) {
    box.addEventListener("keydown", (event) => { if (event.key === "Enter") commit(); });
    box.addEventListener("blur", commit);
  }
  return el("div", {class: "field"},
    el("label", {for: `${name}-min`}, label),
    el("span", {class: "pair"}, low, el("span", {class: "to"}, "to"), high));
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

/* Research a town once rather than once per property.
 *
 * The panel used to say "About a town or a region rather than about a property. These are the notes
 * the spreadsheet's second sheet carries", which describes where the note is stored and not what it
 * is for. What it is for is that everything worth knowing about Portales is true of all two hundred
 * Portales listings, and typing it into two hundred rows is not a thing anybody does twice.
 *
 * Two things the old panel let you get silently wrong. The place had to match the spelling the
 * listing site uses, so "Portales, NM" typed into a blank box matched nothing and looked like the
 * feature was broken. And only a town note reaches a property's row today, while the other kinds are
 * recorded and read back and match nothing. Both are now said out loud, and the places you actually
 * have properties in are offered rather than typed. */
function placeNotesPanel() {
  const known = (held.places || []).filter((p) => p.value);
  const matching = held.matchingKinds || ["city"];
  const existing = held.areaNotes || [];

  const box = el("textarea", {rows: "4", id: "note",
                              "aria-label": "What you know about this place"});
  const place = el("select", {id: "noteplace", "aria-label": "Which place"},
    known.map((p) => el("option", {value: `${p.kind}|${p.value}`},
      `${p.value} (${p.kind}, ${count(p.properties, "property", "properties")})`)),
    el("option", {value: "other"}, "somewhere else"));

  const kind = el("select", {id: "notekind", "aria-label": "What kind of place"},
    (held.settings.area_kinds || []).map((k) => el("option", {value: k}, k)));
  const typed = el("input", {type: "text", id: "noteplacetyped",
                             placeholder: "spelled the way the listing spells it",
                             "aria-label": "Which place"});
  const elsewhere = el("div", {class: "field", hidden: true},
    el("label", {for: "notekind"}, "Kind"), kind,
    el("label", {for: "noteplacetyped"}, "Place"), typed,
    el("span", {class: "hint"},
      "Only a town note reaches a property's row, and only when it matches that property's own " +
      "town exactly. Anything else is kept and shows on the spreadsheet's Areas sheet."));

  const chosen = () => {
    if (place.value === "other") return [kind.value, typed.value.trim()];
    const [k, ...rest] = place.value.split("|");
    return [k, rest.join("|")];
  };

  place.addEventListener("change", () => {
    if (place.value === "other") elsewhere.removeAttribute("hidden");
    else elsewhere.setAttribute("hidden", "");
    const [k, v] = chosen();
    const found = existing.find((n) => n.area_type === k && n.area_value === v);
    box.value = (found && found.notes) || "";
  });

  /* Whatever is selected on arrival, show its note, so the box is an edit rather than a fresh
   * start every time. A note you cannot see is a note you write twice. */
  if (known.length) {
    const [k, v] = chosen();
    const found = existing.find((n) => n.area_type === k && n.area_value === v);
    box.value = (found && found.notes) || "";
  }

  return el("section", {},
    el("h2", {}, "What you know about a place"),
    el("p", {class: "lede"},
      "Research a town once, not once per property. What you write here about a town lands in the " +
      "Town Analysis Notes column of every property in it, and on the spreadsheet's Areas sheet. " +
      "Water, schools, the drive to anywhere, whatever you would otherwise re-type on two " +
      "hundred rows."),
    el("p", {class: "meta"},
      "These belong to this database rather than to this search, so every saved search sees them."),

    known.length
      ? null
      : el("p", {class: "notice"},
          "No run has found anything yet, so there are no towns to write about. Run this search " +
          "first and the places it finds will be here."),

    el("div", {class: "field"}, el("label", {for: "noteplace"}, "Place"), place),
    elsewhere,
    el("div", {class: "field"}, el("label", {for: "note"}, "Note"), box),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "primary",
        onclick: () => {
          const [k, v] = chosen();
          if (!v) {
            say("Which place is the note about?", "problem");
            return;
          }
          if (matching.indexOf(k) === -1) {
            say(`Saved. A ${k} note is kept and shows on the Areas sheet, but only a town note ` +
                "reaches a property's own row.", "plain");
          }
          saveNote(k, v, box.value);
        },
      }, "Save this note")),

    el("div", {id: "notes"}, notesTable(existing)),
  );
}

function notesTable(notes) {
  if (!notes || !notes.length) return el("p", {class: "meta"}, "Nothing written about a place yet.");
  return el("table", {class: "plain"},
    el("thead", {}, el("tr", {},
      el("th", {}, "Place"), el("th", {}, "Kind"), el("th", {}, "Note"))),
    el("tbody", {}, notes.map((note) => el("tr", {},
      el("td", {}, note.area_value),
      el("td", {}, note.area_type),
      el("td", {}, value(note.notes))))));
}

async function saveNote(kind, place, notes) {
  try {
    const answered = await send("/api/areas",
      {area_type: kind, area_value: place, notes: notes});
    held.areaNotes = answered.areas || [];
    say(`Saved a note about ${place}.`, "good");
    document.getElementById("notes").replaceChildren(notesTable(held.areaNotes));
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
