# Proposal: property-assessment

**Trigger:** The enrichment feature's `where-fema-has-no-map` and `where-the-water-goes` changes,
made for a mold-sensitive household after the remnants of Hurricane Polo flooded southern New
Mexico. They put sixteen new values about water in every dossier this feature sends.

**Summary:** A model reading a dossier will see `flood_zone: X (AREA OF MINIMAL FLOOD HAZARD)`,
`soil_flooding: none`, `flash_flood_warnings: 0`, and is liable to write any of them up as a point in
the property's favour. None of them is that. Rincon, which FEMA maps as minimal hazard, stayed under
water a day after the storm; the soil survey reads "none" at all five towns it flooded, because its
class is river flooding of the soil; and a count of zero warnings says the Weather Service never
drew a warning over the spot, not that water cannot reach it. So the instruction says so, in the
same place it already says a value nobody holds is not a negative, and the dossier names the new
values among what was not looked up when they are absent.

The instruction is not part of a reading's fingerprint, so this changes no reading already made.
The new values are, as every enriched value always has been: a property whose dossier gains them
reads as worth reading again, which is the right outcome and costs a model call per property the
next time somebody runs a pass.
