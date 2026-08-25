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

- **2026-08-24, description field extraction (feat-009).** One new top-level key, absent by default.

  ```yaml
  extract:
    model: true
  ```

  `extract` joined the known top-level keys so a typo in it is a complaint rather than silence, and
  `model` must be true or false: `model: gpt-4o` is what somebody will write, and a string that read
  as truthy would turn on a paid service by accident. The complaint says where a model name actually
  goes, which is the environment.

  With the key absent or false, nothing in that feature reads a credential, resolves an address or
  opens a connection. No credential ever goes in a saved search, which is the constitution's rule
  and is why this setting is a switch rather than a configuration block.

- **2026-08-24, browser interface (feat-010).** No change to this feature, and one thing it is now
  measured by.

  Drawing an area on a map and saving it goes through `catalog.edit`, the same operation
  `homescout searches edit --set` uses, so the round-tripping document layer does the writing. A test
  in the interface's own suite writes a polygon into a file that carries a comment and a filter the
  interface never touched, and asserts both survive; and asserts that a refused edit leaves the file
  byte for byte as it was.

  That is the reason the interface can only change what this feature's edit operation can change,
  and it is stated on the screen rather than hidden: what it cannot edit, it shows read-only.

- **2026-08-24, notes for the model (feat-009, `changes/model-notes/`).** A second key under
  `extract`, absent by default.

  ```yaml
  extract:
    model: true
    notes: Around here, community water means a mutual domestic association.
  ```

  Plain words, sent to the model in the instruction with every description this search finds. It
  cannot add a field or a permitted value, and every value the model returns still has to be quoted
  from the description, so the worst a note can do is make the model wrong in the ordinary way. It
  is bounded at 2,000 characters, and the complaint past that says why: the note rides along with
  every description, so its length is a cost per property rather than a cost once.

  It is not a secret and may never become one. The constitution keeps credentials out of a saved
  search, and both places a note can be written say, before it is written, that its text goes to the
  model.

  **One thing changed for `description` at the same time.** `searches edit --set` reads every value
  the way the file would read it, so a number stays a number. A note reading "Community water: a
  shared system" is a sentence, and YAML cannot tell it from a mapping, so keys holding prose are
  now taken exactly as typed. `description` was already exposed to the same bug and is now in that
  set. The visible difference is that `--set description=123` stores the text rather than the
  number. That is recorded as an open question in feat-009's drift ledger (gap-004) rather than
  assumed to be wanted.

