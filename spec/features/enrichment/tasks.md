# Tasks — Location enrichment providers (feat-007)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## The shape a provider has

- [ ] T1: `enrich/provider.py`: the plugin protocol, the failure it may raise, and the check that a
      provider's declared values are names the rule engine's namespace knows (D-4).
- [ ] T2 [P]: `enrich/settings.py`: one entry per provider, each with a default address, a timeout,
      and an environment override (D-10, AC-14).
- [ ] T3 [P]: `enrich/registry.py`: registered providers, in the shape the source registry already
      has, so the pass never names one (AC-1).

## The cache

- [ ] T4: Schema version 3: `enrichment_values`, keyed by provider, rounded location and value name,
      and deliberately not append-only, with the reason in the schema (D-2). Record the change in
      feat-001's manifest.
- [ ] T5: `enrich/cache.py`: read and write, the rounded key at a provider's own precision, and
      fresh against stale against missing (D-3, D-7, AC-2, AC-3, AC-7).
- [ ] T6 [P]: `tests/test_enrich_cache.py`: the three states, the shared key, and that a failure
      leaves a cached value alone (AC-3, AC-4, AC-7).

## The providers

- [ ] T7: `providers/flood.py`: FEMA's flood hazard zones, and the difference between a point in no
      mapped zone (a known answer) and a point nobody asked about (AC-7, the first edge case).
- [ ] T8 [P]: `providers/elevation.py`: the National Map's point query, in feet.
- [ ] T9 [P]: `providers/aquifer.py`: the USGS principal aquifers layer, with a note in the module
      about why it is fetched from a state-run mirror (M-3).
- [ ] T10 [P]: `providers/wildfire.py`: the classified hazard raster, with its pixel values mapped to
      words a criterion can compare against.
- [ ] T11: `providers/boundaries.py`: TIGERweb for shapes, the Census geocoder for what contains a
      point, registered against the port saved searches left open (D-8).
- [ ] T12 [P]: `providers/broadband.py`: absent unless a token is configured, and honest about it
      (D-9).
- [ ] T13 [P]: `tests/test_enrich_providers.py`: each provider against a recorded response, plus the
      configuration override and the not-configured case (AC-11, AC-14).

## The pass

- [ ] T14: `enrich/pass_.py`: which locations, which providers, one lookup per distinct key, per
      provider outcomes, and a property with no coordinates skipped with its own reason (AC-1,
      AC-5, AC-10).
- [ ] T15: `stale_only` and `search` (AC-8), and the pass reachable on its own (AC-9).
- [ ] T16: `api.enrich` and the `enrich` command stop reporting themselves unbuilt and do the work,
      with `--json` and the usual exit codes. Record the change in feat-003's manifest.
- [ ] T17: The rule engine's per-property values gain the enriched names, so a criterion naming
      `flood_zone` finds one (D-7). Record the change in feat-008's manifest.
- [ ] T18 [P]: `tests/test_enrich_pass.py`: AC-1, AC-2, AC-5, AC-6, AC-8, AC-9, AC-10, AC-13.
- [ ] T19 [P]: `tests/enrich_fakes.py`: a transport that counts requests, a provider that fails, and
      a store with properties at known points.

## Finishing

- [ ] T20 [P]: `tests/test_enrich_live.py`: one lookup per provider at three geographically distant
      points, marked slow (AC-12).
- [ ] T21 [P]: the fully cached pass over 5,000 properties, marked slow (performance NFR).
- [ ] T22: Document enrichment in the README: what each provider answers, what a token is needed
      for, and what stale means.
- [ ] T23: `uv run ruff check .` and the full suite, default and slow, green.
- [ ] T24: `/spec-flow:converge`, then the manifest stamp.
