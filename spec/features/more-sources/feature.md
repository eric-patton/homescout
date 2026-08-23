---
schema_version: 2
id: "feat-005"
slug: "more-sources"
title: "Zillow and Redfin sources"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-002]
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
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

# Feature notes — Zillow and Redfin sources

## Scope

Two more adapters against the interface feat-002 defined, chosen because they stress it in
opposite directions. Zillow takes a bounding box and caps at roughly 500 results, so it needs box
splitting. Redfin has no library, is a CSV download that only works where the local MLS permits
it, and must degrade to unavailable without failing the run. Adding these must not require
touching the core.

Brief section 5.1.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
