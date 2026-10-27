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

## run 3 - 2026-09-23

baseline: spec sha256:c8872034365c · plan sha256:9782001dc298 · tasks sha256:613aea6e4ca5 · code n/a

implemented: AC-1 through AC-34

The new scope revision is stored with each run and limits baselines and disappearance evidence.
Completed target runs freeze canonical identity; legacy targets disclose that their identity is
unfrozen. Source handoffs without a shared observation are counted separately. The digest, email,
command line, and browser surface those results. Tests cover these paths and the live schema 14
backup migrated to schema 15 with its recorded runs and snapshots intact.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## run 4 - 2026-10-14

baseline: spec sha256:11d7023c282e · plan sha256:f8a35cf5b796 · tasks sha256:36671ef89dd0 · code n/a

implemented: AC-25

Scoped inline audit of the workspace photo-path defect. Store.store_preview_image writes portable
relative paths and preview_image_path resolves legacy Windows separators without changing records.
The regression failed on the Mac before the fix and passed after it. Live API and browser checks
read a retained photo; post-run SQL comparison found no missing or altered original image records,
annotations, assessments, raw rows, snapshots, events, or identity history. Other unchanged criteria
retain the prior audit disposition; this run makes no new full-feature claim.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## run 5 - 2026-10-27

baseline: spec sha256:11d7023c282e · plan sha256:f8a35cf5b796 · tasks sha256:e98e10dc9eef · code n/a

implemented: AC-1, AC-2, AC-20, NFR-performance

Scoped inline audit of T25's latest-snapshot query optimization. Raw findings: none in the changed
surface. `src/homescout/store/core.py:721` still returns the same fields for live canonical listings,
selects the newest observation by run sequence, preserves narrowed and empty requests, and executes
SELECT statements only. CROSS JOIN changes the lookup order without changing snapshot semantics,
historical comparisons, merge mechanics, annotations, or the schema. No unrequested behavior or
glossary mismatch was found in this surface. Other unchanged criteria retain their prior audit
disposition; this run makes no new full-feature claim. The manifest declares no code_surface, so the
code baseline remains n/a.

`tests/test_store_latest.py:12` verifies sequence ordering even when snapshots arrive out of order,
including a newer empty run and a duplicate or unknown requested ID. It also checks that reads write
nothing. `tests/test_store_latest.py:35` verifies live-record selection through supersession and undo.
`tests/test_store_latest.py:48` reproduces historical-scan work growth before the fix and passes after
it, for both full and narrowed requests. All 1,704 default tests and six slow store/merge performance
tests passed; four default tests were skipped. Ruff and the listing-store artifact validator passed.

A separate process on the Mac evaluated the exact worktree method against the live database with
mode=ro, query_only=ON, and one read transaction. The installed and worktree methods returned equal
full snapshots, narrowed snapshots, and complete review entries. The fresh queue took 4.7432 seconds
before and 0.3649 after, with total_changes=0. This was a read-only benchmark, not a deployment or a
measurement of the complete live browser delay. The browser extension verified saving and removal
of the original match card against an isolated local fixture running the changed code; its after
screenshot is attached to Guildboard card #1. The Mac's running service remains unchanged.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## run 6 - 2026-10-27

baseline: spec sha256:11d7023c282e · plan sha256:f8a35cf5b796 · tasks sha256:a3365813914b · code n/a

implemented: AC-1, AC-2, AC-20, NFR-performance

Scoped inline deployment verification of T25. Raw findings: none in the changed surface. The
runtime code is identical to the audited and tested `7175468` change; only this verification record
and the task receipt were added. The earlier scoped audit and unchanged criteria retain their
disposition. The manifest still declares no code_surface.

The user explicitly approved deploying and verifying live. The clean Mac checkout was fast-forwarded
to `7175468` after checking the transferred bundle hash and confirming the service was idle. All 71
focused snapshot/store/merge tests passed on macOS. The interface process restarted under its existing
launchd job, with no change to scheduling, configuration, dependencies, or schema.

The browser extension verified one reserved live merge: the original card disappeared in 2.552
seconds from the automation click call, including automation overhead, and the queue went from 90
to 89. This is one sample, not a percentile or an exact comparison with a measured pre-fix browser
baseline. A subsequent live matches request took 0.5736 seconds and excluded the original match.
The merge decision persisted. The schema stayed at version 15; counts remained 208,346 raw rows,
112,723 snapshots, and 1,247 annotations. The live after screenshot replaced the local-fixture
image on Guildboard card #1. No active passes remained after verification.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)
