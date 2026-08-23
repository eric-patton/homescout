---
schema_version: 2
id: "feat-007"
slug: "enrichment"
title: "Location enrichment providers"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001]
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

# Feature notes — Location enrichment providers

## Scope

A separately schedulable pass that attaches public data to a location rather than to a listing:
flood zone, broadband service, principal aquifer, wildfire hazard, elevation, and boundary
resolution. Each provider is a plugin declaring its own cache key and time-to-live, cached by
rounded coordinates and never re-fetched on a hit. One dead endpoint marks that one field stale
and the run continues.

Brief section 5.4.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
