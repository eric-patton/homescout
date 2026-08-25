---
schema_version: 2
id: "feat-009"
slug: "field-extraction"
title: "Description field extraction"
status: done
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
  plan:     ready
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-24
  open: 4
  contradicts: 0
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
