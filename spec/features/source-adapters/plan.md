# Implementation plan — source adapters and the Realtor.com source

Realizes `spec.md` in this folder. Requirements live there; this document is the how, and is
expected to be revised as the code teaches us things the spec did not.

## What was measured before deciding

Two decisions below rest on facts that could not be settled by reading, so they were measured
against the live source. Three requests total, five seconds apart, from the machine this tool runs
on. What they established:

1. **Realtor.com's public GraphQL endpoint answers a client that identifies itself honestly.** A
   `POST https://www.realtor.com/frontdoor/graphql` carrying `User-Agent: homescout/0.1 (personal
   listing monitor)` returned HTTP 200 with 16 geography suggestions for "Portales, NM", and a
   for-sale area search for the same place returned all 87 matching properties. The identical
   requests behind a Chrome user agent returned the same data. Impersonation buys nothing here.
2. **The endpoint does require a client-identification header pair, and it accepts an honest one.**
   Without `rdc-client-name` and `rdc-client-version` it answers `HTTP 400 missing client
   identification headers`, with or without `Origin` and `Referer`. With
   `rdc-client-name: homescout` and `rdc-client-version: 0.1.0` it answers HTTP 200 and the full
   result. So the pair is mandatory but its *value* is ours to choose, and D-12 fixes it to name
   this tool. Nothing here requires carrying the reference library's `RDC_WEB_SRP_FS_PAGE`.
3. **No token, cookie, or login is involved.** The search path needs no authentication at all.
4. **The response already carries every field the store keeps.** One sample property carried price,
   status, beds, baths, square footage, lot size, year built, property type, a parsed address with
   coordinates, county, the listing page URL, free text, the photo list, and a small preview image
   address. The field mapping in D-8 is transcribed from that response, not guessed.

## Design decisions

### D-1. No `homeharvest` dependency. We own the client; we borrow only the idea.

The brief named `homeharvest` as the backing for this adapter. Reading it changed the answer.

Version 0.8.18 sends `User-Agent: Mozilla/5.0 (Macintosh ...) Chrome/135.0.0.0` together with
`x-is-bot: false`, and mints an access token by presenting itself as the Realtor.com iPhone app
(`X-Client-ID: rdc_mobile_native,iphone`). It paginates with an unbounded `ThreadPoolExecutor`, and
retries three times on exponential backoff with no jitter.

Each of those contradicts a requirement here: AC-11 forbids impersonating a browser or another
product, AC-6 and AC-16 require paced requests that splitting never turns into a burst, and AC-9
requires jitter. There is no configuration that turns any of them off; `parallel=False` still fires
pages back to back with no delay, and the headers are a module-level constant. Depending on the
library would mean patching around it at three points and hoping none of them moves.

Set against that, what the library actually provides is the shape of one GraphQL query. The
measurement above shows we can issue that query ourselves, honestly, with no token. So the adapter
talks to the endpoint directly and the dependency (which also drags in `pandas` and `pydantic`, for
a project whose store is raw `sqlite3`) is dropped.

We do not copy its query document either. Ours names only the fields D-8 maps, roughly a tenth the
size. A smaller selection set is less to break when the source changes its schema, and every field
in it is one we can point at a use for.

Revisit if the endpoint starts refusing honest clients. The fallback is not to impersonate, it is
to report the source unavailable and say why.

### D-2. One dependency: `requests`

Needed for connection pooling (fewer TLS handshakes to a source we are trying not to annoy),
straightforward timeouts, status codes, and streaming an image body. `urllib.request` can do all of
it and does each awkwardly. Retry, backoff, and pacing are ours (D-3), so nothing else comes with it.

No HTTP mocking library. The paced session takes its transport as a constructor argument (D-9), so
tests substitute a callable and need no new test dependency.

### D-3. Politeness is a gate the adapter cannot get around

`PacedSession` owns every outbound request this feature makes: the minimum delay since the last
request **to that host's source**, the growing backoff with jitter on a refusal or throttle, the
retry bound, the timeout, and the user agent. An adapter has no other way to reach the network, so
"splitting never becomes a burst" (AC-16) and "image downloads are paced too" (AC-23, and the
cross-cutting rule in `product-global.md`) hold structurally rather than by remembering.

Pacing state is keyed by source name, which is what makes AC-7 true: two sources have two
independent clocks and never wait on each other.

The numbers, and why:

| Setting | Default | Floor / bound | Reason |
|---|---|---|---|
| delay between requests to one source | 3.0 s | permitted range 1.0 s to 60.0 s | Slow end of tolerable. A county run of a few hundred listings is minutes, not seconds, which is the point |
| retries after a refusal or throttle | 3 | configurable, 0 allowed | AC-10 |
| first backoff wait | 5.0 s | doubling per attempt, capped at 120 s | AC-9 |
| jitter | multiply the wait by a random 0.5 to 1.5 | always on | Two scheduled runs that collide must not retry in lockstep |
| request timeout | 30 s | configurable | A hung socket is a failed source, not a hung run |
| maximum response body | 64 MB | configurable | An unbounded body is a denial of service the source does not have to intend |
| maximum image body | 4 MB | configurable | A preview image is tens of kilobytes. Four megabytes is already generous |

The floor is global and the rest is per source with a shared default, which answers the spec's open
question. Sources differ in tolerance, so per-source overrides must exist; a floor a source could
lower would not be a floor.

The delay's permitted range is 1.0 to 60.0 seconds, and the default of 3.0 sits three times the
floor and well below the ceiling. That is what AC-8's "slow end of the permitted range" refers to,
and stating the range is what makes the criterion checkable rather than a matter of taste. A
configured value outside the range is refused at load with a message naming the bound it crossed.

The two body limits are enforced by reading the response in chunks and abandoning it once the limit
is passed, not by trusting a `Content-Length` the other side supplies. Exceeding either is a
`failed` outcome with a reason, never a partial row.

### D-4. The capability declaration drives the request, so an undeclared filter cannot be sent

AC-2 says a field absent from the declaration is never sent. Rather than assert that in review, make
it the only path: the declaration maps each query field the source applies to the fragment that
expresses it, and the request builder is a loop over the declaration. There is no branch that reads
a query field directly, so adding a filter to the request means adding it to the declaration.

AC-3's report then falls out for free: what the source applied is the declaration intersected with
the fields the query actually populated, and what the caller must apply locally is the remainder.

### D-5. The ceiling walk is generic; only the split dimension is the adapter's

Every source has a different ceiling and a different dimension it can be split along (Realtor.com by
date listed, Zillow by bounding box, per `product-global.md`). The procedure over them is the same:
ask for the first page, read the reported total, and if it exceeds the ceiling, halve the range and
recurse; otherwise page through and collect. Union the pieces, drop duplicates by source identifier,
and if a piece is still over the ceiling when it can no longer be divided, return what was retrieved
and flag the result truncated, naming the ceiling.

So the walk lives in `sources/ceiling.py`, parameterized by an adapter-declared ceiling and a
`Splittable` the adapter provides. This is what keeps non-negotiable 9 honest: Zillow and Redfin
(feat-005) supply a different `Splittable` and change nothing here.

The recursion is depth-bounded and every probe goes through the paced session, so a pathological
split cannot become a request storm.

Truncation has two causes and one flag. A piece that stays over the ceiling when it can no longer be
divided is one. A source that starts refusing partway through, after some pieces have already been
retrieved, is the other: the walk stops, returns what it has, and flags the same truncation, naming
the refusal rather than the ceiling as the reason. The spec's last edge case is that second path,
and both reach AC-15's flag.

### D-6. Adapters produce values; they never write, and they never sleep on their own

An adapter is constructed with a paced session and nothing else. It cannot reach the store, because
it is never handed one, which is how the spec's reliability requirement ("no adapter writes to the
store") is enforced rather than promised. A run recording what an adapter returned is feat-003's job.

Two consequences worth stating: an adapter never calls `time.sleep` (only the session does, through
an injected sleeper, per D-9), and no value from a response is ever used to build a file path or
passed to anything that evaluates it. Image URLs are checked for an `http`/`https` scheme before
being fetched; the path an image is eventually stored at is derived from the listing id by the store,
never from the URL.

Redirects are not followed on an image fetch. The address checked must be the address retrieved, and
a preview image that only exists behind a redirect is not worth the hole. A redirect is treated as
that row's image being unavailable, which by D-11 costs nothing else.

Proxy support, which `research.md` raised as a risk-mitigation option, is deliberately not built.
The paced session takes its transport as an argument (D-9), so routing through a proxy later is
supplying a different transport rather than a change here. That is the unused seam, and it exists
without any code being written for it.

### D-7. The normalized property record moves up out of the store

`ListingFields` and `SourceRow` move from `homescout.store.models` to a new `homescout/records.py`,
and `homescout.store` re-exports both. Behavior, public names, and every existing test are unchanged.

Why bother: an adapter's output *is* a `SourceRow` (that type's docstring already says so), and the
constitution orders the layers `sources` before `store`. Leaving the definition in the store would
make the sources layer import upward through the whole architecture to describe its own return
value, and would leave `homescout.sources` unusable without a database package it never touches.

One latent fragility gets fixed on the way: `ListingFields.from_row` currently reads a hand-written
tuple of column names that must be kept in step with the dataclass by hand. In the new home it reads
the dataclass's own fields, so the two cannot drift. Which of those fields are *compared* stays in
the store, because that is a store policy, and the store keeps a check that its compared and
informational sets together account for every field on the record.

This is the one place this feature edits a feature that is already finished. Because the move is
behavior-preserving and the old names are re-exported, the listing store's public surface, its
tests, and the audit already on record all stand. What does change is that the store's code no
longer matches what its own audit last read, and an audit has no way to tell a deliberate move from
unexplained drift. So T1 records the move in that feature's ledger, as a note rather than a gap.

### D-8. Realtor.com: geography resolves first, then one search per range

Two operations against `https://www.realtor.com/frontdoor/graphql`:

1. **`Search_suggestions`** turns a free-text area into the source's own geography object, carrying
   an `area_type` of `postal_code`, `city`, `county`, `state`, or `address`. This is how AC-17's six
   accepted forms are issued in the source's own form rather than guessed at. A term that resolves to
   nothing, or an area shape the source has no way to express (a drawn polygon), is reported
   `unavailable` with the reason, never silently substituted (AC-13).
2. **`home_search`** takes either `search_location` (for an area) or `nearby: {coordinates, radius}`
   (for an address with a radius), plus the declared filters, at 200 results per page, and returns
   both the page and the matching `total`. The total is what makes D-5's ceiling walk cheap: one
   request tells us whether a split is needed.

Field mapping, transcribed from a real response:

| Store field | Response path |
|---|---|
| price | `list_price` |
| listing_status | `status` |
| beds | `description.beds` |
| baths | `description.baths_full` plus half of `description.baths_half` |
| sqft, lot_sqft, year_built | `description.sqft`, `.lot_sqft`, `.year_built` |
| property_type | `description.type` |
| address_line, unit, city, state, postal_code | `location.address.*` (`state_code`) |
| county | `location.county.name` |
| latitude, longitude | `location.address.coordinate.*` |
| parcel_number | `tax_record.apn`, falling back to `tax_record.tax_parcel_id` |
| listing_url | `href` |
| description | `description.text` |
| photo_urls | `photos[].href` |
| days_on_market_source | days from `list_date` to now, the source's own claim, recorded and never compared |
| source_listing_id | `property_id` |

A field the response omits stays empty, per invariant 10. A field the response carries in a shape the
mapping does not expect fails the whole query with a parse error naming the field (AC-12 and the
spec's third edge case), because half-read rows written as fact are worse than no rows.

`extra_property_data` (tax history and schools, one extra request per property) stays off by default
and is not implemented in this feature. AC-20's requirement is that with it off the request count
does not grow with the number of properties, and the way to satisfy that is to not have the code path.

### D-9. Time and transport are injected, so pacing is tested without waiting

`PacedSession` takes a clock, a sleeper, a jitter source, and a transport. Tests assert the exact
sleeps that were requested and the exact requests that were made, deterministically and instantly.
One test with a real clock and a small delay proves the production wiring, so the injected seam
cannot drift from reality.

### D-10. Registration is a name to a factory, and nothing else knows the names

`sources/registry.py` maps a source name to a factory. Registering an adapter is one call; nothing in
the run loop, the store, or any other adapter names a source. AC-21's test registers a stub and uses
it without editing any of them.

### D-11. Preview retrieval is on the interface, and the caller contract is written down

AC-23 puts preview retrieval on the adapter, for each returned row. This plan makes it a separate
paced operation rather than work done inside the search call, for two reasons: a caller can hand
each image to the store as it arrives instead of holding thousands of them in memory, and a failure
there is then structurally unable to alter the query's outcome, which is half of what AC-23 asks
for.

The cost of that reading is that somebody has to remember to call it. A lazy iterator that fetched
inside `search()` would remove the need to remember, but it would also mean the source outcome could
not be final until iteration finished, which collides with AC-12. So instead:

- `fetch_preview` is a member of the `Source` protocol, not a convenience on the Realtor.com
  adapter. An adapter that does not implement it does not satisfy the interface, so Zillow and
  Redfin (feat-005) inherit the obligation rather than each deciding for themselves.
- The caller contract is explicit: the run loop calls it once per returned row and passes the result
  straight to the store's preview image storage. That obligation belongs to feat-003 and is recorded
  here so its spec picks it up rather than discovering it.

This matters because the failure mode is silent. Without the contract written down, every criterion
in this feature could pass while no preview image was ever fetched, and the email digest that
depends on one would simply have none. The whole-product review found exactly that hole once
already, and assigned it here.

### D-12. The request headers are fixed here, and every value names this tool

The endpoint requires a client-identification pair (see the measurement above), so "send nothing but
an honest user agent" is not available. Every request the Realtor.com adapter makes carries exactly:

| Header | Value |
|---|---|
| `User-Agent` | `homescout/<version> (personal listing monitor)` |
| `rdc-client-name` | `homescout` |
| `rdc-client-version` | the package version |
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |

And nothing else. No `Origin`, no `Referer`, no `sec-ch-ua`, no `x-is-bot`, no platform claim.

Writing the set out is the point. Left unstated, an implementer meets the mandatory
`HTTP 400 missing client identification headers`, reaches for the only reference available, and
copies `rdc-client-name: RDC_WEB_SRP_FS_PAGE` from the library D-1 rejected. The tool would then
announce itself as Realtor.com's own web application on every request, which is exactly what
non-negotiable 10 and AC-11 forbid, and it would do so while the plan claimed otherwise.

The rule generalizes to every adapter: a header may be sent because the source requires it, and its
value must name this tool. No header value may name another product.

### D-13. The query shape is defined here, consumed by saved searches later

`SearchQuery` (area, price, beds, baths, square footage, lot size, year built, property types,
listing status, listed-since) and the area forms it accepts are defined in this feature because the
adapter interface needs them. Turning a saved search into one is feat-004's job. Adding an area form
this source cannot express is exactly AC-13's case and needs no change here.

## Layout

```
src/homescout/
  records.py              <- ListingFields, SourceRow (moved from store, re-exported by it)
  sources/
    __init__.py           <- the public surface
    base.py               <- Source protocol, Capabilities, SearchQuery, areas, SearchResult
    errors.py             <- SourceFailed, SourceUnavailable
    politeness.py         <- PolitenessConfig, PacedSession
    ceiling.py            <- the generic split / union / truncate walk
    registry.py           <- name to factory
    realtor/
      __init__.py         <- RealtorSource
      queries.py          <- our GraphQL documents
      normalize.py        <- one response property to a SourceRow
tests/
  fixtures/realtor/*.json <- recorded responses
  test_sources_*.py
```

## Task breakdown

See `tasks.md`.

## Verification approach

Tests are pytest under `tests/`, matching the workspace's declared `tests/**/test_*.py`. Every test
verifying a criterion names its trace token `feat-002/AC-N` in the test's docstring.

**Seams.** Four, and no test reaches past any of them into internals:

1. `homescout.sources` public API, with a substituted transport. Most criteria are exercised here.
2. A stub adapter registered through the registry, for the criteria that are about the interface
   rather than about any source (AC-1, AC-14, AC-15, AC-16, AC-21).
3. Recorded Realtor.com responses on disk, for the criteria about that source's shape (AC-5, AC-17,
   AC-18, AC-20, AC-23).
4. The live source, for the two criteria whose whole point is that the real thing answers. Marked
   slow and excluded from the default run.

| Criteria | Seam | How |
|---|---|---|
| AC-1, AC-21 | stub adapter | Register a stub declaring only a name, capabilities, and search; run a query through it |
| AC-2, AC-3 | stub adapter | A query carrying a filter the stub does not declare: assert it is absent from the request and reported as not applied |
| AC-4 | fake transport | Assert source name and a UTC fetch timestamp on every row |
| AC-5 | recorded response | Assert the original property object round-trips, and that every mapped field is derivable from it |
| AC-6, AC-7 | fake transport + injected clock | Assert the requested sleeps between consecutive requests to one source, and that two sources do not wait on each other |
| AC-6 (wiring) | real clock | One request pair at a small delay, asserting real elapsed time |
| AC-8 | config loading | Assert the default sits at the slow end of the range D-3 states, and that a value outside the range is refused with a message naming the bound it crossed |
| AC-9 | fake transport + injected jitter | Feed refusals; assert the waits grow, and that two runs with different jitter do not match |
| AC-10 | fake transport | Feed refusals past the bound; assert `failed` and assert no further request was made |
| AC-11 | fake transport | Assert the header set on every request equals D-12's table exactly, that every value names this tool, and that no value names another product |
| AC-12 | fake transport | An error, a timeout, unparseable content, and a body past the size limit: each yields `failed` with a reason, zero rows, and no exception escaping |
| AC-12, AC-13 (isolation) | two stub adapters | One fails, one succeeds; assert the successful one's rows are unaffected |
| AC-13 | recorded response + stub | An area the source cannot express: assert `unavailable` with a reason, distinguishable from `failed` |
| AC-14 | stub adapter with a ceiling | A generated population larger than the ceiling: assert the union equals the whole population, with duplicates removed |
| AC-15 | stub adapter with a ceiling | Two paths to the same flag: a population that stays over the ceiling at the finest split, and a stub that succeeds for the first pieces then refuses. Each asserts truncated, the reason named, and the retrieved rows returned |
| AC-16 | stub adapter + injected clock | Assert every request made during a split is spaced by the configured delay |
| AC-17 | recorded responses | Each of the six area forms: assert the request issued matches the source's own form for that form |
| AC-18 | recorded responses | Each declared filter: assert the request body measurably changes when it is set |
| AC-19 | stub adapter with a ceiling | A known population and a ceiling of 50, forcing several levels of date splitting: assert the union equals the population exactly |
| AC-20 | recorded responses | Assert the listing request count for a page of properties is one and does not grow with the row count, and that no per-property detail request is made |
| AC-22 | static + fake transport | Assert no adapter reads an environment variable or a credential, and that no request carries an authorization header |
| AC-24 | live source (slow) | A real query over the ceiling: assert it is detected, and that every date range the split produces reports a count within the ceiling. Counts only, no rows retrieved |
| AC-23 | stub adapter + recorded response | Assert the interface requires preview retrieval, so a stub adapter that omits it does not satisfy the protocol; assert one image is fetched per row through the paced session, that a body past the image limit or a non-image content type is refused, and that a failed fetch leaves the row, the outcome, and any previously stored image untouched |

**The over-the-ceiling promise is two criteria, and that was a decision.** The spec originally
promised one thing: run a query against the live source and get back more than 10,000 distinct
properties. The pre-build check rejected the split this plan proposed for it, on the grounds that a
plan may not quietly verify something narrower than the criterion says. It went to a human call, and
the criterion was split instead:

- **AC-19, the algorithm.** Proved offline against a stub source with a known population and a
  ceiling of 50, small enough to force several levels of splitting. The union is checked to equal
  the population exactly, so completeness is demonstrated rather than assumed from a large number.
- **AC-24, the detection.** Proved against the real source, by reading the counts it reports for the
  produced date ranges. No rows are fetched.

What this buys: the part that can actually break is the part that gets tested exhaustively, in
seconds, offline. The live half still catches the thing only the real source can tell us (that the
ceiling is where we think it is and that our splits land under it) without a test that fetches tens
of thousands of rows, and without a test that fails one day because a town's inventory fell.

Test commands name explicit paths, never a bare directory:

```
uv run pytest tests/test_sources_contract.py tests/test_sources_politeness.py tests/test_sources_failures.py tests/test_sources_ceiling.py tests/test_sources_realtor.py
uv run pytest -m slow tests/test_sources_live.py
```

## Deviations from the constitution

None outstanding. Two near misses are worth naming, because both were caught by process rather than
by anyone being careful:

- The brief's named library (`homeharvest`) would have broken non-negotiable 10 in three separate
  ways: a Chrome user agent with `x-is-bot: false`, a token minted by presenting itself as the
  vendor's iPhone app, and unbounded parallel pagination. D-1 drops it rather than deviating.
- This plan's first draft left the request headers unspecified, which the pre-build check flagged as
  a hard block: the endpoint mandates a client-identification pair, and the only reference an
  implementer would reach for supplies Realtor.com's own web application name. D-12 fixes the set
  and the rule that every value must name this tool.
