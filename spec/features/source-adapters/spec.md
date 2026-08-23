## Why

Three sources, no supported API between them, each with its own query surface, its own ceiling,
and its own opinion about callers it dislikes. This feature is the seam that keeps those
differences from leaking: one adapter per source, all answering the same two questions, plus the
shared politeness layer that stands between the tool and getting blocked. It ships one working
adapter, against Realtor.com, because an interface with no implementation proves nothing. The
problem brief is in `research.md`.

## Vocabulary used in this feature

- A **capability declaration** is an adapter's honest answer to "which parts of a query will you
  apply on your side?" Everything it does not claim is applied locally by the caller.
- A **raw listing** is one row exactly as a source returned it, tagged with the source that
  produced it and the time it was fetched. The glossary in `product-global.md` governs.
- A **source outcome** is the per-source result of one query: `ok`, `failed`, or `unavailable`.
  `unavailable` means the source cannot serve this query at all, which is a different thing from
  having tried and failed.

## User stories

- As the person running searches, I want a source that is down or throttling to cost me that
  source's listings and nothing else, so that one bad afternoon does not lose me a run.
- As the person running searches, I want the tool to be slow and polite by default, so that
  scheduled use over months does not get me blocked.
- As the person running searches, I want to know which filters the source applied and which the
  tool applied afterwards, so that a surprising result set is diagnosable.
- As whoever adds the fourth source, I want adding a source to mean writing one adapter, so that
  the core never accumulates source-specific branches.
- As the person running searches, I want a query larger than a source's ceiling to still return
  everything, so that a broad search is not silently truncated.

## Behavior & scenarios

- **Scenario: an adapter declares what it can filter**
  - Given a source that applies price and bedroom filters on its side but not lot size
  - When its capability declaration is read
  - Then price and bedrooms are listed as applied by the source and lot size is not, and the
    caller applies lot size locally

- **Scenario: an unsupported filter is never silently dropped**
  - Given a query carrying a filter the source does not support
  - When the adapter runs the query
  - Then the filter is absent from the source request, is reported as not applied by the
    source, and the returned rows are not claimed to satisfy it

- **Scenario: every returned row is attributed**
  - Given any successful query against any source
  - When its rows are examined
  - Then each row records the source that produced it and the time it was fetched, and the
    source's own response for that row is retained unaltered alongside the normalized fields

- **Scenario: requests are paced**
  - Given a query that requires several requests to one source
  - When the adapter issues them
  - Then consecutive requests to that source are separated by at least the configured delay, and
    the pacing applies per source rather than globally

- **Scenario: a source refuses or throttles**
  - Given a source responding with a refusal or a throttle response
  - When the adapter encounters it
  - Then the adapter waits an increasing interval with random variation before retrying, retries at
    most the configured number of times, and reports the source outcome as `failed` if the
    refusals continue

- **Scenario: a source fails**
  - Given a source that errors, times out, or returns an unusable response
  - When the adapter gives up on it
  - Then it reports the source outcome as `failed` with a human-readable reason, returns no rows
    for that source, and raises nothing that would stop another source from being queried

- **Scenario: a query exceeds the source's ceiling**
  - Given a query whose matching set is larger than the source will return in one response
  - When the adapter runs it
  - Then the adapter splits the query along a dimension the source supports, issues the pieces
    under the same pacing rules, and returns the union with duplicates removed

- **Scenario: the ceiling cannot be worked around**
  - Given a query that still exceeds the ceiling after splitting as far as the source allows
  - When the adapter completes
  - Then it returns the rows it did retrieve and reports that the result was truncated, naming the
    ceiling that caused it

- **Scenario: the Realtor.com adapter accepts the geography forms it supports**
  - Given an area expressed as a ZIP code, a city, a city with a state, a county, a state, or an
    address with a radius
  - When the Realtor.com adapter is asked for it
  - Then the query is issued in the source's own form and the source outcome is `ok`

- **Scenario: an area form a source cannot express**
  - Given an area a source has no way to represent
  - When the adapter is asked for it
  - Then it reports the source outcome as `unavailable` with the reason, rather than substituting
    a different area or returning an empty result

- **Scenario: expensive per-property detail is opt-in**
  - Given the Realtor.com adapter's option to fetch tax history and school data
  - When it is not requested
  - Then no additional per-property request is made, and when it is requested the additional
    requests are paced by the same rules as every other request

- **Scenario: a new source is added**
  - Given a new adapter that satisfies the interface and declares its capabilities
  - When it is registered
  - Then it can be named in a saved search and used in a run with no change to any existing
    adapter, to the run loop, or to the store

## Acceptance criteria

- [ ] AC-1: Every adapter exposes a name, a capability declaration, and a search operation, and a
      test that registers a stub adapter satisfying only those three can run a query end to end.
- [ ] AC-2: A capability declaration enumerates exactly the query fields the source applies on
      its side. A field absent from the declaration is never sent to the source.
- [ ] AC-3: The result of a search reports, per query field, whether the source applied it, so a
      caller can determine what remains to be applied locally.
- [ ] AC-4: Every returned row carries the producing source's name and a fetch timestamp in UTC.
- [ ] AC-5: Every returned row retains the source's original response payload for that property
      alongside the normalized fields, and the normalized fields are derivable from it.
- [ ] AC-6: Consecutive requests to a single source are separated by at least the configured
      delay for that source. A test with a delay configured observes the elapsed spacing.
- [ ] AC-7: Pacing is per source. Requests to two different sources may overlap and are not
      serialized against each other.
- [ ] AC-8: The default configured delay is at the slow end of the permitted range, and a
      configuration that would set it below the enforced floor is rejected at load time with a
      message naming the floor.
- [ ] AC-9: On a refusal or throttle response the adapter waits an interval that grows with each
      successive occurrence and includes random variation, so repeated runs do not retry in
      lockstep.
- [ ] AC-10: Retries are bounded by configuration. After the bound is reached the source outcome
      is `failed` and no further request is made to that source for that query.
- [ ] AC-11: Every request carries a user agent that identifies the tool honestly. No adapter
      impersonates a browser or another product.
- [ ] AC-12: A source that errors, times out, or returns an unparseable response yields a
      `failed` outcome with a human-readable reason and zero rows, and does not propagate an
      exception that would abort a caller querying other sources.
- [ ] AC-13: A source that cannot express the requested query at all yields an `unavailable`
      outcome with a reason, distinguishable from `failed` by the caller.
- [ ] AC-14: A query whose matching set exceeds the source's ceiling is split, and the union of
      the pieces contains every property the unsplit query would have returned had the ceiling not
      applied. Duplicates arising from the split are removed.
- [ ] AC-15: A result that could not be made complete despite splitting is flagged as truncated and
      names the ceiling responsible. It is never returned as though it were complete.
- [ ] AC-16: Every request made while splitting obeys the same pacing and retry rules as a single
      request. Splitting never becomes a burst.
- [ ] AC-17: The Realtor.com adapter accepts a ZIP code, a city, a city with state, a county, a
      state, and an address with a radius, and issues each in the source's own form.
- [ ] AC-18: The Realtor.com adapter declares as source-applied exactly the filters it actually
      pushes, and a test asserts that each declared filter measurably changes the request sent.
- [ ] AC-19: The Realtor.com adapter works around its 10,000-result ceiling by splitting on date
      range, and a query known to exceed it returns more than 10,000 distinct properties.
- [ ] AC-20: Fetching additional per-property detail is off by default. With it off, the number of
      requests does not grow with the number of properties returned.
- [ ] AC-21: Registering an adapter requires no change to any other adapter, to the run loop, or to
      the store. A test registers a new stub adapter and uses it in a run without editing those.
- [ ] AC-22: No adapter reads a credential, an API key, or a login of any kind.
- [ ] AC-23: For each returned row the adapter retrieves one small preview image where the source
      offers one, subject to the same pacing, backoff, and retry rules as every other request. A
      failed image retrieval affects that row's image only: it never fails the query, never changes
      the source outcome, and never removes a previously retrieved image.

## Edge cases & errors

- A source returns an empty result for a query it accepted. That is `ok` with zero rows, not a
  failure, and the caller must be able to tell the two apart.
- A source returns rows that do not match the filters it claimed to apply. The rows are returned
  as fetched; the caller applies its local filtering regardless, which is why AC-3 exists.
- A source's response shape changes. The adapter reports `failed` with a parse error naming the
  field it could not read, rather than returning rows with silently missing values.
- A source returns the same property more than once within one response. The rows are retained
  individually and deduplication is the caller's concern, not a silent drop here.
- The configured delay is set absurdly high. It is honored; slowness is never an error.
- The network is entirely unavailable. Every source reports `failed` and the caller sees a run in
  which nothing succeeded, which is different from a run in which nothing matched.
- A source begins refusing partway through a split query. The pieces already retrieved are
  returned, with the result flagged truncated per AC-15.

## Non-functional requirements

- Performance: adapter overhead outside of waiting on the network and on the configured delay is
  negligible relative to those waits. The pacing floor, not the code, is what makes a run slow.
- Security: no credentials anywhere in this feature. No source response is evaluated,
  deserialized into executable form, or used to construct a file path.
- Reliability: a failure in one adapter cannot affect another adapter's result, and no adapter
  writes to the store.
- Accessibility: none. This feature has no user-facing surface.

## Open questions

- Whether the retry bound and the delay floor are per source or shared is a plan decision. The
  requirements hold either way.
