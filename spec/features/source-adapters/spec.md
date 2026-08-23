## Why

Three providers, no supported API between them, each with its own query surface, its own ceiling,
and its own opinion about callers it dislikes. This feature is the seam that keeps those
differences from leaking: one adapter per provider, all answering the same two questions, plus the
shared politeness layer that stands between the tool and getting blocked. It ships one working
adapter, against Realtor.com, because an interface with no implementation proves nothing. The
problem brief is in `research.md`.

## Vocabulary used in this feature

- A **capability declaration** is an adapter's honest answer to "which parts of a query will you
  apply on your side?" Everything it does not claim is applied locally by the caller.
- A **raw listing** is one row exactly as a provider returned it, tagged with the provider that
  produced it and the time it was fetched. The glossary in `product-global.md` governs.
- A **provider outcome** is the per-source result of one query: `ok`, `failed`, or `unavailable`.
  `unavailable` means the provider cannot serve this query at all, which is a different thing from
  having tried and failed.

## User stories

- As the person running searches, I want a provider that is down or throttling to cost me that
  provider's listings and nothing else, so that one bad afternoon does not lose me a run.
- As the person running searches, I want the tool to be slow and polite by default, so that
  scheduled use over months does not get me blocked.
- As the person running searches, I want to know which filters the provider applied and which the
  tool applied afterwards, so that a surprising result set is diagnosable.
- As whoever adds the fourth source, I want adding a provider to mean writing one adapter, so that
  the core never accumulates provider-specific branches.
- As the person running searches, I want a query larger than a provider's ceiling to still return
  everything, so that a broad search is not silently truncated.

## Behavior & scenarios

- **Scenario: an adapter declares what it can filter**
  - Given a provider that applies price and bedroom filters on its side but not lot size
  - When its capability declaration is read
  - Then price and bedrooms are listed as applied by the provider and lot size is not, and the
    caller applies lot size locally

- **Scenario: an unsupported filter is never silently dropped**
  - Given a query carrying a filter the provider does not support
  - When the adapter runs the query
  - Then the filter is absent from the provider request, is reported as not applied by the
    provider, and the returned rows are not claimed to satisfy it

- **Scenario: every returned row is attributed**
  - Given any successful query against any provider
  - When its rows are examined
  - Then each row records the provider that produced it and the time it was fetched, and the
    provider's own response for that row is retained unaltered alongside the normalized fields

- **Scenario: requests are paced**
  - Given a query that requires several requests to one provider
  - When the adapter issues them
  - Then consecutive requests to that provider are separated by at least the configured delay, and
    the pacing applies per provider rather than globally

- **Scenario: a provider refuses or throttles**
  - Given a provider responding with a refusal or a throttle response
  - When the adapter encounters it
  - Then the adapter waits an increasing interval with random variation before retrying, retries at
    most the configured number of times, and reports the provider outcome as `failed` if the
    refusals continue

- **Scenario: a provider fails**
  - Given a provider that errors, times out, or returns an unusable response
  - When the adapter gives up on it
  - Then it reports the provider outcome as `failed` with a human-readable reason, returns no rows
    for that provider, and raises nothing that would stop another provider from being queried

- **Scenario: a query exceeds the provider's ceiling**
  - Given a query whose matching set is larger than the provider will return in one response
  - When the adapter runs it
  - Then the adapter splits the query along a dimension the provider supports, issues the pieces
    under the same pacing rules, and returns the union with duplicates removed

- **Scenario: the ceiling cannot be worked around**
  - Given a query that still exceeds the ceiling after splitting as far as the provider allows
  - When the adapter completes
  - Then it returns the rows it did retrieve and reports that the result was truncated, naming the
    ceiling that caused it

- **Scenario: the Realtor.com adapter accepts the geography forms it supports**
  - Given an area expressed as a ZIP code, a city, a city with a state, a county, a state, or an
    address with a radius
  - When the Realtor.com adapter is asked for it
  - Then the query is issued in the provider's own form and the provider outcome is `ok`

- **Scenario: an area form a provider cannot express**
  - Given an area a provider has no way to represent
  - When the adapter is asked for it
  - Then it reports the provider outcome as `unavailable` with the reason, rather than substituting
    a different area or returning an empty result

- **Scenario: expensive per-property detail is opt-in**
  - Given the Realtor.com adapter's option to fetch tax history and school data
  - When it is not requested
  - Then no additional per-property request is made, and when it is requested the additional
    requests are paced by the same rules as every other request

- **Scenario: a new provider is added**
  - Given a new adapter that satisfies the interface and declares its capabilities
  - When it is registered
  - Then it can be named in a saved search and used in a run with no change to any existing
    adapter, to the run loop, or to the store

## Acceptance criteria

- [ ] AC-1: Every adapter exposes a name, a capability declaration, and a search operation, and a
      test that registers a stub adapter satisfying only those three can run a query end to end.
- [ ] AC-2: A capability declaration enumerates exactly the query fields the provider applies on
      its side. A field absent from the declaration is never sent to the provider.
- [ ] AC-3: The result of a search reports, per query field, whether the provider applied it, so a
      caller can determine what remains to be applied locally.
- [ ] AC-4: Every returned row carries the producing provider's name and a fetch timestamp in UTC.
- [ ] AC-5: Every returned row retains the provider's original response payload for that property
      alongside the normalized fields, and the normalized fields are derivable from it.
- [ ] AC-6: Consecutive requests to a single provider are separated by at least the configured
      delay for that provider. A test with a delay configured observes the elapsed spacing.
- [ ] AC-7: Pacing is per provider. Requests to two different providers may overlap and are not
      serialized against each other.
- [ ] AC-8: The default configured delay is at the slow end of the permitted range, and a
      configuration that would set it below the enforced floor is rejected at load time with a
      message naming the floor.
- [ ] AC-9: On a refusal or throttle response the adapter waits an interval that grows with each
      successive occurrence and includes random variation, so repeated runs do not retry in
      lockstep.
- [ ] AC-10: Retries are bounded by configuration. After the bound is reached the provider outcome
      is `failed` and no further request is made to that provider for that query.
- [ ] AC-11: Every request carries a user agent that identifies the tool honestly. No adapter
      impersonates a browser or another product.
- [ ] AC-12: A provider that errors, times out, or returns an unparseable response yields a
      `failed` outcome with a human-readable reason and zero rows, and does not propagate an
      exception that would abort a caller querying other providers.
- [ ] AC-13: A provider that cannot express the requested query at all yields an `unavailable`
      outcome with a reason, distinguishable from `failed` by the caller.
- [ ] AC-14: A query whose matching set exceeds the provider's ceiling is split, and the union of
      the pieces contains every property the unsplit query would have returned had the ceiling not
      applied. Duplicates arising from the split are removed.
- [ ] AC-15: A result that could not be made complete despite splitting is flagged as truncated and
      names the ceiling responsible. It is never returned as though it were complete.
- [ ] AC-16: Every request made while splitting obeys the same pacing and retry rules as a single
      request. Splitting never becomes a burst.
- [ ] AC-17: The Realtor.com adapter accepts a ZIP code, a city, a city with state, a county, a
      state, and an address with a radius, and issues each in the provider's own form.
- [ ] AC-18: The Realtor.com adapter declares as provider-applied exactly the filters it actually
      pushes, and a test asserts that each declared filter measurably changes the request sent.
- [ ] AC-19: The Realtor.com adapter works around its 10,000-result ceiling by splitting on date
      range, and a query known to exceed it returns more than 10,000 distinct properties.
- [ ] AC-20: Fetching additional per-property detail is off by default. With it off, the number of
      requests does not grow with the number of properties returned.
- [ ] AC-21: Registering an adapter requires no change to any other adapter, to the run loop, or to
      the store. A test registers a new stub adapter and uses it in a run without editing those.
- [ ] AC-22: No adapter reads a credential, an API key, or a login of any kind.

## Edge cases & errors

- A provider returns an empty result for a query it accepted. That is `ok` with zero rows, not a
  failure, and the caller must be able to tell the two apart.
- A provider returns rows that do not match the filters it claimed to apply. The rows are returned
  as fetched; the caller applies its local filtering regardless, which is why AC-3 exists.
- A provider's response shape changes. The adapter reports `failed` with a parse error naming the
  field it could not read, rather than returning rows with silently missing values.
- A provider returns the same property more than once within one response. The rows are retained
  individually and deduplication is the caller's concern, not a silent drop here.
- The configured delay is set absurdly high. It is honored; slowness is never an error.
- The network is entirely unavailable. Every provider reports `failed` and the caller sees a run in
  which nothing succeeded, which is different from a run in which nothing matched.
- A provider begins refusing partway through a split query. The pieces already retrieved are
  returned, with the result flagged truncated per AC-15.

## Non-functional requirements

- Performance: adapter overhead outside of waiting on the network and on the configured delay is
  negligible relative to those waits. The pacing floor, not the code, is what makes a run slow.
- Security: no credentials anywhere in this feature. No provider response is evaluated,
  deserialized into executable form, or used to construct a file path.
- Reliability: a failure in one adapter cannot affect another adapter's result, and no adapter
  writes to the store.
- Accessibility: none. This feature has no user-facing surface.

## Open questions

- Whether the retry bound and the delay floor are per provider or shared is a plan decision. The
  requirements hold either way.
