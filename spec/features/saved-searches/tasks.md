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
