---
schema_version: 2
id: "feat-002"
slug: "source-adapters"
title: "Source adapters and the Realtor.com source"
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

# Feature notes — Source adapters and the Realtor.com source

## Scope

The adapter interface every provider satisfies, the capability declaration that says which
filters a provider can push server-side, and the shared politeness layer: per-source rate
limiting, backoff, jitter, configurable delay, honest user agent. Ships one working adapter
against Realtor.com, including its result ceiling and the date-range chunking that works around
it. Zillow and Redfin are feat-005 and must require no core change.

Brief section 5.1. Constitution non-negotiables 9 and 10.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
