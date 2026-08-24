<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — source adapters and the Realtor.com source

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:3f5ae53abded · plan sha256:35dd661a0920 · tasks sha256:02218b260aa5

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-12, AC-13, AC-14,
AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-24

- opened gap-001 [contradicts] spec:"AC-11 Every request carries a user agent that identifies the
  tool honestly. No adapter impersonates a browser or another product." · also
  constitution:"non-negotiable 10, an honest user agent"

  Evidence: `src/homescout/sources/politeness.py`, `PolitenessConfig.user_agent`, read by
  `PacedSession.__init__` as `self._config.user_agent or user_agent`.

  Why it matters: the user agent was a configuration setting like any other, so
  `user_agent: "Mozilla/5.0 (Windows NT 10.0) Chrome/135.0.0.0"` in a config file would have made
  the tool claim to be a browser on every request, with nothing rejecting it. The criterion and the
  non-negotiable both read as promises about the tool's behavior, and a knob that turns the promise
  off is not a promise. Every other setting in that file is tunable because the right value depends
  on the source; this one is the tool's identity.

  Severity: anchored to a constitution non-negotiable. At the artifact level this would have
  stamped the pre-build check hard-blocked, which is what it did to the plan's first draft for the
  neighbouring header question.

  Routed: fidelity defect. Remove the setting; the name is passed in by the package and cannot be
  reached from configuration. Regression test citing AC-11.

- opened gap-002 [partial] spec:"AC-23 For each returned row the adapter retrieves one small preview
  image where the source offers one" · plan:"D-11, fetch_preview is a member of the Source protocol
  ... so that a source added later inherits the obligation instead of quietly declining it"

  Evidence: `src/homescout/sources/base.py`, `BaseSource.fetch_preview` returned `None`.

  Why it matters: the plan's whole argument for putting preview retrieval on the interface was that
  an adapter must not be able to skip it. The shared base class then handed every adapter a silent
  no-op, so Zillow and Redfin could satisfy the interface, pass every test, and never fetch an
  image. That is the same hole the whole-product review found once already, where nobody owned the
  preview image the email digest depends on, reintroduced one layer down by a default value.

  Routed: fidelity defect. The base raises rather than returning; a source with no images returns
  None deliberately.

- opened gap-003 [contradicts] spec:"AC-23 A failed image retrieval affects that row's image only:
  it never fails the query, never changes the source outcome" · also spec:"AC-12 ... does not
  propagate an exception that would abort a caller querying other sources"

  Evidence: `src/homescout/sources/realtor/__init__.py`, `fetch_preview` caught `SourceFailed` and
  nothing else, and no shared wrapper existed.

  Why it matters: `search` is carefully uncrashable, catching everything including the things nobody
  anticipated, precisely so one source cannot take a run down with it. Preview retrieval is a second
  entry point into the same adapter and had none of that. An unexpected error there, in the least
  important thing a run retrieves, would have ended the run.

  Routed: fidelity defect. A `preview` wrapper on the base gives the same guarantee `search` gives,
  in one place rather than in every caller.

- opened gap-004 [unrequested] code:"registry.create_all and base.dedupe"

  Evidence: `src/homescout/sources/registry.py`, `create_all`, called from nowhere;
  `src/homescout/sources/base.py`, `dedupe`, called only from tests after the deduplication moved
  into the ceiling walk.

  Why it matters: `create_all` anticipates the run loop, which the command line feature owns and
  specifies. `dedupe` was superseded during implementation and left behind as public surface. Both
  are the same shape of thing the listing store's audit removed: behavior belonging to another
  feature, or to no feature, living here.

  Routed: removal. The command line feature builds its own set of sources when it needs to.

verdict: open 4 (missing 0, partial 1, contradicts 2, unrequested 1)

## run 2 — 2026-08-23

baseline: spec sha256:3f5ae53abded · plan sha256:35dd661a0920 · tasks sha256:02218b260aa5

implemented: AC-1 through AC-24

- closed gap-001

  The user agent is no longer configuration. `PolitenessConfig` has no such field, and a config file
  naming one is refused at load with the unknown-setting message, so a misspelling and an attempt to
  impersonate fail the same way. `PacedSession` takes the name from the package.

  Regression test citing AC-11:
  `tests/test_sources_contract.py::test_the_user_agent_is_not_a_setting`, which feeds a Chrome user
  agent through configuration and asserts it is refused.

- closed gap-002

  `BaseSource.fetch_preview` raises `NotImplementedError` naming the adapter and saying what to do
  instead. An adapter with no images returns None on purpose, which is a decision on the record
  rather than an omission nobody sees.

  Regression test citing AC-23:
  `test_an_adapter_must_decide_what_preview_retrieval_means_for_it`.

- closed gap-003

  `BaseSource.preview` wraps retrieval with the same guarantee `search` carries: nothing escapes,
  including the unanticipated. Regression test citing AC-23 and AC-12:
  `test_a_preview_can_never_interrupt_a_run`, which raises a bare `RuntimeError` from an adapter's
  preview and asserts the caller gets None.

- closed gap-004

  Both removed from the package and from its public surface.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## Noted during implementation, fixed before this ledger opened

Not gaps (they never reached the audited code) but worth recording, because both are the kind of
defect that passes every test that was written before it:

- **The radius on an address search was discarded.** `_build` sent `radius: "0mi"` regardless of what
  the saved search asked for, so "everything within five miles of this address" would have returned
  one house and read as a market with nothing in it. Fixed to read the radius from the query, with a
  test asserting `5mi` reaches the request.
- **Deduplication collapsed a source's own repeat.** The walk deduplicated across all rows rather
  than across pages, so a source returning one identifier twice in a single response with different
  values would have lost the second. That is precisely the bug the listing store's audit found one
  layer down, and the spec's own edge case forbids it. The boundary is now the page: a repeat across
  pieces is our own overlapping ask and is dropped; a repeat inside one response is the source
  contradicting itself and both halves survive.
- **The recursion bound bounded nothing.** The walk limited split depth, which permits a million
  requests because the branch count doubles at every level. Found by a test that hung. The walk now
  carries a budget on total requests, and exhausting it is an honest truncation.
