---
schema_version: 2
id: "feat-011"
slug: "spreadsheet-export"
title: "Spreadsheet export"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-007, feat-009]
requires_design: null
readiness:
  research: none
  design:   n/a
  spec:     none
  plan:     none
  tasks:    none
gate:
  analyze: not-run
  product_global_hash: ""
  constitution_hash: ""
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
