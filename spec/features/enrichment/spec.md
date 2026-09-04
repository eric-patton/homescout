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
      elevation, boundary resolution, wildland-urban interface, county, and data center proximity
      exist and are individually enableable.
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
      known negative rather than as a missing value, in the same way a point outside a mapped flood
      zone is.
- [ ] AC-16: Broadband service is answered from a locally held index of the FCC's published
      availability files, keyed by census block, rather than from a per-property request to any
      service. Building the index for a state is an explicit action, never a side effect of an
      enrichment pass.
- [ ] AC-17: A property's block is resolved from its coordinates through the FCC's keyless block
      service, paced like every other request this feature makes, and cached like every other
      enriched value.
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
      recorded as a known negative, in the same way a point outside a mapped flood zone is, and is
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

## Edge cases & errors

- A provider returns a successful response with no data for the point, which is the normal answer
  for a location outside a mapped hazard area. This is a known negative value, not a missing one,
  and the two must not be conflated. Where the provider covers only part of the country there is a
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
  an answer rather than a gap, in the same way a point outside a mapped flood zone is, and it is
  recorded as a known negative.
- Crime and school data are referenced by the export template but have no national free source.
  They are left blank rather than filled from a source that only covers part of the country.

## Non-functional requirements

- Performance: enriching a fully cached area of 5,000 properties completes in under five seconds
  and makes no network requests. A cold pass is bounded by provider pacing rather than by local
  work, for every provider that asks a question per location, which is all of them but one. The
  data center provider makes no per-location request at all, so its cold pass is bounded by local
  work alone, and AC-29a is what keeps that work small enough not to matter. Stated this way rather
  than deleted, because it is still the right expectation for the other eight, and a reader who
  cannot tell which kind they are looking at is the reader this feature is written for.
- Security: no credentials are required, and none is embedded. Seven of the eight providers are
  keyless public services, and the eighth needs no credential either; broadband remains the one
  exception. The data center provider's two sources are both keyless, and what it downloads is
  public data written where the database lives, which is local data and never committed; neither
  index is ever evaluated, and nothing in either becomes a path. It was not one when this was written. The FCC's national map now requires an account, and its API wants two values rather than one: the
  account name and the token, sent as headers. Both are read from the environment or the
  uncommitted `.env` file, where every other secret in this product lives, and the provider is
  absent by default and makes no request without both. The tool is fully functional with neither,
  which is product invariant 9. What is downloaded is a public dataset and is written where the
  database lives, which is local data and is never committed. Responses are data, never evaluated,
  and never used to construct paths; a downloaded archive is read in memory and nothing in it
  becomes a path.
- Reliability: any provider failing leaves every cached value intact and every other provider's
  results usable.
- Accessibility: none. No user-facing surface.

## Open questions

- Whether permanent values such as elevation should carry an infinite time to live or a very long
  one is a plan decision with no behavioral difference within this release.
