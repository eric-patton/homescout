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

## Change: the wildland-urban interface, for New Mexico (`changes/wildland-urban-interface/`)

- [x] T34: `rules/namespace.py`: a `wildland_urban_interface` enriched text field, with its closed
      set of values so the browser's criterion builder offers them rather than a free-text box, and
      a gloss saying the coverage. `outside coverage` is one of the offered values on purpose: it is
      not a kind of interface, and hiding it is how somebody writes a negation that matches every
      property in every other state (AC-22, AC-24). First, because
      `enrich/registry.py` checks declared values against the namespace in both directions at import
      and the registration below cannot load without it (AC-22).
- [x] T35: `enrich/settings.py`: a `wui` endpoint entry for the UNM Earth Data Analysis Center
      interface layer that serves `nmwrap.org`, and a `wui_coverage` entry for the same server's
      county layer that settles the ambiguous case. Both overridable like every other address
      (D-14, AC-14).
- [x] T36: `enrich/providers.py` `WildlandUrbanInterface`, registered as `name = "wui"` so the
      registry key, the settings key from T35 and the `HOMESCOUT_ENRICH_WUI_URL` override are one
      string. A point-in-polygon query through the same `point_query` and `features_of` helpers the
      flood provider uses. Reads the source's own classification attribute and maps it to `intermix`
      or `interface`; a code this build does not know is a `ProviderFailed` naming the code, never a
      guess (D-14, AC-22, AC-25). Coverage is declared on the provider: outside the declared box the
      answer is `outside coverage` with no request at all, and inside it with no polygon the county
      layer settles whether this is a known negative or a point the source does not cover (D-14,
      AC-23, AC-24, AC-26). Precision four, matching
      flood: the interface boundary can run down a street. No time to live: the classification is a
      2010 census-block product and does not change, which is the same answer elevation gives.
- [x] T37: `enrich/registry.py`: register it in the shipped tuple, ordered with the other cheap
      permanent lookups (AC-22).
- [x] T38: Both surfaces render the three readings distinctly, never one as another (AC-24).
      `export/columns.py` and the export templates get a Wildland-Urban Interface column outside the
      default set, as Wildfire Hazard already is. The browser's listing page needs its own renderer
      rather than the shared one: the known negative here is `null`, and the shared renderer turns
      `null` into "not known, nobody determined this", which is the one sentence this field must
      never say. Record the change in feat-011's and feat-010's manifests.
- [x] T39 [P]: `tests/test_enrich_providers.py`: the two classifications off a fixture response, an
      empty feature list as a known negative, an unknown code as a failure naming it, and a point
      outside the coverage answering without any request at all (AC-22, AC-23, AC-25).
- [x] T40 [P]: `tests/test_enrich_cache.py`: the three readings side by side, asserting not
      applicable, known negative, and missing are distinguishable and that none renders as another
      (AC-24).
- [x] T41: `tests/test_enrich_live.py`: the real layer behind the slow marker, one lookup inside New
      Mexico and one outside it (AC-12, AC-26).
- [x] T42: README: what the interface value answers, that it covers New Mexico only, and what
      `outside coverage` means in a cell. Add the new host to the list of what this tool talks to; it
      is a state university server rather than a federal one, which is a first here.
- [x] T43: Coverage is visible where providers are listed: `api.enrich`'s per-provider outcome and
      the `homescout enrich` rendering carry a declaring provider's coverage, so a column that
      answers for one state says so without opening the module (AC-26). Providers that cover the
      country declare nothing and read exactly as they do now.
- [x] T44: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T45: `/spec-flow:converge`, then the manifest stamp.
- [x] T46: A defect found in use, not by inspection: a state named in full resolved to no boundary
      at all. The Census speaks FIPS and the lookup only translated from the postal abbreviation, so
      `New Mexico` produced `STATE='New Mexico'` and matched nothing, while `NM` worked. Everything
      else in this product already treats the two spellings as one state.

      What made it expensive is how quietly it failed. The one source that takes a state by name
      kept working, so results looked normal; the two that need a bounding box could only report
      that they had no way to express the area; and because a lookup that finds nothing is cached
      deliberately, the empty answer outlived the bug. A statewide search ran at a third of its
      coverage for two runs, and a run missing two of three sources can never conclude a house is
      gone, so the freshness this product exists for was silently off as well.

      Fixed in `enrich/boundaries.py` with `BY_NAME`, read from the table in `enrich/states.py` that
      already holds all three federal spellings rather than typed out again. Pinned by
      `tests/test_enrich_providers.py::test_a_state_resolves_written_out_as_well_as_abbreviated`
      citing `feat-007/AC-11`, which asserts the query rather than the answer, because a wrong
      translation here returns no rows rather than wrong ones.
