## Why

The questions that decide a rural property are not listing fields: flood zone, broadband, aquifer,
wildfire, elevation. All are free and public, all attach to a location rather than to a listing,
and all are effectively permanent, which makes them worth caching hard and asking once. The design
constraint that shapes everything here is that public endpoints move and go down, so one dead
service must cost one column rather than a run. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **provider** here is an external public data service, not a listing source. Each is a plugin
  declaring the values it supplies, its cache key, and its time to live.
- A value is **fresh** when it is cached and within its time to live, **stale** when it is cached
  and past it, and **missing** when it was never obtained. Stale is usable and labelled; missing is
  not a value.

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
      elevation, and boundary resolution exist and are individually enableable.
- [ ] AC-12: Every provider covers the whole country. A test asserts a successful lookup at
      locations in geographically distant states.
- [ ] AC-13: Outbound requests are paced per provider with backoff on throttling, in the same
      spirit as listing sources.
- [ ] AC-14: Endpoint addresses are configuration rather than embedded constants, so a service that
      moves is a settings change rather than a code change.

## Edge cases & errors

- A provider returns a successful response with no data for the point, which is the normal answer
  for a location outside a mapped hazard area. This is a known negative value, not a missing one,
  and the two must not be conflated.
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
- Crime and school data are referenced by the export template but have no national free source.
  They are left blank rather than filled from a source that only covers part of the country.

## Non-functional requirements

- Performance: enriching a fully cached area of 5,000 properties completes in under five seconds
  and makes no network requests. A cold pass is bounded by provider pacing, not by local work.
- Security: no credentials. Responses are data, never evaluated, and never used to construct paths.
- Reliability: any provider failing leaves every cached value intact and every other provider's
  results usable.
- Accessibility: none. No user-facing surface.

## Open questions

- Whether permanent values such as elevation should carry an infinite time to live or a very long
  one is a plan decision with no behavioral difference within this release.
