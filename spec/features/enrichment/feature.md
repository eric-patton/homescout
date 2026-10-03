---
schema_version: 2
id: "feat-007"
slug: "enrichment"
title: "Location enrichment providers"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001]
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
  last_run: 2026-10-03
  open: 8
  contradicts: 0
human_signoff: []
open_decisions: []
overrides: []
extends: []
---

# Feature notes — Location enrichment providers

## Scope

A separately schedulable pass that attaches public data to a location rather than to a listing:
flood zone, broadband service, principal aquifer, wildfire hazard, elevation, and boundary
resolution, and since then the wildland-urban interface, county, data centers, soils, flash-flood
history, streams and arroyos, and high-hazard dams. Each provider is a plugin declaring its own cache key and time-to-live, cached by
rounded coordinates and never re-fetched on a hit. One dead endpoint marks that one field stale
and the run continues.

Brief section 5.4.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes to this feature's own spec

- **2026-08-23, during planning.** The security requirement read "no credentials". Verifying the
  endpoints showed the FCC's national broadband map is now keyed, and the keyless one it replaced
  covered mobile service only and is gone. Two criteria collided: AC-11 wants a broadband provider
  to exist, and the requirement wanted no credentials anywhere.

  Settled by narrowing the requirement rather than dropping the provider: no credential is
  *required*, none is embedded, and broadband is absent by default and enabled by a token in the
  environment. That is the shape the constitution already uses for every other secret, and product
  invariant 9 already says an optional component absent by default leaves the tool fully functional.
  Recorded here because a requirement that quietly changes to match what was built is worth nothing.

- **2026-08-24, spreadsheet export (feat-011).** No change to this feature, and one thing it is now
  measured by.

  Four of the default sheet's columns come from here: FEMA Flood Zone, Principal Aquifer, Internet,
  and (as columns outside the default set) Wildfire Hazard and Elevation. On a live run over
  Portales, after `homescout enrich`, flood zone, elevation, aquifer and wildfire each answered for
  all 83 properties, and Internet answered for none, because the FCC map needs a token this
  installation has not got. That is the shape this feature always promised: a provider that needs
  something nobody supplied is skipped and says so, rather than failing.

  The export reports an empty enriched column as "the enrichment pass has not been run for these
  properties", which is the first place in the product where a person is told to run this.

- **2026-08-25, the wildland-urban interface.** A question about whether `nmwrap.org` could feed
  New Mexico searches turned into the first provider here that does not cover the country.

  Most of what that portal publishes was rejected on the evidence. Its wildfire-potential raster is
  the same USFS product the `wildfire` provider already reads. Its historic-fire layer stops at 2017,
  so a point inside the Hermits Peak and Calf Canyon burn scar answers "no fire here". The national
  alternative, USDA's Community Wildfire Risk Reduction Zones, is disqualified by its own service
  description: the pixel values "have been altered" and the service is "intended primarily for data
  visualization" rather than analysis. Recording an altered value as a property's exposure class is
  the guess product invariant 10 forbids.

  What was taken is the interface layer, which answers a question hazard potential does not: whether
  houses are standing in the vegetation rather than how the vegetation would burn. It is an exact
  vector attribute with no resampling and no disclaimer.

  Two things this cost. The national-coverage rule was amended on main, in both governing documents,
  to permit a partial-coverage provider on the condition that a location outside its coverage reads
  as not applicable rather than as an answer; that restaged every feature's pre-build check. And the
  coverage test is not a bounding box, because New Mexico's box contains El Paso: the ambiguous case,
  inside the box with no polygon, asks a county layer before recording a negative.

  Checked while verifying: the endpoint the shipped `wildfire` provider uses carries no such
  alteration notice and its legend matches `WILDFIRE_CLASSES` exactly. No defect there.

- **2026-09-04, how close the data centres are (`changes/how-close-the-data-centers/`).** Asked for
  as a map layer, and half of it belongs here: three distances, split by whether a data centre is
  running, being built, or merely applied for, because a house four miles from each of those is in
  three different positions.

  The first provider here whose `fetch` makes no request. There is no service that answers "what is
  the nearest data centre to here", because nearest is asked of a set rather than of a point, so two
  national records are fetched whole and the arithmetic is local. That parts company with D-12,
  which said an index is only ever built when a person asks; the boundary was protecting predictable
  cost, and 1,665 records over two requests plus one query is not the FCC's gigabytes.

  Two sources because neither is enough. The tracker is the only free national record carrying a
  project's *status*, and its interest is contested projects, so Virginia has 463 rows and New
  Mexico has 9 and Meta's Los Lunas campus is missing entirely. OpenStreetMap has that campus, as
  outlines rather than pins.

  The part worth remembering is the precision rule. The tracker rates its own siting and the bottom
  rating is a county centroid: one New Mexico proposal is recorded at a city of "Lea County", 4,400
  square miles. So the number's own precision carries the caveat, a tenth of a mile down to a whole
  mile down to no number at all, and the sites that get no number are named as standing somewhere in
  the property's county instead. Dropping them would have made a house beside a seven-thousand-
  megawatt proposal read exactly like a house nobody asked about.

  The pre-build check earned its place twice. It found that this provider makes the performance
  requirement's own sentence false, since a cold pass here is bounded entirely by local work, and
  that a plain loop over three and a half thousand sites would miss the five-second bar by an order
  of magnitude; the fix is a spatial index and a test that asserts the time. It also found that D-12
  claimed broadband was the only provider with state, which this made untrue.

- **2026-09-04, a defect found by the slow suite: the live coverage test skipped the data center
  provider.** Three failures, one per distant state, the day after the provider arrived. The test
  built its providers bare, and this one is not configured until it has been told where its indexes
  live; a pass attaches the store, the test never had. It attaches a throwaway workspace now, so the
  provider is checked live like the rest. Recorded as `T-dc-14`.

- **2026-09-30, saved searches' named addresses (feat-004, `changes/named-addresses/`).** The
  boundary provider answers one more question for saved searches: where is this street address.
  `CensusBoundaries.place_address` asks the Census one-line geocoder (a new `address` endpoint in
  `settings.py`, overridable like the rest, paced under its own key) and keeps the point, the line
  it matched and that line's ZIP code in the same cache as the boundaries. A match is believed for a
  year and no match for thirty days, so new construction is asked about again once the Census has
  it. Cache-only like everything else the provider answers during a run; `prepare_addresses` is the
  one call that may fetch, and saved searches makes it before a run starts, never inside the
  filtering loop. Free, national and keyless, which is the constitution's rule for external data.

- **2026-10-03, where water goes (`changes/where-fema-has-no-map/`, `changes/where-the-water-goes/`).**
  Asked for by a mold-sensitive household the week after the remnants of Hurricane Polo flooded
  southern New Mexico and put McLeod Dam into a Flash Flood Emergency: show where the storm went and
  where it could happen again, so those houses can be avoided.

  Decided by three independent reviews run before anything was written (one verifying every
  candidate source live at New Mexico coordinates, one fitting the answer to this codebase, one
  arguing a mold-sensitive buyer's case), then counted against the 846 New Mexico listings the live
  search keeps. Two proposals died on those counts: dropping every house any past emergency covered
  (14 percent of the list, because emergency polygons are drawn over towns), and a rolling
  past-year warning count (56 percent, and it would forget this storm next October).

  The first finding was about this feature's own flood value. It read an empty FEMA answer as "in no
  flood zone", on the belief that FEMA maps the whole country; it maps about three quarters of New
  Mexico, and 285 of the live search's locations were places with no digital map at all. Zone D was
  the second hole, and reading only the first feature FEMA returned was a real defect. So the flood
  provider now asks FEMA's availability layer when the zone layer is empty (`not mapped`), supplies
  FEMA's own yes or no (`flood_hazard_area`), reads every feature worst first, and leaves the yes or
  no empty wherever FEMA has not decided.

  Then four providers, each answering a question FEMA does not, each free, national and keyless:
  soils (USDA Soil Data Access, the shallow-groundwater and wetland signal), flash-flood history
  (the Weather Service's warnings and storm reports since 2008, archived by Iowa State), streams and
  arroyos (USGS hydrography), and high-hazard dams (USACE National Inventory of Dams). The soil
  survey read "none" at every town the storm flooded, which is why it is a groundwater signal here
  and not a flash-flood one, and why streams came into this change rather than a later one.

  Flash floods and dams hold national records a state at a time, like the data centre provider, in
  a shared `kept.py`. A closed year of warnings is fetched once, ever. Verified live on 2026-10-03:
  at Hatch, the held record shows the McLeod emergency and a high-hazard dam in poor condition within
  ten miles; Arrey, in Sierra County, reads `not mapped`; a playa east of Albuquerque reads frequent
  flooding with the water table at the surface; Rincon is beside the Rincon Arroyo.

  Found while building it: `settings.picture_of` turned a map-service layer's query address into an
  export address no ArcGIS map service serves. Nothing drew one until FEMA's zones; fixed under the
  browser feature's `floods-on-the-map`.

