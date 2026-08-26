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

## run 2 — 2026-08-25

baseline: spec sha256:731fe1a66bbd · plan sha256:4c9d8487ee3c · tasks sha256:f5180f76ed35

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-12, AC-13, AC-15,
AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24

- confirmed gap-001 [partial] spec:"AC-4 Excluded properties are retrievable on request" · also
  spec:"AC-6 An explicit sort requested by the user takes precedence" · also spec:"AC-11 A property
  with an `undetermined` verdict is reported as such"

  Two of the three anchors are now reachable, because the two features run 1 routed this to have
  since been built.

  AC-4: `src/homescout/export/rows.py:64` includes what a `drop` rule removed when
  `--include-dropped` asks, reading `excluded()` from `rules/results.py`, and the browser reaches
  the same answer through `web/app.py:341`. What a criterion removed, and which criterion removed
  it, is now something a person can ask for from either surface.

  AC-6: `api.results` sends every row once and `web/static/results.js:119` sorts on a column
  heading click. An explicit sort therefore replaces the boost and demote order rather than being
  merged with it, which is the precedence the criterion asks for.

  AC-11 is what remains, and it is unchanged since run 1 in substance: `rules/results.py:93` carries
  `undetermined` per property, naming the criterion and the field it could not read, and nothing
  reads it. A search for the name across `web/`, `export/`, `cli/` and `api.py` returns no use. The
  core still answers a question nobody asks.

  Not closed, because closing asserts a fix that has not landed. Narrowed rather than split: the id
  keeps its three anchors so the history stays readable, and the open behavior is now one anchor.

- opened gap-002 [contradicts] spec:"AC-14 The distinction between a name that does not exist and a
  name that exists but has no value yet is preserved in the reported message"

  Evidence: `rules/check.py:115` branches on `field.populated`, which is a static declaration in
  `rules/namespace.py:103-112` where all eight enriched fields still read `False`. Meanwhile
  `rules/verdicts.py:97` genuinely fills those names from the enrichment cache
  (`known_values(enriched_values_for(...))`) before a criterion is evaluated. So a criterion naming
  `flood_zone`, `wildfire_hazard` or `wildland_urban_interface` is told that nothing fills it and
  that the rule "never drops or flags anything", about a rule that does both.

  Why this is a contradiction and not a stale comment: this feature's own notes record the intended
  behavior. Under "2026-08-23, location enrichment (feat-007)": *"the notice a criterion gets about
  an unfilled field stops appearing when it stops being true."* It has not stopped. Description
  field extraction (feat-009) flipped its six extracted names to `populated: true` in the same edit
  that filled them; location enrichment filled the enriched names and left all eight declared unfilled.

  Worse than wrong, it is unclearable. `populated` is a declaration rather than a question about the
  cache, so running enrichment does not quiet it. Observed on a statewide saved search carrying three
  fire and flood criteria: four notices of this kind, on a workspace where the providers are
  registered, the credentials are present, and the values fetch.

  Why it matters at all, given that the criteria still fire: AC-14 exists because the two messages
  have different fixes. "This name does not exist" means correct the rule. "This name is not filled
  yet" means wait for the feature that will fill it. A person told the second about a working
  criterion waits for something that already shipped, or deletes a rule that was doing its job. The
  message is load-bearing precisely for somebody who cannot read the code to check.

  For whoever takes the fix: flipping the eight flags to `true` is the obvious move and is probably
  the wrong one. `populated` earns its keep for the extracted fields, where a build genuinely may not
  fill them. The enriched case wants a different question, closer to "is a provider registered and
  configured for this name", which `enrich/registry.py:79` already answers at import time.

  Routed: /spec-flow:change, fidelity lane. If the code were perfect the spec would still be right,
  so this is a defect to fix and trace, not a delta to write.

verdict: open 2 (missing 0, partial 1, contradicts 1, unrequested 0)

## run 3 — 2026-08-25

baseline: spec sha256:731fe1a66bbd · plan sha256:4c9d8487ee3c · tasks sha256:f5180f76ed35

- closed gap-002 [was contradicts] spec:"AC-14 The distinction between a name that does not exist
  and a name that exists but has no value yet is preserved in the reported message"

  Fixed rather than relabelled. The eight enriched fields now declare `populated: true`, which the
  registry's import-time assertion already guaranteed was true, and `rules/namespace.py` gained
  `unconfigured()`: a live question about this installation rather than a claim about this build.

  The distinction AC-14 asks for is now three ways rather than two, and the third is the one that
  was missing. A name that does not exist is a problem. A name nothing in the build fills is a
  notice naming the feature that will fill it. A name something fills, where the provider behind it
  is registered but not configured *here*, is a notice saying exactly that. A name that is filled
  and simply empty for one property says nothing at validation, because that is the property's own
  answer and belongs in a verdict.

  The broadband provider is what makes the third case real rather than theoretical: it needs a
  credential, so `download_mbps` is genuinely undetermined without one and answerable with one, and
  no static table could ever have told those apart. That is why the fix is not flipping a flag.

  Closed by: `rules/check.py:115-133` (both branches), `rules/namespace.py:136-160`
  (`unconfigured`). Regression tests citing this gap:
  `tests/test_rules_namespace.py::test_a_criterion_on_a_provider_that_is_configured_is_told_nothing_at_all`
  and `tests/test_rules_definition.py::test_a_rule_on_a_provider_that_needs_no_credential_is_not_warned_about`,
  both asserting silence, which is what a working criterion should hear. Two existing tests asserted
  the defective wording and were corrected in the same change rather than left green against a bug.

- confirmed gap-001 [partial] spec:"AC-11 A property with an `undetermined` verdict is reported as
  such"

  Unchanged since run 2 and not touched by this fix. The core still records which criterion could
  not be answered and which field was missing; no surface reads it. Left open deliberately: closing
  it means reopening a feature that reads done, which is a human call and was put to the owner.

verdict: open 1 (missing 0, partial 1, contradicts 0, unrequested 0)
