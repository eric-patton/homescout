# Proposal: named-addresses

**Trigger:** The person running searches asked for eight specific Louisiana houses to be run as
"one-offs", and the tool had no way to say "this house". The run was done by hand on 2026-09-30 as a
throwaway search (`la-one-offs`): each address was placed with the Census one-line geocoder, a
half-mile circle went around each point, and the search was run like any other. Afterwards: "I feel
like we should just build functionality for the ability to add any number of specific addresses to
any search, if the various tools will allow for that."

**Summary:** A saved search can name any number of street addresses beside its areas, or instead of
them. Every run places each address on the map once, asks every source for a small circle around it,
and keeps only the listing at that address. A named house is exempt from the search's filters and
exclude areas, because a person who names a house has already decided they want to see it, and a
year-built filter silently hiding it would defeat the point. The search's criteria still judge it, so
a house in a flood zone is still set aside, visibly and with its reason. (The person chose this over
"obey everything" and "skip filters, obey exclusions".)

**The tools do allow it, and nothing new is needed from any listing site.** The by-hand run is the
evidence: all eight addresses were placed by the geocoder, and all eight houses came back, each from
every source that lists it, through the query paths that already exist (Realtor's radius, the
Zillow and Redfin boxes). What the by-hand version could not do is keep only the named house: the
circles also returned 18 neighbours for sale, and three of the eight houses stayed as three separate
records apiece (see the defect below).

**Why half a mile.** Measured on the eight: the geocoder places a rural address by interpolating
along the road, and the listing sites put the house on its parcel. The distance between the two was
0.02 to 0.07 miles on ordinary streets and up to 0.30 miles on the numbered highways, where lots are
large. A quarter mile would have missed two of the eight. The circle only decides what is asked
for; the address comparison decides what is kept, so a generous circle costs a few discarded rows
and nothing else.

**Where the address lookup lives.** The boundary port this feature declared (D-10), and which
enrichment registered (feat-007, Census), already answers "where is this place" for a radius around
a named place. Placing a street address is one more question on the same port, answered by the same
government service through its one-line address endpoint: free, national, no key, and a source the
constitution already admits. Cached like every other answer the port gives.

## Blast radius

- **Requirements affected:** AC-1 (the file shape gains a key) and AC-3 (what qualifies) are
  modified. New criteria for the file shape, placing, validation, asking, keeping only the named
  house, the exemption from filters, the per-address report, and the browser editor. The vocabulary
  gains "named address"; the edge cases gain five.
- **Design decisions affected:** D-4 (the file shape), D-5 and D-6 (the run loop's queries and its
  exact test: a named address is kept by address, not by geometry), D-7 (coarse resolution is reused
  unchanged for the circle), D-10 (the port gains a question), D-13 (validation checks the shape of
  the list and still fetches nothing). New decisions D-21 to D-26 in the plan.
- **Tasks affected:** new tasks under "Change: named addresses" in `tasks.md`. No finished task is
  reopened.
- **Already-built code affected:** `search/definition.py`, `search/areas.py`, `search/validate.py`,
  `search/boundaries.py` (the port), `runner.py` (the per-source loop, and "names no area"),
  `api.py` (the run outcome carries the per-address report), `enrich/boundaries.py` and
  `enrich/settings.py` (feat-007: the Census one-line endpoint behind the port),
  `web/static/search.js` and the run status on screen (feat-010: the editor and the report), and the
  README's saved-search section.

**Other features, recorded in their own manifests when built, as earlier changes here were:**
feat-007 implements the new port question; feat-010 gains the editor for the list, under this
feature's criterion, as the reason editor was (`feat-004/AC-14`, `feat-010/AC-25`).

**One defect this depends on, fixed in its own lane rather than here** because the address matcher's
spec was already right: the address matcher (feat-006) gives no key at all to a numbered highway with
no state in front of it. `51131 Highway 445` and `33063 Hwy 43 Hwy` normalize to an empty street
name, because the rule that keeps land parcels out of the key ("a name made only of numbers is no
name") also removes a highway number once its type word is stripped. So the same house from three
sites stayed three records, and was never even queued for review. That breaks feat-006's AC-1 (rows
whose normalized addresses and ZIP codes agree are matched) and would break this change's matching
on every rural highway address. Fix it first.

Two more found during the by-hand run, unrelated to this change and reported rather than folded in:
Realtor answers 400 to a query for `pending` or `contingent` listings (16 of 24 queries, exactly the
8 circles times those two statuses), and a search's results table lists every other search's
disappeared properties (444 New Mexico houses in the Louisiana search's table, hidden behind the
disappeared filter).

## Status
- [x] delta reviewed (analyze, 2026-09-30: two runs, every finding closed)
- [ ] implemented & verified
- [ ] folded into the feature's spec.md (product.md regenerates; never edit it by hand)
