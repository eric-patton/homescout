---
schema_version: 2
id: "feat-010"
slug: "browser-interface"
title: "Browser interface"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-004, feat-006, feat-007, feat-008]
requires_design: true
readiness:
  research: ready
  design:   ready
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:d720d6d2ec75"
  constitution_hash: "sha256:d73230560d0f"
converge:
  last_run: 2026-08-25
  open: 4
  contradicts: 0
human_signoff: []
open_decisions:
  - id: "od-1"
    description: "Does the map's address change with its name, /fire/{name} to /map/{name}? Resolved 2026-08-29: yes, and the old address keeps working. The page moves to /map/{name} and /fire/{name} answers with a permanent redirect to it, so the address matches the name and no bookmark made from a phone breaks silently. Recorded in changes/like-with-like/ AC-71 and built by T171."
    owner: "eric-patton"
    resolved: true
overrides: []
extends: []
---

# Feature notes — Browser interface

## Scope

Nine screens on localhost: the search builder with polygon drawing, the saved search list, the
results table with every column and inline-editable annotations, the listing detail with photos
and enrichment and merge provenance and a price timeline, the run history diff, the merge review
queue, the map, the settings surface, and the surface holding what has been set aside. Five when
this was written; the rest arrived as recorded changes below.
Editing annotations directly in the table is what makes this replace the spreadsheet rather than
merely produce one. Plain HTML and vanilla JavaScript, no framework, no second build toolchain.

Brief section 8. This is the one feature that requires a design artifact.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Changes recorded here

- **2026-08-24, notes for the model (feat-009, `changes/model-notes/`).** Two boxes. The settings
  page gained "What you want the model told", for the installation's note; a search page gained
  "Notes for the model, for this search". Both say, above the box rather than below it, that the
  text is sent to the model with every description and that it cannot add a field or a new answer.

- **2026-08-24, a defect found while building that.** The criteria box on a search page was drawing
  empty on a search that had criteria, and the "Save the criteria" button under it built its request
  from that box. A search with three rules showed none, and one click would have written the empty
  box back over them.

  The cause was in the element builder every page shares: a textarea holds its text as content
  rather than in an attribute, so building one with `value=` set an attribute nothing reads. Fixed
  in `common.js` rather than at the one call site, because the next textarea would have inherited
  it, with a regression test in the real-browser suite asserting a textarea built by that helper
  holds its text.

- **2026-08-24, broadband from the FCC's own files (feat-007, `changes/broadband-from-the-fcc-files/`).**
  The settings page's broadband panel became a real one: which states are held and which quarter,
  a box to download another, and the sentence that has to travel with the number. It says the figure
  is the census block's advertised service rather than the property's measured line, and says why
  satellite is left out, because "1200 Mbps" beside an address reads as a promise about that address
  and is not one.

- **2026-08-25, location enrichment (feat-007).** The listing page's "Where it is" section gained a
  renderer of its own for the wildland-urban interface value, and a sentence explaining it, in the
  same place and for the same reason the broadband speeds already have one.

  The bug it fixes was live in this feature's own code path rather than in enrichment's: the shared
  value renderer turns `null` into "not known, nobody determined this". For every other enriched
  field that is correct. For this one the known negative *is* `null`, so the browser would have said
  nobody checked about a place that was checked. The criterion builder is unaffected and needed no
  change: it reads the rule namespace over the API, so the new field and its values appeared there
  on their own.

- **2026-08-29, what you set aside has a page (`changes/the-list-is-what-you-watch/`).** A saved
  search can be in four states and the list showed all four. Archived and deleted ones move to a
  surface of their own, each shown as what it was rather than as a name on a button, and the list
  holds what is being watched. A deleted search can finally be discarded for good, which was
  previously impossible: the file was kept forever and nothing removed it, so the strip at the foot
  of the list only ever grew. It is the only operation here that removes a file, so it is the only
  one that asks for the name to be typed, and it says what survives before it is confirmed.

  The pre-build check held this one on a security finding, and the finding was not about the new
  code. Asked what the permanent removal would be written next to, it found that restoring a search
  built a glob pattern out of the raw name while every other operation on a saved search resolved
  through the strict name rule, and a pattern with `..` in it walks out of its own directory.
  Nothing could actually be moved by it: the name check runs after the search and refuses before
  anything happens. It was saved by the order its checks fall in, which protects that function and
  not the pattern, and the pattern was about to be copied into the one function that deletes. Fixed
  in the defect lane, with a regression test that reads why the name was refused, because the first
  version of that test passed against the unfixed function.

- **2026-08-29, like with like (`changes/like-with-like/`).** The map is called the map, and moved
  to an address that says so with the old one still answering. The results toolbar is three named
  groups rather than eleven controls in a row. Two checkboxes over the judgment became one control
  with four answers. Every reason a row is missing is in the bar above the table with the number it
  is holding and its own control to lift it, which is what that bar was built for and what it was
  built without: 737 of 951 rows were held back by the judgment and the bar was empty. Every screen
  about a search now offers the others, built once rather than five times, which is how the search
  builder came to reach none of them.

- **2026-08-29, not forty-three columns (`changes/not-forty-three-columns/`).** The results table
  opened on every column it has, forty-three of them and about five screens, and the ones a person
  decides with were scattered among them. It opens on a named view of a dozen now, with Hazards and
  Everything beside it, and the chooser groups all forty-three by where each value comes from rather
  than listing them flat.

  The pre-build check caught the one decision that mattered and I had not made it. "A remembered
  arrangement wins over the view" has two implementations that behave oppositely: store the view's
  name and recompute what it hides on each load, and hiding one column of the twelve brings the
  other thirty-one back on the next visit, because only the column that was touched was written
  down. So a view is applied at exactly two moments, nothing remembered at all and somebody picking
  one, and what is stored is the resulting set with the name as a label on it. That opened a second
  case: everybody who used this table before today has an arrangement stored and no view name, and
  reading that as "apply the default" would rearrange exactly the people the rule protects.

- **2026-08-29, the last pass over a reading of the whole interface.** Four defects and three
  changes, written together because they were what was left.

  The defects: the map counted what it hides over the rows it can draw rather than over the run, so
  it said a different number from the table in the same words; thumbnails blinked, because the
  virtual window replaces every row on every scroll and a fresh element is a fresh load; a merge
  event printed a run of thirty-two-character identifiers into a table cell and had them clipped
  mid-identifier; and the search builder's map opened at a fixed point that, for a statewide search,
  is inside one of its own polygons.

  **Say what you count** (`changes/say-what-you-count/`). Four screens showed a total called
  "properties" and no two agreed, which is four correct answers to four different questions with one
  noun on them. Each says what it counts now. A property with no address is named for what is known
  about it rather than by a hexadecimal string, in one place because four surfaces name a property.

  **The page is not the manual** (`changes/the-page-is-not-the-manual/`). Instructions behind a
  disclosure, open the first visit. The criterion explanation said once above the list rather than
  under each of fifteen. The tools moved off the settings page, which keeps its own address so no
  bookmark breaks. And a figure in the overview strip is drawn at zero, because a tile appearing is
  harder to notice than a number changing.

  **Work the table** (`changes/work-the-table/`). 737 of 951 properties in this workspace had been
  passed one at a time, each through a dialog. A range can be selected and one action applies to all
  of it, written by one core operation that reports what it wrote and what it refused. And the
  builder says which panel is unsaved instead of apologising for it in its opening line.

- **2026-08-29, come back to it (`changes/come-back-to-it/`, with feat-001's
  `changes/what-a-pass-is-doing/`).** Asked whether the interface says a pass is running and shows
  how far along it is when you return to it. It did not. The panel was real, streamed live, and was
  started in exactly one place: the button handler. Reload, open another tab or pick up a phone and
  the tools page looked idle while extraction was twenty minutes in; the list of searches showed one
  frozen badge with no progress behind it; every other screen said nothing at all, because the
  navigation is four fixed links. The clearest evidence it was a gap rather than a decision is that
  pressing the same button again worked: the server answered "already running", the page ignored
  that and attached its watcher anyway, and the progress came back.

  What a pass is doing now lives in the store rather than in the memory of whichever process started
  it, so it survives a restart, and the scheduled nightly job is visible in a browser. Screens
  rejoin what is already running when they load, and one marker in the shared frame says so from
  wherever you are standing.

  The pre-build check held both changes, and all three findings were mine. The security one is worth
  keeping: recording a failure moves it from a string in one process to bytes in a database file
  this workspace keeps a backup of beside, and extraction's existing credential stripper was applied
  to its own per-description failures and not to the exception that ends a pass, which is exactly
  the string this makes durable. The scrubbing moved into the single function that writes a row.
  Then: the capability was reachable from the browser only, which invariant 5 forbids, answered by
  widening the overview both surfaces already draw rather than inventing a command; and two
  artifacts disagreed about who decides a pass is already running, which was hiding a real change,
  since reading it from the store makes the answer global and the browser will now refuse to start
  an extraction while the nightly job is running one.

  A fourth was found by a test rather than by the check: the recorder did not close its own row on
  the way out, so a caller who forgot the closing call would have left a pass reading as running
  until the clock said otherwise. It closes itself now.

- **2026-08-29, what the model made of it (`changes/what-the-model-made-of-it/`).** A hundred and
  fifty-five assessments existed and the table did not know they were there: they were readable
  from a terminal, from the raw API, and nowhere a person looks. Deliberately left until somebody
  had read real ones, because what is worth showing about an assessment in a table already
  forty-three columns wide is a question of taste and guessing it first would have been guessing.

  A count, second in the opening view beside the address, marked when anything is serious and marked
  differently when the assessment no longer describes the property. Pressing it opens the whole
  assessment under the row: the account, each concern with the evidence it came from, what each
  picture showed, what to check, and what could not be told.

  The pre-build check held it twice and the second one mattered. "Pressing a row opens it" would
  have taken a meaning away from a gesture that already had two: moving the cell focus, which is
  what makes a writable column typable, and extending the batch range with shift. The one it would
  have displaced is the one somebody had already reported losing, in those words, in a comment that
  is still in the file. The count opens it instead. The first finding was that "an ordinary column"
  is a claim about where a column is declared, and declaring it raised feat-011's header test;
  both are answered by an arrangement that already existed, since forty-four columns are declared
  and the default sheet uses thirty-two.

  The expanding row cost one line rather than a mechanism, because this table already places rows
  from heights it measured rather than assuming they are equal. That was checked before the change
  was proposed rather than after.

- **2026-09-04, data centres on the map (`changes/data-centers-on-the-map/`).** A fourth layer over
  the fire, off by default, on the terms the other three already have. Three kinds told apart by how
  filled a shape is rather than by its colour, because every hue on that map is spoken for: a
  green-to-red hazard scale underneath and three judgment colours on top. Fill turned out to be the
  better encoding anyway, since solid, half and empty are ordered the way running, being built and
  merely asked for are ordered.

  Nothing is drawn more precisely than its record knows it. A mapped building is drawn at its real
  size, which over Ashburn says what a data centre is more plainly than the legend does; a
  town-level site is bigger and dashed; and a site placed no better than a county is drawn as that
  county, which is why turning this on turns the county outlines on with it.

  The pre-build check held this one on a security finding, and the finding was right. The tracker is
  crowd-sourced and carries petition links, community-group sites and up to eight source links a
  record, so this is the first layer on any surface here to render addresses this tool did not
  write. The defence already existed in `common.js`, which is the only thing that builds an anchor
  and yields nothing for a scheme that is not http or https; what was missing was the requirement to
  use it, and the test that would notice if somebody stopped.

  The pointer rule of AC-60 was broken again, in the way that costs the most, and the browser test
  caught it before anybody saw it. This is the first layer with clickable shapes of real extent, and
  the properties are drawn on a canvas in a pane *below* it, so a filled campus outline was a hole
  in the map for every house inside it. An outline now answers on its stroke and not on its fill.
  The first fix did not work and looked as though it had: the rule was written
  `.leaflet-centers-pane path.dc-outline`, which loses on specificity to Leaflet's own
  `.leaflet-pane > svg path.leaflet-interactive`, so it was simply never applied.

- **2026-09-04, a defect found while building that.** Every browser test of the map had been
  silently skipping. The surface moved to `/map/{name}` with the old address kept as a permanent
  redirect, and the harness still asked for `/fire/{name}` and then looked for a page at the address
  it had asked for. The miss is a skip rather than a failure, and the message is "the browser did
  not open the page", which reads as a machine without Chrome on it.

  Six tests came back when the address was corrected, and three of them failed on wording that had
  moved on without them: "satellite view" for "satellite", and two counts still expecting
  "disappeared" after both surfaces were made to say "off the market" from one place. The code was
  right in all three; the expectations had drifted while nothing was watching.

- **2026-09-04, a defect found in use: the data centre layer made the map slow.** Reported as
  laggy with the layer on and worst zoomed out, and measured in the browser as eleven thousand
  `<svg>` elements and a nine-second zoom. Every shape had been given a renderer of its own, and a
  renderer is a layer the map keeps after the shapes drawn on it are cleared, so every pan left a
  few hundred empty drawing surfaces behind. One renderer now, made once in the layer's own pane,
  which is also where the shapes were always meant to be and had never been: a renderer draws in
  its own pane, not the shape's, so the pointer rule written for that pane had been reaching
  nothing. Recorded as `T215`, with a regression test that counts surfaces after moving the map.

- **2026-09-04, as fast at hour six (`changes/as-fast-at-hour-six/`).** Reported as the site
  slowing down over time and being fast again right after a restart, which reads as a leak and was
  not one. The server was measured doing the same work at two speeds: a results answer of 1,251
  rows in 0.7 seconds from a fresh process and in 3 to 4.8 seconds from the copy the scheduled
  task had started three hours earlier, with the same reads, the same bytes and the same memory in
  both. Windows 11 had moved the hidden, below-normal-priority process into its efficiency mode.
  Lifting that alone took the answer back to 0.7 seconds; raising the priority did nothing. So the
  server asks not to be throttled when it starts, from the one place every start passes through,
  best effort and Windows only, with a test that reads the state back through `serve()` itself.
  The interface's own three-second requirement had been missed in practice for a reason no
  requirement named; AC-96 names it.
