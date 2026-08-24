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
- **2026-08-23, command line and run orchestration (feat-003).** `Store.record_observations` now
  returns one canonical listing id per input row, in input order, rather than the distinct ids with
  repeats collapsed. Nothing about what is written changed, and no acceptance criterion here spoke
  to the return value. The reason is the run loop: it holds the rows in memory and has to know which
  property each one became, so it can retrieve a preview image for a property that has none. Zipping
  a collapsed list against the original rows would attach images to the wrong properties from the
  first repeat onward, and the alternative was to reimplement this feature's private identity rule
  in the run loop, which is the one rule this project cannot afford to have two of. The distinct
  list is `dict.fromkeys` away for any caller that wants it. Covered by a test here citing
  `feat-001/AC-4`. The now-unused private identity helper was removed with it.
- **2026-08-23, rule engine (feat-008).** Schema version 2: one table, `rule_verdicts`, recording
  what each criterion decided about each property in each run, with the same append-only triggers
  every other history table carries. Verdicts are recorded rather than recomputed because
  re-evaluating an edited criterion against an old snapshot would change what that run decided,
  which non-negotiable 1 forbids, and because every digest already sent would then disagree with
  the database it came from.

  The trigger generator now takes the list of tables to protect rather than reading the module-level
  one, so that each schema version protects the tables it creates. Version 1's migration text is
  byte-for-byte unchanged, which is the rule that matters here: a migration that has run on
  somebody's real database is history too. Three read and write methods were added alongside it
  (`record_verdicts`, `verdicts`, `fired`), keeping every statement of SQL behind this package.
