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
- **2026-08-23, location enrichment (feat-007).** Schema version 3: one table, `enrichment_values`,
  holding what a public data service said about a place, keyed by provider, rounded location and
  value name.

  The one table in this database that is deliberately not append-only, and the exception is written
  into the schema rather than left to be noticed. Every other table records what this tool observed,
  and the rules that protect those are scoped to exactly that: the constitution's first
  non-negotiable is about what a run saw of a listing, and product invariant 1 names snapshot and
  raw-listing history. A cached copy of a federal map is neither. The narrower rule that does apply
  is the enrichment feature's own: a provider failure never removes a cached value, which is
  enforced by failures never reaching the write at all.

  Two methods came with it, `cache_values` and `cached_values`, the second reading in bulk because
  five providers against five thousand properties is twenty-five thousand lookups and a query each
  would spend the whole performance budget on round trips.
- **2026-08-24, scheduling and digests (feat-012).** Schema version 4: one table, `deliveries`,
  recording what was reported about a run (the digest file, and the email) and how it went, with the
  same append-only triggers every other history table carries. It is history rather than a log line
  because it answers a question a person asks the morning after: did last night's run mail me and I
  missed it, or did it decide there was nothing worth saying, or does this installation have no mail
  account at all? Those are three different outcomes on the same table. A second attempt after a
  failure is a second row, never a correction of the first. Nothing in this feature's own criteria
  is affected, and the new table holds no listing data and no credential.
- **2026-08-24, address matching and merge review (feat-006).** Schema version 5: two tables, and
  one read.

  `merge_decisions` records what a person decided about two records, and it is the load-bearing one:
  non-negotiable 6 says an ambiguous merge is flagged for a human and never guessed, and
  non-negotiable 7 says losing a user's judgment is the one failure this tool cannot have. **One row
  per pair**, even when the person answered about a group of three, because the comparison that
  consults it works pairwise and a group-level answer that a pairwise lookup could not find would be
  an answer quietly lost. Append-only, so a change of mind is a new row and the sequence of answers
  stays readable.

  `merge_contradictions` records evidence that turned up later and disagrees with a decision. Shown,
  never acted on: a decision is not overruled by evidence, it is questioned by it. The same
  disagreement noticed again is not recorded twice, because a pair somebody decided about is
  compared on every run and three hundred copies of March's disagreement would bury last night's.

  `Store.latest_snapshots()` came with them: the most recent snapshot of every live listing in one
  query, which is what the merge pass compares. One query rather than one per listing, because a
  county is several thousand of them and this runs after every run.

- **2026-08-24, description field extraction (feat-009).** Schema version 6: one table,
  `extracted_values`, and it is the second cache in this database rather than history.

  It holds what a language model said about a piece of prose, so it is a copy of somebody else's
  answer and not an observation this tool made. That is why the append-only triggers do not reach
  it, the same exception `enrichment_values` takes for the same reason.

  **Nothing the deterministic patterns produce is stored at all.** They are regular expressions over
  at most four thousand characters and running them costs less than the query that would fetch the
  answer, and a cached pattern result would be stale the moment the pattern that wrote it was
  corrected. Only the expensive backend is cached.

  The key is the **digest of the description** rather than the listing, which is what makes "a
  description is processed at most once" true regardless of how many properties or runs carry the
  same text. The model is in the key too, so a person who changes models can ask again rather than
  being stuck with a cache nobody can invalidate. A row with a null value means the model was asked
  and determined nothing, which is a real answer and is what stops the same question being paid for
  every night.

- **2026-08-24, browser interface (feat-010).** No schema change, and one flag with a narrow reason.

  `Store.open(shared=True)` lifts SQLite's refusal to be used from a thread other than the one that
  opened it. Exactly one caller passes it, and only because a web server hands requests to a pool of
  worker threads: the interface holds a lock around every request, and around the thread a run goes
  into, which is what makes lifting the check safe. Everything else in this product is one thread,
  leaves it alone, and keeps the check as a real guard rather than a formality.

  Found by running the real server rather than by reading. The tests had been reaching for a shared
  store explicitly, so the first thing that hit it was the actual `homescout serve`.

- **2026-08-24, broadband from the FCC's own files (feat-007, `changes/broadband-from-the-fcc-files/`).**
  Schema version 7: `broadband_blocks`, one row per census block.

  The third table in this database that is a cache rather than history, after `enrichment_values`
  and `extracted_values`, and it gets no append-only trigger for the same reason as those two: it
  holds a copy of somebody else's published dataset. The FCC publishes quarterly and a state is
  refreshed whole, so `state` is on every row rather than inferred from the block, and replacing a
  stale quarter leaves every other state alone.

