# Tasks — Saved searches and geography (feat-004)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## Groundwork

- [x] T1: Add `shapely>=2.0` and `ruamel.yaml>=0.18` to `pyproject.toml` and lock them (D-2).
- [x] T2: Turn `src/homescout/search.py` into `src/homescout/search/__init__.py` with no behavior
      change, and confirm the existing suite is still green (D-1).

## The seam the run loop enters through

- [x] T3: Replace `queries()` with `areas` and `queries_for(capabilities)` on the definition
      protocol and on `InMemorySearch` (D-5). Update `runner.run_search` to ask each source for its
      own queries, `cli/main.py:190` and `cli/render.py:120` to count `areas`, and
      `tests/cli_fakes.py` plus `tests/test_cli_live.py` to match.
- [x] T4: A source left with no expressible area records `unavailable` naming the areas, rather than
      failing the run (D-5). Test in `tests/test_searches_run.py`.
- [x] T5: Replace `keeps()` with `place() -> Placement` (D-6). The run loop keeps `inside` and
      `unlocatable`, drops `outside`, and counts the third into `SourceReport.not_locatable`, which
      the digest's per-source block carries through.
- [x] T5a: `SearchProblem` gains a severity, and only a `problem` makes a definition invalid
      (D-20). `api.run_search`, `api.validate_search` and the `validate` command change from "any
      problem" to "any of severity problem"; the command's human and machine output both show
      notices.
- [x] T6: Record T3, T5 and T5a in feat-003's manifest under "Later changes by other features",
      naming the criterion each one serves here.

## The source layer's new area (feat-002)

- [x] T7: Add `PointRadius(latitude, longitude, miles)` to `sources/base.py` and to the `Area`
      union (D-8).
- [x] T8: Accept it in the Realtor adapter: `_resolve` returns a `Place` directly for a
      `PointRadius` with no geocoding request, and `_build` reads its miles the way it reads an
      `AddressRadius`'s (D-8). Offline test in `tests/test_sources_realtor.py`.
- [x] T9: Record T7 and T8 in feat-002's manifest under "Later changes by other features".

## Geometry

- [x] T10 [P]: `search/geometry.py`: GeoJSON (geometry or Feature) to shapely, validity and
      self-intersection, prepared containment, bounding box, and the covering circle (centroid plus
      the farthest vertex plus a margin) (D-7, D-15).
- [x] T11 [P]: `search/boundaries.py`: the provider port, its registry, and the no-op default
      (D-10).
- [x] T12: `search/areas.py`: every area type from the file, each answering its coarse form for a
      given capability declaration and its three-valued containment test (D-7, D-9). Depends on
      T10 and T11.

## The file

- [x] T13 [P]: `search/document.py`: round-trip load and save, one-key edit, and a location string
      built from each node's line and column (D-14, D-13).
- [x] T14 [P]: `search/validate.py`: every rule in D-13, collected in one pass, nothing fetched.
- [x] T15: `search/definition.py`: `FileSearch` (areas, filters to a query, freshness, the exact
      test) and `FileCatalog` (list, load, create from the commented template, edit). Depends on
      T12, T13, T14.
- [x] T15a: A search name is constrained to a safe file name and the resolved path is checked to be
      inside the searches directory, for reading and for creating (D-19).
- [x] T16: `default_catalog` returns the file catalog when nothing is registered, and a missing
      `searches/` directory means no saved searches rather than an error (D-16).
- [x] T16a: The wholly excluded search and the area no configured source can express are reported
      as notices (D-20).

## Tests

- [x] T17 [P]: `tests/searches_fakes.py`: the definition-file builder, the counting boundary
      provider, and a source that raises if it is contacted.
- [x] T18 [P]: `tests/test_searches_document.py`: AC-1, AC-8, AC-12.
- [x] T19 [P]: `tests/test_searches_validation.py`: AC-9, AC-10, the ambiguity rule (D-17), the
      notices (D-20), and the security NFR: a constructor tag is a problem rather than an effect,
      and a traversing name is refused for reading and for creating (D-19).
- [x] T20 [P]: `tests/test_searches_geometry.py`: AC-2, AC-3, AC-4, and the overlapping-areas and
      exclusion edge cases.
- [x] T21 [P]: `tests/test_searches_run.py`: AC-5, AC-6, AC-7, AC-11, AC-13, and the wholly excluded
      search.
- [x] T22 [P]: `tests/test_searches_performance.py`: the two-second budget over 5,000 properties,
      marked slow.

## Finishing

- [x] T23: Document the definition file in the README: where searches live, the shape, and the two
      additions to the brief's form.
- [x] T24: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T25: A live run of a real definition file end to end, against Realtor, proving the file, the
      geometry and the loop work together outside the fakes.
- [x] T26: `/spec-flow:converge`, then the manifest stamp.

## Change: why an area is in or out (`feat-004/AC-14`)

- [x] T-reason-1: `search/areas.py`, `api.py`, `web/static/search.js`, `app.css`: a reason on every
      area, shown and edited beside its name (`feat-004/AC-14`).

      "Let's add a reasoning for things that are left out that we can see and edit."

      Asked for after a real question nobody could answer from a screen. Somebody looking at
      realtor.com saw houses in Carlsbad and asked why none were on the map. They are excluded on
      purpose, by a polygon named `permian-oil-and-gas`, for flaring, truck traffic, potash and the
      waste repository. The editor could already show that: it draws every exclusion on its map with
      its name. What no surface could show was the *why*, because the why was a YAML comment and
      nothing reads a comment.

      That distinction decided the question rather than decorating it. The reason ends "the airshed
      is regional, so there is no part of this that a smaller shape would rescue", which is exactly
      the argument against carving Carlsbad out, and it was the one line the app could not show.

      Text, optional, on areas as well as exclusions. Absent and whitespace are one state, so a
      cleared box reads as unwritten rather than as an answer somebody gave. Not text is refused,
      like a name that is not text: a definition that says what is wrong with it beats one that
      runs with a reason nobody can read.

- [x] T-reason-2: `tests/test_searches_document.py`: kept through a load, on every kind of area and
      both lists; blank and whitespace both read as unwritten; a reason that is not text is a
      problem in the file (`feat-004/AC-14`).

- [x] T-reason-3: the seven exclusions in the real workspace moved out of comments and into fields,
      by hand rather than through the interface. The interface's own "save the areas" replaces both
      lists wholesale, and the document layer round-trips a file but cannot keep comments attached
      to a list node it is handed a new copy of: saving that search drops twelve comment lines and
      re-wraps every coordinate. Pre-existing, worth knowing, and the strongest argument for this
      change: a reason kept as a comment is a reason one click away from being lost, where a reason
      kept as a field survives the same click.

- [x] T-reason-4: `web/static/search.js`, `app.css`: the reason opens in a window rather than
      living in the cell (`feat-004/AC-14`, `feat-010/AC-25`).

      "Might be better to have a button you can click to see and edit this in a popup. It is so
      small", with a picture, and the picture was the argument: a textarea in that cell came out
      about ninety pixels across and showed two words of a sentence. The row already spends its
      width on a kind, a place, a name and two controls, and a share of forty per cent asked of a
      table that is auto-laid-out is a suggestion rather than a width.

      The cell now carries a button showing the reason itself, clamped to two lines, and pressing
      it opens a window with room to read and write the whole thing. The value rather than the word
      "Edit", because a column of identical buttons tells somebody scanning the table nothing and
      being readable at a glance was the whole point of putting it here.

      It borrows `dialog.ask` rather than growing its own frame, adding only the width it needs. A
      second set of dialog styling is two dialogs that drift apart.

      Nothing here writes: the answer goes back on the row and the panel is marked unsaved, exactly
      as the name box behaves, and "Save the areas" is still the only thing that writes. Cancel and
      keep are separate, because a dialog that treats a change of mind as agreement loses work.

      Two things the first attempt got wrong and this one asserts. A minimum width on the cell
      pushed the table past its panel and put the Remove button off the edge where nobody could
      reach it, so it is a share now with a scroll behind it: the reason is the least urgent thing
      in the row and must not cost somebody a control. And an unwritten reason says so rather than
      showing an empty box, because a blank control reads as broken.

- [x] T-reason-5: `tests/test_web_browser.py`: the button, the window, and both ways out
      (`feat-004/AC-14`). Asserts the room actually grew, by measuring the window against the cell
      it replaced rather than trusting a stylesheet; that cancelling keeps what was there; that
      keeping updates the button and marks the panel unsaved without writing anything.

- [x] T-reason-6: `web/static/search.js`, `app.css`: a bin instead of the word "Remove"
      (`feat-004/AC-14`, `feat-010/AC-3`). "Instead of the word Remove, can you have an icon of a
      trash bin to free up more horizontal space?"

      It was the least informative sixty pixels in a row that had already run past its panel: every
      row said the same word and nobody reads it twice. Drawn with `createElementNS` rather than
      from markup, which is the rule everything this product draws follows, and in `currentColor`
      so it turns red with the button rather than carrying a second copy of the palette.

      What did not go with the word is what the control announces. The name stays on the button for
      anything reading the page aloud, `title` puts it under a pointer, and the column heading is
      still the word, kept in the document and clipped out of the layout so the column can actually
      narrow. A button whose only label is a drawing is a button somebody has to guess at, and the
      guess is expensive here because pressing it takes an area out of the search.

## Defect: adding or removing a named place undid itself

- [x] T-named-1: `web/static/search.js`: the table's named places are a draft that is kept
      (`feat-004/AC-2`).

      Found by the test for the bin above, which pressed it and watched the row come back.

      The list of towns, counties and postal codes was rebuilt from the fetched search on every
      redraw, and both controls that change it redraw immediately, so both undid themselves. Adding
      a town pushed it onto the list, redrew, and the redraw read the fetched search again and
      dropped it: the page then said "Added Portales. Save the areas to write it into the file"
      about a row that was already gone. Removing one was the same in reverse, and looked like a
      flicker.

      The drawn shapes never had this, because the layer group they live in *is* the state and a
      redraw reads it rather than replacing it. The named places now stand on the same footing:
      seeded once from what the server said, kept across redraws, and reset at the two moments the
      draft is genuinely stale, which are a fresh fetch and a successful save.

- [x] T-named-2: `tests/test_web_browser.py`: a town added stays added and a town removed stays
      removed (`feat-004/AC-2`). Checked against the rebuilding version, which fails both.

- [x] T-named-3: `web/static/search.js`: the bin asks first (`feat-004/AC-2`, `feat-010/AC-3`).
      "Removing should have a confirmation modal."

      The word was a wide target that said what it did. The picture is a small one that does not,
      and one click on it took a row out with nothing in between, so the question belongs here now
      rather than before the icon.

      What it asks about is proportionate to what is behind it, because those are not the same. A
      town is a name somebody retypes in ten seconds. A drawn shape is a boundary somebody traced
      on a map and there is no retyping that, so the dialog says which of the two this is. The
      reason is shown when one is written, because it is the part somebody would actually be sorry
      to lose and the decision should be made looking at it rather than at a name.

      It is careful not to overstate itself. Nothing is written until "Save the areas", so this is a
      change to a draft rather than a deletion, and the dialog says so: frightening somebody about
      the wrong thing is its own kind of lie. "Keep it" takes the focus, so a stray Enter keeps the
      area, and the backdrop, Escape and every other way out mean no, which is the rule the results
      table's confirmation already follows.

- [x] T-named-4: `tests/test_web_browser.py`: asked, and a change of mind is honoured
      (`feat-004/AC-2`). The two tests that pressed the bin now answer the question, and the bin
      test asserts both halves: that it is asked at all, and that "Keep it" leaves the area alone,
      which is the worst way for a confirmation to be wrong. Checked against a bin that does not
      ask, which fails it.

## Change: named addresses (`changes/named-addresses/`, `feat-004/AC-15` to `AC-22`)

"I feel like we should just build functionality for the ability to add any number of specific
addresses to any search, if the various tools will allow for that." Asked after eight Louisiana
houses were run by hand as a throwaway search. The person chose: a named house skips the search's
filters and exclusions, and the criteria still judge it.

- [x] T-address-0: Prerequisite, in feat-006's defect lane rather than here: a numbered highway with
      no state in front of it (`51131 Highway 445`, `33063 Hwy 43 Hwy`) gets an address key. It had
      none: `_street_name` stripped the type word, was left with only digits, and returned no name,
      so the same house from three sites stayed three records and was never queued. Fixed as
      feat-006's T-highway-1 and T-highway-2 (`hwy 445` for all three spellings).
- [x] T-address-1: `search/addresses.py` (new), `search/definition.py`, `search/validate.py`: the
      `addresses` key, `NamedAddress(text, reason, at)`, `definition.addresses`, and the shape checks
      of AC-17 (including the 200-character limit and the notice above 50), located and fetching
      nothing (D-21). Validation's "needs at least one area" and the run loop's "names no area" both
      allow a search with addresses and no areas. The scope fingerprint behind revision-aware
      comparisons takes the addresses in only when there are some, so adding a house starts a new
      baseline and no existing search's baseline moves. The `searches create` template shows the key,
      commented out.
- [x] T-address-2: `search/boundaries.py`, `enrich/boundaries.py`, `enrich/settings.py`, `api.py`:
      `PlacedAddress` and the port's optional `place_address` and `prepare_addresses`; the Census
      one-line endpoint (`address`) behind them, a year for a match and thirty days for no match,
      keyed by the address with case, spacing and commas folded. `prepare_addresses` fetches through
      a fetching twin over the same store and session, so the provider a run reads stays cache-only;
      `api.run_search` calls it inside the run claim, skipping addresses that carry `at` (D-22). A
      provider without the method places nothing, and those addresses are reported as not looked
      for. Recorded in feat-007's manifest.
- [x] T-address-3: `search/addresses.py`, `search/definition.py`, `runner.py`: `AddressPlan`,
      `address_plan()` and `address_queries_for` (half a mile, overlapping circles grouped and asked
      for as one circle containing every member's own, three statuses for a source that pushes a
      status and one query for a source that does not). The per-source step is reshaped so a source
      is unavailable only with neither area nor address queries and the area half keeps its
      application exactly as before. Rows are kept for an address by D-24's three parts, exempt
      from filters and exclusions, and a named house the area half already kept is one observation.
      `fresh_enough(named=True)` is always fresh (AC-20).
- [x] T-address-4: `runner.py`, `digest.py`, `web/runs.py`, `cli/render.py`: `AddressReport` on the
      outcome (placed, the matched line, found by, missed by), always present in `run --json` and the
      run status, one line per address on the command line, and "found N of M named addresses" in
      each source's recorded detail (D-25).
- [x] T-address-5: `tests/test_searches_addresses.py`, nineteen tests over every row of the
      verification table except AC-22: text and entry forms, round trip and the command line's edit,
      every shape problem located with nothing asked, the notice above fifty, looked up once over
      the real Census provider and a counting transport, the cache lifetimes, the status fan-out and
      shared circles, an addresses-only search, a house under contract, neighbours discarded, the
      three real spellings of one highway house from two sources, units on one side, a missing and a
      wrong ZIP, the lookup's ZIP, exempt from filters, an exclusion and freshness while a drop rule
      still fires, the three report answers, both command-line forms, and a refused status.
      Checked against three broken versions of the run loop (keep every row, compare units always,
      filter named rows), each of which turns the matching tests red.
- [x] T-address-6: `web/api.py` document, `web/static/search.js`, `web/static/searches.js`: a "Named
      houses" panel beside the areas, with its own save, the reason window, the bin that asks first,
      and a box that takes one address or many pasted one per line, a repeated one named once; the
      panel says before anything is added that each address goes to the Census once and the sites
      only see a circle (D-26). "Save the areas" no longer refuses a search whose only content is
      named houses. The run status page says how many named houses were found and lists each one.
      `tests/test_web_browser.py`: add, paste with a repeat, a reason, the bin with "Keep it" then
      "Remove it", and the saved file (`feat-004/AC-22`). It found a real fault on its first run:
      redrawing the panel replaced the section, which dropped its "changed, not saved" mark and the
      page's edit listeners with it; the panel now rebuilds only its contents. Recorded in feat-010's
      manifest.
- [x] T-address-7: README, "Specific houses" under saved searches: `addresses`, `at`, that a named
      house skips filters and exclusions but not criteria, where an address goes (the Census once,
      the sites only a circle), and that "not found" is an ordinary answer.
- [x] T-address-8: `uv run ruff check .` and the full suite green (1,459 default, 63 slow browser
      tests). Then, with the person's OK, the live `la-one-offs` search rewritten from eight
      circles to the eight addresses as they were pasted, the server restarted onto this code, and
      the search run twice on 2026-09-30.

      First run: every address placed by the Census, all eight found by all three sources, and each
      source kept exactly eight listings, where the by-hand circles had kept twenty-six. The three
      highway houses merged into one record each, which the highway fix made possible. Realtor
      reported failed only because it refuses `pending` and `contingent` (the known source defect);
      its for-sale queries found all eight. The scope change started a new comparison series, so no
      old neighbour was read as gone. Second run: eight of eight found, nine records unchanged,
      nothing new or gone.

      Nine records rather than eight: Redfin pins 51131 Highway 445 316 metres from where the other
      two do, past the address matcher's 50-metre tolerance, so that pair is ambiguous and goes to a
      person, which is the address matcher working as specified. It reached the review queue only
      after the second run: a record merged during a run has no snapshot of its own until the next
      one, so the queue has nothing to compare it with. Reported to the person as an address-merge
      behaviour, not changed here.

      Found by the code-against-spec audit before the run block was written, and fixed in this
      change: a search naming only houses, none of which could be placed, reported every source as
      having "no way to express any of this search's areas ()". It now says that no named address
      could be placed (`runner._cannot_cover`, pinned by
      `test_a_search_of_only_houses_none_of_them_placed_says_so`).
- [x] T-address-9: the delta folded into `spec.md` (AC-15 to AC-22 added; AC-1, AC-3 and the
      definition's vocabulary modified; the named-address vocabulary, story, four scenarios, six
      edge cases and two non-functional lines added), then `/spec-flow:converge` run 2 over the
      folded spec. Folded first rather than after, because an audit against the unfolded spec would
      have read the whole change as unrequested behaviour. One sentence was added to AC-15 before
      folding: named addresses are part of the observation scope of feat-001's AC-32, which the code
      already did and that criterion's list did not say; recorded in feat-001's manifest and pinned
      by `test_naming_a_house_changes_the_scope_and_naming_none_changes_nothing`.

## Closing the drift ledger's open gaps (2026-09-30)

The person asked for every recommendation to be carried out, so the gaps the 2026-09-30 audit left
open were worked rather than reported.

- [x] T-gap-001: `api._resolve_boundaries`, `enrich/boundaries.resolve`: the enrichment pass looks
      up the centre of every radius around a named place, and caches it where the search's
      cache-only provider reads it, so such a circle is tested here like any other area
      (`feat-004/AC-5`, gap-001). The validation notice now says the circle is the source's to apply
      until that lookup has run, rather than that nothing can do it.
      `tests/test_enrich_providers.py`: the centre looked up once and read back cache-only, and
      the pass asking for a named centre and not for a centre given as coordinates; both checked
      against the unfixed code, where they fail.
- [x] T-gap-002: `tests/test_web_parity.py`: one definition with a drawn shape, a filter and a named
      house, run from the command line into one fresh database and from the browser's run button
      into another, recording the same properties from the same questions (`feat-004/AC-7`,
      gap-002).
- [x] T-state-1: `changes/state-areas/`: a state is one of AC-2's area forms, folded into `spec.md`;
      the existing state test cites AC-2 (`feat-004/AC-2`, gap-004). No code changed.

## Address radius

- [x] T-radius-1: Add address centers and preserve radius metadata; validate finite values and
      test local distance and coarse query coverage (`feat-004/AC-23`, AC-2, AC-4, AC-5, AC-14).
- [x] T-radius-2: Prepare unplaced radius addresses once before a run; keep other areas working
      when lookup fails, with no address sent to sources (`feat-004/AC-23`, AC-6).
- [x] T-radius-3: Add the shared preview operation and terminal entry point, verifying cache
      reuse, input refusal and no definition writes (`feat-004/AC-24`).

Radius validation: the default pytest suite, focused address/radius tests, real-browser
preview/save/reopen and stale-response tests, Python lint, and JavaScript syntax checks.
