# Tasks — Location enrichment providers (feat-007)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## The shape a provider has

- [x] T1: `enrich/provider.py`: the plugin protocol, the failure it may raise, and the check that a
      provider's declared values are names the rule engine's namespace knows (D-4).
- [x] T2 [P]: `enrich/settings.py`: one entry per provider, each with a default address, a timeout,
      and an environment override (D-10, AC-14).
- [x] T3 [P]: `enrich/registry.py`: registered providers, in the shape the source registry already
      has, so the pass never names one (AC-1).

## The cache

- [x] T4: Schema version 3: `enrichment_values`, keyed by provider, rounded location and value name,
      and deliberately not append-only, with the reason in the schema (D-2). Record the change in
      feat-001's manifest.
- [x] T5: `enrich/cache.py`: read and write, the rounded key at a provider's own precision, and
      fresh against stale against missing (D-3, D-7, AC-2, AC-3, AC-7).
- [x] T6 [P]: `tests/test_enrich_cache.py`: the three states, the shared key, and that a failure
      leaves a cached value alone (AC-3, AC-4, AC-7).

## The providers

- [x] T7: `providers/flood.py`: FEMA's flood hazard zones, and the difference between a point in no
      mapped zone (a known answer) and a point nobody asked about (AC-7, the first edge case).
- [x] T8 [P]: `providers/elevation.py`: the National Map's point query, in feet.
- [x] T9 [P]: `providers/aquifer.py`: the USGS principal aquifers layer, with a note in the module
      about why it is fetched from a state-run mirror (M-3).
- [x] T10 [P]: `providers/wildfire.py`: the classified hazard raster, with its pixel values mapped to
      words a criterion can compare against.
- [x] T11: `providers/boundaries.py`: TIGERweb for shapes, the Census geocoder for what contains a
      point, registered against the port saved searches left open (D-8).
- [x] T12 [P]: `providers/broadband.py`: absent unless a token is configured, and honest about it
      (D-9).
- [x] T13 [P]: `tests/test_enrich_providers.py`: each provider against a recorded response, plus the
      configuration override and the not-configured case (AC-11, AC-14).

## The pass

- [x] T14: `enrich/pass_.py`: which locations, which providers, one lookup per distinct key, per
      provider outcomes, and a property with no coordinates skipped with its own reason (AC-1,
      AC-5, AC-10).
- [x] T15: `stale_only` and `search` (AC-8), and the pass reachable on its own (AC-9).
- [x] T16: `api.enrich` and the `enrich` command stop reporting themselves unbuilt and do the work,
      with `--json` and the usual exit codes. Record the change in feat-003's manifest.
- [x] T17: The rule engine's per-property values gain the enriched names, so a criterion naming
      `flood_zone` finds one (D-7). Record the change in feat-008's manifest.
- [x] T18 [P]: `tests/test_enrich_pass.py`: AC-1, AC-2, AC-5, AC-6, AC-8, AC-9, AC-10, AC-13.
- [x] T19 [P]: `tests/enrich_fakes.py`: a transport that counts requests, a provider that fails, and
      a store with properties at known points.

## Finishing

- [x] T20 [P]: `tests/test_enrich_live.py`: one lookup per provider at three geographically distant
      points, marked slow (AC-12).
- [x] T21 [P]: the fully cached pass over 5,000 properties, marked slow (performance NFR).
- [x] T22: Document enrichment in the README: what each provider answers, what a token is needed
      for, and what stale means.
- [x] T23: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T24: `/spec-flow:converge`, then the manifest stamp.

## Change: broadband from the FCC's own files (`changes/broadband-from-the-fcc-files/`)

- [x] T25: `enrich/broadband.py`: the FCC file API with its two credential headers, the most recent
      published quarter, one state's fixed-broadband files, and the aggregation to one row per
      census block keeping the best advertised residential speeds and the providers that offer them
      (D-12, D-13, AC-16, AC-19, AC-20).
- [x] T26: Schema version 7: `broadband_blocks`, a cache like `enrichment_values` and not history,
      so no append-only trigger and re-indexing a state replaces that state's rows (D-12, AC-16).
      Record the change in feat-001's manifest.
- [x] T27: `enrich/providers.py` `Broadband`: configured on both credentials and an index that has
      something in it; `fetch` resolves the point to its census block through the FCC's keyless
      block service, paced like everything else, and reads the block locally. A state with no index
      is its own outcome naming the state and the command (D-12, AC-17, AC-18, AC-21).
- [x] T28: `api.broadband` and a `homescout broadband` command: show what is loaded, `--state XX`
      to load or refresh one (AC-16). Record the change in feat-003's manifest.
- [x] T29: The settings page's broadband panel gains the account-name variable, what is loaded, and
      a button to load a state (AC-16, AC-21). Record the change in feat-012's manifest.
- [x] T30 [P]: `tests/test_enrich_broadband.py`: the aggregation over a fixture file including
      satellite rows that must not reach the speed, the block lookup, an unloaded state as its own
      outcome, half a credential as not configured, and the two headers on the request (AC-16
      through AC-21).
- [x] T31: `tests/test_enrich_live.py` gains the real thing behind the slow marker, skipped without
      credentials (AC-12).
- [x] T32: README: what broadband now needs, what it answers, and that the figure is the block's
      advertised service rather than the property's measured service.
- [x] T33: `uv run ruff check .` and the full suite green, then `/spec-flow:converge` and the
      manifest stamp.
