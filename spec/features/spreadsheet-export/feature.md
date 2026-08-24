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
  analyze: pass
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
