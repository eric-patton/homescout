---
schema_version: 2
id: "feat-001"
slug: "listing-store"
title: "Listing store and snapshot history"
status: done
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
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-23
  open: 0
  contradicts: 0
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

## Later changes by other features

- **2026-08-23, source adapters (feat-002).** `ListingFields` and `SourceRow` moved out of
  `homescout.store.models` into `homescout/records.py`, and `homescout.store` re-exports both. An
  adapter's output *is* a `SourceRow`, and the architecture runs `sources` before `store`, so
  leaving the definition here would have made the sources layer import backwards through the
  product to describe its own return value. Behavior-preserving: the public names, this feature's
  tests, and the audit already on record all stand. Recorded here so a later audit reads it as
  deliberate rather than as unexplained drift.
- On the way, `ListingFields.from_row` stopped reading a hand-maintained tuple of column names and
  now reads the dataclass's own fields, so the two can no longer disagree. The store keeps a check
  at import that its compared and informational sets together account for every field on the
  record.
