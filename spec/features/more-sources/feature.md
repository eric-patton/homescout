---
schema_version: 2
id: "feat-005"
slug: "more-sources"
title: "Zillow and Redfin sources"
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
  open: 2
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Zillow and Redfin sources

## Scope

Two more adapters against the interface feat-002 defined, chosen because they stress it in
opposite directions. Zillow takes a bounding box and caps at roughly 500 results, so it needs box
splitting. Redfin has no library, is a CSV download that only works where the local MLS permits
it, and must degrade to unavailable without failing the run. Adding these must not require
touching the core.

Brief section 5.1.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes to this feature's own spec

- **2026-08-24, during planning.** AC-7 read: the Redfin adapter reports `unavailable` when the
  region does not permit downloads, with a human-readable reason. Probing the real endpoint showed
  that Redfin does not say. Every response carries one identical line, *"In accordance with local
  MLS rules, some MLS listings are not included in the download"*, whatever the region: a box over
  Springfield, Illinois returns two properties, and a box over Portales, New Mexico, a town of
  twelve thousand, returns sixty-one. The restriction is real and it is invisible.

  Satisfying the criterion as written would mean inventing a signal, and the only one available is a
  row-count threshold, which would report a genuinely quiet market as a policy restriction and a
  restricted market as quiet. Both errors are worse than not answering.

  Narrowed rather than dropped: `unavailable` is reported for the refusals that are unambiguous (a
  response that is not a CSV download, an error envelope, a block page), and the site's own notice
  is carried in the detail of **every** Redfin result, so this source's contribution is never
  presented as complete. The promise AC-7 was protecting, that a coverage gap is never mistaken for
  a quiet market, is kept by saying so every time rather than by guessing when to say it.

  Recorded here because a requirement that quietly changes to match what was built is worth nothing.
