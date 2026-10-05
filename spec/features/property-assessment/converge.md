<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — property assessment

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-29

baseline: spec sha256:424c783d638b · plan sha256:ec0a8523e074 · tasks sha256:7bac2e062ff2

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13,
AC-14, AC-16, AC-17

- opened gap-001 [partial] spec:"AC-15 Whether a run assesses what it found is a property of the
  saved search, off unless turned on"

  Evidence: `src/homescout/search/validate.py` parsed `assess.model`, refused a non-boolean with a
  sentence naming what the pass sends, and set `reading.model_assessment`;
  `src/homescout/search/definition.py` exposed it on the definition. Nothing read it. A search
  file could say `assess: {model: true}` and be validated, accepted and completely ignored.

  This was found by reading the built code against the criterion, not by a failing test. The tests
  covering T23 asserted the switch parsed, which it did. A setting that is accepted and ignored is
  worse than one that does not exist, because it reads as a decision somebody made.

- closed gap-001 [was partial] a run now consults the switch

  `assess/pass_.py` gained `enabled_for` and `for_run`, mirroring the
  extraction pass's own pair, and `runner.py` calls it. The assembly moved out of `api.assess`
  and into `assess/pass_.py:assess_search` so that both callers reach one implementation: left in
  `api`, a run would have had to reach across a layer into a surface's function or copy it, and a
  copied assembly is how the pass a run performs drifts from the pass a person asks for.

  Ordering is stated where it is made: the assessment runs after `record_verdicts` rather than
  before, because a dossier carries which rules fired and there is nothing to carry until they
  have. That is a different position from the extraction pass, which runs *before* the criteria so
  that a rule naming `sewer` sees this run's recovered value.

  Citation: `tests/test_assessment.py::test_a_run_assesses_only_when_the_search_asked_it_to`, which
  asserts the half that matters — off is the default, and off reaches nothing: `for_run` is handed
  objects that would raise if touched and returns `None` without touching them.

- checked and holding, recorded because each was cheap to get silently wrong:

  **AC-13 (pacing).** `assess` uses a new pacing key, and the model's politeness config names only
  `extract` in its per-source table. A key absent from that table falls through to the config's
  default, and the default here *is* the model policy, so the assessment pass gets the same 2s
  delay, 60s timeout and three retries. Verified by asking the built session for both keys rather
  than by reading the table. Had the default been the generic source policy, this pass would have
  been unpaced against a paid API and nothing would have said so.

  **AC-1 (the set).** `export.latest_run` selects with `only_completed=True`, so a half-finished run
  cannot define what is in play.

  **AC-7 (decides nothing).** Nothing under `src/homescout/assess/` writes a judgment or an
  annotation. The only reads of `judgment` are in `criteria.py`, pulling past decisions in as
  calibration. The pass's single write is `record_assessment`, into a table of its own.

- unrequested behaviour swept for and not found. The module surface is `dossier`, `criteria`,
  `surroundings`, `model`, `pass_`, and every public name in them is cited by a criterion or a task.

contradicts: 0

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## Notes carried forward

T28, drawing an assessment beside a person's own notes, is deliberately not built and is marked
`[-]` rather than unchecked. It is a change against feat-010 and is deliberately unspecified until
this has run over a real set, because what is worth showing is a question somebody answers after
reading twenty of these. That is a decision on the record rather than an omission, and the next
converge run should not open a gap for it.

## run 2 - 2026-10-03

baseline: spec sha256:7a301ed5b159 · plan sha256:a1a2df255c3d · tasks sha256:af13a2c957ad · code n/a (no `code_surface` declared, and this workspace's validator has no code fingerprint)

Scoped to `changes/what-the-water-did/` (AC-21, AC-22). AC-1 to AC-20 were not re-read: nothing in
this change touches them, and AC-18 to AC-20 still await a full run.

implemented: AC-21, AC-22

note: the dossier now keeps a stored empty water value whose empty is an answer (no water table
recorded, no stream within a mile, not decided by FEMA), said in words, from the enrichment feature's
AC-43 and D-21. It is traced there rather than unrequested here. Its one consequence for this feature
is that a property holding one of those values has a new fingerprint once, so its reading is read
again on the next pass somebody starts (AC-19), which is the right outcome and is said in
`feature.md`. A test now also pins that a stored-empty soil, stream, flash-flood or dam value with
no meaning of its own is named among the unknowns.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## run 3 - 2026-10-04

baseline: spec sha256:406245a0e082 | plan sha256:fb8a879266a7 | tasks sha256:1eafde240685 | code n/a (no code_surface declared; this workspace validator has no code fingerprint)

Scoped inline drift-auditor review of changes/concurrent-assessment against AC-23, AC-24,
related AC-9, AC-11, AC-13 and AC-20, the plan, tasks, constitution and product-global.
Prior behavior outside this change was not re-audited. The existing deferred T28 decision stands.
Raw findings: no new missing, partial, contradicts or unrequested behavior in this scope.

implemented:

AC-23: assess/settings.py:23,32 validates concurrency before requests through the existing
local environment loader, default eight, range 1 to 32. assess/pass_.py:220,226 bounds both
workers and submitted jobs. Picture callbacks and assessment writes remain on the coordinator;
only ask/ask_in_favour run on workers. sources/politeness.py:328,347,351 shares atomic pacing
and cooldown, including Retry-After. sources/transport.py:50 gives each thread a pooled HTTP
session. assess/pass_.py:493 closes owned connections after workers stop, preserving borrowed
session ownership. New tests prove overlap, bounded preparation, actual SQLite ownership,
configuration rejection and cleanup.
AC-24: assess/pass_.py:245,256,267 consumes ready futures and saves results before an earlier
slow request finishes. Coordinator progress names finished, successful full readings, top-ups,
failures, remaining and active jobs. The existing shared progress callback reaches both surfaces;
no new UI implementation is needed. Tests prove partial failure and matching final counts.
AC-9, AC-11, AC-20: fingerprint, per-search criteria and property deduplication are unchanged;
current readings are excluded before submission and the limit retains top-up priority. Tests
prove saved readings are skipped after restart and all top-ups finish before full readings begin.
No model, reasoning effort, prompt, search-file or user annotation change was made.

Verification: the full default suite passed 1,660 tests, with 126 live/slow tests deselected.
All 29 new concurrency tests passed again after freezing the Retry-After HTTP-date test clock.
Python lint and both scoped spec validators passed. Live activation is a separate operational
step after this audit, using the user's authorized restart of the existing model pass.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)
