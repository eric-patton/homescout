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
 *
 * WHERE A THING IS MISSING, IT SAYS WHERE TO GET IT. Telling somebody to set a variable they have
 * never heard of, and leaving them to find out who issues it, is telling them the name of their
 * problem rather than the way out of it. Every panel that can be unconfigured carries the page
 * that issues the thing it wants.
 */

let held = null;
let told = null;

whenReady(() => {
  /* A page of forms, so it is bounded to a measure rather than stretched across the window. */
  document.body.classList.add("narrow");
  nav("/settings");
  load().catch(fail);
});

async function load() {
  held = (await ask("/api/configuration"));
  told = (await ask("/api/notes"));
  draw();
}

function draw() {
  shell("Settings",
    el("h1", {}, "Settings and tools"),
    el("p", {class: "lede"},
      `Everything lives in ${held.workspace}. The optional parts are absent until you set them up, ` +
      "and the tool works without any of them."),
    modelPanel(),
    notesPanel(),
    mailPanel(),
    mapPanel(),
    broadbandPanel(),
    toolsPanel(),
    exportPanel(),
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
    placeholder: "gpt-5.6-luna, or whatever your local server calls it",
    "aria-label": "Which model to ask",
  });
  const effort = el("select", {id: "effort", "aria-label": "How hard the model should think"},
    el("option", {value: ""}, "not a reasoning model"),
    (model.efforts || []).map((one) =>
      el("option", {value: one}, one === "none" ? "none (answer straight away)" : one)));
  effort.value = model.effort || "";

  return el("section", {},
    el("h2", {}, "Reading descriptions with a model ", present(model.configured, "ready", "off")),
    el("p", {class: "lede"},
      "Optional, and off unless a saved search asks for it. The six fields recovered from listing " +
      "prose are filled by patterns that need nothing at all; this only adds a model for the " +
      "descriptions those patterns could not settle."),

    model.configured
      ? el("p", {class: "notice notice-good"},
          `Ready: ${model.model} at ${model.base_url}` +
          (model.effort ? `, thinking at ${model.effort}` : "") +
          (model.local ? ", on this machine, so no credential is needed."
                       : (model.credential ? ", with a credential from your environment."
                                           : ", with no credential.")))
      : el("p", {class: "notice notice-flag"}, model.needs || model.why_not || "Not configured."),

    el("div", {class: "field"}, el("label", {for: "baseurl"}, "Address"), url,
      el("span", {class: "hint"},
        "Leave it at api.openai.com for a hosted model. LM Studio on this machine serves " +
        "http://localhost:1234/v1 and needs no credential.")),
    el("div", {class: "field"}, el("label", {for: "modelname"}, "Model"), name),
    el("div", {class: "field"},
      el("label", {for: "effort"}, "How hard it thinks"), effort,
      el("span", {class: "hint"},
        "Only for models that reason before answering, which is every recent GPT-5. Reading a " +
        "description is transcription rather than judgment, so low is plenty and none is often " +
        "enough. A model that does not reason refuses the request outright if this is set, so " +
        "leave it as it is for a local one.")),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "primary",
        onclick: () => write({
          HOMESCOUT_EXTRACT_BASE_URL: url.value.trim(),
          HOMESCOUT_EXTRACT_MODEL: name.value.trim(),
          HOMESCOUT_EXTRACT_REASONING_EFFORT: effort.value,
        }),
      }, "Save")),

    el("p", {class: "meta"},
      "The credential is read from " + (model.variables || []).slice(-2).join(" or ") +
      " in your environment. This page will not accept one and the server refuses to write one."),
    whereToGet(model.where),
    el("p", {class: "meta"},
      "Turn it on for a search on that search's own page. Nothing is asked of a model until one " +
      "does."),
  );
}

/* ------------------------------------------------------------------ */
/* What you want the model told                                        */
/* ------------------------------------------------------------------ */

/* The instruction the model gets is generated from the six fields and the words each one may take.
 * It knows nothing about the market being searched, which is where this actually goes wrong: around
 * here "community water" is a mutual domestic association rather than a city main, and a listing
 * saying it is describing a shared system. You know that. This is how you say so.
 *
 * It says out loud that the text is sent, because a box whose contents go to somebody else's
 * computer should say so before you type in it rather than after. */
function notesPanel() {
  const limit = told.limit || 2000;
  const box = el("textarea", {
    id: "modelnotes", rows: 6, maxlength: limit,
    placeholder: "Around here, community water means a mutual domestic association rather than a " +
      "city main. Treat swamp cooler and evaporative cooler as the same thing.",
    "aria-label": "What you want the model told about reading listings here",
  });
  box.value = told.notes || "";

  const count = el("span", {class: "hint"}, `${(told.notes || "").length} of ${limit} characters`);
  box.addEventListener("input", () => {
    count.textContent = `${box.value.length} of ${limit} characters`;
  });

  return el("section", {},
    el("h2", {}, "What you want the model told ",
      present(Boolean(told.notes), "written", "nothing yet")),
    el("p", {class: "lede"},
      "Optional, and only used when a search asks for the model. Write what you would tell " +
      "somebody reading these listings on your behalf: how things are worded around here, what a " +
      "phrase means locally, what to be careful about."),

    el("div", {class: "field"},
      el("label", {for: "modelnotes"}, "Notes for the model"), box, count),

    el("div", {class: "actions"},
      el("button", {type: "button", class: "primary", onclick: () => saveNotes(box.value)}, "Save"),
      told.notes
        ? el("button", {type: "button", class: "quiet", onclick: () => saveNotes("")}, "Clear")
        : null),

    el("p", {class: "notice notice-flag"},
      "This text is sent to the model with every description, so keep anything private out of it. " +
      "It cannot add a field or a new answer: everything the model reports is still checked " +
      "against the same list of words, and still has to be quoted from the listing."),
    el("p", {class: "meta"}, `Kept in ${told.path}. A search can add its own note on its own page.`),
  );
}

async function saveNotes(text) {
  try {
    told = await send("/api/notes", {notes: text});
    say(told.truncated ? `Saved, cut to ${told.limit} characters.` : "Saved.", "good");
    draw();
  } catch (error) {
    fail(error);
  }
}

/* ------------------------------------------------------------------ */
/* The nightly email                                                   */
/* ------------------------------------------------------------------ */

function mailPanel() {
  const mail = held.mail;
  const gmail = mail.gmail || {};
  const usingGmail = (mail.host || "").toLowerCase() === gmail.host;

  const to = el("input", {
    type: "text", id: "mailto", value: mail.to || "", placeholder: "you@example.com",
    "aria-label": "Where the nightly email goes",
  });
  const host = el("input", {
    type: "text", id: "mailhost", value: mail.host || "", placeholder: gmail.host,
    "aria-label": "The outgoing mail server",
  });
  const from = el("input", {
    type: "text", id: "mailfrom", value: mail.sender || "",
    placeholder: gmail.address || "the account you send as",
    "aria-label": "The address it is sent from",
  });
  const security = el("select", {id: "mailsecurity", "aria-label": "How it connects"},
    el("option", {value: "starttls"}, "starttls (port 587)"),
    el("option", {value: "ssl"}, "ssl (port 465)"),
    el("option", {value: "none"}, "none (port 25)"));
  security.value = mail.security || "starttls";

  const saveIt = (values) => write(values);

  return el("section", {},
    el("h2", {}, "The nightly email ", present(mail.configured, "ready", "off")),
    el("p", {class: "lede"},
      "Optional. With no account configured, runs still happen and the digest file is still " +
      "written; only the email is absent. The email goes out only on nights something changed."),

    gmail.credential && !mail.configured
      ? el("p", {class: "notice notice-good"},
          `A Google App Password for ${gmail.address || "a Gmail account"} is already in your ` +
          "environment. Say where the email should go and press the button below, and that is the " +
          "whole setup.")
      : null,

    el("div", {class: "field"},
      el("label", {for: "mailto"}, "Send it to"), to,
      el("span", {class: "hint"}, "More than one address, separated by commas, is fine.")),

    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "primary",
        onclick: () => {
          const wanted = to.value.trim();
          if (!wanted) { say("Say where the email should go first.", "problem"); return; }
          saveIt({
            HOMESCOUT_SMTP_HOST: gmail.host,
            HOMESCOUT_SMTP_SECURITY: "starttls",
            HOMESCOUT_SMTP_PORT: "587",
            HOMESCOUT_MAIL_TO: wanted,
          });
        },
      }, usingGmail ? "Save the Gmail setup" : "Set it up through Gmail")),

    el("p", {class: "meta"},
      "Gmail needs an App Password, which is not your Google password: sixteen characters that can " +
      "send mail and nothing else, revocable any time. Put it in GMAIL_APP_PASSWORD (which this " +
      "reads if it is already there for something else) or HOMESCOUT_SMTP_PASSWORD, in your " +
      "environment or by hand in the .env file. It is never typed on this page."),
    whereToGet(mail.where),

    el("details", {},
      el("summary", {}, "A different mail server"),
      el("div", {class: "field"}, el("label", {for: "mailhost"}, "Server"), host),
      el("div", {class: "field"}, el("label", {for: "mailfrom"}, "Send from"), from),
      el("div", {class: "field"}, el("label", {for: "mailsecurity"}, "Connection"), security),
      el("div", {class: "actions"},
        el("button", {
          type: "button",
          onclick: () => saveIt({
            HOMESCOUT_SMTP_HOST: host.value.trim(),
            HOMESCOUT_SMTP_SECURITY: security.value,
            HOMESCOUT_SMTP_PORT: "",
            HOMESCOUT_MAIL_FROM: from.value.trim(),
            HOMESCOUT_SMTP_USERNAME: from.value.trim(),
            HOMESCOUT_MAIL_TO: to.value.trim(),
          }),
        }, "Save this instead")),
      el("p", {class: "meta"},
        "Its password goes in HOMESCOUT_SMTP_PASSWORD, the same way and for the same reason.")),

    el("h3", {}, "What is set now"),
    el("div", {},
      setting("goes to", value(mail.to)),
      setting("server", value(mail.host), mail.port ? ` port ${mail.port}` : null,
              mail.security ? ` over ${mail.security}` : null),
      setting("sent from", value(mail.sender)),
      setting("password", present(mail.credential, "found in your environment", "not set")),
      setting("digest file", value(mail.digest_path))),
  );
}

/* ------------------------------------------------------------------ */
/* The map                                                             */
/* ------------------------------------------------------------------ */

const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_CREDIT = "© OpenStreetMap contributors";

/* The government's own photography of its own country, which is the right default for a tool that
 * only searches this one. Public domain, no key, and the same kind of federal service the fire
 * layer and the broadband map already come from, so turning it on adds a background rather than a
 * new kind of relationship. */
const USGS = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly"
           + "/MapServer/tile/{z}/{y}/{x}";
const USGS_CREDIT = "Imagery: USGS National Map";

function mapPanel() {
  const source = el("input", {
    type: "text", id: "tiles", value: held.map.tiles || "",
    placeholder: "https://tile.example.org/{z}/{x}/{y}.png",
    "aria-label": "Tile URL template for the map background",
  });

  const photo = el("input", {
    type: "text", id: "satellite", value: held.map.satellite || "",
    placeholder: "https://imagery.example.org/{z}/{y}/{x}",
    "aria-label": "Tile URL template for the satellite background",
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

    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: held.map.tiles ? null : "primary",
        onclick: () => write({
          HOMESCOUT_MAP_TILES: OSM,
          HOMESCOUT_MAP_ATTRIBUTION: OSM_CREDIT,
        }),
      }, "Use OpenStreetMap"),
      held.map.tiles
        ? el("button", {
            type: "button",
            class: "danger",
            onclick: () => write({HOMESCOUT_MAP_TILES: "", HOMESCOUT_MAP_ATTRIBUTION: ""}),
          }, "Turn it off")
        : null,
    ),
    whereToGet(held.map.where),

    /* A second background rather than a different one. Somebody looking at rural land wants both:
     * the drawn map says where the roads go and what the parcel is called, and the photograph says
     * what is actually on the ground. The map switches between them with a checkbox; this decides
     * whether there is anything to switch to. */
    el("h3", {}, "Satellite view ", present(held.map.satellite, "on", "off")),
    el("p", {class: "meta"},
      "A second tile server, and so a second computer being told which part of the world you are "
      + "looking at. The one offered here is the United States Geological Survey's own imagery: "
      + "public domain, no account, and the same kind of federal service the fire layer already "
      + "comes from. It covers this country only, and it stops at about the depth of a house."),
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        onclick: () => write({
          HOMESCOUT_MAP_SATELLITE: USGS,
          HOMESCOUT_MAP_SATELLITE_ATTRIBUTION: USGS_CREDIT,
        }),
      }, "Use the USGS imagery"),
      held.map.satellite
        ? el("button", {
            type: "button",
            class: "danger",
            onclick: () => write({
              HOMESCOUT_MAP_SATELLITE: "",
              HOMESCOUT_MAP_SATELLITE_ATTRIBUTION: "",
            }),
          }, "Turn it off")
        : null,
    ),
    whereToGet(held.map.satellite_where),

    el("details", {},
      el("summary", {}, "A different tile server"),
      el("div", {class: "field"}, el("label", {for: "tiles"}, "Tile URL"), source),
      el("div", {class: "actions"},
        el("button", {
          type: "button",
          onclick: () => write({
            HOMESCOUT_MAP_TILES: source.value.trim(),
            HOMESCOUT_MAP_ATTRIBUTION: source.value.trim() ? held.map.attribution || "" : "",
          }),
        }, "Save what is typed")),
      el("div", {class: "field"}, el("label", {for: "satellite"}, "Satellite URL"), photo),
      el("div", {class: "actions"},
        el("button", {
          type: "button",
          onclick: () => write({
            HOMESCOUT_MAP_SATELLITE: photo.value.trim(),
            HOMESCOUT_MAP_SATELLITE_ATTRIBUTION:
              photo.value.trim() ? held.map.satellite_attribution || "" : "",
          }),
        }, "Save what is typed"))),
  );
}

/* ------------------------------------------------------------------ */
/* Broadband                                                           */
/* ------------------------------------------------------------------ */

/* The one provider with a dataset behind it, and the panel has to say why.
 *
 * There is no service that will tell you what internet one house can get: the FCC's public API
 * hands over per-state files and nothing finer. So this downloads a state once and answers from it,
 * and the wording is careful about what the number then means, because "1200 Mbps" next to an
 * address reads as a promise about that address and it is not one. */
function broadbandPanel() {
  const wires = held.broadband;
  const loaded = wires.states || [];
  const where = el("div", {id: "broadbandprogress"});
  const state = el("input", {
    type: "text", id: "broadbandstate", placeholder: "NM", maxlength: 2, size: 4,
    "aria-label": "Which state to download",
  });

  return el("section", {},
    el("h2", {}, "Internet at a property ",
      present(wires.configured && loaded.length, "ready",
              wires.configured ? "no data yet" : "off")),
    el("p", {class: "lede"},
      "Optional. Nothing else here needs an account; this does, because the FCC's map does. " +
      "Every other public service this tool reads is keyless."),

    wires.configured
      ? null
      : el("p", {class: "notice notice-flag"},
          "Two values are needed and " +
          (wires.credential ? "the account name is missing" : "neither is set") +
          ". Set " + (wires.variables || []).join(" and ") + " in your environment, or by hand in " +
          "the .env file beside the database. This page will not write a credential."),

    wires.configured && !loaded.length
      ? el("p", {class: "notice notice-flag"},
          "Signed in, and no state's data downloaded yet. There is no per-property service to " +
          "ask, so this reads the FCC's own published files a state at a time. About fifty " +
          "megabytes and half a minute for a state, and then it is local.")
      : null,

    loaded.length
      ? el("table", {class: "plain"},
          el("thead", {}, el("tr", {},
            el("th", {}, "State"), el("th", {}, "Census blocks"), el("th", {}, "Published"))),
          el("tbody", {}, loaded.map((row) => el("tr", {},
            el("td", {}, row.state),
            el("td", {}, Number(row.blocks).toLocaleString()),
            el("td", {}, row.as_of)))))
      : null,

    wires.configured
      ? el("div", {},
          el("div", {class: "field"},
            el("label", {for: "broadbandstate"}, "Download a state"), state,
            el("span", {class: "hint"},
              "Two letters. Downloading a state you already have refreshes it to the current " +
              "quarter.")),
          el("div", {class: "actions"},
            el("button", {
              type: "button",
              class: "primary",
              onclick: () => {
                const wanted = state.value.trim().toUpperCase();
                if (!wanted) {
                  say("Which state? Two letters, such as NM.", "problem");
                  return;
                }
                start("broadband", {state: wanted}, where, "Downloading " + wanted);
              },
            }, "Download it")),
          where)
      : null,

    el("p", {class: "meta"},
      "What you get is the best advertised residential speed in a property's census block, as " +
      "filed with the FCC. Not a measurement, and not that property's own line: a block can be a " +
      "few houses or a few square miles. Satellite is left out, because it is available almost " +
      "everywhere and would make every rural property look served while telling you nothing."),
    whereToGet(wires.where),
  );
}

function interfacePanel() {
  const named = held.interface.allowed_hosts || [];
  return el("section", {},
    el("h2", {}, "This interface"),
    el("div", {},
      setting("listening on", `127.0.0.1:${held.interface.port}`),
      setting("also answers to", named.length ? named.join(", ") : value(null)),
      setting("database", held.database)),
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
    el("h2", {}, "Write a spreadsheet"),
    el("p", {class: "lede"},
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
    el("div", {class: "actions"},
      el("button", {
        type: "button",
        class: "primary",
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
      }, "Write it")),
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
