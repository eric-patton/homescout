# Proposal — enrichment

**Trigger:** The person running searches asked whether New Mexico's wildfire risk portal
(`nmwrap.org`) could feed these searches, since New Mexico is where the searches are. The portal
turns out to be a thin Esri front end over a public ArcGIS server at the University of New Mexico's
Earth Data Analysis Center, keyless, query-enabled, and speaking the same request shape this
feature's other providers already speak.

**Summary:** Most of what that portal publishes this tool either already has or should not touch.
Its headline wildfire-potential raster is the same USFS Wildfire Hazard Potential product the
`wildfire` provider already reads. Its historic-fire boundary layer stops at 2017, so it has no
Hermits Peak and Calf Canyon (2022) and no South Fork or Salt (2024): a point inside the largest
burn scar in state history answers "no fire here", which is precisely the false good news this
feature exists to prevent.

One layer is worth having, and it answers a question nothing else here answers. The
wildland-urban interface is where housing meets or intermingles with undeveloped wildland
vegetation, and it is the distinction fire agencies and insurers actually act on. It is not
derivable from hazard potential: hazard potential describes how the vegetation would burn, while
the interface describes whether houses are standing in it. The layer is a vector polygon with one
exact attribute, so there is no resampling and no decoding, and a point that falls in no polygon is
a real answer rather than a gap.

The national alternatives were checked first and rejected on the evidence. The USDA Forest Service
publishes Community Wildfire Risk Reduction Zones for the whole country, keyless, on the same
server family the `wildfire` provider already uses, in five clean classes. Its own service
description says the pixel values "have been altered from the original raster dataset" and that the
service is "intended primarily for data visualization" rather than quantitative analysis. Recording
an altered value as a property's exposure class would violate the invariant that a field is never
filled with a guess. The related national exposure-type layer is worse: its legend names three
classes while the raster returns a continuous nought-to-one-thousand scale that this build cannot
decode with confidence.

So the source is regional, and that is the part of this change that costs something. The rule
requiring national coverage was amended on main first, in both governing documents, to permit a
partial-coverage provider on the condition that a location outside its coverage is reported as not
applicable rather than as an answer. This change is what that amendment was for, and it carries the
obligation: outside New Mexico the value must say so, and must never read as "not in the interface".

While verifying this, the endpoint the shipped `wildfire` provider already uses was checked against
the same standard and is sound: eight-bit pixels, values one through seven, no alteration notice,
and a legend matching `WILDFIRE_CLASSES` exactly. No defect there.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected:** AC-11 (which providers exist) gains one. AC-12 (national coverage)
  needs restating now that a provider may cover part of the country, and its live test needs a
  second assertion: a lookup inside the coverage answers, and one outside it reports not
  applicable rather than answering. The feature's fresh / stale / missing vocabulary gains a fourth
  condition that is none of the three, because not-applicable is a determined value rather than a
  state of the cache. The security requirement's count of keyless providers changes. The edge case
  covering a successful response with no data for the point has to separate "in coverage and in no
  polygon" from "not covered at all".
- **Design decisions affected:** D-4 (a provider is a plugin the pass never names) holds unchanged,
  which is the whole point of this being a new module and a registration. D-2 (the cache) and D-7
  (reading a value says how old it is) are deliberately *not* changed: `Status` stays
  `fresh | stale | missing`, and not-applicable is carried as the value's content rather than as a
  fourth status. Making it a status would ripple into every reader of every provider to serve one
  provider, and it would be the wrong shape besides: the value was determined, and what was
  determined is that this source does not answer here. That choice is new and needs recording as a
  design decision.
- **Tasks affected (regenerate these):** none of the existing ones. New tasks for the provider, the
  endpoint entry, the namespace field, the export column, the tests, and the README.
- **Already-built code affected:** `enrich/providers.py` (a new provider), `enrich/settings.py` (a
  new endpoint entry), `enrich/registry.py` (the registration, whose import-time check against the
  rule namespace runs in both directions and will fail until the field exists),
  `rules/namespace.py` (the new enriched field), `export/columns.py` and the export templates (a
  column outside the default set, as wildfire hazard already is), and whatever the command line and
  the browser use to render an enriched value.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
