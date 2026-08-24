---
schema_version: 2
id: "feat-004"
slug: "saved-searches"
title: "Saved searches and geography"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-003]
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
  open: 4
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Saved searches and geography

## Scope

The hand-editable YAML search definition and the two-stage geography it drives: a coarse query in
whatever form each source accepts, then an exact local point-in-polygon test against the drawn
areas. Owns area resolution for cities, counties, ZIP codes, radii, and polygons, exclusion areas,
and the requirement that a definition round-trips losslessly through the browser interface.

Brief section 6.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes by other features

- **2026-08-23, rule engine (feat-008).** The `rules` section is now read rather than only
  shape-checked. `search/validate.py` hands it to the rule engine, which parses and checks each
  criterion and returns located problems in the shape this feature already carries; the file format
  still owns where the section sits in the document and where to point when something in it is
  wrong. A file-backed definition parses its criteria once when it loads, so a run never re-reads
  the grammar per property.

  A direct call rather than a fourth registry. The catalog, the boundary provider and the merge
  queue are ports because their implementations genuinely vary; the rule engine is not optional and
  has no second implementation, so a registry would model a state the product never occupies and
  would let a search with unreadable criteria validate cleanly whenever somebody forgot to register.
- **2026-08-23, location enrichment (feat-007).** The boundary provider this feature declared a port
  for is registered: Census TIGERweb for the shapes of named places, the Census geocoder for what
  contains a point. That is what gap-001 in this feature's ledger was waiting for.

  Registered cache-only. A saved search tests its geography once per property inside the filtering
  loop, and a boundary that had to be fetched at that moment would put a paced network request in
  the middle of a loop that is meant to be local and instant. The shapes a saved search names are
  fetched by the enrichment pass, once, and read from the cache everywhere else. A workspace that
  registers the provider also removes it when it closes, because registration is process-wide.
