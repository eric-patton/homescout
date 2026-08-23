<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — listing store and snapshot history

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:64362b1ff63f · plan sha256:b4f0e832f4a4 · tasks sha256:1a994f135c81

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-13, AC-14,
AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-25, AC-26

- opened gap-001 [contradicts] spec:"AC-24 A property returned more than once within a single
  source's response for a single run is recorded once per distinct source row" · also
  constitution:"non-negotiable 5, never destroy source rows"

  Evidence: `src/homescout/store/core.py`, `record_observations`. Rows are keyed by
  (source, source identifier) and a repeat of that key inside one response is skipped outright, so
  no row is written for it at all.

  Why it matters: the code reads that key as the identity of the property, but the criterion is
  about rows, and a source returning one identifier twice with different values is returning two
  pieces of evidence. Discarding the second destroys a source row, which the project rules forbid
  outright, and no source will ever tell us later what it said. Confirmed by direct probe: one
  response carrying the same identifier at 400,000 and at 350,000 leaves only the 400,000 row, with
  no record that the other was ever seen.

  Severity: anchored to a constitution non-negotiable. At the artifact level the same violation
  would have stamped the pre-build check as hard-blocked.

  Routed: fidelity defect. The spec is right and the code is wrong. Fix plus a regression test
  citing gap-001. Remediation task T18.

- opened gap-002 [partial] spec:"AC-12 Days on market is derived from the tool's own first
  observation. Given a source reporting a contradictory value, the tool's value is used and the
  source's value never overwrites it."

  Evidence: `src/homescout/store/models.py`, `ListingFields` has no field for a source's own
  days-on-market, so there is no path by which one could be stored.

  Why it matters: the guarantee holds, but only because the situation the criterion describes
  cannot be represented at all. The spec's own scenario, a source reporting four hundred days for a
  property first seen forty days ago, cannot be written as a test. A criterion that cannot fail is
  not verified, it is unfalsifiable, and the first source adapter will want the source's claim
  recorded for exactly the debugging this criterion anticipates.

  Routed: remediation task T19. Keep the source's claim as an informational field, outside the
  compared set, and prove by test that it never substitutes.

- opened gap-003 [unrequested] code:"Comparison.counts exposes a combined matched total"

  Evidence: `src/homescout/store/models.py`, `Comparison.counts` adds a "matched" key summing new,
  changed, unchanged and returned.

  Why it matters: nothing in this feature's spec asks for it. It anticipates the run digest, which
  the command line feature owns and specifies. Behavior belonging to another feature, living here,
  is how a layer boundary starts to blur.

  Routed: removal. The command line feature defines the digest's counts when it needs them.
  Remediation task T20.

verdict: open 3 (missing 0, partial 1, contradicts 1, unrequested 1)

## run 2 — 2026-08-23

baseline: spec sha256:64362b1ff63f · plan sha256:b4f0e832f4a4 · tasks sha256:b4b8f6b31a77

implemented: AC-1 through AC-26

- closed gap-001

  Fixed in `src/homescout/store/core.py`, `record_observations`: every row a response contains is
  now written, and only the property collapses. A repeat of an identifier joins the same canonical
  listing, the run still holds one snapshot of it, and the comparison still reports one event.

  Regression test citing gap-001:
  `tests/test_store_history.py::test_a_repeated_identifier_in_one_response_keeps_both_rows`, which
  feeds one response carrying the same identifier at two different prices and asserts both rows
  survive. The pre-existing duplicate test now also asserts the row count, so the collapse cannot
  quietly come back.

- closed gap-002

  A source's own days-on-market claim is retained as an informational field, deliberately outside
  the compared set. Two tests citing gap-002: one proves the locally derived figure wins over a
  source claiming four hundred days for a property first seen forty days ago, and one proves that a
  source incrementing its own counter overnight is not a market event. The criterion's own scenario
  is now writable as a test, which it previously was not.

- closed gap-003

  The combined "matched" total is removed. The run digest, and whatever counts it needs, belongs to
  the command line feature.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)
