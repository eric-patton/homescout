---
schema_version: 2
id: "feat-011"
slug: "spreadsheet-export"
title: "Spreadsheet export"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-007, feat-009]
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: not-run
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-24
  open: 2
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Spreadsheet export

## Scope

A first-class xlsx export with configurable column templates, whose default reproduces the
hand-built consolidated sheet the user maintains today. The address cell links to the listing, a
second sheet carries area and town notes, unstructured fields are left blank rather than guessed,
and re-exporting must never clobber edits made in the app.

Brief section 9.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Changes recorded here

- **2026-08-25, location enrichment (feat-007).** One column added, outside the default set, where
  Wildfire Hazard already sits: Wildland-Urban Interface. No change to the default sheet, which is a
  promise about a document somebody already has.

  It needed its own renderer rather than the shared one, and the reason is worth carrying. Every
  other enriched column's known negative is a value (`X`, `false`). This one's is `None`, which is
  also what an unfetched value looks like from the outside, so the renderer reads whether the key is
  present rather than what it holds. It writes three distinct phrases: in the interface and which
  kind, not in the interface, and outside coverage. The third exists because the source covers New
  Mexico only, and a blank cell there would read as the second.
