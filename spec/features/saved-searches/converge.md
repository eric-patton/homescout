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
