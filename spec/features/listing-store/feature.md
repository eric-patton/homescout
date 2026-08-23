---
schema_version: 2
id: "feat-001"
slug: "listing-store"
title: "Listing store and snapshot history"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: []
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
  plan:     ready
  tasks:    none
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Listing store and snapshot history

## Scope

The SQLite schema and the append-only history that every difference is computed from: raw
per-source rows, canonical listings, snapshots, annotations, and runs. Owns the immutability
rules, the snapshot comparison that produces new / changed / gone, days-on-market and price
history computed from local history, and the disappeared status. Owns the trivial promotion of a
single source's row to a canonical listing; real cross-source matching belongs to feat-006.
Annotations are defined and stored here; editing them is the browser interface's job.

Brief sections 3, 5.3. Decisions D3, D4, D5.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
