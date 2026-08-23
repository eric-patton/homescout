---
schema_version: 2
id: "feat-012"
slug: "scheduling-digests"
title: "Scheduling and digests"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-003, feat-008]
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

# Feature notes — Scheduling and digests

## Scope

Unattended operation through Windows Task Scheduler, and the two things a finished run reports:
a compact JSON digest written where an automated agent can read it, and an email digest readable
on a phone with a thumbnail, price, address, key flags, and a link. Suppressed entirely when
nothing changed. Credentials come from the environment, never from committed config.

Brief section 10. Decision D2 supplies the thumbnail the email needs.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.
