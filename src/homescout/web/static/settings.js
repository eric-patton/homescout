"use strict";
/* What this installation has set up, what it has not, and the things you run occasionally.
 *
 * TWO KINDS OF SETTING, AND THE DIFFERENCE IS THE POINT. Some are plain choices: which model to
 * ask, where the map's tiles come from, where the digest is written. Those are editable here and
 * are written to the `.env` file beside the database.
 *
 * The rest are credentials, and this page will not write one. It says whether one is present and
 * never what it is, and the server refuses to write anything whose name looks like a secret. A
 * credential comes from your environment or from that file by your own hand, which is the
 * constitution's rule and is the reason there is no box here to type a key into.
 */

let held = null;

whenReady(() => {
  nav("/settings");
  load().catch(fail);
});

async function load() {
  held = (await ask("/api/configuration"));
  draw();
}

function draw() {
  shell("Settings",
    el("h1", {}, "Settings and tools"),
    el("p", {class: "lede"},
      `Everything lives in ${held.workspace}. The optional parts are absent until you set them up, ` +
      "and the tool works without any of them."),
    modelPanel(),
    mapPanel(),
    mailPanel(),
    broadbandPanel(),
    toolsPanel(),
    interfacePanel(),
  );
}

function present(is, yes, no) {
  return badge(is ? yes : no, is ? "good" : "plain");
}

/* ------------------------------------------------------------------ */
/* Reading descriptions with a model                                   */
/* ------------------------------------------------------------------ */

function modelPanel() {
  const model = held.model;
  const url = el("input", {
    type: "text", id: "baseurl", value: model.base_url || "",
    "aria-label": "Where the OpenAI-compatible server is",
  });
  const name = el("input", {
    type: "text", id: "modelname", value: model.model || "",
    placeholder: "gpt-4o-mini, or whatever your local server calls it",
    "aria-label": "Which model to ask",
  });

  return el("section", {},
    el("h2", {}, "Reading descriptions with a model ", present(model.configured, "ready", "off")),
    el("p", {class: "lede"},
      "Optional, and off unless a saved search asks for it. The six fields recovered from listing " +
      "prose are filled by patterns that need nothing at all; this only adds a model for the " +
      "descriptions those patterns could not settle."),

    model.configured
      ? el("p", {class: "notice notice-good"},
          `Ready: ${model.model} at ${model.base_url}` +
          (model.local ? ", on this machine, so no credential is needed."
                       : (model.credential ? ", with a credential from your environment."
                                           : ", with no credential.")))
      : el("p", {class: "notice"}, model.needs || model.why_not || "Not configured."),

    el("h3", {}, "A model on this machine"),
    el("p", {class: "meta"},
      "LM Studio serves an OpenAI-compatible API on http://localhost:1234/v1 and needs no " +
      "credential. Start it, load a model, then put its address and the model's name below."),
    el("h3", {}, "A hosted one"),
    el("p", {class: "meta"},
      "Leave the address as api.openai.com and name a model. The credential is read from " +
      "OPENAI_API_KEY or HOMESCOUT_EXTRACT_API_KEY in your environment. " +
      (model.credential
        ? "One is already there, so naming a model is all that is left."
        : "There is none there yet.")),

    el("div", {class: "field"}, el("label", {for: "baseurl"}, "Address"), url),
    el("div", {class: "field"}, el("label", {for: "modelname"}, "Model"), name),
    el("button", {
      type: "button",
      onclick: () => write({
        HOMESCOUT_EXTRACT_BASE_URL: url.value.trim(),
        HOMESCOUT_EXTRACT_MODEL: name.value.trim(),
      }),
    }, "Save"),

    el("p", {class: "meta"},
      "This page will not accept a credential and the server refuses to write one. Set it in your " +
      "environment, or by hand in the .env file beside the database."),
    el("p", {class: "meta"},
      "Turn it on for a search on that search's own page. Nothing is asked of a model until one " +
      "does."),
  );
}

/* ------------------------------------------------------------------ */
/* The map                                                             */
/* ------------------------------------------------------------------ */

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_CREDIT = "© OpenStreetMap contributors";

function mapPanel() {
  const source = el("input", {
    type: "text", id: "tiles", value: held.map.tiles || "",
    placeholder: "https://tile.example.org/{z}/{x}/{y}.png",
    "aria-label": "Tile URL template for the map background",
  });

  return el("section", {},
    el("h2", {}, "The map's background ", present(held.map.tiles, "on", "off")),
    el("p", {class: "lede"},
      "Off by default, and this is the one setting worth reading before turning on. A tile server " +
      "is somebody else's computer, and asking it for tiles tells it which part of the world you " +
      "are looking at. Everything else this tool talks to is a listing site, a public data " +
      "service, your own model, or your own mail server."),
    el("p", {class: "meta"},
      "Drawing an area works without a background. It is much easier with one."),

    el("div", {class: "field"}, el("label", {for: "tiles"}, "Tile URL"), source),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        onclick: () => write({
          HOMESCOUT_MAP_TILES: OSM,
          HOMESCOUT_MAP_ATTRIBUTION: OSM_CREDIT,
        }),
      }, "Use OpenStreetMap"),
      el("button", {
        type: "button",
        onclick: () => write({
          HOMESCOUT_MAP_TILES: source.value.trim(),
          HOMESCOUT_MAP_ATTRIBUTION: source.value.trim() ? held.map.attribution || "" : "",
        }),
      }, "Save what is typed"),
      el("button", {
        type: "button",
        onclick: () => write({HOMESCOUT_MAP_TILES: "", HOMESCOUT_MAP_ATTRIBUTION: ""}),
      }, "Turn it off"),
    ),
  );
}

/* ------------------------------------------------------------------ */
/* The rest of the configuration                                       */
/* ------------------------------------------------------------------ */

function mailPanel() {
  const mail = held.mail;
  return el("section", {},
    el("h2", {}, "The nightly email ", present(mail.configured, "ready", "off")),
    el("p", {class: "lede"},
      "Optional. With no account configured, runs still happen and the digest file is still " +
      "written; only the email is absent. The email goes out only on nights something changed."),
    el("dl", {class: "facts"},
      el("dt", {}, "to"), el("dd", {}, value(mail.to)),
      el("dt", {}, "server"), el("dd", {}, value(mail.host)),
      el("dt", {}, "digest file"), el("dd", {}, value(mail.digest_path)),
    ),
    el("p", {class: "meta"},
      "A mail password is a credential, so it is set in your environment or by hand in the .env " +
      "file and never here. The variables are: " + mail.variables.join(", ") + "."),
  );
}

function broadbandPanel() {
  return el("section", {},
    el("h2", {}, "Broadband speeds ", present(held.broadband.configured, "ready", "off")),
    el("p", {class: "lede"},
      "The FCC's national broadband map needs an API token, which is why the Internet column is " +
      "empty. Every other public data service this uses needs nothing. Set " +
      held.broadband.variable + " in your environment to turn it on."),
  );
}

function interfacePanel() {
  const named = held.interface.allowed_hosts || [];
  return el("section", {},
    el("h2", {}, "This interface"),
    el("dl", {class: "facts"},
      el("dt", {}, "listening on"), el("dd", {}, `127.0.0.1:${held.interface.port}`),
      el("dt", {}, "also answers to"),
      el("dd", {}, named.length ? named.join(", ") : value(null)),
      el("dt", {}, "database"), el("dd", {}, held.database),
    ),
    el("p", {class: "meta"},
      "The server listens on this machine and nowhere else, always. A name in the second row is a " +
      "reverse proxy on this machine that forwards to it, which is how it is reached from a phone. " +
      "There is no authentication, so whatever can reach that proxy can use this."),
  );
}

/* ------------------------------------------------------------------ */
/* The things you run occasionally                                     */
/* ------------------------------------------------------------------ */

function toolsPanel() {
  const where = el("div", {id: "toolprogress"});
  const searches = el("input", {
    type: "text", id: "toolsearch", placeholder: "all of them",
    "aria-label": "Limit these to one saved search",
  });

  return el("section", {},
    el("h2", {}, "Things to run occasionally"),
    el("p", {class: "lede"},
      "None of these is part of a run, and each takes minutes because every request is paced."),
    el("div", {class: "field"},
      el("label", {for: "toolsearch"}, "Only this saved search (optional)"), searches),

    el("table", {class: "plain"},
      el("tbody", {},
        tool("Attach public data",
          "Flood zone, elevation, aquifer and wildfire hazard for every property with " +
          "coordinates. Cached hard, so this is mostly a first-time thing.",
          [
            ["Run it", () => start("enrich", {search: searches.value.trim() || null}, where,
              "Enrichment")],
            ["Only what is stale", () => start("enrich",
              {stale: true, search: searches.value.trim() || null}, where, "Enrichment")],
          ]),
        tool("Ask the model about descriptions",
          "Only the descriptions the patterns could not settle, and only ones it has not already " +
          "been asked about. Needs a model configured above.",
          [
            ["Run it", () => start("extract", {search: searches.value.trim() || null}, where,
              "Extraction")],
            ["Just ten, to try it", () => start("extract",
              {limit: 10, search: searches.value.trim() || null}, where, "Extraction")],
          ]),
        tool("Write the digest and email it",
          "What a scheduled night does at the end. The file is written either way; the email goes " +
          "only if something changed and an account is configured.",
          [["Do it now", () => start("deliver", {}, where, "Delivery")]]),
      ),
    ),
    where,
    exportPanel(),
  );
}

function tool(title, why, actions) {
  return el("tr", {},
    el("th", {scope: "row"}, title),
    el("td", {},
      el("p", {class: "meta"}, why),
      el("div", {class: "actions"},
        actions.map(([label, go]) => el("button", {type: "button", onclick: go}, label)))),
  );
}

function exportPanel() {
  const search = el("input", {
    type: "text", id: "exportsearch", "aria-label": "Which saved search to export",
  });
  const template = el("input", {
    type: "text", id: "exporttemplate", placeholder: "default",
    "aria-label": "Which column template",
  });
  const format = el("select", {id: "exportformat", "aria-label": "Which format"},
    el("option", {value: "xlsx"}, "spreadsheet"),
    el("option", {value: "csv"}, "comma separated"));
  const force = el("input", {type: "checkbox", id: "exportforce"});
  const dropped = el("input", {type: "checkbox", id: "exportdropped"});
  const where = el("div", {id: "exportresult"});

  return el("section", {},
    el("h3", {}, "Write a spreadsheet"),
    el("p", {class: "meta"},
      "The default column set is the hand-built consolidated sheet, exactly. It lands in the " +
      "exports folder beside the database unless the file is already there, in which case it says " +
      "so rather than replacing it."),
    el("div", {class: "field"}, el("label", {for: "exportsearch"}, "Saved search"), search),
    el("div", {class: "field"}, el("label", {for: "exporttemplate"}, "Template"), template),
    el("div", {class: "field"}, el("label", {for: "exportformat"}, "Format"), format),
    el("div", {class: "field"},
      el("label", {for: "exportforce"}, force, " replace it if it is already there")),
    el("div", {class: "field"},
      el("label", {for: "exportdropped"}, dropped, " include properties a criterion removed")),
    el("button", {
      type: "button",
      onclick: async () => {
        try {
          const written = await send("/api/export", {
            search: search.value.trim() || null,
            template: template.value.trim() || null,
            format: format.value,
            force: force.checked,
            include_dropped: dropped.checked,
          });
          where.replaceChildren(
            el("p", {class: "notice notice-good"},
              `${written.properties} properties written to ${written.path}`),
            el("ul", {}, (written.reasons || []).map((r) => el("li", {}, `empty because ${r}`))),
          );
        } catch (error) {
          where.replaceChildren(el("p", {class: "notice notice-problem"}, error.message));
        }
      },
    }, "Write it"),
    where,
  );
}

/* ------------------------------------------------------------------ */

async function start(task, body, where, label) {
  try {
    await send(`/api/${task}`, body);
  } catch (error) {
    fail(error);
    return;
  }
  watchBackgroundTask(task, where, label, () => load().catch(fail));
}

async function write(values) {
  try {
    held = await send("/api/configuration", {set: values});
    say("Saved.", "good");
    draw();
  } catch (error) {
    fail(error);
  }
}
