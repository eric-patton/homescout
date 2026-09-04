# Delta — enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-28**: A data center provider exists, is individually enableable, is registered like every
  other provider, and requires no change to the enrichment pass. It supplies five values for a
  location, named here because a person types these into a saved search:
  `data_center_miles`, how far to the nearest one operating; `data_center_approved_miles`, how far
  to the nearest one approved or under construction; `data_center_proposed_miles`, how far to the
  nearest one proposed; `data_center_nearest`, what the nearest of those three is and which of the
  three it is; and `data_center_in_county`, which of the three has a site in this property's county
  that is too coarsely located to measure. It needs no credential.

- **AC-29**: The values are computed from locally held indexes rather than from a per-property
  request, in the same spirit as broadband (AC-16). Both indexes cover the whole country and are
  fetched whole: the tracker is 1,665 records in two paged requests, and the mapped buildings are
  one query. Unlike broadband, building an index is not an explicit action, because these are
  small enough to be a side effect of a pass that finds them stale. Staleness is decided once per
  pass and never per location: at the five thousand properties the performance requirement names,
  the difference between those two readings is one check and five thousand. A pass over an area
  whose indexes are fresh makes no outbound request at all, and the per-property work is local,
  which AC-2's assertion of zero requests on a second pass covers unchanged.

- **AC-37**: The per-location work is answered through a spatial index rather than by walking the
  set. Roughly 3,400 points and outlines, asked once per distinct cache key, is on the order of ten
  million comparisons over an area the size of the one the performance requirement names, which a
  straightforward loop does not do in the time that requirement allows. `shapely` is already a
  dependency of this product and its own spatial index answers exactly this question, so this costs
  nothing but saying so.

- **AC-30**: The two indexes carry different times to live and the difference is deliberate. A
  mapped building is effectively permanent and is held for a long time. A project's status is the
  most perishable value this feature holds, because a site that moved from proposed to approved is
  exactly the change somebody is watching for, so it is held for days rather than months. A stale
  index is still used and still labelled stale, as every other value is (AC-7), because last week's
  answer about a data center is worth more than no answer.

- **AC-31**: The source's statuses collapse to the three the values report, and the mapping is
  written down rather than inferred: operating and expanding are operating; approved, permitted and
  under construction are approved; proposed and pre-proposal are proposed. Suspended and cancelled
  feed no distance, because a cancelled project is not a thing near a house. A status this build
  does not recognise is a failure naming the status, never a guess at which of the three it belongs
  in, on the same principle AC-25 already applies to an unrecognised hazard class.

- **AC-32**: The precision of a distance is the precision its source can support, and carries the
  caveat that a separate column would let a reader skip. A distance to a site the tracker locates
  precisely, or to a mapped building's own outline, is reported to a tenth of a mile. A distance to
  a site the tracker locates only to a town is reported to a whole mile. A site the tracker locates
  only to a county yields no distance at all, because there is no honest number to give: its point
  is a county centroid, and a county here can be four thousand square miles. A test asserts that
  the same site at the same distance reports differently at each of the three, and that no value
  ever reports more precision than its source declares.

  The rounding that forms the cache key is part of this promise rather than separate from it. A
  location is rounded before it is asked about, and that rounding is the cache key (AC-2, AC-3), so
  a rounding coarser than the finest distance reported would undo the promise quietly: three
  decimal places of latitude moves a point by up to about 110 metres, which is the same order as
  the 161 metres a tenth of a mile resolves. This provider rounds to four places, about 11 metres,
  chosen to be finer than anything it reports.

- **AC-33**: A site too coarsely located to measure is not silently dropped. When one stands in the
  county this property is in, that is recorded and names which of the three it is, so the value
  reads as "a proposed site is somewhere in this county" rather than as an empty cell. This is an
  answer at the grain the source actually knows, and it is distinct from a missing value (AC-7) and
  from a determined distance. A test asserts all three read differently, because without this a
  house beside a seven-thousand-megawatt proposal would read exactly like a house nobody asked
  about, which is the confusion AC-7 exists to prevent.

- **AC-34**: Both sources feed the operating distance and neither is de-duplicated against the
  other, because the nearest of two measurements of one site is that site, and a double count costs
  nothing when the answer is a minimum. A mapped building is measured to its outline rather than to
  a point inside it. Nothing counts how many data centers are near a property, and nothing is
  scored, ranked, hidden or coloured by any of these values.

- **AC-35**: The tracker's under-counting is stated wherever a reader meets these values, and is
  named as a different thing from the coverage limit of AC-26. Both sources cover the whole
  country, so nothing here is outside coverage; what the tracker is short of is *completeness*,
  because its interest is contested projects, and a quietly-running facility nobody objected to can
  be absent. The second source exists to cover that and does not fully close it. A reader is told
  that a distance to an operating data center is a nearest *known* one.

- **AC-36**: Both sources are credited where their data is shown, as their terms require: the
  tracker is free for non-commercial use with attribution, and the mapped buildings are under the
  Open Database License with attribution to OpenStreetMap contributors. Nothing collected from
  either is republished, which the constitution already requires of everything here.

## MODIFIED

- **AC-11, which providers exist**
  - Was: Providers for flood zone, broadband service, principal aquifer, wildfire hazard,
    elevation, boundary resolution, wildland-urban interface, and county exist and are individually
    enableable.
  - Now: the same list, plus data center proximity.

- **Non-functional requirements, performance: what bounds a cold pass**
  - Was: "A cold pass is bounded by provider pacing, not by local work."
  - Now: that holds for every provider that asks a question per location, which is all of them but
    this one. This provider makes no per-location request, so its cold pass is bounded by local work
    alone, and AC-37 is what keeps that work small enough not to matter. The sentence is amended
    rather than deleted because it is still the right expectation for the other eight, and a reader
    who does not know which kind they are looking at is the reader this feature is written for.

- **Vocabulary used in this feature: a determined answer can be coarser than the question**
  - Was: three conditions describing the cache (fresh, stale, missing) and a fourth describing the
    answer instead (not applicable, meaning the provider was asked, answered, and what it answered
    is that this location is outside what it covers).
  - Now: a fifth reading, alongside not-applicable and for the same reason. A value is **known only
    at county grain** when the provider was asked, answered, and what it answered is true of a
    county rather than of a point. Like not-applicable it is a determined value rather than a state
    of the cache, and it is not a negative: "a proposed data center is somewhere in this county" is
    something the source knows, stated at the only grain it knows it. The two are still different.
    Not applicable means this source does not answer here. County grain means it answers, and the
    answer is not about a point.

- **Non-functional requirements, security: the count of keyless providers**
  - Was: "Six of the seven providers are keyless public services, and the seventh needs no
    credential either; broadband remains the one exception."
  - Now: the same statement with the count moved on by one. The new provider needs no credential,
    and both of its sources are keyless. What it downloads is public data written where the
    database lives, which is local data and never committed, and neither index is ever evaluated or
    used to construct a path.

## REMOVED

Nothing.
