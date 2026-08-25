---
schema_version: 2
id: "feat-007"
slug: "enrichment"
title: "Location enrichment providers"
status: done
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
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-24
  open: 3
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Location enrichment providers

## Scope

A separately schedulable pass that attaches public data to a location rather than to a listing:
flood zone, broadband service, principal aquifer, wildfire hazard, elevation, and boundary
resolution. Each provider is a plugin declaring its own cache key and time-to-live, cached by
rounded coordinates and never re-fetched on a hit. One dead endpoint marks that one field stale
and the run continues.

Brief section 5.4.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes to this feature's own spec

- **2026-08-23, during planning.** The security requirement read "no credentials". Verifying the
  endpoints showed the FCC's national broadband map is now keyed, and the keyless one it replaced
  covered mobile service only and is gone. Two criteria collided: AC-11 wants a broadband provider
  to exist, and the requirement wanted no credentials anywhere.

  Settled by narrowing the requirement rather than dropping the provider: no credential is
  *required*, none is embedded, and broadband is absent by default and enabled by a token in the
  environment. That is the shape the constitution already uses for every other secret, and product
  invariant 9 already says an optional component absent by default leaves the tool fully functional.
  Recorded here because a requirement that quietly changes to match what was built is worth nothing.

- **2026-08-24, spreadsheet export (feat-011).** No change to this feature, and one thing it is now
  measured by.

  Four of the default sheet's columns come from here: FEMA Flood Zone, Principal Aquifer, Internet,
  and (as columns outside the default set) Wildfire Hazard and Elevation. On a live run over
  Portales, after `homescout enrich`, flood zone, elevation, aquifer and wildfire each answered for
  all 83 properties, and Internet answered for none, because the FCC map needs a token this
  installation has not got. That is the shape this feature always promised: a provider that needs
  something nobody supplied is skipped and says so, rather than failing.

  The export reports an empty enriched column as "the enrichment pass has not been run for these
  properties", which is the first place in the product where a person is told to run this.
