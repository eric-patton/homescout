# Proposal: enrichment

**Trigger:** The household searching New Mexico is mold sensitive, and on 2026-10-03, after the
remnants of Hurricane Polo flooded the Hatch valley and put McLeod Dam into a Flash Flood Emergency,
asked for "something that will show us areas that flooded with this recent event and areas that this
could happen in so we can avoid getting houses in those areas."

**Summary:** Before adding anything new, the flood value this feature already supplies had to stop
telling them a place was dry when nobody had looked. Three things were wrong with it, and only one
was a bug.

**What the live cache showed.** Of the 2,428 flood lookups held for the statewide search, 1,735 were
plain `X`, 285 were empty, 208 were Zone `D`, and about 130 were in an `A` zone. The empty ones are
not places FEMA mapped as dry. FEMA's own availability layer has no digital flood map at all for ten
of New Mexico's thirty-three counties (Catron, De Baca, Guadalupe, Harding, Hidalgo, Mora, Quay,
Sierra, Torrance and Union); Arrey, in Sierra County, where a levee breached during this storm,
answers nothing from the zone layer. This feature's spec called an empty answer a known negative,
because it believed "the National Flood Hazard Layer maps the whole country". It does not, and the
provider has been saying "in no flood zone" about places no one ever studied.

Zone `D` is the second hole. FEMA uses it for "possible but undetermined" hazard, and marks it as
outside the special flood hazard area. Read literally, that is a no. It means nobody looked.

The third is the bug: the provider read the first feature FEMA returned and ignored the rest. Where
two studies meet, or where a floodway lies inside its zone, FEMA answers with more than one feature,
in whatever order its server keeps them.

And a trap in the value's shape, found while looking: `flood_zone` carries its qualifier, so a
floodway reads `AE (FLOODWAY)`, and the live criterion `flood_zone in ["A", "AE", ...]` does not
match it. Nothing in the cache had that value yet. It would have dropped through.

**The change.**

- When the zone layer answers nothing, the availability layer is asked once. No digital map is the
  determined value `not mapped`, which is the same shape the interface provider already uses for
  `outside coverage`: a determined answer whose content is "this source does not answer here".
- A new boolean, `flood_hazard_area`, is FEMA's own yes or no for its special flood hazard area,
  read from the `SFHA_TF` attribute. A criterion asks it instead of listing zone letters, so a
  floodway and every `A` and `V` variant are caught by one test.
- `flood_hazard_area` is empty, never false, wherever FEMA has not decided: Zone `D`, an
  `AREA NOT INCLUDED`, and `not mapped`. A point FEMA has mapped but where no zone comes back is a
  hole in FEMA's data (a digital map covers the ground with zones edge to edge, plain `X` included),
  so both values are empty there too, rather than a negative.
- Every feature returned is read and the worst is kept: the hazard area (a floodway first), then
  the unstudied, then the shaded `X`, then the levee `X`, then plain `X`.

**What this costs.** Adding a value makes every cached flood key incomplete, so the next pass asks
FEMA about all of them once more, which is also how the 285 empty ones get their real answer. About
2,700 requests at the one-second floor, run as its own pass.

**What is not changed.** `flood_zone` keeps FEMA's text, qualifier and all, so every criterion
already written against it means what it meant. The criterion the household uses is not edited by
this change; the browser change that ships beside it offers the new one.
