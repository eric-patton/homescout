---
schema_version: 2
id: "feat-009"
slug: "field-extraction"
title: "Description field extraction"
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

# Feature notes — Description field extraction

## Scope

Pulling structured fields out of listing prose: heating and cooling, water source, sewer or
septic, gas, roof and construction. Deterministic pattern matching is the always-on baseline. An
optional model pass is opt-in per search, cached per description, and speaks one
OpenAI-compatible request shape so a hosted key and a local server are the same code path. A
field that could not be determined is left empty, never guessed, and every extracted value
carries whether a pattern or a model produced it.

Brief sections 9, 14. Decision D1.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
