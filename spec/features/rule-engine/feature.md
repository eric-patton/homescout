---
schema_version: 2
id: "feat-008"
slug: "rule-engine"
title: "Rule engine"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-004]
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
  open: 1
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Rule engine

## Scope

User criteria as data rather than code, stored in the saved search so they are tunable per
search and diffable in git. Four severities: drop, flag, boost, demote. Owns the restricted
expression evaluator over a fixed field namespace, with no general-purpose interpreter anywhere
in the path, and a clear error when a rule names an unknown or not-yet-enriched field.

Brief section 5.5. Constitution non-negotiable 11.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes by other features

- **2026-08-23, location enrichment (feat-007).** The enriched names this feature declares are now
  filled. A criterion naming `flood_zone` or `over_principal_aquifer` finds a value where one has
  been fetched, and finds nothing where none has, which the three-valued evaluator already reads as
  undetermined.

  Read from the cache and never fetched during evaluation. Criteria are evaluated inside a loop over
  every property a run saw, and a lookup there would be a paced network request per property;
  enrichment is a separate pass for exactly that reason. The registry that supplies the providers
  also checks, at import, that every enriched name this feature declares has something that fills
  it, so the notice a criterion gets about an unfilled field stops appearing when it stops being
  true.

- **2026-08-24, description field extraction (feat-009).** The six extracted names are filled.

  `heating`, `cooling`, `water_source`, `sewer`, `gas` and `roof` were declared here from the first
  release with `populated: false`, so a rule naming one got told which feature would arrive to fill
  it. They now say `populated: true`, and a criterion naming one finds a value.

  Every value is a word from a short closed vocabulary that `extract/fields.py` checks against this
  table at import, in both directions: a value no criterion can name is work nobody can use, and a
  name declared here with nothing filling it is a promise the tool cannot keep.

  `"none"` is one of those words and means the description said the property does **not** have the
  thing. It reaches a criterion. An **empty** field does not, so a rule naming one is undetermined
  rather than false, which is what stops a house being excluded for having a quiet listing. Observed
  on a live run over Portales: of 83 properties, a well criterion fired on 2, was false for 2, and
  was undetermined for 79.

- **2026-08-24, spreadsheet export (feat-011).** No change, and one use worth recording.

  A sheet is what a run's criteria kept: `results()` decides which rows appear, so a property a
  `drop` rule removed is absent from the workbook unless `--include-dropped` asks for it, and the
  `flag` badges are available as a column outside the default set. Nothing about the sheet
  re-evaluates a criterion; it reads the verdicts the run recorded, which is why exporting last
  week's run still produces last week's answer.

## Changes recorded here

- **2026-08-24, the namespace became something a person can read.** `rules/namespace.py` gained
  `vocabulary()`: every field with its type, the closed set of values where there is one, a few real
  examples where the set is open, and a sentence for the fields whose name does not say what they
  mean.

  Both surfaces already had `names()`, and a list of names is half an answer. Somebody writing
  `cooling == "swamp cooler"` has named a real field and compared it to a word that can never be
  true, and nothing anywhere said so. The value sets are read from the tables that decide them (the
  extraction vocabulary, the wildfire legend, the listing statuses) rather than restated, so a value
  added in one of those reaches anybody writing a criterion in the same edit.

