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
depends_on: [feat-004, feat-006, feat-008]
requires_design: true
readiness:
  research: ready
  design:   ready
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: not-run
  product_global_hash: "sha256:d720d6d2ec75"
  constitution_hash: "sha256:d73230560d0f"
converge:
  last_run: 2026-08-25
  open: 4
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Browser interface

## Scope

Five screens on localhost: the map and search builder with polygon drawing, the saved search
list, the results table with every column and inline-editable annotations, the listing detail
with photos and enrichment and merge provenance and a price timeline, and the run history diff.
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
