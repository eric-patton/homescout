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

## Design decisions: the list is what you watch (`changes/the-list-is-what-you-watch/`)

- **Paused stays on the list; archived and deleted leave it.** The three states were treated as one
  kind of "set aside" and they are not. A pause is a search somebody is still watching and means to
  come back to within the month, so a pause that made the search vanish is a pause nobody would
  use. Archived is "not watching this at all", deleted is "no longer a saved search". The line is
  drawn at whether the person still expects to see it in the morning.

- **The set-aside surface is not offered when there is nothing set aside.** The archived toggle it
  replaces had the opposite property and had to: it stayed on screen after the last archived search
  came back, because otherwise the state it held would have had no control left to turn it off. A
  link to a page is not a state, so it can simply be absent.

- **Discarding is core, not browser.** It could have been a route that unlinked a file, and then the
  command line would have had no way to do a thing the browser can, which product invariant 5 and
  AC-22 both rule out. The operation lives in `api.py` with the other five and both surfaces call
  it.

- **Two steps, and the first one is the safety.** Discarding refuses a search that is not already
  deleted. That is what keeps the irreversible operation away from the list of live searches
  entirely: to lose a definition somebody has to delete it, go to another surface, and type its
  name. Rejected the alternative of a single "delete permanently" on the card, which puts an
  unrecoverable action one mis-aimed click from a reversible one.

- **The confirmation is the name typed, not a second button.** This interface already has a
  two-press confirmation on the card (press Delete, then press "Yes, delete X") and a dialog for
  passing a house, and both are right for what they guard. Neither is enough here. Typing the name
  is the only confirmation shape that cannot be got through by reflex, and this is the only
  operation in the product that needs one.

- **What survives is said before the decision.** Above the buttons, not under them. The whole risk
  of this operation is somebody believing it removes their run history, and a sentence that
  reassures them after they have decided is a sentence that arrived too late to be reassurance.

- **The name resolves through `safe_path`, and this is the finding that held the gate.** The strict
  name rule and the containment check, exactly as `create`, `delete` and `duplicate` already use
  them, and never a glob pattern built from the name. `restore` next door does the latter, and a
  pattern with `..` in it matched a file two directories up on this workspace's own interpreter.

  `restore` comes to no harm from it, and that is why this is a design decision rather than a
  footnote. The name check that would reject an escaping name runs after the search rather than
  before it, to work out where the file is going, and it refuses before anything moves: measured,
  no file can be moved or removed through `restore` by any name at all. The function is saved by
  the order its two checks happen to fall in. That protects the function and says nothing about the
  pattern, and the pattern is what the next author copies. A permanent removal copying it has
  nothing downstream to be saved by.

- **The typed name and the request guard are two different jobs.** The dialog protects the person at
  the keyboard from removing the wrong search by reflex. The host, origin and header check on the
  request is what protects the route from a page on another origin, and it already covers `DELETE`
  along with every other write. Recorded because the proposal's own sentence about typing the name
  reads, to a hurried implementer, as though it were the security boundary. It is not, it cannot be,
  and a server with no authentication is exactly where that misreading is expensive.

- **The precondition is the server's fact, not the page's memory.** Whether the search is really in
  the deleted state is read from the catalogue inside the request that removes it, and no flag the
  browser sends about it is accepted. The workspace lock already serialises every request that
  touches the database, so nothing races today. This is written so that a later change to that lock
  cannot silently make the only irreversible operation in the product the one that races.

## Design decisions: like with like (`changes/like-with-like/`)

- **The map is renamed and the layer is not.** "Fire" was never wrong about the hazard layer, it was
  wrong as the name of the surface. The legend still says wildfire hazard potential, the criterion
  namespace still has `wildfire_hazard`, and the enrichment field keeps its name. Only what a person
  is invited to click changes.

- **Grouping, not hiding.** Every group is open and named. The temptation with eleven controls is a
  menu, and a menu is how the column chooser's predecessor became a feature that had to be asked for
  twice because nobody could find it. Naming three groups costs one line of vertical space and
  removes the need to read eleven labels to find one.

- **One field, one control.** "Show passed" and "only kept" both narrow by judgment, and holding
  them as two booleans forced `apply` to order them so they could not contradict each other. That
  ordering is a comment explaining why a state the controls can express is not a state the table
  can be in, which is the shape of a control set that is wrong. Four answers, one in force.

- **"Show gone" stays separate.** Judgment and presence are two different facts about a property and
  folding them into one control would produce answers like "kept, including ones that are off the
  market" that read as nonsense. It moves into the filter bar with the others; it does not merge.

- **Totals in one place, reasons in the other, and the old line was both at once.** "159 of 951
  properties, 67 disappeared and hidden, 737 passed and hidden, 8 kept, 67ms" is two different kinds
  of fact in one sentence. How many there are is a total and nobody can act on it. Why some are
  missing is a reason and every one of them is something a person might want to undo. So the totals
  stay in a line under the controls, shorter: how many are drawn, out of how many the run found, and
  how many are kept. Every reason moves into the bar carrying its own number and its own control to
  lift it. Nothing is said twice, which was the risk in the alternative of keeping the line intact
  and adding the bar above it.

  The rejected alternative was letting the bar absorb the totals as well. It reads cleanest and it
  breaks on the one number that is not a filter: "159 of 951" cannot be lifted, so as a chip it is
  either a control that does nothing when pressed or a number with nowhere to live.

- **The render time goes.** It sat in the middle of the totals line and it is a number for whoever
  is writing this table rather than whoever is reading it. Worth saying out loud because removing
  something visible is the kind of change that gets quietly reverted by somebody who assumes it fell
  out by accident.

- **The per-search navigation is built once in `common.js`.** Five copies is how the search builder
  ended up reaching none of the other four surfaces: each page grew the links its author needed
  that day. One builder, called by every surface that is about a search, and a surface added later
  appears on all of them at once.

- **The listing page's way back is to where it came from, not to a search.** A property can appear
  in several saved searches, so "back to the search" has no single answer. What it has is the table
  the reader arrived from, which is a fact about this visit rather than about the property.

## Design decisions: not forty-three columns (`changes/not-forty-three-columns/`)

- **The views live in the browser, and that follows from AC-45 rather than from convenience.** The
  arrangement of this table is a view preference that is never written to the workspace, so that two
  people reading one workspace arrange it independently. A view is the same kind of thing: the
  opening arrangement. Putting the lists in the core would make one person's idea of "deciding"
  everybody's, and would make adding a view a release.

- **A view is a list of column names, not a list of positions or a filter over origins.** Names,
  because that is what the arrangement already remembers and what survives a release that adds a
  column. Not origins, because the useful views cut across them: deciding with a house means its
  price, which the listing reported, and its wildfire hazard, which is public data, and the verdict
  written on it. An origin-shaped view would be a view of the data model rather than of the job.

- **The remembered arrangement wins, and that is the load-bearing decision here.** Everything else in
  this change is reversible in one press; overwriting an arrangement somebody spent an afternoon on
  is not. So the view decides only what a table nobody has arranged yet opens on. It also means the
  change is invisible to anybody who has already arranged this table, which is the right blast
  radius for a default.

- **What is stored is the resulting set of columns; the view's name is a label on it.** Two plausible
  implementations here produce opposite behaviour and only one is right, so it is written down.

  A view is *applied*, meaning it computes which columns are hidden, at exactly two moments: when
  nothing is remembered at all, and when a person picks one. It is never recomputed from its name on
  a later load. The stored hidden set is authoritative and the name only says where that set came
  from.

  The alternative, storing the name and deriving the set on every load, breaks twice. Somebody who
  hides one column of the twelve would come back to the other thirty-one reappearing, because the
  view would be reasserted around the single thing they wrote down. And a release that changed what
  Deciding contains would silently rearrange a table somebody was already using, which is the thing
  "the remembered arrangement wins" exists to prevent.

  This falls out of how `remember()` already works: it writes the whole hidden set on every save
  rather than a delta. The name is one more key beside it.

- **A stored arrangement with no view name is somebody's existing arrangement, and is left alone.**
  Anybody who used this table before this change has an order and a hidden set stored and no view.
  Reading that as "no view, so apply the default" would rearrange exactly the people this decision
  is protecting. It reads as Custom.

- **The five groups are the origins the columns already declare**, in the same order the table's own
  `ORIGINS` table lists them: `listing` is reported by the listing, `derived` is worked out by this
  tool, `extracted` is read out of the description, `enriched` is public data about the place, and
  `annotation` is yours to write in. The words are read from the same declaration the heading
  tooltips read rather than written out again here.

- **Deviating leaves the view rather than fighting it.** Hide one column and the control says Custom.
  The alternative, a view that reasserts itself, is a control that undoes what the person just did,
  and the two ways of hiding a column would have to agree about it or one of them would be lying.

- **Three, and named for the job rather than for the data.** Deciding, Hazards, Everything. Hazards
  exists because it is what this household is actually filtering for and the reason the enrichment
  pass exists at all; without it "the public data" is a group in a chooser rather than a way of
  reading the table. A fourth would need somebody to want it.

- **The chooser's groups are the core's words, read from the same declaration the heading tooltips
  read.** Two sets of words for five origins is how a chooser comes to call something "public data"
  while the tooltip over the same column calls it something else, and nothing on the page would ever
  say that had happened.

## Design decisions: the last three changes together

These were written as one pass over what was left of a reading of the whole interface, so the
decisions that cut across them are here rather than repeated three times.

- **Four totals stay four.** Collapsing them to one number would mean picking one screen's question
  and answering it on screens that are not asking it. What was wrong was never the arithmetic; it
  was one noun on four different populations, which is how four correct numbers read as a fault.

- **A property with no address is named once, in the shared file.** Four surfaces name a property,
  and four copies of "what to call this one" is how one of them keeps printing a hexadecimal string
  after the other three stopped. The identifier is kept everywhere it already is: it is exact, it is
  how the property is asked for again, and it is the thing to quote when something is wrong. It is
  not the thing to lead with.

- **A disclosure rather than deletion, and open on the first visit.** The instructions are worth
  having and worth having once. Remembered per browser, like every other view preference on this
  surface and for the same reason: it is about this person's screen and not about the workspace.
  What goes behind one is what is identical on every visit; a sentence that changes with the state
  of the thing it is about stays where it is.

- **Settings and tools split along "set once" against "come back to".** The navigation has named
  both since the settings surface existed. The line is not what a section is about but how often
  somebody is on it: the model's address is set once and then reports itself, and asking the model
  about descriptions is a thing to run this week and again next week.

- **A zero is drawn.** A tile appearing is harder to notice than a number changing, and the strip's
  whole job is answering "is there anything for me today". A figure that does not apply to this
  installation at all stays absent, because "none today" and "this does not happen here" are
  different answers and a zero would say the wrong one.

- **A batch judgment is one core operation, not forty browser writes.** Product invariant 5 puts it
  in the core so both surfaces reach it, and the failure mode decides the shape: forty separate
  writes is forty chances to stop half way with nothing recording which half. One call, one answer,
  one count of what changed.

- **The reason is written to every property in the batch.** A reason typed at the moment forty
  houses were ruled out is as true of each of them as a reason typed on one, and the alternative,
  storing it once against the batch, would invent a second kind of annotation with its own answers
  for merging, unmerging and re-export. The annotation already has those answers.

- **The builder keeps four save buttons.** They write four genuinely different parts of a
  definition, and one button over all of them would write parts nobody touched, which AC-3 forbids
  by requiring that a definition opened and re-saved here is unchanged apart from the edits made.
  The fault was never the four buttons; it was that nothing said which panel was dirty, and the
  lede apologised for it instead.
