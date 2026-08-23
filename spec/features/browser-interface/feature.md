---
schema_version: 2
id: "feat-010"
slug: "browser-interface"
title: "Browser interface"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-004, feat-006, feat-008]
requires_design: true
readiness:
  research: none
  design:   none
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
