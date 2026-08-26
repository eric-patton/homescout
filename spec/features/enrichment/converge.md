<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — location enrichment providers

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:05e7d2225567 · plan sha256:cb180dfc31e1 · tasks sha256:d598a7fd08c5

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-10, AC-12, AC-13, AC-14

- opened gap-001 [partial] spec:"AC-8 The pass can be limited to stale and missing values only"

  Evidence: `src/homescout/enrich/pass_.py`, `_keys_to_ask`. The default pass already asks only for
  values that are stale or missing, because a fresh cache hit makes no request (AC-2). So the
  criterion's wording describes what the pass does with no flag at all, and a `--stale` flag meaning
  the same thing would do nothing.

  What is built instead: `--stale` refreshes only values that were fetched before and have aged, and
  leaves values nobody has ever fetched for a full pass. That is the distinction the flag is for.
  Filling in a county nobody has enriched is thousands of requests at a second each; topping up what
  has gone out of date is a handful, and a nightly schedule wants the second without ever
  accidentally starting the first.

  Why it is not a contradiction: the criterion's purpose (the pass can be limited) is satisfied, and
  its parenthetical (to stale *and missing*) describes the default. The code does more than the
  criterion asks rather than less, and the scenario's wording is the part that is wrong.

  Routed: a `/spec-flow:change` proposal against AC-8 and its scenario, to say that the default asks
  for stale and missing and that the flag narrows to stale. Recorded rather than applied: rewriting a
  criterion to match code that was already written is the move this ledger exists to prevent.

- opened gap-002 [partial] spec:"AC-11 Providers for flood zone, broadband service, principal
  aquifer, wildfire hazard, elevation, and boundary resolution exist and are individually enableable"

  Evidence: all six exist. Five are in `enrich/registry.py` and can be built by name; boundary
  resolution is in `enrich/boundaries.py` and is registered against the port saved searches declared,
  not into the provider registry. So the sixth cannot be named in a list of providers to run, and
  none of the five can be enabled or disabled from the command line: `api.enrich` takes a `providers`
  argument and the `enrich` command offers no way to pass one.

  Why it matters: "individually enableable" is what makes a broken service survivable by choice
  rather than only by accident. Today a provider that starts refusing can be worked around by moving
  its endpoint (AC-14) but not by switching it off.

  Why it is not a contradiction: every provider exists, each declares itself independently, and the
  one that needs a key is genuinely off by default and reports itself skipped. What is missing is a
  surface for choosing, not the ability underneath it.

  Routed: a `--provider` option on the `enrich` command, and a decision about whether boundary
  resolution belongs in the same registry as the value providers. Both are small; neither was in the
  plan, so neither was built. No remediation task opened here.

verdict: open 2 (missing 0, partial 2, contradicts 0, unrequested 0)

## What was checked and found clean

- **Every endpoint answers, at three points three thousand miles apart.** Flood, elevation, aquifer
  and wildfire, in New Mexico, Louisiana and Alaska, live, in a minute. The elevations differ from
  each other by thousands of feet, which is the check that a provider is answering about the place
  rather than answering the same thing everywhere.
- **A named place resolves to a shape, and the second ask makes no request.** Roosevelt County came
  back as a polygon and Portales as a point, and a cache-only reader found both without touching the
  network. That is what makes a boundary usable inside a filtering loop.
- **The cache is not append-only, on purpose, and the reasoning is written where the table is.** The
  constitution's first non-negotiable is about what a run observed of a listing; product invariant 1
  names snapshot and raw-listing history. A cached copy of a federal map is neither, and the rule
  that does apply, that a failure never removes a value, is enforced by failures never reaching the
  write.
- **The aquifer layer is national data served by a state.** No federal keyless copy answers today.
  Named as a mirror in the module and in the plan rather than passed off as a federal endpoint, and
  its address is configuration like every other.
- **Nothing in the offline suite touches the network.** The first version of the command-line tests
  did, and took two minutes doing it: the `enrich` command builds providers from the registry, so a
  test that ran it against the real registry made real requests to five government services. The
  registry is swapped for fakes in those tests now, and the whole offline suite is back under nine
  seconds.

## run 2 — 2026-08-24

baseline: spec sha256:b42cda270066 · plan sha256:c7a3759e149c · tasks sha256:9f8718d5d105

Run after the change `changes/broadband-from-the-fcc-files/` was built: broadband answered from the
FCC's own published files rather than from a request that never had an endpoint to go to.

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13,
AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21

- confirmed gap-001 [partial] `--stale` still narrows a pass without a way to name which values are
  stale per provider. Unchanged by this run.

- confirmed gap-002 [partial] the six providers still cannot be individually enabled from either
  surface. Unchanged in substance, and this run made it slightly more visible: broadband is now the
  provider most likely to be the one somebody wants to switch off, because it is the one with a
  dataset behind it, and there is still no `--provider` option to do it with.

- opened gap-003 [contradicts] spec:"AC-11 Providers for flood zone, broadband service, principal
  aquifer, wildfire hazard, elevation, and boundary resolution exist and are individually enableable"

  Opened and closed in this same run, deliberately. The ledger is the honest record of what the code
  was doing and for how long, and a defect that existed from the first build until now does not
  become something that never happened just because it was found and fixed on the same day. From the first build until this change, `enrich/providers.py` `Broadband.fetch`
  read the token, discarded it without putting it in any header, and asked
  `https://broadbandmap.fcc.gov/api/public/map/location`, which answers `405 Method Not Available`.
  Every request it ever made failed. Nobody saw it because nobody had a token, so the provider
  reported itself not configured and was skipped, and the one state that would have exposed it was
  the state nobody was in.

  It surfaced the moment somebody set a token and asked why the column was still empty.

- closed gap-003

  `enrich/broadband.py` plus the rewritten `Broadband` in `enrich/providers.py`, with the real shape
  measured against the live service and written into the plan as M-7 so the next reader does not
  have to re-derive it. `tests/test_enrich_broadband.py` covers the parts that could go wrong
  quietly, and `tests/test_enrich_live.py` now asserts the FCC still publishes the listing this
  reads, so a reorganization at their end shows up as a failed test rather than as a refresh that
  finds nothing. Verified end to end against the real service: 60,287 New Mexico census blocks
  indexed, and 82 of this store's 83 properties answered.

- opened gap-004 [unrequested] code:"`enrich/pass_.py` calls `attach(store)` on any provider that
  has it"

  Evidence: `src/homescout/enrich/pass_.py`, at the top of `run_pass`.

  The provider protocol is `configured()` and `fetch(session, lat, lon)`, and nothing in the spec
  describes a provider that holds anything. Broadband has to, because the answer is in a local
  dataset rather than in a response, and the store is where that dataset lives. The hook is how it
  gets one without changing the protocol for the other five, and it is deliberately duck-typed: a
  provider with no `attach` is untouched.

  Routed: a human decision, and the honest options are two. Legitimize it as a spec addition on this
  feature (a provider may declare that it needs the store, and the pass supplies it), or leave it as
  a documented quirk of one provider. It is recorded rather than assumed because "the pass never
  names a provider" is one of this feature's own design claims and this is the closest anything has
  come to bending it.

verdict: open 3 (missing 0, partial 2, contradicts 0, unrequested 1)

## run 3 — 2026-08-25

baseline: spec sha256:e2f4700bb0f2 · plan sha256:73df91d88e91 · tasks sha256:d41501b705ed

Run after the change `changes/wildland-urban-interface/` was built: the first provider here that
does not cover the whole country, and the coverage rule that had to be amended on main to allow it.

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13,
AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-23, AC-24, AC-25, AC-26

- confirmed gap-001 [partial] `--stale` still narrows a pass without a way to name which values are
  stale per provider. Unchanged by this run.

- confirmed gap-002 [partial] the providers still cannot be individually enabled from either
  surface. `api.enrich` takes a `providers` argument and `registry.create` honours it, so the
  library has always been able to; no surface offers it. `homescout enrich` has `--stale` and
  `--search` and nothing else (`src/homescout/cli/main.py`, the `enrich` parser).

  This run makes it bite harder rather than less. There are seven providers now, and the new one is
  the first that answers for only part of the country, so "run everything except the one that does
  not apply to me" is a thing somebody outside New Mexico would reasonably want and still cannot ask
  for.

- opened gap-005 [partial] spec:"AC-22 A wildland-urban interface provider exists, is individually
  enableable, and supplies a value naming which kind of interface a location stands in"

  Evidence: `src/homescout/cli/main.py`, the `enrich` parser, which has no `--provider` option.

  The same defect as gap-002 and a different anchor, so it is tracked separately rather than folded
  in: the criterion is new, and a reader who fixes gap-002 without noticing this one would close a
  gap and leave the identical claim unmet two criteria further down. Two thirds of AC-22 are met:
  the provider exists and supplies the value. The middle third is the shared one.

  Routed with gap-002: one `--provider` option on the enrich command, and its equivalent on the
  settings page, closes both.

- confirmed gap-004 [unrequested] `enrich/pass_.py` still calls `attach(store)` on any provider
  that has it. Unchanged by this run: the interface provider holds nothing and does not use the
  hook, so nothing here bent the protocol further. Still awaiting the human decision recorded in
  run 2.

note: two defects in the new code were found while reading it for this audit and fixed before the
audit's findings were taken, so neither is a gap. Both were in the surfaces rather than the
provider, and both were the same mistake in different places: the browser's listing page sent the
interface value through the shared renderer, which turns `null` into "not known, nobody determined
this", and the rule namespace declared no closed set of values for the field, so the browser's
criterion builder offered a free-text box and never showed that `outside coverage` is a value the
field can hold. The first would have said "nobody checked" about a place that was checked; the
second is how somebody writes a negation that quietly matches every property in every other state.
They are recorded here because they are exactly the failure this feature is built around and they
survived until the code was read against the spec, which is what this run is for.

verdict: open 4 (missing 0, partial 3, contradicts 0, unrequested 1)
