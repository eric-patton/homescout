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
