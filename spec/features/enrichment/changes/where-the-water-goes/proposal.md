# Proposal: enrichment

**Trigger:** The same request as `where-fema-has-no-map`, from a mold-sensitive household searching
New Mexico, the week after the remnants of Hurricane Polo: show "areas that flooded with this recent
event and areas that this could happen in so we can avoid getting houses in those areas."

**Summary:** FEMA answers one question, the one-percent river flood, and in New Mexico it answers
it for less than three quarters of the state. This storm showed the rest. Rincon, which FEMA maps as
Zone `X`, minimal hazard, stayed evacuated and under water a day after the Rincon Arroyo breached its
levees. McLeod Dam, an earthen flood-control dam above Garfield and Salem that the federal inventory
already rated high hazard, condition poor, with no emergency action plan, went into a Flash Flood
Emergency for imminent failure. A Clovis woman whose house flooded had been told she did not live in
a flood zone. So this change adds four providers, each answering a question FEMA does not, and each
from a free, national, keyless public source.

**How this was decided.** Three independent reviews were run before anything was written: one
verifying every candidate source live at New Mexico coordinates, one fitting the result to this
codebase, and one arguing the case of a mold-sensitive buyer. The rules they converged on were then
counted against the 846 New Mexico listings the live search keeps today, and two proposals were
withdrawn on those counts (below).

**The four.**

1. **Soils** (USDA NRCS Soil Data Access, one request per point). The survey's own map-unit
   aggregates: flooding frequency class, ponding, depth to the seasonal water table, the wettest
   drainage class, and the hydric (wetland) share. This is the strongest mold signal there is that
   has nothing to do with a storm: shallow groundwater wicks into a slab or crawlspace every
   irrigation season. It is not a flash-flood signal and must never be read as one. At all five
   towns this storm flooded, the survey reads "no flooding", because its flooding class describes
   overbank river flooding of the soil, not water arriving down a wash.

2. **Flash-flood history** (the National Weather Service's own warnings and storm reports, as
   archived by Iowa State's Environmental Mesonet). How many flash-flood warnings have covered a
   point since 2008, how many of those became Flash Flood Emergencies, the date of the latest, and
   how many flood reports were filed within a mile since 2005. This is the one record that sees
   where flash flooding actually happens in an arid state, including burn scars: Ruidoso has had 98
   warnings since 2002, 69 of them since the 2024 fires. It is also how "this event" is in the data
   at all. No inundation footprint for this storm exists anywhere public: USGS has opened no
   high-water-mark event for it, Copernicus has no activation, FEMA has no declaration yet, and NOAA's
   storm database runs three months behind. The warnings and the reports are the record there is.

3. **Streams and arroyos** (USGS National Hydrography Dataset, one request per point). Distance to
   the nearest mapped natural channel, and what it is. In New Mexico the water that floods a house
   usually arrives down an arroyo that is dry three hundred days a year. Rincon is 600 feet from the
   Rincon Arroyo. Without this, Garfield and Marquez Ville Road pass every other check.

4. **Dams** (USACE National Inventory of Dams, a state at a time). The nearest high-hazard dam, how
   many lie within ten miles, and the worst condition among them. New Mexico has 145 high-hazard
   dams rated poor or unsatisfactory, most of them flood-control dams built in the 1950s and 60s and
   past their design life, and Hatch is ringed by fourteen within fifteen kilometres. NID gives each
   dam as a single point and inundation maps for local dams are not public, so this says "near",
   never "downstream", wherever it is read.

**What the counts changed.** Dropping every house any past Flash Flood Emergency covered would have
set aside 117 of the 846 (14 percent), because emergency polygons are drawn over whole towns: Roswell,
Alto, Ruidoso, Santa Fe. So emergencies are a value and a flag, and a drop only alongside a mapped
channel within 500 feet. And a rolling "warned in the past year" count, first proposed as the way to
make this storm rule-able, fired on 56 percent of the list and would quietly forget this storm next
October; it was replaced by the year of the latest warning, which changes only when the weather does.

**Shape.** Soils and streams ask a service per point, like the flood provider. Flash floods and dams
hold a national record a state at a time beside the database, fetched whole as a side effect of a
pass that finds it stale, like the data center provider (D-15): flash-flood polygons since 2008 are
about 35 megabytes for New Mexico, once; past years never change and are never fetched again; the
current year and the reports are refreshed weekly; the dams are 138 kilobytes a state. One module
holds the machinery the two share (D-17).

**What was rejected, and why.** NASA's OPERA surface-water maps caught the Hatch emergency from
orbit, and need an Earthdata login: out under the keyless rule. NOAA's height-above-nearest-drainage
data is in a requester-pays bucket: a paid service. FEMA's National Risk Index rated all four test
points the same at tract level, too coarse to tell two houses apart. Flood insurance claims are thin
where almost nobody carries flood insurance, so no claims means nothing. The National Water Model's
fourteen-day high-flow layer is modelled rather than observed, and rolls off. Burn scars were
deferred: the warning history already sees post-fire flooding empirically. Listing text ("water
damage", "remediated") was deferred to the extraction feature, because a plain keyword search for
"flood" in the current listings was almost all sunlight flooding rooms.
