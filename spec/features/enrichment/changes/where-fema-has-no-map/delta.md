# Delta: enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-38**: Where FEMA has no digital flood map at all, `flood_zone` is the determined value
  `not mapped`. It is decided by asking FEMA's availability layer, and that layer is asked only when
  the zone layer returned nothing, so a point inside a zone costs one request as before. `not mapped`
  is distinct from a value nobody obtained and from a zone FEMA did assign, and a test asserts the
  three read differently. Its address is configuration like every other (AC-14).

- **AC-39**: A provider value `flood_hazard_area` says whether a point is in FEMA's special flood
  hazard area, read from FEMA's own `SFHA_TF` attribute rather than inferred from a zone's text, so
  a floodway (`AE (FLOODWAY)`) is in it whatever its zone reads. Every feature FEMA returns for the
  point is read and the worst is kept: the hazard area (a floodway first), then an unstudied zone,
  then the shaded `X` (the 0.2 percent annual chance area, and the qualifiers FEMA's own renderer
  draws in the same colour: the 1 percent areas of less than a square mile or less than a foot deep,
  and the non-accredited levee area), then the levee-reduced `X`, then plain `X`. A flag that is
  neither `T` nor `F` is a failure naming it, never a guess. An older feature with no flag at all is
  read by FEMA's own definition, which is the `A` and `V` zones.

- **AC-40**: `flood_hazard_area` is empty, never false, wherever FEMA has not decided: Zone `D`,
  `AREA NOT INCLUDED`, and `not mapped`. FEMA marks Zone `D` as outside its hazard area, and that
  mark means nobody looked. A point FEMA has mapped where the zone layer still returns nothing is a
  hole in FEMA's data rather than an answer from it, because a digital map covers its ground with
  zones edge to edge, plain `X` included; both values are empty there.

## MODIFIED

- **Edge cases & errors, the first bullet: a successful response with no data**
  - Was: a provider returning no data for a point is "the normal answer for a location outside a
    mapped hazard area", a known negative.
  - Now: that remains true of every provider whose source covers its ground completely (the aquifer
    layer, the interface layer inside its coverage). It is not true of the flood layer, whose
    coverage has holes: there, an empty answer is resolved by the availability layer into
    `not mapped` (AC-38) or into a gap in FEMA's data (AC-40), and neither is a negative.

- **AC-11, which providers exist**
  - Was: the flood zone provider supplies `flood_zone`.
  - Now: it supplies `flood_zone` and `flood_hazard_area`.

## REMOVED

Nothing.

## Defect traced to this change

- The flood provider read only the first feature FEMA returned (`feat-007/AC-11`). Fixed by AC-39,
  with a regression test that answers with a plain `X` listed before a floodway.
