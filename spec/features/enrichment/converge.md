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

## run 4 - 2026-10-03

baseline: spec sha256:623658f4944c · plan sha256:9407ceaaae32 · tasks sha256:d3fc054fed5e · code n/a (no `code_surface` declared, and this workspace's validator has no code fingerprint)

Run after `changes/where-fema-has-no-map/` and `changes/where-the-water-goes/` were built: FEMA read
properly, and soils, flash-flood history, streams and arroyos, and high-hazard dams. The first run
since 2026-08-25, so the data center change (AC-28 to AC-37) is read here for the first time too.

implemented: AC-1 to AC-7, AC-9, AC-10, AC-12, AC-15 to AC-21, AC-23 to AC-34, AC-37, AC-38, AC-40,
AC-42, AC-44, AC-45, AC-46, AC-49, AC-51, AC-52, AC-53

- confirmed gap-001 [partial] `--stale` still means aged values only (`enrich/pass_.py`,
  `_keys_to_ask`). Unchanged.

- confirmed gap-002 [partial] no surface can enable one provider: `homescout enrich` has no
  `--provider` (`cli/main.py`, the enrich parser) and `/api/enrich` passes no list (`web/app.py`).
  Twelve providers now, five of them added since this gap opened.

- confirmed gap-005 [partial] the same, anchored on AC-22. Unchanged.

- confirmed gap-004 [unrequested] the `attach(store)` hook, now used by four providers (broadband,
  data centers, flash floods, dams), with `ready()` and `why_not()` beside it. Still awaiting the
  human decision recorded in run 2.

- opened gap-006 [partial] spec:"AC-47 A refresh that fails leaves the held records in use and
  labelled stale"

  Evidence: `enrich/floods.py` and `enrich/dams.py` keep `stale` on the record and nothing reads it;
  `enrich/pass_.py` stores each point's answer through `cache_values`, which stamps it fresh, so a
  failed refresh yields values labelled fresh for another full lifetime. The data center provider
  (AC-30) has the same shape. Route: defect, T-cv4-1.

- opened gap-007 [partial] spec:"AC-5 the pass completes and reports per-provider outcomes"

  Evidence: a state whose warnings, reports or inventory fail is kept in `failures` on the record
  and never reported; the pass says ok unless every state fails. Route: T-cv4-11, left open.

- opened gap-008 [partial] spec:"AC-43 every surface that shows it says no water table recorded"

  Evidence: `cli/render.py` drops empty values, so `homescout show` omits a recorded-empty water
  table; the assessment dossier hands the model the bare text None. Route: defect, T-cv4-2.

- opened gap-009 [partial] spec:"AC-48 What these values are is said wherever they are read" and
  spec:"AC-54 The inventory is credited where its data is shown"

  Evidence: the listing page's water sentence leaves out that emergency areas are drawn over towns
  and that reports are placed to about a kilometre, and appears only for some values; a dam value
  shown alone carries no credit and no "near". Route: defect, T-cv4-3.

- opened gap-010 [partial] spec:"AC-36 Both sources are credited where their data is shown" and
  spec:"AC-35 a nearest known one"

  Evidence: the listing page shows data center values with no credit and no "nearest known".
  Predates this change. Route: T-cv4-12, left open.

- opened gap-011 [partial] spec:"AC-13 Outbound requests are paced per provider with backoff"

  Evidence: `enrich/kept.py` `fetch` bypasses the paced session D-5 names: a fixed one-second pause
  shared across hosts, no jitter, one twenty-second retry. Route: T-cv4-4.

- opened gap-012 [partial] spec:"AC-55 A test asserts the time for each of the two"

  Evidence: `tests/test_enrich_performance.py` times both records together through a stub that
  says every point is in New Mexico, so the real outline lookup is never timed. Route: T-cv4-5.

- opened gap-013 [partial] spec:"AC-50 whether it is perennial, intermittent or ephemeral"

  Evidence: `enrich/providers.py` `CHANNELS` and `_channel` also say `stream` and `river`, which
  the data cannot refine, and `stream_nearest` carries the distance. Route: T-cv4-6.

- opened gap-014 [partial] spec:"AC-14 Endpoint addresses are configuration"

  Evidence: `api.py` `_drawn_warning` builds the archive's warning page address from a constant.
  Route: T-cv4-7.

- opened gap-015 [partial] spec:"AC-41 each checked to be a number"

  Evidence: `enrich/providers.py` `Soils.fetch` calls `float()`, which passes NaN and infinity.
  Route: T-cv4-8.

- opened gap-016 [partial] spec:"AC-7 a missing value is never rendered as a negative answer"

  Evidence: in the sheet a stored-empty `flood_zone`, `dam_miles` or `dam_nearest` is blank, which
  the sheet's own note reads as "not run". Plan D-21 chose it. Route: T-cv4-13, left open.

- opened gap-017 [unrequested] code:"`enrich/providers.py` `SHADED_X` ranks FEMA's 1 PCT and
  non-accredited levee qualifiers with the 0.2 percent X"

  AC-39 names only the 0.2 percent X. FEMA's own renderer draws these in the same colour. Route:
  legitimise, T-cv4-9.

- opened gap-018 [unrequested] code:"`enrich/dams.py` keeps a dam's purpose and owner, `floods.py`
  keeps a warning's damage threat, and `dam_nearest` ends with the distance"

  None of AC-46 or AC-52 states them; the map's AC-99 and AC-100 use the first three. Route:
  legitimise, T-cv4-10.

note: before this audit ran, the live install's first pass showed the flash-flood and dam providers
reporting ok and storing nothing (the states query called the store's connection as a function and
a catch-all hid it). Fixed before the audit, with a test over a real store; recorded here because it
is the failure this ledger exists to catch and it got past every test that faked the store.

verdict: open 17 (missing 0, partial 14, contradicts 0, unrequested 3)

## run 5 - 2026-10-03

baseline: spec sha256:9a459a5b1e4c · plan sha256:543715372d75 · tasks sha256:c4974b6198c1 · code n/a (no `code_surface` declared, and this workspace's validator has no code fingerprint)

Run after the run 4 remediation, T-cv4-1 to T-cv4-10, and the spec amendments to AC-39, AC-43,
AC-46, AC-50, AC-52 and plan D-18.

implemented: AC-1 to AC-7, AC-9, AC-10, AC-12 to AC-21, AC-23 to AC-29, AC-31 to AC-34, AC-37 to
AC-55

- closed gap-006 `_fresh_or_fail` in `enrich/providers.py` makes a record whose refresh failed a
  failure for the pass, so cached values age into stale instead of being stamped fresh. Test:
  `test_a_record_that_could_not_be_refreshed_is_not_stored_as_fresh`.
- closed gap-008 one table of what a stored empty says (`rules/namespace.py` `EMPTY_MEANS`), read by
  `cli/render.py` and the assessment dossier and text. Tests: `test_the_terminal_says_what_a_
  recorded_empty_means`, `test_the_model_reads_a_recorded_empty_as_the_answer_it_is`.
- closed gap-009 the listing page's water sentence carries every caveat AC-48 names, and any dam
  value brings the inventory's credit and "near, not downstream". Test: `test_the_listing_page_and_
  the_core_say_the_same_thing_about_an_empty`.
- closed gap-011 the record fetch's pacing is written into D-18 as a decision, with jitter added.
- closed gap-012 flash floods and dams are timed separately, through real outlines.
- closed gap-013 AC-50 amended to the words the data supports and the distance in words.
- closed gap-014 the warning page address is the `flash_flood_page` setting.
- closed gap-015 a non-finite coordinate fails before the soil query is built.
- closed gap-017 AC-39 amended to name FEMA's other shaded-X qualifiers.
- closed gap-018 AC-46 and AC-52 amended to state the damage threat, purpose, owner and distance.

- confirmed gap-001 [partial] unchanged.
- confirmed gap-002 [partial] unchanged.
- confirmed gap-004 [unrequested] unchanged.
- confirmed gap-005 [partial] unchanged.
- confirmed gap-007 [partial] unchanged.
- confirmed gap-010 [partial] unchanged.
- confirmed gap-016 [partial] unchanged.

- opened gap-019 [partial] spec:"AC-30 A stale index is still used and still labelled stale"

  Evidence: `enrich/datacenters.py` `tracked` returns the stale index when a refresh fails, and the
  pass stores the answers worked out from it as fresh. The shape gap-006 fixed for flash floods and
  dams, in the provider that came before them. Not copied across, because AC-30 asks for a stale
  index to keep being used, so the fix is a decision about that feature. Route: T-cv5-1, left open.

verdict: open 8 (missing 0, partial 7, contradicts 0, unrequested 1)
