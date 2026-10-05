## Why

The questions that decide a rural property are not listing fields: flood zone, broadband, aquifer,
wildfire, whether the house stands in the wildland-urban interface, elevation. All are free and public, all attach to a location rather than to a listing,
and all are effectively permanent, which makes them worth caching hard and asking once. The design
constraint that shapes everything here is that public endpoints move and go down, so one dead
service must cost one column rather than a run. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **provider** here is an external public data service, not a listing source. Each is a plugin
  declaring the values it supplies, its cache key, and its time to live.
- A value is **fresh** when it is cached and within its time to live, **stale** when it is cached
  and past it, and **missing** when it was never obtained. Stale is usable and labelled; missing is
  not a value. Those three describe the cache. A fourth condition describes the answer instead: a
  value is **not applicable** when the provider was asked, answered, and what it answered is that
  this location is outside what it covers. That is a fresh, determined value whose content happens
  to be an absence of jurisdiction, and it is not one of the other three.

  A fifth reading sits alongside not-applicable and arrives for the same reason. A value is **known
  only at county grain** when the provider was asked, answered, and what it answered is true of a
  county rather than of a point. Like not-applicable it is a determined value rather than a state of
  the cache, and it is not a negative: "a proposed data center is somewhere in this county" is
  something the source knows, stated at the only grain it knows it. The two are still different.
  Not applicable means this source does not answer here. County grain means it answers, and the
  answer is not about a point.
- A **determined value that is not a measurement** is an answer whose content is about the
  source rather than the place, and each one is spelled out rather than left empty:
  `outside coverage` (the interface), `not mapped` (FEMA has no digital map), `not surveyed` (no
  soil survey), `none mapped within a mile` (no stream or arroyo), and `none within 10 miles`
  (no high-hazard dam). An **empty** value that is stored is also an answer, and which answer is
  fixed per value: for `flood_zone` and `flood_hazard_area` it is "FEMA has not decided", for
  `water_table_cm` "the survey records no water table", for `stream_feet` "no channel within
  a mile", and for `dam_miles` and `dam_nearest` "no high-hazard dam is held for this state or its
  neighbours". A value with no stored row at all is missing, which is the only empty that means
  nobody asked (AC-7). Plan D-21 says how each surface renders each of these.
- The **wildland-urban interface** is where housing meets or intermingles with undeveloped wildland
  vegetation. **Intermix** is housing and vegetation mixed together; **interface** is housing against
  a large continuous block of it. A covered location in neither is not in the interface, which is an
  answer. An uncovered one is not applicable, recorded as `outside coverage`, which is not.

## User stories

- As the person running searches, I want flood, water, internet, and fire answered for every
  property automatically, so that I stop researching them one at a time in four separate government
  tools.
- As the person running searches, I want a service being down to cost me that one column, so that a
  federal outage does not cost me a run.
- As the person running searches, I want a value that was never fetched to look different from a
  value that was fetched and came back negative, so that I do not read an empty cell as good news.
- As the person running searches, I want enrichment to run on its own schedule, so that a long
  backfill does not have to happen inside a listing run.
- As the person running searches, I want repeat runs over the same area to make no requests, so
  that the tool is not asking a public service the same question every night.

## Behavior & scenarios

- **Scenario: a value is fetched once**
  - Given a property at a location never enriched before
  - When the enrichment pass runs
  - Then each configured provider is asked once, the values are cached against the location, and
    the property carries them

- **Scenario: a cache hit costs nothing**
  - Given a location whose values are cached and fresh
  - When the enrichment pass runs again
  - Then no request is made to any provider for that location, and the cached values are used

- **Scenario: nearby properties share a lookup**
  - Given two properties whose locations round to the same cache key
  - When the enrichment pass runs
  - Then one lookup serves both

- **Scenario: a provider is down**
  - Given one provider whose endpoint is unreachable
  - When the enrichment pass runs
  - Then that provider's values are marked missing or left at their previously cached value marked
    stale, the failure is reported, every other provider's values are obtained normally, and the
    pass completes

- **Scenario: only stale values are refreshed**
  - Given a mixture of fresh, stale, and missing values
  - When the pass is asked to refresh only what is stale
  - Then requests are made only for stale and missing values, and fresh values are untouched

- **Scenario: a property has no usable location**
  - Given a property with no coordinates
  - When the enrichment pass runs
  - Then no lookup is attempted, its enriched values are missing, and the reason is recorded as an
    unresolvable location rather than a provider failure

- **Scenario: missing is not false**
  - Given a property whose aquifer value was never obtained
  - When it is read
  - Then the value reads as missing, and nothing presents it as "not over an aquifer"

## Acceptance criteria

- [ ] AC-1: Each provider is a plugin declaring the values it supplies, its cache key, and its time
      to live. Adding one requires no change to the enrichment pass.
- [ ] AC-2: Values are cached against a rounded location plus the provider, and a cache hit within
      the time to live makes no outbound request. A test asserts zero requests on a second pass.
- [ ] AC-3: Two locations that round to the same cache key share one lookup.
- [ ] AC-4: A provider failure marks that provider's values for the affected locations as missing,
      or leaves a previously cached value in place marked stale, and never removes a cached value.
- [ ] AC-5: A provider failure does not prevent any other provider from being queried, and the pass
      completes and reports per-provider outcomes.
- [ ] AC-6: A provider failure never fails the listing run that requested enrichment.
- [ ] AC-7: Fresh, stale, and missing are distinguishable when a value is read, and a missing value
      is never rendered as a negative answer.
- [ ] AC-8: The pass can be limited to stale and missing values only, and to the properties of one
      named search.
- [ ] AC-9: The pass is invocable independently of a listing run and can be scheduled separately.
- [ ] AC-10: A property with no usable coordinates is skipped with a recorded reason distinct from a
      provider failure, and does not cause a request or an error.
- [ ] AC-11: Providers for flood zone, broadband service, principal aquifer, wildfire hazard,
      elevation, boundary resolution, wildland-urban interface, county, data center proximity,
      soils, flash-flood history, streams and arroyos, and dams exist and are individually
      enableable. The flood zone provider supplies `flood_zone` and `flood_hazard_area`.
- [ ] AC-12: A provider covers the whole country unless it declares otherwise. A test asserts a
      successful lookup at locations in geographically distant states, for every provider this
      installation can run. A provider that is not configured is skipped by name rather than
      silently passed over. Broadband covers the country a state at a time: every state can be
      indexed and the test asserts that, while a state nobody has indexed reads as an unloaded
      state rather than as a gap in coverage. A provider that declares partial coverage is tested
      on both sides of its boundary: inside it answers, and outside it reports not applicable
      rather than answering.
- [ ] AC-13: Outbound requests are paced per provider with backoff on throttling, in the same
      spirit as listing sources.
- [ ] AC-14: Endpoint addresses are configuration rather than embedded constants, so a service that
      moves is a settings change rather than a code change.
- [ ] AC-15: A census block in a loaded state with no filed residential service is recorded as a
      known negative rather than as a missing value, in the same way a point over no principal
      aquifer is.
- [ ] AC-16: Broadband service is answered from a locally held index of the FCC's published
      availability files, keyed by census block, rather than from a per-property request to any
      service. Building the index for a state is an explicit action, never a side effect of an
      enrichment pass.
- [ ] AC-17: A property's 2020 census block is resolved from its coordinates through the FCC's
      keyless block service, with the keyless Census coordinate geocoder as fallback after a failed
      or unusable FCC lookup. After the first FCC failure, that provider uses Census for the
      remaining lookups in the pass; a new provider tries FCC again. Both use the existing paced
      session and its bounded network policy, without file-API credentials. A lookup must identify
      one valid 15-digit block in a known state, with any supplied state agreeing with its prefix.
      An ambiguous or unusable answer is a failure, never a known negative. If both services fail,
      the reported reason names both, and cached broadband values remain intact. Successful values
      are cached as before and availability still comes only from the loaded FCC state index.
- [ ] AC-18: The recorded broadband values are the best advertised residential download and upload
      speeds in that block and the providers that offer them. Every surface that shows them says
      the figure is for the block rather than for the property, and says advertised rather than
      measured.
- [ ] AC-19: Satellite service is excluded from the reported speeds and named separately if at all,
      because it is available almost everywhere and including it would report every rural property
      as served while saying nothing about what it can get.
- [ ] AC-20: The FCC's file API is reached with the account name and the token it requires, both
      read from the environment or the uncommitted `.env` and neither ever from a saved search or
      committed config. With either absent the provider is not configured, makes no request, and
      its values read as missing rather than as a failure.
- [ ] AC-21: A property whose state has no index loaded is reported as that, naming the state and
      what would load it, and is distinct both from a provider that is not configured and from a
      provider that failed.
- [ ] AC-22: A wildland-urban interface provider exists, is individually enableable, and supplies a
      value naming which kind of interface a location stands in. It is registered like every other
      provider and requires no change to the enrichment pass.
- [ ] AC-23: A location inside the provider's coverage that falls in no interface polygon is
      recorded as a known negative, in the same way a point over no principal aquifer is, and is
      distinguishable from a value nobody obtained.
- [ ] AC-24: A location outside the provider's coverage is recorded as not applicable, which is
      written as the value `outside coverage`. That is a determined value and not a state of the
      cache: it is distinct from the known negative of AC-23, distinct from the missing value of
      AC-7, and no surface may render it as either. A test asserts all three read differently.
      Deciding it costs no request, and it is not re-asked on a later pass, because a value the
      provider will never answer differently is not a value worth asking about again.
- [ ] AC-25: The classification is read from the source's own attribute. A code this build does not
      recognize is a failure naming the code, never a guessed classification, on the same principle
      the wildfire hazard provider already follows: a wrong fire rating is worse than no fire rating.
- [ ] AC-26: A provider that does not cover the whole country declares what it does cover, and that
      declaration is readable wherever the provider is listed, so nobody has to open the module to
      learn what a column answers for. Providers that cover the country declare nothing, which is
      the default AC-12 states. The coverage test of AC-12 asserts, for a declaring provider, both a
      successful lookup inside its coverage and a not-applicable result outside it.
- [ ] AC-27: A provider answers which county contains a location, supplying `county_name`. Two of
      the three listing sites never send a county at all, so without it a quarter of a statewide
      table shows an empty county and the emptiness is one site's silence rather than a fact about
      the property. A location the service places in no county returns an answer of nothing, which
      is a different thing from a location nobody asked about. It needs no credential and no new
      service address, and is added to the pass without changing the pass, which is AC-1 applying to
      it unchanged.

- [ ] AC-28: A data center provider exists, is individually enableable, is registered like every
      other provider, and requires no change to the enrichment pass. It supplies five values for a
      location, named here because a person types these into a saved search: `data_center_miles`,
      how far to the nearest one operating; `data_center_approved_miles`, how far to the nearest one
      approved or under construction; `data_center_proposed_miles`, how far to the nearest one
      proposed; `data_center_nearest`, what the nearest of those three is and which of the three it
      is; and `data_center_in_county`, which of the three has a site in this property's county that
      is too coarsely located to measure. It needs no credential.
- [ ] AC-29: The values are computed from locally held indexes rather than from a per-property
      request, in the same spirit as broadband (AC-16). Both indexes cover the whole country and are
      fetched whole: the tracker is 1,665 records in two paged requests, and the mapped buildings
      are one query. Unlike broadband, building an index is not an explicit action, because these
      are small enough to be a side effect of a pass that finds them stale. Staleness is decided
      once per pass and never per location: at the five thousand properties the performance
      requirement names, the difference between those two readings is one check and five thousand.
      A pass over an area whose indexes are fresh makes no outbound request at all, and the
      per-property work is local, which AC-2's assertion of zero requests on a second pass covers
      unchanged.
- [ ] AC-30: The two indexes carry different times to live and the difference is deliberate. A
      mapped building is effectively permanent and is held for a long time. A project's status is
      the most perishable value this feature holds, because a site that moved from proposed to
      approved is exactly the change somebody is watching for, so it is held for days rather than
      months. A stale index is still used and still labelled stale, as every other value is (AC-7),
      because last week's answer about a data center is worth more than no answer.
- [ ] AC-31: The source's statuses collapse to the three the values report, and the mapping is
      written down rather than inferred: operating and expanding are operating; approved, permitted
      and under construction are approved; proposed and pre-proposal are proposed. Suspended and
      cancelled feed no distance, because a cancelled project is not a thing near a house. A status
      this build does not recognise is a failure naming the status, never a guess at which of the
      three it belongs in, on the same principle AC-25 already applies to an unrecognised hazard
      class.
- [ ] AC-32: The precision of a distance is the precision its source can support, and carries the
      caveat that a separate column would let a reader skip. A distance to a site the tracker
      locates precisely, or to a mapped building's own outline, is reported to a tenth of a mile. A
      distance to a site the tracker locates only to a town is reported to a whole mile. A site the
      tracker locates only to a county yields no distance at all, because there is no honest number
      to give: its point is a county centroid, and a county here can be four thousand square miles.
      A test asserts that the same site at the same distance reports differently at each of the
      three, and that no value ever reports more precision than its source declares.

      The rounding that forms the cache key is part of this promise rather than separate from it. A
      location is rounded before it is asked about, and that rounding is the cache key (AC-2, AC-3),
      so a rounding coarser than the finest distance reported would undo the promise quietly: three
      decimal places of latitude moves a point by up to about 110 metres, which is the same order as
      the 161 metres a tenth of a mile resolves. This provider rounds to four places, about 11
      metres, chosen to be finer than anything it reports.
- [ ] AC-33: A site too coarsely located to measure is not silently dropped. When one stands in the
      county this property is in, that is recorded and names which of the three it is, so the value
      reads as "a proposed site is somewhere in this county" rather than as an empty cell. This is
      an answer at the grain the source actually knows, and it is distinct from a missing value
      (AC-7) and from a determined distance. A test asserts all three read differently, because
      without this a house beside a seven-thousand-megawatt proposal would read exactly like a house
      nobody asked about, which is the confusion AC-7 exists to prevent.
- [ ] AC-34: Both sources feed the operating distance and neither is de-duplicated against the
      other, because the nearest of two measurements of one site is that site, and a double count
      costs nothing when the answer is a minimum. A mapped building is measured to its outline
      rather than to a point inside it. Nothing counts how many data centers are near a property,
      and nothing is scored, ranked, hidden or coloured by any of these values.
- [ ] AC-35: The tracker's under-counting is stated wherever a reader meets these values, and is
      named as a different thing from the coverage limit of AC-26. Both sources cover the whole
      country, so nothing here is outside coverage; what the tracker is short of is *completeness*,
      because its interest is contested projects, and a quietly-running facility nobody objected to
      can be absent. The second source exists to cover that and does not fully close it. A reader is
      told that a distance to an operating data center is a nearest *known* one.
- [ ] AC-36: Both sources are credited where their data is shown, as their terms require: the
      tracker is free for non-commercial use with attribution, and the mapped buildings are under
      the Open Database License with attribution to OpenStreetMap contributors. Nothing collected
      from either is republished, which the constitution already requires of everything here.

- [ ] AC-37: The per-location work is answered through a spatial index rather than by walking the
      set. Roughly 3,400 points and outlines, asked once per distinct cache key, is on the order of
      ten million comparisons over an area the size of the one the performance requirement names,
      which a straightforward loop does not do in the time that requirement allows. `shapely` is
      already a dependency of this product and its own spatial index answers exactly this question,
      so this costs nothing but saying so.

- [ ] AC-38: Where FEMA has no digital flood map at all, `flood_zone` is the determined value
      `not mapped`. It is decided by asking FEMA's availability layer, and that layer is asked only when
      the zone layer returned nothing, so a point inside a zone costs one request as before. `not mapped`
      is distinct from a value nobody obtained and from a zone FEMA did assign, and a test asserts the
      three read differently. Its address is configuration like every other (AC-14).
- [ ] AC-39: A provider value `flood_hazard_area` says whether a point is in FEMA's special flood
      hazard area, read from FEMA's own `SFHA_TF` attribute rather than inferred from a zone's text,
      so a floodway (`AE (FLOODWAY)`) is in it whatever its zone reads. Every feature FEMA returns
      for the point is read and the worst is kept: the hazard area (a floodway first), then an
      unstudied zone, then the shaded `X` (the 0.2 percent annual chance area, and the qualifiers
      FEMA's own renderer draws in the same colour: the 1 percent areas of less than a square mile
      or less than a foot deep, and the non-accredited levee area), then the levee-reduced `X`, then
      plain `X`. A flag that is neither `T` nor `F` is a failure naming it, never a guess. An older
      feature with no flag at all is read by FEMA's own definition, which is the `A` and `V` zones.
- [ ] AC-40: `flood_hazard_area` is empty, never false, wherever FEMA has not decided: Zone `D`,
      `AREA NOT INCLUDED`, and `not mapped`. FEMA marks Zone `D` as outside its hazard area, and that
      mark means nobody looked. A point FEMA has mapped where the zone layer still returns nothing is a
      hole in FEMA's data rather than an answer from it, because a digital map covers its ground with
      zones edge to edge, plain `X` included; both values are empty there.
- [ ] AC-41: A soils provider exists, is individually enableable, is registered like every other
      provider, and requires no change to the enrichment pass. It supplies five values from the USDA
      NRCS Soil Data Access service, keyless and national, one paced request per location:
      `soil_flooding`, the soil map unit's flooding frequency class; `soil_ponding_percent`, the share
      of the unit that ponds; `water_table_cm`, the shallowest depth to a seasonal water table in
      centimetres; `soil_drainage`, the unit's wettest drainage class; and `hydric_percent`, the share
      that is hydric (wetland) soil. The query sent is built only from the two coordinates, each checked
      to be a number, and from nothing a page or a saved search supplied.
- [ ] AC-42: The words are the source's own classes, read rather than inferred, in lower case:
      `none`, `very rare`, `rare`, `occasional`, `frequent`, `very frequent` for flooding, and the
      seven drainage classes from `excessively drained` to `very poorly drained`. The flooding class
      is the worst among the unit's major components as the source computes it. The legacy class
      `Common`, which a handful of older surveys still carry, reads `frequent`, because it is the
      older name for occasional-to-frequent and the cost of reading it low falls entirely one way. A
      class this build does not recognise is a failure naming it, never a guess. Reading `Common` as
      `frequent` is the one written exception to that rule, and it is not a guess at an unknown
      code: `Common` is a documented legacy class whose range runs from occasional to frequent, and
      it is read at the top of that range because reading it low costs somebody a damp house.
- [ ] AC-43: Three readings stay apart. A place with no soil survey reads `soil_flooding` as `not
      surveyed`, a determined value, as the interface provider's `outside coverage` is. A surveyed
      place where the survey records no seasonal water table leaves `water_table_cm` empty, and
      every surface that shows it says the survey records no water table (on the listing page, the
      command line and to the assessment model in those words; in the table and the sheet, `none
      recorded`) rather than "not known". A place nobody asked about has no value at all. Wherever
      these values are shown, two caveats travel with them: a soil value describes a map unit, which
      can be hundreds of acres, rather than the parcel; and soil flooding is overbank river flooding
      of the soil, which says nothing about flash floods arriving down a wash.
- [ ] AC-44: A flash-flood provider exists, is individually enableable, is registered like every
      other provider, and requires no change to the pass. It supplies five values, named because a
      person types them into a saved search: `flash_flood_warnings`, how many National Weather Service
      flash-flood warnings have covered the point since 2008; `flash_flood_emergencies`, how many of
      those were ever raised to a Flash Flood Emergency; `flash_flood_latest`, the date of the most
      recent warning that covered it; `flash_flood_latest_year`, that date's year, as a number a
      criterion can compare; and `flood_reports_nearby`, how many flood, flash-flood or debris-flow
      storm reports were filed within one mile since 2005. It needs no credential.
- [ ] AC-45: The values are answered from locally held records, fetched whole a state at a time for
      the states the store's properties are in, through a spatial index, as the data center provider
      answers from its own (AC-29, AC-37). Building them is a side effect of a pass that finds them
      stale, decided once per pass and never per location. A year that has ended is fetched once and
      never again, because a closed year's warnings do not change; the current year and the storm
      reports are held for seven days. A year's file fetched before that year closed (or within a
      week of its end) is fetched once more after it closes, and is then held for good. A pass over
      a state whose records are fresh makes no request.
- [ ] AC-46: Each warning is counted once, by its identity: the issuing office, the phenomenon, the
      significance, the event number and the year. The polygon counted is the one issued, which is
      the warning's widest extent, since an update can only shrink it. A warning is an emergency if
      it was ever raised to one, including by a follow-up statement, which is how most of New
      Mexico's were declared. The damage threat the Weather Service attached (considerable or
      catastrophic) is kept with it, worst first, for the map to show (`feat-010/AC-99`).
- [ ] AC-47: A point in a state whose records are not held reads as missing, never as zero, because
      zero means "held, and never warned". A refresh that fails leaves the held records in use and
      labelled stale, as every other stale value is (AC-7). The storm reports are a separate record from
      the warnings, and failing to fetch one does not take the other's values with it.
- [ ] AC-48: What these values are is said wherever they are read. A warning says where the
      Weather Service warned, not where water went, and its polygon is drawn wide (a median of about
      550 square kilometres in New Mexico); "warned" is the word, never "flooded". An emergency polygon is
      drawn over whole towns. A storm report is positioned to about a kilometre, usually as an offset
      from a named place, which is why reports are counted within a mile rather than at the point.
      Dates are the local standard time of the place, worked out from its longitude, so a warning issued
      on a September evening is dated that evening rather than the next day in Greenwich.
- [ ] AC-49: Everything these sources say in words is data. A report's remark is shown as text and
      never as markup, and the archive's own ready-made HTML link is not kept at all.
- [ ] AC-50: A streams provider exists, is individually enableable, is registered like every other
      provider, and requires no change to the pass. From the USGS National Hydrography Dataset,
      keyless and national, one paced request per location, it supplies `stream_feet`, the distance
      to the nearest mapped natural channel within a mile, and `stream_nearest`, which channel that
      is: its name where it has one, whether it is perennial, intermittent or ephemeral where the
      dataset says (a plain `stream`, or a `river` drawn through a lake, where it does not), and the
      distance again in words. A natural channel is a stream, river or wash, including the line a
      river is drawn along through a lake; a canal, ditch, pipeline or underground conduit is not,
      because water does not leave one of those the way it leaves an arroyo. With no channel within
      a mile, `stream_feet` is empty and `stream_nearest` says `none mapped within a mile`, which is
      an answer.
- [ ] AC-51: The distance is measured to the channel's line rather than to any point on it, and is
      reported to the nearest ten feet, which is finer than the map it is measured on and no finer.
      Its cache key rounds to five decimal places, about a metre, so the key is finer than the
      number it keys, which is the promise AC-32 makes for data centers. A mapped channel is a
      channel somebody mapped: an unmapped wash can be closer, and this is said where the value is
      shown.
- [ ] AC-52: A dams provider exists, is individually enableable, is registered like every other
      provider, and requires no change to the pass. From the USACE National Inventory of Dams,
      keyless, it supplies four values about high-hazard dams, which are the ones whose failure
      would probably cost a life: `dam_miles`, how far to the nearest one among the states held for
      this property (its own and its neighbours, AC-53), to a tenth of a mile, at any distance;
      `dam_nearest`, what that dam is (its name, its inventory id, the year it was built, its
      condition and when that was assessed, whether it has an emergency action plan, and the
      distance); `dams_nearby`, how many lie within ten miles; and `dam_worst_nearby`, the worst
      condition among those, or `none within 10 miles`. Each held dam also keeps its primary purpose
      and owner, which no value carries and the map shows when the dam is opened
      (`feat-010/AC-100`). Where no high-hazard dam is held at all, `dam_miles` and `dam_nearest`
      are empty, `dams_nearby` is 0 and `dam_worst_nearby` is `none within 10 miles`.
- [ ] AC-53: The inventory is fetched whole a state at a time, for the states the store's properties
      are in and the states bordering them, because a dam ten miles away can be across a state line. It
      is held for ninety days, refreshed as a side effect of a pass that finds it stale, and a point in a
      state whose inventory or neighbours' inventories are not held reads as missing. The inventory's
      codes are mapped by a table written down here rather than inferred: condition 1 to 6 is
      satisfactory, fair, poor, unsatisfactory, not rated, not available; hazard 4 is high; emergency plan
      1 to 3 is yes, no, not required. `not rated` and `not available` both read `not rated`, which is
      never read as satisfactory. A code this build does not recognise is a failure naming it.
- [ ] AC-54: "Near" is said, and "downstream" never is. The inventory places each dam as one point
      on a structure that can run more than a mile, and inundation maps for local dams are not
      public, so nothing here knows which way a dam drains. The inventory is credited where its data
      is shown, and the README credits all four of this change's sources: the inventory, the Weather
      Service and Iowa State's archive of it, the Natural Resources Conservation Service, and the
      U.S. Geological Survey.
- [ ] AC-55: Enriching a fully cached area of five thousand properties stays inside the performance
      requirement with these providers registered, and the two that hold records answer through a spatial
      index. A test asserts the time for each of the two, in the shape AC-37 already asserts it for data
      centers.

## Edge cases & errors

- A provider returns a successful response with no data for the point, which is the normal answer
  for a location outside a mapped hazard area. This is a known negative value, not a missing one,
  and the two must not be conflated. That holds for every provider whose source covers its ground
  completely, and not for the flood layer, whose coverage has holes: there an empty answer is
  resolved by FEMA's availability layer into `not mapped` (AC-38) or into a gap in FEMA's data
  (AC-40), and neither is a negative. Where the provider covers only part of the country there is a
  third reading, and all three must stay separate: the point is in no mapped area (a negative), the
  point is somewhere this provider does not cover (not applicable), or nobody has asked (missing).
- The interface source is reachable but the property is in a state it does not cover. Not a failure
  and not a negative: the value is not applicable, no request needs to be repeated on the next pass,
  and the reason is legible without opening the source.
- A property sits inside the coverage but outside every interface polygon, which is the normal
  answer for a town centre. A known negative, cached like any other answer.
- A provider changes its response shape. Reported as a failure naming the field that could not be
  read, and the previously cached value is retained as stale rather than being overwritten with
  nothing.
- A provider is slow enough to stall the pass. Requests time out and are treated as failures for
  that location rather than hanging the pass.
- A cache entry exists from a provider that has since been removed from configuration. It is
  retained and ignored rather than deleted, so re-enabling the provider does not re-fetch.
- Rounding places a property's location on the wrong side of a hazard boundary. The rounding
  precision is configurable per provider, so a boundary-sensitive value can use a finer key than
  elevation does.
- The rules refer to an enriched value for a search where that provider is not enabled. Reported by
  the rule engine as a value that will never be populated, which is why the distinction in AC-7
  matters.
- The broadband provider has no credential. It reports itself as not configured, makes no request,
  and its values read as missing rather than as a provider failure, because nobody asked and nothing
  broke. The same is true with a token but no account name, since the FCC requires both. A third
  state sits between those and working: credentials present, no index loaded for the state a
  property is in, which names the state rather than reading as either of the other two.
- A census block is in a state whose index is loaded and has no filed residential service. That is
  an answer rather than a gap, in the same way a point over no principal aquifer is, and it is
  recorded as a known negative.
- Crime and school data are referenced by the export template but have no national free source.
  They are left blank rather than filled from a source that only covers part of the country.

## Non-functional requirements

- Performance: enriching a fully cached area of 5,000 properties completes in under five seconds
  and makes no network requests. A cold pass is bounded by provider pacing rather than by local
  work, for every provider that asks a question per location, which is all of them but three. The
  data center, flash-flood and dam providers make no per-location request at all, so their cold
  pass is bounded by local work alone, and AC-37 and AC-55 are what keep that work small enough not
  to matter. Stated this way rather than deleted, because it is still the right expectation for the
  other ten, and a reader who
  cannot tell which kind they are looking at is the reader this feature is written for.
- Security: no credentials are required, and none is embedded. Every provider but broadband is a
  keyless public service. Broadband was keyless when this was first written and is not now: the
  FCC's national map requires an account, and its API wants two values rather than one, the account
  name and the token, sent as headers. Both are read from the environment or the uncommitted `.env`
  file, where every other secret in this product lives, and the provider is absent by default and
  makes no request without both. The tool is fully functional with neither, which is product
  invariant 9.

  What any provider downloads (the FCC's files, the data center indexes, the flash-flood and dam
  records) is a public dataset written where the database lives, which is local data and never
  committed. Responses are data: never evaluated, never used to construct a path, and a downloaded
  archive is read in memory. The soils query is the only request here with a body, and that body
  is a fixed query text with two checked numbers in it and nothing else.
- Reliability: any provider failing leaves every cached value intact and every other provider's
  results usable.
- Accessibility: none. No user-facing surface.

## Open questions

- Whether permanent values such as elevation should carry an infinite time to live or a very long
  one is a plan decision with no behavioral difference within this release.
