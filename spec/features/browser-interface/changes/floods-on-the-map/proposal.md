# Proposal: browser-interface

**Trigger:** The request recorded in the enrichment feature's `where-the-water-goes` change, from a
mold-sensitive household searching New Mexico the week after the remnants of Hurricane Polo: "show
us areas that flooded with this recent event and areas that this could happen in."

**Summary:** The values that enrichment change adds answer "is this house near water" for a whole
table at once and let a criterion set a house aside. They do not show anybody where the storm went.
That is a map's job, and this tool's map already exists: it is the per-search map that draws the
wildfire model, the wind, counties and towns, rainfall and data centres under the properties. So
this adds three things to it rather than building a second map that would have to copy the pins,
the judgments, the list under the map, the ruler and the rainfall, all of which matter as much for
flood as for fire.

1. **What is drawn under the properties becomes a choice:** the wildfire model, FEMA's flood zones,
   or neither. FEMA's map service only draws its zones close in (about zoom 14, a few miles across),
   so the page says so rather than showing a blank map at state scale, and asks for no tile it knows
   will come back empty.

2. **Flash floods:** the Weather Service's flash-flood warnings over a chosen window of dates, with
   the ones raised to a Flash Flood Emergency drawn heavier and named, and the flood reports filed in
   the same window as points. The window opens on the fortnight ending with the most recent
   emergency in the held record, which today is the Hurricane Polo storm, so the page shows this
   storm without a date being written into the code. The word on this layer is "warned", never
   "flooded": a warning says where the Weather Service expected flooding, and nothing public yet
   says where the water went.

3. **Dams:** every high-hazard dam in the inventory for the states on the map, drawn as a triangle
   shaded by its condition. Opening one says what it is, when it was built, its condition and when
   that was assessed, and whether it has an emergency action plan. McLeod Dam is in the inventory as
   "Mclead Flood Control Dam", which is said, because that is not the spelling anybody will search
   for.

The results table's Hazards view gains the new columns, and the search builder's suggestion "point
out the ones in a real FEMA flood zone" asks `flood_hazard_area` rather than listing two zone letters
and missing a floodway.

**What it is careful about.** The warnings are big polygons over the houses, which is the case the
pointer rule of AC-60 exists for: they answer on their outline and never on their fill, so a house
inside a warning still opens. The reports' remarks were written by spotters and the public and are
shown as text and never as markup. Everything is read from records this machine already holds; the
page causes no new host to be asked except FEMA's map service, for the zones, and says so.
