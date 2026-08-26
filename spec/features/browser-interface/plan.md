# Plan — Browser interface (feat-010)

Read `spec.md`, then `design.md`. The design decided what the screens are and how they behave; this
decides how they are built.

## What was measured first

In `design.md`, in full: 5,000 rows of 32 columns in Chrome, comparing a table whose rows are all in
the DOM against one that renders only what is in view. The short version, because it is the single
most consequential number in this feature:

> Sorting five thousand rows takes half a millisecond. Putting the answer on screen takes **3,766ms**
> if every row is in the DOM and **25ms** if only the visible ones are. The budget is 200ms.

Two more that shape the plan:

- **Sending the whole result set once is free**: 3.45MB of JSON, parsed in 18ms, over a loopback
  interface. So the table is served once and every interaction after that is local, which is AC-7
  exactly.
- **The dependency cost is fourteen packages.** `fastapi` plus `uvicorn` pulls in starlette,
  pydantic and their own dependencies. The constitution names FastAPI, so that is settled, but it is
  worth stating: this feature roughly doubles the installed footprint of the tool.

## Design decisions

### D-1: layout

A new package, `src/homescout/web/`, above everything and importing almost nothing.

| file | holds |
|---|---|
| `web/app.py` | the application: routes, and nothing else. |
| `web/wire.py` | turning what `api` returns into the documents the pages read. |
| `web/serve.py` | starting it, bound to loopback, with the port and the address as parameters. |
| `web/static/*.html` | one file per surface. |
| `web/static/*.js` | one script per surface, plus `common.js` for what they share. |
| `web/static/app.css` | one stylesheet. |
| `web/vendor/` | the map library, committed, with a manifest of fingerprints. |

`web/app.py` imports `homescout.api` and `homescout.digest` and nothing else from this product. That
is checked by a source scan rather than promised (D-1 in the design).

### D-2: the endpoints, and what each of them calls

Every one is a translation. The right-hand column is the whole of the endpoint's body.

| method and path | calls |
|---|---|
| `GET /api/searches` | `api.list_searches`, plus `api.show_search` per name for the summary |
| `GET /api/searches/{name}` | `api.show_search`, `api.validate_search` |
| `POST /api/searches/{name}` | `api.edit_search` |
| `PUT /api/searches/{name}` | `api.create_search` |
| `POST /api/searches/{name}/run` | `api.run_search`, in a thread, reporting progress |
| `GET /api/runs/{search}/status` | the progress of a run started here |
| `GET /api/results/{name}` | `api.results` (new, see D-3) |
| `GET /api/listings/{id}` | `api.listing` (new) |
| `GET /api/listings/{id}/image` | `api.preview_image` (new), served as bytes |
| `POST /api/listings/{id}/annotation` | `api.annotate` |
| `GET /api/changes/{name}` | `api.changes` |
| `GET /api/matches` | `api.pending_matches` |
| `POST /api/matches/{id}` | `api.resolve_match` |
| `GET /api/areas`, `POST /api/areas` | `api.area_notes`, `api.set_area_note` (both new) |

### D-3: five capabilities are missing from the core, and they are added there

The interface needs things no surface has needed yet. They go in `homescout.api`, not in `web`,
because non-negotiable 8 says both surfaces are thin wrappers over one library and because product
invariant 5 says every capability is reachable from both.

| new in `api` | why |
|---|---|
| `results(workspace, name)` | the table's rows: the latest completed run's results with their flags |
| `listing(workspace, id)` | one property's full picture: snapshot, history, events, sources, enrichment, extraction, annotation |
| `preview_image(workspace, id)` | the stored thumbnail, as bytes and a content type |
| `area_notes(workspace)` and `set_area_note(...)` | AC-19, and the export's second sheet already reads them |
| `run_status(...)` | what a run started elsewhere is doing |

**Invariant 5 means the command line gets two of them too**, or this feature has quietly made the
browser the only way to do something. `homescout show <listing-id>` prints one property's full
picture, and `homescout areas` lists and writes area notes. Both are small, both are the terminal
half of a capability this feature introduces, and leaving them out would be the first violation of
that invariant in the product.

### D-4: the table holds the data and the DOM holds the view

M-1 and M-2 in `design.md`. Concretely:

- `results.js` fetches once, keeps the rows as an array, and never fetches again for a sort or a
  filter.
- A scrolling container, a spacer whose height is `rows × 22px`, and a `<tbody>` translated to the
  right offset holding about sixty rows.
- Sort is `Array.sort` on the array and a redraw of the window. Filter is `Array.filter` and the
  same.
- The columns come from `homescout.export.columns`, served as part of the results document, so the
  table and the spreadsheet cannot disagree about what a column is called.

The one thing this costs is that the browser's own find-in-page only sees the rows in view. That is
a real loss and the mitigation is the filter box, which is faster than find-in-page anyway and finds
things below the fold, which find-in-page in a scrolled container does not reliably do.

### D-5: no data ever becomes markup

Stated in `design.md` as a rule; here is the mechanism. `common.js` has exactly one way to build an
element:

```js
el("td", {class: "value"}, text)   // text goes in via textContent, always
```

There is no `innerHTML` anywhere in `web/static`, no template literal that produces markup, and a
test asserts both by scanning the served files. A listing description containing `<script>` is a
listing description containing the characters `<script>`, and that is a property of there being no
path to anything else rather than of anybody escaping correctly.

### D-6: the map library is committed, with its fingerprint

Fourteen files, 255KB: Leaflet 1.9.4 (BSD-2-Clause) and Leaflet.draw 1.0.4 (MIT), their stylesheets,
the images their toolbars need, and both licences. `web/vendor/manifest.json` records each file's
name, version, source URL and SHA-256, and a test verifies the bytes against it.

That manifest is the point. Hand-vendored JavaScript usually has worse provenance than any other
dependency in a project; this has the same provenance a lock file gives, and the check runs in the
ordinary test suite rather than in somebody's memory.

The two alternatives are both worse. Fetching from a content network at page load makes a localhost
tool need the internet to draw a polygon, and breaks AC-16's "the served assets are the files as
committed". Leaving the directory empty for the person to fill makes the map broken out of the box
for a library the constitution already names as the stack.

The surface still checks at load and says so in plain text if the files are missing, which costs
nothing and turns a deleted directory into a sentence.

### D-7: a run is started in a thread and polled

`api.run_search` takes minutes because politeness is a requirement, and an HTTP request that takes
minutes is one a browser gives up on.

So `POST /api/searches/{name}/run` starts the run in a thread, returns immediately with a token, and
`GET /api/runs/{search}/status` reports what the run's own `progress` callback has said, plus the
outcome when it finishes. The progress text is the same text the terminal prints, because it is the
same callback.

**The store's own claim mechanism is what stops two runs colliding**, not a lock in this layer: a
run started here while one is running from a terminal is refused by the core with the message the
core already has, which is also the store-is-locked edge case answered in the same place.

### D-8: what the pages are, as files

Six HTML files, six scripts, one stylesheet, one shared script. Served by FastAPI's static file
handling from the package directory, so `homescout serve` works from an installed wheel and not only
from a checkout.

AC-16 says a test asserts the served assets are the files as committed. It does: it requests each
one and compares the bytes to the file on disk. There is no build step to fail to run, and that is
the point of the whole constraint.

### D-9: keyboard operation, and how it is tested

Designed in D-9 of `design.md`. Tested three ways, because "fully operable by keyboard" is not one
assertion:

- **Structurally**: every interactive element is a real control (`button`, `a`, `input`,
  `select`) or carries an explicit `tabindex` and role, asserted by parsing the served HTML.
- **In a browser**: the results table is driven with keys alone through Chrome, from focusing the
  grid to editing an annotation and committing it, and the store is checked afterwards.
- **Nothing by colour alone**: every badge, status and difference event carries a text label,
  asserted by parsing what the scripts produce for a known document.

### D-11: the guard against the browser, and where it lives

`design.md` D-11 says why. Here is where: one middleware in `web/app.py`, ahead of every route, and
one test file that tries each attack.

```
Host must be 127.0.0.1:<port> or localhost:<port>      -> stops DNS rebinding
Origin, if sent, must be this server's own             -> stops a cross-site request
X-Homescout: 1 on POST and PUT                         -> stops a form post from a hostile page
```

The header is set once in `common.js`'s fetch helper, so no page has to remember it. A refusal names
which check failed, because a person who has changed the port and cannot work out why nothing saves
deserves a sentence rather than a 403.

### D-12: the tile background is a setting, and the default is none

`design.md` D-12 says why: a tile server is outbound traffic to a third party and
`product-global.md` lists four kinds of outbound traffic, none of which is that.

`HOMESCOUT_MAP_TILES` holds a tile URL template and an attribution string. Unset, the map draws over
a plain background with a scale bar and a coordinate readout, and one line of text says what a tile
source would add and what it costs. Read through the same `.env`-and-environment loader the digest
and the extraction model already use, so there is one place to look for every setting in this
product.

### D-10: what this feature does not own

- **Any decision.** The endpoints call `api` and serialize. Six of the fourteen are one line.
- **A design system.** One stylesheet, system fonts, and no dependency.
- **Authentication.** There is none by design (the constitution), which is exactly why the bind
  address is tested rather than assumed.

## Verification approach

- **The thinness is a source scan**, not a promise: nothing in `web` imports the store, the runner,
  the rule engine or the export.
- **Every action is performed twice**, once through HTTP and once through `api`, and the resulting
  database is compared table by table. That is AC-14 and it is the only way to check "no business
  logic here" behaviourally.
- **The bind address is tested against a routable address**, not read out of a constant.
- **The served bytes are compared to the committed files.**
- **The table is measured in a real browser** at 5,000 rows, against the three-second and
  two-hundred-millisecond budgets, the same way the design's numbers were produced.
- **An inline edit is driven by keyboard in a real browser**, and the annotation is read back from
  the store.
- **A failing save is forced** by making the core refuse, and the row is checked for the typed value
  still being there and for the row not claiming to be saved.
- **A hostile description** containing markup is served to the results table and the detail surface,
  and the page is checked for it having become an element.
- **The browser guard is attacked**: a request with a rebinding `Host`, one with a foreign `Origin`,
  and a mutating one with no custom header, each refused and each naming which check refused it.
- **The vendored files are verified against their manifest**, byte for byte.
- **An annotation written here appears in the spreadsheet export's second sheet**, which is AC-19's
  claim about two features agreeing and is the only place it can be checked.

## Design decisions — passing a house (`changes/pass-a-house/`)

- **The judgment is an annotation, not a new kind of state.** It could have been a column on the
  listing, and that would have been a second kind of user-written data with its own answers for what
  happens across a merge, an unmerge and a re-export. The annotation already has all three answers
  and they are tested (listing store AC-15 to AC-17). One migration on `annotations`, one entry in
  `ANNOTATION_FIELDS`, and the permanence comes free.

- **Three states, and the third is the absence of the other two.** `keep`, `pass`, and nothing.
  Nothing means nobody has decided, which is not the same as deciding to keep: the first is most of
  a fresh run and the second is a house somebody looked at. Storing undecided as a value rather than
  as an absence would mean writing an annotation to every property a run ever saw, which breaks "an
  annotation is written only by a person".

- **Hiding is the existing pattern, used twice.** The table already hides disappeared listings
  behind a checkbox and reports the number hidden. This is that, with a second predicate. The count
  line is not decoration: a table quietly shorter than the run that filled it is how somebody
  concludes a market has nothing in it.

- **The same control passes and un-passes.** Setting the judgment to the value it already holds
  clears it. One control, no separate undo, and no way to end up looking at a menu to find how to
  reverse something you did by accident.

- **A criterion still cannot name it.** Rejected deliberately, and recorded here because it is the
  kind of decision that gets quietly reversed later by somebody adding one convenient field to the
  namespace. A criterion is the tool's test over what it observed; an annotation is the person's
  conclusion. Feeding the second into the first makes a search that agrees with you because you told
  it to.

- **Merge takes the union.** If either constituent was passed, the merged record is passed. The
  alternative loses a decision on a technicality nobody would accept: the tool noticing that two
  records were one house does not mean you changed your mind about the house.

- **The core decides what is hidden; the surfaces only render it.** Held by the pre-build check as a
  blocking finding against non-negotiable 8, and worth recording because the first draft got it
  wrong in an ordinary way: the filter went in the browser, and the command line was given its own
  task to do the same thing. Two implementations of one decision, in two languages.

  So `results` marks each row with what the core decided, and both surfaces honour the mark. The
  browser still receives every row and toggles locally, so the checkbox stays instant, but "passed
  means hidden unless asked" is written once. The existing "show gone" toggle is the counter-example
  that made this easy to get wrong: it filters in the browser, and has never had a second surface to
  disagree with it.
