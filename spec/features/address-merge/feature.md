---
schema_version: 2
id: "feat-006"
slug: "address-merge"
title: "Address matching and merge review"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-005]
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

# Feature notes — Address matching and merge review

## Scope

The hardest part of the product: deciding that rows from different sources describe the same
house, when the same address is formatted differently by every provider. Normalized street plus
ZIP as the primary key, coordinates within about fifty metres to confirm, parcel number preferred
wherever present. Owns the rule that raw rows are never destroyed, the queue of ambiguous matches
a human resolves rather than the machine guessing, and the persistence of those decisions across
future runs.

Brief section 5.2. Constitution non-negotiables 5, 6, 7.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
