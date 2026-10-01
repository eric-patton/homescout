<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — saved searches and geography

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-23

baseline: spec sha256:57fa249b0b1b · plan sha256:25347cb2cfeb · tasks sha256:451e34a85fcf

implemented: AC-1, AC-2, AC-3, AC-4, AC-6, AC-9, AC-10, AC-11, AC-12, AC-13

- opened gap-001 [partial] spec:"AC-5 Exact filtering removes every returned property whose location
  falls outside the search's geometry, regardless of which source returned it or what that source
  filtered"

  Evidence: `src/homescout/search/areas.py`, `_inside_circle` answers `inside` for every property
  when the area is a radius around a place name and no boundary provider is registered. Every other
  area kind is exact.

  Why it matters: a search whose areas include a circle around a named town cannot have that circle
  applied here, because nothing in the product can yet turn a name into a point. The source applies
  it, so the properties that came back did come from inside it, but a property returned by a
  *different* area's coarse query is not removed on this area's account. The criterion says "every
  returned property", and this is one case where it is the source's word rather than a local test.

  Why it is not a contradiction: AC-13 delegates place resolution to enrichment (feat-007) by
  design, so this is a consequence the spec itself creates rather than the code disagreeing with it.
  Answering `unknown` instead was the plan's original wording, and it was worse: a search whose only
  area is a radius around a town would have reported every property in it as not locatable, drowning
  the count that exists to make a genuinely unplaceable property visible.

  Routed: closed by feat-007 (location enrichment) registering a provider, which the code path
  already reads. Until then the condition is reported to the user as a notice on the definition
  (`test_a_radius_around_a_name_says_it_is_the_sources_to_apply`), so nobody has to read this ledger
  to find out. No remediation task here.

- opened gap-002 [partial] spec:"AC-7 The command line and the browser interface pass identical
  geometry into the same resolution and filtering code. A test asserts identical results from both
  entry points for one definition."

  Evidence: `tests/test_searches_run.py`,
  `test_the_command_line_and_the_core_place_the_same_properties` drives the command line and the
  facade in `api.py` that the browser will call. There is no browser interface: feat-010 is
  specified and unbuilt.

  Why it matters: half of the criterion is a claim about a surface that does not exist. What is
  proved today is that the command line makes no geometry decisions of its own, which is the part
  that could have gone wrong while building this feature. What is not proved is the part that can
  only go wrong while building feat-010.

  Routed: feat-010 (browser interface), whose own tests re-assert this criterion with a real second
  surface. Recorded here so a reader of this feature does not mistake a passing test for the whole
  criterion. The pre-build check raised the same point as S2, so this is the same finding, now
  anchored to code.

- opened gap-003 [partial] spec:"AC-8 A definition loaded and re-saved without modification is
  unchanged, including geometry precision and any parts the interface does not itself edit"

  Evidence: `src/homescout/search/document.py`. Comments, key order, quoting, number formatting
  including trailing zeros, and top-level list style all survive exactly
  (`test_a_definition_loaded_and_written_back_is_the_same_file`,
  `test_a_shape_is_not_re_approximated_by_a_save`). One thing does not: layout *inside* a list. A
  flow list hand-wrapped across several lines comes back on one, and a compact nested sequence
  (`- - [x, y]`) is written with the inner dash on its own line. No value changes.

  Why it matters: the criterion says "unchanged", and for those two hand-written layouts the bytes
  are not. In practice nothing rewrites an unmodified file (the only writer is an edit, which by
  definition modifies), and what this tool writes is already in the form it writes, so a file it has
  saved once is a fixed point. But someone hand-wrapping a long coordinate list will see it joined
  the first time they change a price.

  Why it is not a contradiction: the round-trip library is what makes the rest of the criterion true
  at all, and no YAML library in Python preserves intra-collection line breaks. The alternative was
  a parser that discards comments and key order, which fails the criterion far worse.

  Routed: documented in `document.py` and pinned by
  `test_a_hand_wrapped_list_keeps_its_values_though_not_its_line_breaks`, so the day it changes,
  somebody finds out from a test. No remediation task; reopen if a round-trip library that keeps
  intra-collection layout appears.

- opened gap-004 [unrequested] code:"a state is an area type a definition may use"

  Evidence: `src/homescout/search/areas.py`, `KINDS` includes `state`, and `coarse_for` resolves it
  to the source layer's `State` area. `spec.md` AC-2 enumerates the forms an area may take: polygon,
  city, county, ZIP code, and radius. A state is not among them, and neither is it in the brief's
  schema.

  Why it is here: the source layer already accepts a state as an area (feat-002), and the state
  lookup this feature needs anyway for the qualifier in "Portales, NM" makes supporting one nearly
  free. It is exercised by `test_a_state_written_either_way_is_the_same_state`.

  Why it matters either way: a state-wide search is a real thing to want and a plausible way to hit
  a source's result ceiling hard. Leaving it undocumented means the first person to try it finds an
  undocumented feature; removing it costs a capability the layer underneath already has.

  Routed: a human decision. Either legitimize it with a `## ADDED` delta to AC-2 through
  `/spec-flow:change`, or remove the kind and its test. Recorded rather than decided, because
  widening a spec to match code that was already written is exactly the move this ledger exists to
  prevent anyone making silently.

verdict: open 4 (missing 0, partial 3, contradicts 0, unrequested 1)

## Noted during implementation, fixed before this ledger opened

Not gaps, but worth recording, because each is the kind of defect that survives every test written
before it:

- **A provider registered after a definition was loaded was never seen.** The first question asked
  of a boundary provider cached its own answer, including the answer "there is no provider". An area
  loaded before enrichment registers one would have stayed unresolvable for the life of the
  definition. Now the absence of a provider is not remembered, and only a real answer is.
- **Two runs of one search in one invocation looked a place up twice**, because each `load` built a
  fresh definition with a fresh memo. The catalog now holds a loaded definition for as long as the
  file's modification time and size are unchanged, which is what makes AC-13 true in the sense it is
  written.

## Found by the first live run, against another feature

- **The radius search had never worked against the real site.** It carried the same sort bucket the
  area search uses, and Realtor.com answers a radius query carrying one with a server error and no
  rows, which is indistinguishable from a market with nothing for sale in it.

  This feature turns a drawn shape into a circle, and a circle is a radius query, so the first live
  run of a drawn shape found it immediately. No offline test could: the radius path is exercised
  against a fake transport, which returns what it is told regardless of what the document says.

  A defect in the source adapters (feat-002), recorded in that feature's manifest with its fix. The
  radius query now sorts explicitly by listing date, newest first, which the site accepts and which
  paging by offset needs anyway. Pinned offline by an assertion on the document shape, and covered
  live by `test_a_drawn_shape_in_a_file_runs_against_the_real_site`.

## run 2 - 2026-09-30

baseline: spec sha256:d958c90ed32b · plan sha256:618846e997f4 · tasks sha256:bcd8f4bd2603 · code n/a
(this feature declares no code surface, and this repository's linter predates code fingerprints)

Scope: the named-addresses change (`changes/named-addresses/`), folded into `spec.md` before this
run, plus every gap left open by run 1. Audit performed inline in the main session at the operator's
standing instruction that other agents are brought in only on request.

implemented: AC-1, AC-3, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22

Evidence for the new criteria, each with tests citing its token in `tests/test_searches_addresses.py`
(twenty-one) and `tests/test_web_browser.py` (AC-22):

- AC-15: `search/addresses.py` `read` and `_entry`; `search/validate.py` `_addresses` and
  `NOTHING_TO_SEARCH`; `search/definition.py` `FileSearch.addresses`; the scope digest takes the list
  only when there is one (`_observation_revision`), pinned against a literal the earlier code
  computed. `searches edit --set addresses=[...]` reaches it through `catalog.edit`.
- AC-16: `enrich/boundaries.py` `place_address` (cache, a year for a match, thirty days for none,
  `_expired`) and `prepare_addresses` (a fetching twin, so the run's provider stays cache-only);
  `api._place_named_addresses` inside the run claim, skipping `at`. Proved over the real provider and
  a counting transport: one request across two runs.
- AC-17: `search/addresses.py` `_text` (empty, over 200), `_at` (pair, numbers, range), unknown
  keys, the repeat notice and the notice above 50; nothing contacted (a placer that records every
  question records none).
- AC-18: `AddressPlan.queries_for` (no filter ever set, three statuses or one by
  `capabilities.applies`); `_circles` groups overlapping circles into one that contains each
  member's own; `runner.run_search` asks a source unless it has neither area nor address queries.
- AC-19: `runner._at_address` (number and street, ZIP when both have one, unit when both carry
  one) and `_wanted` (the person's ZIP, else the lookup's, else none); `_ask_for_addresses` drops
  every other row unrecorded.
- AC-20: named rows bypass `passes` and `definition.place`; `record_verdicts` still runs over the
  run; `fresh_enough(named=True)`.
- AC-21: `runner.AddressReport` on `RunOutcome`; `digest.py` (`run --json`), `web/runs.py` (run
  status), `cli/render._named_addresses`; "found N of M named addresses" in each source's recorded
  detail.
- AC-22: `web/static/search.js` `addressPanel`, `saveAddresses`, `addressWhy`, the house branch of
  `confirmRemoval`; `web/static/searches.js` `namedReport`; `api.search_document` carries the list.

Live: two runs of the real `la-one-offs` search on 2026-09-30 (tasks T-address-8). Eight of eight
found by all three sources, eight listings kept per source, no neighbours.

Constitution and product-global, checked against the new code: every new request goes through a
paced session (the Census lookup under its own `address` key at the provider floor); no guess about
which house was meant (a row with no usable address is never kept for one); an `at` places the query
and is never written onto a listing; both surfaces render one core report and decide nothing; the
only new outbound traffic is to a free, public, national endpoint. No violation found.

Unrequested sweep over the change's surface: nothing found. The run-status summary line and list,
the commented example in the `searches create` template, and "Save the areas" accepting a search of
only named houses are each the stated behaviour of AC-22, AC-15 or both.

- confirmed gap-001 [partial] spec:"AC-5 Exact filtering removes every returned property whose
  location falls outside the search's geometry"

  Unchanged in substance. The provider is registered now, but the enrichment pass resolves only the
  shapes of cities, counties, ZIP codes and states (`api._resolve_boundaries`), never the point a
  radius around a place name needs, so `_inside_circle` still answers `inside` for such an area
  unless something else cached that point. Still the source's word rather than a local test, and
  still reported to the person as a notice on the definition.

- confirmed gap-002 [partial] spec:"AC-7 The command line and the browser interface pass identical
  geometry into the same resolution and filtering code. A test asserts identical results from both
  entry points for one definition."

  Evidence moved, class did not. The browser interface exists, and its runs go through
  `api.run_search` exactly as the command line's do (`web/runs.py`), which is the structural half
  of the criterion and now covers named addresses too. No test drives one definition through both
  entry points and compares the results, which is the half the criterion names.

- confirmed gap-003 [partial] spec:"AC-8 A definition loaded and re-saved without modification is
  unchanged"

  `search/document.py` unchanged since run 1; intra-list layout still is not kept.

- confirmed gap-004 [unrequested] code:"a state is an area type a definition may use"

  Still in `KINDS` and still not in AC-2. Worth knowing for the human decision this was routed to:
  the person's own main search, `nm-statewide`, is a single `type: state` area, so removing the kind
  would break the search they run every night. Legitimizing it through `/spec-flow:change` is the
  likely answer, but it remains theirs to give.

verdict: open 4 (missing 0, partial 3, contradicts 0, unrequested 1)

Found during this audit and fixed before this block was written (so not a gap): a search naming only
houses, none of which could be placed, reported each source as having "no way to express any of this
search's areas ()". `runner._cannot_cover` now says no named address could be placed; pinned by
`test_a_search_of_only_houses_none_of_them_placed_says_so`.

## run 3 - 2026-09-30

baseline: spec sha256:1e7eaf51f292 · plan sha256:618846e997f4 · tasks sha256:70dff275a581 · code n/a
(no declared code surface; this repository's linter predates code fingerprints)

Scope: the gaps run 2 left open, after the person asked for every recommendation to be carried out.
Inline, as before.

implemented: AC-2, AC-5, AC-7

- closed gap-001 spec:"AC-5 Exact filtering removes every returned property whose location falls
  outside the search's geometry"

  The enrichment pass now looks up the centre of every radius around a named place
  (`api._resolve_boundaries` asks for `("locate", place)`, `enrich/boundaries.resolve` fetches it),
  and the search's cache-only provider reads it, so `_inside_circle` measures rather than deferring
  once the pass has run. Until it has, the validation notice says so. Citation: T-gap-001;
  `test_the_centre_of_a_radius_around_a_named_place_is_looked_up_and_kept` and
  `test_the_enrichment_pass_asks_for_the_centre_of_every_radius_around_a_name`, both of which fail
  against the code as it stood.

- closed gap-002 spec:"AC-7 ... A test asserts identical results from both entry points for one
  definition."

  `test_one_definition_gives_the_same_results_from_both_surfaces` runs one definition (a drawn
  shape, a filter and a named house) from the command line and from the browser's run button into
  two fresh databases and asserts the same recorded properties and the same source queries.
  Citation: T-gap-002.

- closed gap-004 code:"a state is an area type a definition may use"

  Legitimized rather than removed, through `changes/state-areas/`: AC-2 lists a state, written by
  name or by code. The person's nightly search is a single state area, which is what decided it.
  Citation: T-state-1; `test_a_state_written_either_way_is_the_same_state` cites AC-2.

- confirmed gap-003 [partial] spec:"AC-8 A definition loaded and re-saved without modification is
  unchanged"

  Unchanged since run 1, and routed then: the round-trip library keeps comments, key order and
  values but not line breaks inside a list, and no Python YAML library does. Reopen the remedy if
  one appears.

verdict: open 1 (missing 0, partial 1, contradicts 0, unrequested 0)
