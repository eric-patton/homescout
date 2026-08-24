<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — rule engine

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:731fe1a66bbd · plan sha256:4c9d8487ee3c · tasks sha256:f5180f76ed35

implemented: AC-1, AC-2, AC-3, AC-5, AC-7, AC-8, AC-9, AC-10, AC-12, AC-13, AC-14, AC-15, AC-16,
AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24

- opened gap-001 [partial] spec:"AC-4 Excluded properties are retrievable on request, with their
  exclusion reasons" · also spec:"AC-6 ... An explicit sort requested by the user takes precedence
  over both" · also spec:"AC-11 A property with an `undetermined` verdict is reported as such"

  Evidence: `src/homescout/rules/results.py` answers all three. `excluded` returns what was removed
  and by which criterion, `results` takes the sort a caller asks for, and every `Result` carries the
  criteria nobody could answer with the field each was missing. No surface reaches any of the three:
  the command line has no results view, and the browser interface (feat-010) and the export
  (feat-011) are unbuilt.

  What does reach a person today: the per-rule exclusion *counts*, in the run's digest entry, so an
  empty result set is never unexplained. And the systemic half of AC-11, which the spec's own edge
  case says is the more useful message: a criterion naming a field nothing fills is reported once
  when the search is validated, rather than as a per-property verdict nobody reads.

  Why it is not a contradiction: the criteria say a user can ask, and the core answers. What is
  missing is a surface to ask from, and the two features that provide one both depend on this one.

  Routed: feat-010 (browser interface) and feat-011 (spreadsheet export). Recorded here so a reader
  does not mistake a passing test for a capability a person can reach.

verdict: open 1 (missing 0, partial 1, contradicts 0, unrequested 0)

## Noted during implementation, fixed before this ledger opened

- **A pre-build finding this feature's own gate overstated.** The security pass claimed a nested
  doubling expression could reach billions of digits and gigabytes of memory. Measurement during
  implementation showed the length bound already caps it at seven levels of doubling, a 768-digit
  number in under a millisecond. The correction is written into `analyze.md` under its own heading
  rather than quietly dropped, the severity is corrected from hard to soft, and the magnitude bound
  stays for the two reasons that survive the correction. Worth recording here as well, because a
  gate report that overstates is a gate report somebody stops reading.

- **`null` as a literal could not have worked.** The plan had `water_source == null` as the way to
  ask whether a value is missing. In this product an undeterminable value is empty (invariant 10),
  so empty and unknown are one state, and a comparison with an unknown operand is unknown: the
  question could never have been answered. The grammar has `is null` and `is not null` instead,
  which always answer. The plan is amended and says it was amended.

- **Three pieces of code nothing used** were removed before this ledger opened: a severity-to-order
  helper on a rule, a grouping helper duplicated in two modules, and two module-level functions
  written for callers that never arrived. Dead code anywhere is a liability; in the package a user's
  own text passes through, it is surface that nobody is reading.

## What was checked and found clean

Recorded because "nobody looked" and "somebody looked and it was fine" are different facts, and this
feature is the one the brief names as an injection surface.

- **No compilation facility anywhere in the evaluation path.** Six modules, checked by identifier
  rather than by text search, on every test run
  (`test_no_module_in_the_evaluation_path_names_a_way_to_run_code`). The parser is written here
  precisely so this check can be trivially true.
- **Nothing in the path imports anything that can reach the world.** Checked at the import line, so
  a module that cannot import the filesystem cannot use it however it is called.
- **Twelve things that look like escapes fail to parse**, including attribute access, subscripting,
  comprehensions, lambdas, the walrus, and a conditional expression. Not rejected: unparseable,
  because the grammar has no rule that could produce them.
- **A rule cannot name what a source claims about time on market.** `days_on_market_source` is
  withheld from the namespace deliberately, and an assertion at import fails if a listing field is
  ever added without a decision about whether a criterion may see it. Freshness in this product is
  computed from this tool's own first observation, and a criterion able to name the site's own
  figure would have been a way around that, one rule at a time.
