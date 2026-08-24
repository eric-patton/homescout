# Design — Browser interface (feat-010)

The one feature in this product that needs a design artifact before a plan, because it is the only
one where the shape of the thing is not implied by what it has to do. Six surfaces, one of them a
table of five thousand rows that has to stay quick, all of it plain HTML and JavaScript that must
still start in five years.

Read `spec.md` first. This decides what the screens are and how they behave; `plan.md` decides how
they are built.

## What was measured first

Two numbers in the requirements decide the whole design of the results table: five thousand rows
interactive within three seconds, and sorting or filtering within two hundred milliseconds without
contacting the server. Whether a plain table can do that is not a matter of opinion, so it was
measured in Chrome before anything was designed, with 5,000 rows of 32 columns of realistic content.

| | rows all in the DOM | only the rows in view |
|---|---|---|
| first render | 60ms | **18ms** |
| DOM nodes | 165,045 | **1,663** |
| sort, then show the result | **3,766ms** | **25ms** |
| filter to 1,355 rows, then show it | 984ms | **39ms** |
| one scroll step | n/a | 56ms |

- **M-1: rebuilding the table on every sort is nineteen times over budget.** Sorting the data itself
  takes half a millisecond. Putting the answer on screen takes nearly four seconds, because a table
  of a hundred and sixty-five thousand elements has to be laid out again. The cost is entirely in
  the DOM, and it is not a matter of writing the loop better.
- **M-2: rendering only the rows in view is comfortably inside every budget**, with a factor of five
  to spare on the tightest one. So that is what the table does, and D-4 is how.
- **M-3: hiding rows instead of rebuilding takes 173ms**, which is inside the two-hundred-millisecond
  budget and has no margin in it, on a machine with nothing else running. It was the tempting middle
  option and it is not taken.
- **M-4: sending the whole result set once is free.** Five thousand rows is 3.45MB of JSON, which
  parses in 18ms. Over a loopback interface the transfer is not worth measuring. That settles AC-7's
  "without a round trip to the server for each interaction" as *the server is asked once*, rather
  than as a caching scheme.

## The six surfaces

One page per surface, served as a file, each with its own small script. Not one application with
routes: six pages, because a page that can be reloaded and bookmarked is the simplest thing that
works, and because a failure on one surface cannot then take the others with it (the reliability
requirement).

| surface | path | what it is for |
|---|---|---|
| Saved searches | `/` | the list, last run, run now, open, duplicate |
| Map and search builder | `/search/<name>` | draw areas and exclusions, set filters and criteria, save |
| Results table | `/results/<name>` | every column, sort, filter, annotate in place |
| Listing detail | `/listing/<id>` | photographs, description, enrichment, timeline, provenance |
| Run comparison | `/changes/<name>` | what changed since any earlier run |
| Merge review | `/matches` | the pairs the tool refused to guess at |

The landing surface is the saved search list rather than the map, because the common daily act is
"what happened overnight" and the rare act is "define a new area".

## D-1: the server is a thin translator, and it is provably thin

Every endpoint does one thing: read the request, call one function in `homescout.api`, and serialize
the answer. No endpoint reads the store directly, and no endpoint decides anything.

That is non-negotiable 8, and AC-14 asks for it to be tested rather than promised. It is tested two
ways: a source scan asserting that nothing in the web package imports `homescout.store`,
`homescout.runner`, `homescout.rules` or `homescout.export`, and a behavioural test performing each
action through the HTTP surface and again through `api` directly and comparing the resulting
database.

The practical consequence is that a capability missing from `api` is a capability this interface
cannot have, which is the right way round: it means the command line gets it too.

## D-2: the wire format is the one this product already speaks

Every endpoint answers with the same envelope `homescout.digest.envelope` already produces for
`--json`, and mostly with the same documents. The results table reads the same shape a digest
carries; the comparison surface reads a comparison; the merge queue reads what `matches list`
returns.

One shape, already tested, already what an automated caller sees. A second serialization of the same
things is a second place for them to drift.

## D-3: nothing from a source or a note is ever markup

Every value that came from a listing site or from something a person typed is put on the page with
`textContent`, never with `innerHTML`. There is no template string that interpolates data into
markup anywhere in this feature, and a source scan asserts it, because the way this rule breaks is
one convenient `innerHTML` in a function that builds a badge.

The security requirement says listing text is rendered as text and never as markup. This is that,
made structural: there is no path from data to markup to accidentally take.

The one place a value becomes something active is a link, and its target is checked the way the
digest and the spreadsheet already check one: `http` and `https` only.

## D-4: the results table renders the rows in view and nothing else

Forced by M-1 and M-2. The whole result set lives in JavaScript as an array of plain objects; the
DOM holds only the rows visible in the scrolling area plus a few above and below.

- **Sorting and filtering happen on the array**, which is half a millisecond, and then the visible
  window is drawn again, which is twenty-five.
- **A spacer element carries the full height**, so the scrollbar is honest about how many rows there
  are, which is what makes this different from pagination. The spec says so explicitly: this
  requirement "is not satisfied by silently paginating away rows the user asked to see".
- **The count is always visible**: how many properties the search holds, how many the filter kept,
  and how many are hidden as disappeared.

The columns are the export's columns, read from the same declaration (`homescout.export.columns`),
so the table and the spreadsheet cannot disagree about what a column is called or where its value
comes from.

## D-5: an inline edit is a form that never lies about what was saved

The rule the spec is most specific about, and the failure it names is the important one: a person
must never be left believing an edit was recorded when it was not.

1. A cell for rank, verdict, red flags, summary, next step or notes becomes editable in place. Enter
   or moving away commits; Escape restores.
2. The row shows **saving**, then **saved** with the time, or **not saved** with the reason.
3. **A failed save keeps the typed value in the field**, marks the row, and leaves it editable.
   Nothing is discarded, and the row is visibly different from a saved one in text as well as in
   colour (AC-18).
4. The response carries the annotation as the store now holds it, and the row takes its values from
   that rather than from what was typed. That is what makes the two-tabs edge case behave: the
   second tab's next save shows it the current value rather than silently keeping a stale one.

There is no autosave timer and no debounce. An edit is committed by an action the person took, and
the reason is that a timer that fires while somebody is typing produces half-written judgment, which
is the one thing non-negotiable 7 says this tool cannot lose.

## D-6: the map draws, and the library is vendored with its fingerprint recorded

The constitution names Leaflet and Leaflet.draw, and AC-16 says the served assets are the files as
committed, which together mean the library is vendored rather than fetched from a content network at
page load. A personal tool that stops working when a CDN reorganizes is exactly what the
five-year rule is about, and a localhost tool that needs the internet to draw a polygon is worse.

So `web/vendor/` holds the library files, and beside them a manifest recording each file's SHA-256,
its version and where it came from. A test verifies the files against the manifest, which is the
provenance a lock file gives every other dependency in this project and which hand-vendored
JavaScript usually has none of.

**The files are committed**, 255KB of them, because AC-16 says the served assets are the files as
committed and because a tool whose map needs a working internet connection in five years is exactly
what the five-year rule is about. Leaflet is BSD-2-Clause and Leaflet.draw is MIT; both licences are
committed beside them.

The map surface still checks for the library at load and says so plainly if it is not there, which
costs nothing and means somebody who deletes the directory gets a sentence rather than a blank
rectangle.

What the map surface does with the library:

- Draw a polygon, name it, and mark it as an area or an exclusion. Exclusions render differently and
  are labelled, never distinguished by colour alone.
- Add a city, county, ZIP or radius by name, which needs no drawing at all and is the common case.
- A polygon that crosses itself is refused as it is drawn, with the reason, rather than saved and
  failed at run time. The check is the one `search.geometry` already has, so the answer here and the
  answer at run time are the same answer.

## D-11: no authentication, and therefore a guard against the browser itself

The constitution says there is no authentication, single user, localhost only. That settles who may
use this. It does not settle **what may use it**, and the gap between those two is the classic hole
in every tool that serves an unauthenticated API on a loopback port.

Any web page the person visits, in any tab, can send a request to `http://127.0.0.1:8765/`. The
same-origin policy stops that page reading the answer; it does not stop the request happening. A
`POST` that deletes a saved search does not need its response read to have done the damage. And a
hostile domain that resolves to `127.0.0.1` can read the answers too, because to the browser it is
then a same-origin request.

Neither of those is an authentication problem and neither is fixed by adding a password. Three
checks fix both, cost nothing, and are invisible in ordinary use:

1. **The `Host` header must name a loopback address.** A page on `evil.invalid` that resolves there
   still sends `Host: evil.invalid`, so this is what stops DNS rebinding.
2. **An `Origin` header, when present, must be this server's own.** A cross-site request carries the
   attacker's origin; the interface's own requests carry ours.
3. **Every request that changes something must carry `X-Homescout: 1`.** A form submitted by a
   hostile page cannot set a custom header without a preflight, and a preflight is refused by 1 and
   2. Reads do not need it.

A request that fails any of them is refused with a message saying which, so the failure mode is a
sentence rather than a mystery.

## D-12: the map's background is configuration, and it is empty by default

A tile server is a third party, and asking it for tiles tells it which part of the world is being
looked at. `product-global.md` lists exactly four kinds of outbound traffic this product makes, and
a tile server is not one of them.

So there is no tile source by default. The map draws areas, exclusions and property markers over a
plain background with a scale and a coordinate readout, which is enough to place and adjust a shape
somebody already knows. `HOMESCOUT_MAP_TILES` turns a background on, taking a tile URL template, and
the surface says in one line what that means before anybody sets it: the viewport is sent to whoever
serves those tiles.

The same shape as every other optional outbound thing here (the extraction model, the broadband
token, the mail account): absent by default, a person's decision, and stated rather than assumed.
If the tiles should be on by default one day, the sentence in `product-global.md` has to change
first, and changing it is a decision about the whole product rather than about this screen.

## D-7: a saved search edited here is the same file, and the parts nobody touched are untouched

AC-3 is the criterion that decides whether a person can trust this at all, because a file they wrote
by hand carries comments, ordering and formatting that mean something to them.

The interface never writes YAML. It calls `api.edit_search` with the specific values that changed,
and the round-tripping document layer that saved searches already has does the writing. That layer
exists precisely for this and already keeps comments and ordering; using anything else here would be
building a second, worse one.

The consequence worth stating: **this interface can only change what `api.edit_search` can change.**
A part of a definition it cannot edit is a part it shows read-only and says so, rather than
rewriting the file around it.

## D-8: what a missing value looks like

AC-10 asks for a missing value to be visibly different from a known negative, which is the whole
product's rule arriving on a screen. Three states, three appearances, all of them text:

| state | shown as |
|---|---|
| known | the value |
| known to be absent | the value, which is the word `none`, in the ordinary style |
| nobody determined it | an em-space and the label `not known`, dimmed, and never blank |

A blank cell is deliberately not used for "not known", because a blank cell reads as an empty string
somebody could have filled in, and because in a wide table a run of blanks reads as a broken column.

## D-9: keyboard operation is the primary path, not an accommodation

AC-17 asks for every surface to be fully operable by keyboard. The table is where that is hard and
where it is designed rather than tested for afterwards:

- The table is a grid with roving focus: arrows move between cells, Home and End go to the ends of a
  row, Page Up and Page Down move by a screen, and the windowed rendering keeps the focused cell in
  the DOM when it scrolls.
- Enter on an editable cell starts editing; Enter commits; Escape cancels; Tab commits and moves.
- The merge review decisions are buttons in the tab order with real labels, not icons.
- Every surface has a skip link and one visible focus style that is not a colour change alone.

## D-10: what a run looks like while it is happening

A run takes minutes, because politeness is a requirement. So starting one from the list surface does
not block a page:

- The run is started, and the page polls a status endpoint that reports what the run's own progress
  callback reports, which is the same text the terminal prints.
- **The results table always shows the last completed run**, and says a run is under way when one
  is. It never shows a half-written one, which the store's own design already makes possible: an
  incomplete run is not a comparison baseline and its snapshots are not the latest completed state.
- A failing source shows as a failing source, with the run still counted as having happened, which
  is what the whole product means by degraded.

## D-11: what this feature does not own

- **Any decision.** Merging, criteria, geography, extraction, export: all of it is called, none of
  it is reimplemented.
- **Authentication.** There is none by design, which is why there is a bind address and why it is
  tested.
- **Anything that is not localhost.** The server binds to `127.0.0.1`, and a test asserts a
  connection to a routable address is refused rather than trusting the default.

## Open questions

None. Two things are worth a human's attention and both are decisions recorded rather than
questions: D-6 commits 255KB of third-party JavaScript with its fingerprints, and D-12 leaves the
map's tile background off until somebody turns it on.
