<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — command line and run orchestration

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:c0b3ddeac620 · plan sha256:707ff03b520b · tasks sha256:3c3d84b4df13

implemented: AC-1, AC-2, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14,
AC-15, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29,
AC-30, AC-31, AC-32

- opened gap-001 [partial] spec:"AC-3 Exit codes are stable and documented"

  Evidence: `src/homescout/cli/codes.py`, the meanings appear only as source comments. Neither
  `homescout --help` nor the README names a single code.

  Why it matters: the codes are the whole contract between this tool and a scheduled task, and half
  of "stable and documented" is missing. Somebody writing the Task Scheduler entry has to open the
  source to learn that 1 means degraded, which is exactly the friction the machine contract exists
  to remove. The stability half holds; the documented half does not.

  Routed: task T23 in this feature's own list. The help text and the README.

- opened gap-002 [contradicts] spec:"AC-16 When every saved search is run at once, each definition
  is validated on its own: the ones that fail are reported and skipped, the ones that pass still
  run" · also spec:"AC-26 A run of a saved search that is already running declines ... the run
  already in progress is unaffected"

  Evidence: `src/homescout/api.py`, `run_all` catches `InvalidSearch` and nothing else. A saved
  search already running raises `RunInProgress`, and one naming an unregistered source raises
  `InvalidInput`, and both escape the loop.

  Why it matters: the criterion's reasoning is that an observation not made tonight can never be
  made later, so one bad definition must not cost a night of history for the searches that were
  fine. The code honours that for a definition that fails validation and breaks it for two other
  ways a search can be unstartable. The realistic case is the one the whole feature was blocked on:
  a nightly run of everything collides with a manual run of one search, and instead of skipping that
  one, every remaining search is skipped too. The failure is silent in the worst way, because the
  digest simply has fewer entries in it.

  Routed: fidelity defect. The code is wrong and the spec is right. Skip and report with the reason,
  the same as an unreadable definition. Regression test citing AC-16.

- opened gap-003 [contradicts] spec:"AC-3 Exit codes are stable ... precondition not met, meaning
  the operation is valid but cannot proceed yet" · plan:"D-6 Precedence when one invocation produces
  several: internal error, then invalid input, then degraded, then success"

  Evidence: `src/homescout/cli/codes.py`, `PRECEDENCE` lists four of the five codes. `worst_of` walks
  it and falls through to `SUCCESS` for anything it does not find, so `worst_of([PRECONDITION])`
  returns 0.

  Why it matters: an invocation whose only outcome was "cannot proceed yet" reports success. A
  scheduled run of every saved search, every one of them declining because a manual run held the
  claim, would exit 0 and tell nobody that nothing happened. Reporting work that did not happen as
  success is the single thing an exit-code contract exists to prevent, and the plan's own precedence
  list has the same hole, so this was specified wrong and built to match.

  Severity: this one traces to product invariant 6, which makes the exit code the thing an automated
  agent acts on. At the artifact level a finding anchored there would have stamped the pre-build
  check hard-blocked.

  Routed: fidelity defect, plus a one-line correction to the plan's precedence list. Precondition
  sits above degraded: a search that did not run at all is worse news than one that ran with a
  source down. The order is then asserted to account for every code, so a sixth one cannot be
  forgotten the same way. Regression test citing AC-3.

verdict: open 3 (missing 0, partial 1, contradicts 2, unrequested 0)

## run 2 — 2026-08-23

baseline: spec sha256:c0b3ddeac620 · plan sha256:94b1b6d6f164 · tasks sha256:ed12989ebc5a

implemented: AC-1 through AC-32

- closed gap-001

  The codes and their meanings are in `homescout --help`, as an epilogue after the options, and in
  the README as a table with the precedence rule under it. Somebody writing a Task Scheduler entry
  can read both without opening the source.

  Regression test citing AC-3: `test_the_exit_codes_are_documented_where_someone_will_read_them`,
  which asserts every code's number and the words for the three that are easy to confuse appear in
  both places. It fails if a code is added and only documented in one of them.

- closed gap-002

  `run_all` now catches the two other ways a saved search can fail to start and records each as
  skipped with its reason: `invalid` for a definition that does not validate or names an
  unregistered source, `in progress` for one another process is already running. The digest carries
  the reason, and the exit code follows from it: invalid input for the first, precondition for the
  second.

  Regression tests citing AC-16: `test_a_search_that_is_already_running_does_not_stop_the_others`,
  which holds a real claim from a second process while a run of everything goes past it, and
  `test_a_search_naming_an_unregistered_source_does_not_stop_the_others`.

- closed gap-003

  The precondition code has its place in the order, above degraded. More usefully, the order is now
  asserted at import to account for every code, so the way this was missed cannot happen twice: a
  sixth code that nobody adds to the list fails at import rather than silently reporting success.
  The plan's own precedence list, which had the same hole, is corrected.

  Regression tests citing AC-3: `test_the_precedence_order_accounts_for_every_code` and
  `test_a_run_of_everything_that_managed_nothing_never_reports_success`, which drives two unreadable
  definitions through a run of everything and asserts the answer is not zero.

verdict: open 0 (missing 0, partial 0, contradicts 0, unrequested 0)

## Noted during implementation, fixed before this ledger opened

Not gaps (they never reached the audited code) but worth recording, because each is the kind of
defect that passes every test written before it:

- **A status filter would have deleted the evidence it exists to watch for.** A saved search asks for
  what is for sale. A source that cannot apply that filter returns everything, and the local half of
  the filter then dropped the very property that had just gone pending. The store saw nothing where
  the source had told us something, and could only have reported it as an unexplained disappearance.
  Found by a digest test that expected a status change and got a disappearance. The status filter now
  shapes what is asked for and never hides what came back, which is AC-32.
- **"What changed since today" was rejected as a date in the future.** A bare date means the end of
  that day, and the end of today has not happened yet. Now clamped to the current moment, so only a
  day that has not started is refused.
- **An unknown property identifier crashed instead of being reported.** The store's own error for it
  was not among the ones the facade translates, so `annotate` on a bad id exited with the internal
  error code. Every one of the store's errors is now classified deliberately.
- **The two-surfaces comparison was testing the clock.** It normalized generated timestamps by their
  first-appearance order, so two operations landing in the same microsecond in one database and not
  in the other changed the numbering and failed the comparison, about one run in three. Timestamps
  are now blanked: whether two writes shared a microsecond is a fact about how busy the machine was,
  not about what the operation did. It was also picking its property with `listings()[0]`, and two
  properties observed in one run share a first-observed time, so the store's stable tiebreak on the
  identifier made that a coin toss. It now names the address it means.

## Found by the first live run, against another feature

- **Preview retrieval never returned a picture from the real source.** Realtor.com gives its image
  addresses as plaintext `http://`, its image host answers each one with a 301 to the identical
  `https` address, and image fetches deliberately do not follow redirects, so every preview in the
  product was a 167-byte redirect page. No offline test could catch it, because a fake transport
  returns whatever it is told to.

  This is a defect in the source adapters (feat-002), not here, and it is recorded in that feature's
  manifest with its fix and two tests citing `feat-002/AC-23`. It is noted here because this
  feature's first live run is what found it, and because the caller contract that made it visible
  (a run retrieves one preview per property that has none) is this feature's.
