---
schema_version: 2
id: "feat-003"
slug: "command-line"
title: "Command line and run orchestration"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001, feat-002]
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

# Feature notes — Command line and run orchestration

## Scope

The run loop that asks each source what it can filter, pushes those filters, applies the rest
locally, writes a snapshot, and records per-source status, plus the command line that exposes it.
Owns the machine contract: every command takes --json, returns a stable exit code, and never
prints prose an automated caller has to parse. Owns the digest shape emitted by run --all.

Brief sections 5, 7. Product invariant 6.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
