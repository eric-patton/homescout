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
  analyze: not-run
  product_global_hash: "sha256:d720d6d2ec75"
  constitution_hash: "sha256:d73230560d0f"
converge:
  last_run: 2026-08-25
  open: 4
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

- **2026-08-25, the wildland-urban interface.** A question about whether `nmwrap.org` could feed
  New Mexico searches turned into the first provider here that does not cover the country.

  Most of what that portal publishes was rejected on the evidence. Its wildfire-potential raster is
  the same USFS product the `wildfire` provider already reads. Its historic-fire layer stops at 2017,
  so a point inside the Hermits Peak and Calf Canyon burn scar answers "no fire here". The national
  alternative, USDA's Community Wildfire Risk Reduction Zones, is disqualified by its own service
  description: the pixel values "have been altered" and the service is "intended primarily for data
  visualization" rather than analysis. Recording an altered value as a property's exposure class is
  the guess product invariant 10 forbids.

  What was taken is the interface layer, which answers a question hazard potential does not: whether
  houses are standing in the vegetation rather than how the vegetation would burn. It is an exact
  vector attribute with no resampling and no disclaimer.

  Two things this cost. The national-coverage rule was amended on main, in both governing documents,
  to permit a partial-coverage provider on the condition that a location outside its coverage reads
  as not applicable rather than as an answer; that restaged every feature's pre-build check. And the
  coverage test is not a bounding box, because New Mexico's box contains El Paso: the ambiguous case,
  inside the box with no polygon, asks a county layer before recording a negative.

  Checked while verifying: the endpoint the shipped `wildfire` provider uses carries no such
  alteration notice and its legend matches `WILDFIRE_CLASSES` exactly. No defect there.
