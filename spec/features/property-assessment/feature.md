---
schema_version: 2
id: "feat-013"
slug: "property-assessment"
title: "Property assessment"
status: active
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001, feat-007, feat-008, feat-009]
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:d720d6d2ec75"
  constitution_hash: "sha256:d73230560d0f"
converge:
  last_run: 2026-08-29
  open: 0
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Property assessment

## Scope

A second model pass, over the properties still in play rather than over every description in the
store, that reads one property against the criteria this household has already written down and
records what it makes of it.

The distinction from description field extraction (feat-009) is the whole reason this is its own
feature rather than a change to that one. That pass transcribes: it reads a description and fills
six enumerated fields, it is deliberately sent a description and nothing else, and its own code
says why that blindfold is right — there is no address in scope there to send. This pass judges. It
needs the address, the coordinates, the photograph, the hazard ratings, which rules fired, and the
household's own words about what it is avoiding, none of which feat-009 may be given. Two passes,
two boundaries, and the boundary is the thing being changed.

What it writes is its own, beside the person's judgment and never inside it. Every property row
already carries `rank`, `red_flags`, `summary`, `next_step`, `fire_egress`, `sewage_exposure`,
`outbuildings`, `taxes` and `crime`, all of them empty; the store declares them the user's own
judgment, never written by a run, and that stands. What you concluded and what a model guessed have
to be legible as different things, which is also the only arrangement in which the second is worth
having.

Not a decision. It ranks, it explains, it flags, and it never hides a property: keeping and passing
stay the person's, which is non-negotiable 7 and the reason this tool exists.

## Sources

The reading of the interface on 2026-08-29 that produced the browser-interface changes, and the
person running searches asking directly for it: "couldn't we make this more useful then by having
the AI do a real full assessment on properties that we haven't hidden or rejected... giving us an
overview of any findings it has or how it measures against what we have in our prompt to it of
things we are looking for or not looking for? Maybe even showing it some images or the fire map
plus wind directions?"

The scope was settled in the same conversation: address, coordinates, wind and terrain included,
which is the fullest of the three options offered and the only one that drops the no-address
boundary deliberately rather than by omission.

The measurements behind it are in `research.md`.
