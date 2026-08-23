# Research — more-sources

## Discovery input

From `homescout-brief.md` section 5.1:

- Zillow is reachable through a library that takes a bounding box natively and enforces a hard cap
  of roughly 500 results per query regardless of paging. Getting more means splitting the box.
- Redfin has no library at all. Its results page offers a download that is an ordinary request
  carrying the search parameters, capped at 350 rows, and available only where the local multiple
  listing service permits downloads. In much of the country it simply is not there.
- The brief's stated test of the adapter interface is that adding a source means writing one
  adapter and not touching the core. These two are the proof, because they stress the interface in
  opposite directions: one is a library with a geometry-shaped query, the other is a bare download
  that may not exist.

## Problem brief

### Problem statement

Someone consolidating a regional market struggles to see the whole market from one provider because
each has partial coverage and its own undocumented ceiling, which results in properties that are
listed, findable, and simply absent from the tool. A solution should add two more providers behind
the existing interface, each working around its own ceiling and its own availability limits,
without any of that leaking into the core, and without a provider that is unavailable in a region
being mistaken for a provider that failed.

### Target users

- **The person running searches** (primary): wants coverage, and wants to know when a provider had
  nothing to say versus could not be asked.

### Jobs to be done

- Fetch listings from Zillow for a drawn area despite a hard per-query ceiling.
- Fetch listings from Redfin where it is available, and report clearly where it is not.
- Prove the adapter interface holds without core changes.

### Success signals

- A search over an area with more than 500 Zillow results returns all of them.
- A region where Redfin downloads are not permitted produces a clear `unavailable` outcome, not a
  failure and not an empty success.
- Neither adapter required a change to the interface, the run loop, or the store.

### Constraints

- The same politeness floor as every other provider: pacing, backoff, jitter, honest user agent.
  Splitting a query must not become a burst.
- No credentials, no paid API, no multiple listing service access.

### Explicitly out of scope

- The adapter interface and the politeness layer themselves (feat-002).
- Reconciling these providers' rows with Realtor.com's (feat-006).

### Open questions

- Whether Redfin availability can be determined before issuing a request, or only from the
  response, affects how quickly an unavailable region is reported. Either satisfies the
  requirements.
