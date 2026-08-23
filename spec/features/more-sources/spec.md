## Why

Two more sources, chosen because they stress the adapter interface in opposite directions. Zillow
is a library that wants a bounding box and refuses to return more than about 500 rows however
politely you page. Redfin is not a library at all, is capped lower, and in much of the country is
simply not available because the local multiple listing service does not permit downloads. If both
of these fit behind the existing interface without touching the core, the interface is real. The
problem brief is in `research.md`.

## User stories

- As the person running searches, I want an area with more than 500 Zillow results to return all of
  them, so that a ceiling I did not choose does not silently truncate my market.
- As the person running searches, I want to know when Redfin is unavailable in a region rather than
  simply absent from the results, so that I can tell a coverage gap from a quiet failure.
- As the person running searches, I want these sources paced as carefully as the first one, so
  that adding coverage does not increase the odds of being blocked.
- As whoever maintains this, I want both sources to have required no change to the core, so that
  the fourth source is equally cheap.

## Behavior & scenarios

- **Scenario: a bounding box within the ceiling**
  - Given a Zillow query whose matching set is under the per-query ceiling
  - When it runs
  - Then it issues one query and reports the outcome `ok` with those rows

- **Scenario: a bounding box over the ceiling**
  - Given a Zillow query whose matching set exceeds the per-query ceiling
  - When it runs
  - Then the box is subdivided, each piece is issued under the standard pacing, and the union is
    returned with duplicates removed

- **Scenario: subdivision cannot resolve the ceiling**
  - Given a query where even the smallest permitted subdivision exceeds the ceiling
  - When it runs
  - Then the rows retrieved are returned, flagged as truncated, naming the ceiling responsible

- **Scenario: an area that is not a box**
  - Given a search area that is a polygon, a city, or a county
  - When the Zillow adapter is asked for it
  - Then it queries the bounding box that contains the area, and exact filtering afterwards removes
    what falls outside

- **Scenario: Redfin where downloads are permitted**
  - Given a region whose multiple listing service permits downloads
  - When the Redfin adapter runs
  - Then it retrieves the rows, reports the outcome `ok`, and respects the row cap by reporting
    truncation if the cap was reached

- **Scenario: Redfin where downloads are not permitted**
  - Given a region whose multiple listing service does not permit downloads
  - When the Redfin adapter runs
  - Then it reports the outcome `unavailable` with the reason, returns no rows, and the run
    continues and is recorded as degraded rather than failed

- **Scenario: no core change**
  - Given both adapters registered
  - When a search naming all three sources runs
  - Then the run loop, the store, and the first adapter are unchanged from before these two existed

## Acceptance criteria

- [ ] AC-1: Both adapters satisfy the adapter interface and declare their capabilities honestly,
      verified by the same tests that verify the first adapter.
- [ ] AC-2: The Zillow adapter accepts a bounding box natively and issues it in the source's own
      form.
- [ ] AC-3: A Zillow query exceeding the per-query ceiling is subdivided, and the union of the
      pieces contains every property the ceiling suppressed. A test asserts more than 500 distinct
      properties returned for such an area.
- [ ] AC-4: Subdivision obeys the standard pacing, backoff, and jitter. A test observes that the
      pieces are not issued as a burst.
- [ ] AC-5: A Zillow query that remains over the ceiling after maximal subdivision returns what it
      retrieved, flagged as truncated and naming the ceiling.
- [ ] AC-6: A non-rectangular area is queried as its containing bounding box, and the adapter does
      not claim to have filtered to the exact area.
- [ ] AC-7: The Redfin adapter reports the outcome `unavailable`, distinct from `failed`, when the
      region does not permit downloads, and the reason is human-readable.
- [ ] AC-8: A run in which Redfin is `unavailable` completes, records that outcome, and marks no
      property as disappeared on the strength of Redfin's absence.
- [ ] AC-9: The Redfin adapter respects its row cap and reports truncation when the cap is reached
      rather than presenting a capped result as complete.
- [ ] AC-10: Both adapters tag every row with the producing source and a fetch timestamp, and
      retain the source's original payload, as the interface requires.
- [ ] AC-11: Neither adapter reads a credential, an API key, or a login.
- [ ] AC-12: Registering both adapters requires no change to the adapter interface, the politeness
      layer, the run loop, or the store. A test asserts that a run naming all three sources succeeds
      with both adapters supplied only through registration, touching no core behavior.

## Edge cases & errors

- A Zillow bounding box straddles a coastline or an international border, so much of it is empty.
  Subdivision still terminates rather than recursing on empty regions indefinitely.
- Redfin availability changes between runs as a listing service changes policy. Each run records
  the outcome it actually observed rather than caching availability indefinitely.
- Redfin returns a download whose columns have changed. This is a parse failure reported as
  `failed`, with the field that could not be read named, not silently missing values.
- Zillow returns fewer rows than its ceiling for a query that should exceed it, which can indicate
  throttling rather than a small market. Treated under the standard backoff rules.
- A subdivided Zillow query begins being refused partway through. The pieces already retrieved are
  returned, flagged truncated.
- Both new sources are unavailable while the first succeeds. The run is degraded and complete.

## Non-functional requirements

- Performance: subdivision issues the smallest number of queries that clears the ceiling; wall-clock
  time is dominated by the pacing floor rather than by adapter code.
- Security: no credentials. No source response is evaluated or used to construct a path.
- Reliability: either adapter failing leaves the other adapters' results and the run intact.
- Accessibility: none. No user-facing surface.

## Open questions

None.
