# Proposal — browser-interface

**Trigger:** A house near Taos that every criterion in the search was happy with, and that the people
using this tool were not. In their words: a lot of the shortlisted houses "were too close to fire
areas", and of that one, "technically that's not in a fire zone, just really close to one".

**Summary:** The criteria are right and the answer is still wrong. `wildfire_hazard` is the model's
class for the ground a house stands on, and for that house it is genuinely "very low": it sits in a
green pocket a few hundred metres from a solid wall of red. Every rule looks at the point. Nobody
lives at a point.

Two answers exist. One is a value: how far to the nearest severe hazard, computed and testable by a
criterion, which is the better long-term answer and needs a way to sample the raster in bulk that
this tool does not have yet. The other is a way of looking, which is what was asked for: put every
property on the hazard model and let a person see what each one is next to.

This is the second. A map draws the same layer the enrichment pass reads, at the same address, with
a pin per property, and a pin opens into the same keep-or-pass decision the table offers, asking the
same question about why. "Half a mile from the red" is a reason somebody can see in a second and
cannot easily say from a table of numbers, and it is exactly the reason worth writing down.

It works out nothing and decides nothing. That is deliberate: a page that quietly scored houses on
proximity would be a criterion with no rule behind it and no way to argue with.

## Blast radius

- **A seventh surface**, which is a change to AC-1's list.
- **No new service and no new address.** The layer is the one the wildfire provider already reads: an
  ArcGIS service that answers about a point at `identify` draws that data at `exportImage`, so the
  address is derived from the configured one rather than written out a second time. Pointing the
  provider at another server moves the map with it.
- **It asks that server for the part of the country on screen**, which is what any map does and which
  nothing else in this tool does unless a map background has been turned on. Said on the page, in the
  same place and much the same words the map background's own warning uses.
- **No new core reads.** The page is built from the results answer, which already carries every
  property's location, its judgment, its hazard and its links.
- **The rule engine is untouched.** No criterion gains a proximity test here; that is the other
  answer, and it needs its own change when the sampling exists to support it.

## What this is not

Not a scoring pass and not a filter. Nothing is dropped, ranked or coloured by how close it is to
anything. The map shows what is there and the person decides, which is the same division of labour
the rest of the tool keeps.
