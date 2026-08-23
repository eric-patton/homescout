# Tasks — source adapters and the Realtor.com source

Glyphs: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` not applicable ·
`[H]` needs a human. `[P]` marks a task that can run alongside its group peers.

Each task names the criteria it satisfies. Tests carry the trace token `feat-002/AC-N`.

## Group A — foundation

T1 and T2 touch disjoint files and depend on nothing here, so they can run alongside each other.
T3 needs both.

- [ ] **T1. Move the normalized property record out of the store.** `[P]` `ListingFields` and
      `SourceRow` move to `src/homescout/records.py`; `homescout.store` re-exports both, so its
      public surface and every existing test are unchanged. `ListingFields.from_row` reads the
      dataclass's own fields instead of a hand-maintained name tuple, and the store keeps a check
      that its compared and informational sets together account for every field.
      This is the one place this feature edits a feature already finished, so record the move as a
      note in the listing store's ledger: behavior-preserving, public names unchanged, so a later
      audit of that feature reads it as deliberate rather than as unexplained drift.
      Verify: the whole existing suite passes untouched.
      Files: `src/homescout/records.py`, `src/homescout/store/models.py`,
      `src/homescout/store/schema.py`, `src/homescout/store/__init__.py`,
      `spec/features/listing-store/converge.md`.
- [ ] **T2. Politeness config and the paced session.** `[P]` The minimum delay between requests to
      one source, the growing backoff with jitter on a refusal or throttle, the retry bound, the
      timeout, and the honest user agent, all owned by one object that every request passes through.
      Pacing state is keyed by source, so two sources never wait on each other. Configuration
      validates at load and refuses a delay outside the permitted range, naming the bound it
      crossed. Response bodies are read in chunks against a size limit, with a much smaller limit
      for images, so an unbounded body is a `failed` outcome rather than a filled disk. Redirects
      are not followed. The clock, the sleeper, the jitter source, and the transport are all
      injected.
      Satisfies AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, and the security review's body-size finding.
      Files: `src/homescout/sources/politeness.py`.
- [ ] **T3. The adapter interface and the query shape.** The `Source` protocol (name, capability
      declaration, search, preview retrieval), the normalized query and the area forms it accepts,
      the capability declaration itself, and the search result carrying rows, outcome, per-field
      applied report, and truncation. The declaration drives the request, so a field it does not
      name has no path to the source. Preview retrieval is a protocol member rather than one
      adapter's convenience, so the later Zillow and Redfin work inherits the obligation.
      Satisfies AC-1, AC-2, AC-3, AC-4. Underpins AC-23.
      Files: `src/homescout/sources/base.py`, `src/homescout/sources/errors.py`.

## Group B — the behaviors every source shares

T5 and T6 touch disjoint files and neither needs the other.

- [ ] **T4. Failing and being unavailable.** An error, a timeout, or an unusable response becomes a
      `failed` outcome carrying a human-readable reason and zero rows, and never escapes as an
      exception that would stop another source being queried. A query the source cannot express at
      all becomes `unavailable` with its own reason, which a caller can tell apart from `failed`.
      Satisfies AC-12, AC-13.
      Files: `src/homescout/sources/base.py`, `src/homescout/sources/errors.py`.
- [ ] **T5. The ceiling walk.** `[P]` Ask for the first page, read the reported total, and if it
      exceeds the source's declared ceiling, halve the split dimension and recurse; otherwise page
      through. Union the pieces and drop duplicates by source identifier. Two paths reach the
      truncation flag and both return what was retrieved: a piece still over the ceiling when it can
      no longer be divided, naming the ceiling, and a source that begins refusing partway through,
      naming the refusal. Every request, probes included, goes through the paced session, and the
      recursion is depth-bounded.
      Satisfies AC-14, AC-15, AC-16.
      Files: `src/homescout/sources/ceiling.py`.
- [ ] **T6. The registry.** `[P]` A source name to a factory, and nothing outside it names a source.
      A test registers a stub adapter declaring only the interface members and runs a query through
      it, editing no other adapter, no run loop, and no store code.
      Satisfies AC-1, AC-21.
      Files: `src/homescout/sources/registry.py`.

## Group C — the Realtor.com source

- [ ] **T7. The request headers.** Fix the exact header set from the plan's D-12 and assert it: the
      endpoint requires a client-identification pair, and every value this tool sends names this
      tool. Nothing carries a browser, platform, or other-product claim. The reference library's
      constant is the trap this task exists to close.
      Satisfies AC-11.
      Files: `src/homescout/sources/realtor/__init__.py`, `src/homescout/sources/politeness.py`.
- [ ] **T8. Geography resolution.** Turn a ZIP code, a city, a city with state, a county, a state,
      or an address with a radius into the source's own geography object, and issue each in that
      form. A term that resolves to nothing, or an area shape the source cannot express, reports
      `unavailable` with the reason rather than substituting a different area or returning nothing.
      Satisfies AC-13, AC-17.
      Files: `src/homescout/sources/realtor/__init__.py`,
      `src/homescout/sources/realtor/queries.py`.
- [ ] **T9. The search request.** Build the query from the capability declaration: price, beds,
      baths, square footage, lot size, year built, property type, and listing status pushed to the
      source, everything else reported back as not applied. Page at 200 and read the matching total.
      A test asserts each declared filter measurably changes the request body.
      Satisfies AC-2, AC-3, AC-18, AC-20.
      Files: `src/homescout/sources/realtor/__init__.py`,
      `src/homescout/sources/realtor/queries.py`.
- [ ] **T10. Normalization.** One response property to one row: the mapping in the plan's D-8, the
      source's original object retained beside it, the source name and a UTC fetch timestamp
      attached. A field the response omits stays empty. A field in an unexpected shape fails the
      query with a parse error naming it, rather than yielding a row with a silently missing value.
      Satisfies AC-4, AC-5, AC-12.
      Files: `src/homescout/sources/realtor/normalize.py`.
- [ ] **T11. Working around the ten-thousand ceiling.** Supply the date-listed range as this
      source's split dimension and its ceiling as ten thousand, so the generic walk from T5 applies
      with no source-specific code in it. Proved against a stub with a known population and a
      ceiling of 50, forcing several levels of splitting, with the union checked to equal the
      population exactly.
      Satisfies AC-19.
      Files: `src/homescout/sources/realtor/__init__.py`.
- [ ] **T12. Preview images.** Retrieve one small preview image per row where the source offers one,
      through the same paced session as every other request, with the URL's scheme checked before it
      is fetched, redirects refused, the body capped, and the content type checked. A failed
      retrieval affects that row's image only: it never fails the query, never changes the source
      outcome, and never removes an image already held.
      Settled at the pre-build check (plan D-11): this is a separate paced operation, it lives on the
      interface rather than on this one adapter, and the caller contract is that the run loop calls
      it once per row and hands each result straight to the store.
      Satisfies AC-23.
      Files: `src/homescout/sources/realtor/__init__.py`, `src/homescout/sources/politeness.py`.

## Group D — the bar

- [ ] **T13. No credentials, anywhere.** Assert no adapter reads an environment variable, a key file,
      or a login, and that no request carries an authorization header. The measurement recorded in
      the plan says none is needed; this keeps it true.
      Satisfies AC-22.
- [ ] **T14. Failure isolation.** Two adapters, one failing: assert the successful one's rows,
      outcome, and pacing are untouched, and that nothing propagates.
      Covers the reliability requirement and the spec's network-unavailable edge case.
- [ ] **T15. The live tests.** Slow-marked and excluded from the default run: one honest-client smoke
      test against the real source, and the detection check (a query over ten thousand is detected as
      such, and every date range the split produces reports a count within the ceiling). Counts are
      read; rows are not retrieved.
      Satisfies AC-24.
      Files: `tests/test_sources_live.py`.
- [ ] **T16. Recorded response fixtures.** Save the responses the offline tests read, with the
      capture date noted, so a source schema change shows up as a fixture that no longer matches
      reality rather than as a test that quietly still passes.
      Files: `tests/fixtures/realtor/*.json`.
