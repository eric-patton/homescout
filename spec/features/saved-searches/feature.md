---
schema_version: 2
id: "feat-004"
slug: "saved-searches"
title: "Saved searches and geography"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-003]
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

# Feature notes — Saved searches and geography

## Scope

The hand-editable YAML search definition and the two-stage geography it drives: a coarse query in
whatever form each source accepts, then an exact local point-in-polygon test against the drawn
areas. Owns area resolution for cities, counties, ZIP codes, radii, and polygons, exclusion areas,
and the requirement that a definition round-trips losslessly through the browser interface.

Brief section 6.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
