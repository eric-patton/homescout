# Proposal: browser-interface

**Trigger:** Reading the interface back: four screens show a total called "properties" and no two
agree. The list says 1,328 being watched, the results table says 951, the run comparison says 1,211,
the map says 155 on it. All four are right and nothing on any of them says which population it is
counting, so the natural read is that two of them are broken.

**Summary:** These are four different questions with one noun on them. How many properties this
whole workspace is watching, how many the latest run of this search found, how many were matched
against the previous run, and how many are drawn on this map. Each is worth knowing and none of them
is the others. Every count says what it counts.

The same fault in miniature is on the listing page, where a property with no address is titled with
a thirty-two character hexadecimal string, and appears in the run comparison under the same string.
Six of the fourteen new properties in this workspace currently read that way. The identifier is the
right thing to have and the wrong thing to lead with.

## Blast radius

- **Requirements affected here:** AC-1 is untouched; this modifies AC-11 (the run comparison) and
  AC-9 (the listing detail), and adds one criterion covering counts across the surfaces.
- **Already-built code affected:** `web/static/searches.js`, `results.js`, `changes.js`, `fire.js`,
  `listing.js`. No server change: every one of these numbers is already in an answer, and what
  changes is the words beside it.
- **Not a change to any number.** Nothing is recounted and no total moves. The map's held-back
  counts were separately wrong and are fixed as a defect against AC-67, not here.

## What this is not

Not one number everywhere. Four different populations is the truth, and collapsing them would mean
picking one screen's question and answering it on screens that are not asking it.

## Status
- [ ] delta reviewed (analyze)
- [ ] implemented & verified
- [ ] folded into spec.md
