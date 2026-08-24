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
