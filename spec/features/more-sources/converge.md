<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — Zillow and Redfin sources

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-24

baseline: spec sha256:694d7c7773d3 · plan sha256:07b3cd93dd66 · tasks sha256:b1783d96dea9

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8, AC-9, AC-10, AC-11, AC-12

- opened gap-001 [partial] spec:"AC-7 The Redfin adapter reports the outcome `unavailable`,
  distinct from `failed`, when the region does not permit downloads, and the reason is
  human-readable"

  Evidence: `src/homescout/sources/redfin/__init__.py`, `_refuse_if_not_a_download`. `unavailable`
  is reported for three answers, each naming what came back: the site's error envelope, an HTML
  block page, and an empty body. None of them is the case the criterion names.

  Why the case the criterion names is not there: the endpoint does not carry it. Every response, in
  every region, ends with the same sentence about local rules. A metropolitan box over Springfield,
  Illinois returns two properties; a box over Portales, New Mexico, a town of twelve thousand,
  returns sixty-one. The restriction is real and it is invisible to any reader of the response.

  What is built instead: every Redfin result carries a standing caveat in its detail saying this
  source's contribution is never known to be complete. Reported every time rather than guessed at,
  because the only available guess is a row-count threshold, which would report a quiet market as a
  policy restriction and a restricted market as quiet.

  Why it is not a contradiction: the criterion's purpose is that a coverage gap is never presented
  as a quiet market, and that purpose is kept, more bluntly than the criterion asked for. What
  cannot be done is the specific mechanism the criterion names.

  Routed: recorded as a narrowing in `feature.md` under this feature's own later changes, with the
  measurement behind it, and raised in the pre-build check as C-1 before any of it was built. No
  remediation task: there is nothing to build, and the criterion's own text is left alone rather
  than rewritten to match the code.

- opened gap-002 [unrequested] code:"each adapter translates the site's property types and listing
  statuses into one shared vocabulary"

  Evidence: `zillow/normalize.py` `PROPERTY_TYPES` and `STATUSES`, `redfin/normalize.py` the same
  two tables. Zillow says `SINGLE_FAMILY`, Redfin says `Single Family Residential`, Realtor.com says
  `single_family`, and all three are recorded as `single_family`. Likewise `FOR_SALE`, `Active` and
  `for_sale` all become `for_sale`.

  Nothing in this feature's spec asks for it. It was done because a criterion says
  `property_type == 'single_family'` and because address matching, which is the next feature, has to
  compare properties across sources: without one vocabulary, a rule written against one source is
  silently false for the other two, and a merge cannot tell a house from a house.

  A value no table knows is kept exactly as the site wrote it rather than dropped or guessed at, so
  an unfamiliar property type stays visible as a fact about the market.

  Routed: a human decision, and the recommendation is to legitimize it as an addition to this
  feature's spec rather than remove it. It is small, it is load-bearing for two other features, and
  the alternative (three vocabularies in one column) is a defect waiting for whoever writes the
  first rule. Recorded rather than self-applied.

verdict: open 2 (missing 0, partial 1, contradicts 0, unrequested 1)

## What was checked and found clean

- **Splitting recovers the whole market, and that is asserted as set equality.** A fixed universe of
  two thousand properties, a site that answers any box with the ones inside it capped at five
  hundred while reporting the true count, and the walk returns exactly the two thousand: none lost,
  none twice. An assertion that merely counted past five hundred would pass on a walk that lost half
  the market and found the rest twice, which is why this one compares sets.
- **The core was not touched, and both directions are checked.** Neither new package imports the
  store, the run loop, the merge layer or either surface, and nothing outside the sources package
  imports an adapter. The two places outside it that so much as mention one are a starter template
  and an in-memory default, both whitelisted by name in the test, so a third appearing is a signal
  rather than a silence.
- **The shared interface tests are parametrized over the registry.** They found a real omission
  while being written: the Redfin adapter had no answer for preview retrieval at all and was
  inheriting the interface's refusal. It now answers None, with the reason (the download has
  twenty-seven columns and none of them is a photograph) written where somebody will look for it.
- **Every filter each adapter declares was measured against the real site**, not read from anyone's
  documentation. That is what found the one this feature does not declare: Redfin will not narrow by
  lot size under any parameter name tried, while every other filter does work. Undeclared, filtered
  locally, and written into the README, because for a tool whose own saved searches are mostly about
  acreage it is the difference between that source being useful and being nearly so.
- **The politeness floor is untouched and the pieces of a split go through it.** Observed on a fake
  clock rather than assumed: a query that splits waits between its pieces. Zillow also turned out to
  need one request per box rather than one per page, so this feature makes fewer requests than the
  obvious implementation of it would.
- **Neither adapter can mark a property as disappeared.** Checked end to end rather than argued:
  a run with Redfin refusing completes, is recorded degraded, and reports nothing gone. Absence is
  not evidence, the store enforces it, and a new source cannot get around it.
