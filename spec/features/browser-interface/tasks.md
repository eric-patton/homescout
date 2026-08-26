# Tasks — Browser interface (feat-010)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## What the core is missing

- [x] T1: `api.results`, `api.listing`, `api.preview_image`, `api.area_notes`, `api.set_area_note`
      and `api.run_status`: the five capabilities no surface has needed yet (D-3). Record the change
      in feat-003's manifest.
- [x] T2: `homescout show <listing-id>` and `homescout areas`, the terminal halves of the two new
      capabilities, so product invariant 5 still holds (D-3). Record the change in feat-003's
      manifest.
- [x] T3 [P]: `tests/test_api_additions.py`: each new operation, including a property that does not
      exist, a run with no completed baseline, and an area note round-tripping.

## The server

- [x] T4: `web/app.py`: the fourteen endpoints, each of them a call to `api` and a serialization
      (D-2), with the product's own envelope as the wire format.
- [x] T5: `web/serve.py`: bound to `127.0.0.1` by default, with the address and port as parameters,
      and `api.serve` stopping reporting itself unbuilt.
- [x] T6: `web/wire.py`: `api` answers turned into the documents the pages read, reusing
      `digest.envelope` and the export's column declaration (D-2, D-4).
- [x] T7: The run started in a thread with a status endpoint, and two runs colliding answered by the
      core's own claim rather than by a lock here (D-7, AC-13).
- [x] T8 [P]: `tests/test_web_contract.py`: the bind address against a routable one (AC-15), the
      served bytes against the committed files (AC-16), and the source scan asserting nothing here
      imports the store, the runner, the rule engine or the export (AC-14).
- [x] T9 [P]: `tests/test_web_endpoints.py`: every action performed through HTTP and again through
      `api`, with the resulting database compared table by table (AC-14).

## The surfaces

- [x] T10: `static/common.js`: the one way to build an element, which puts text in by
      `textContent` and has no path to markup at all (D-5); the fetch helper; the missing-value
      rendering (AC-10); and the focus and skip-link behaviour (D-9).
- [x] T11: `static/searches.html` and `.js`: the list, last run, run now with progress, open,
      duplicate (AC-1, AC-13).
- [x] T12: `static/results.html` and `.js`: the windowed table, sorting, filtering, badges, the
      default order from boost and demote, and the disappeared filter that says how many it hides
      (D-4, AC-7, AC-8, AC-20).
- [x] T13: Inline annotation editing: saving, saved, not saved with the typed value kept, and the
      row taking its values from what the store returned (D-5, AC-4, AC-5, AC-6).
- [x] T14: `static/listing.html` and `.js`: photographs, description, enrichment, extraction with
      its evidence, the price and status timeline, and the source rows with the signal that joined
      them (AC-9).
- [x] T15: `static/changes.html` and `.js`: a comparison against any earlier run, matching what the
      terminal produces (AC-11).
- [x] T16: `static/matches.html` and `.js`: the pairs, their agreeing and conflicting signals, and a
      decision that is durable; and the empty queue saying so plainly (AC-12).
- [x] T17: `static/search.html` and `.js`: the builder's non-drawing half (city, county, ZIP,
      radius, filters, criteria), saving through `api.edit_search` so the file round-trips (AC-3).
- [x] T18: The map: drawing areas and exclusions, a self-intersecting polygon refused as it is drawn,
      and the surface working without the library present and saying what is missing (D-6, AC-2).
- [x] T19: `web/vendor/`: Leaflet 1.9.4 and Leaflet.draw 1.0.4 committed with both licences, plus
      `manifest.json` recording each file's version, source and SHA-256 (D-6).
- [x] T20 [P]: `tests/test_web_vendor.py`: every committed file verified against the manifest byte
      for byte, and the manifest itself checked for naming a source and a version for each.
- [x] T20b: The tile background as configuration, off by default, with the map drawing over a plain
      background and one line saying what a tile source costs (D-12).

## Safety and access

- [x] T21 [P]: `tests/test_web_safety.py`: a description containing markup served to the table and
      the detail surface and checked for not having become an element; a listing URL with a refused
      scheme; and the source scan for `innerHTML` (D-5).
- [x] T21b: The browser guard: the `Host` check, the `Origin` check and the custom header on
      mutating requests, each refusal naming which check refused it (D-11).
- [x] T21c [P]: `tests/test_web_guard.py`: a rebinding host, a foreign origin, and a mutating
      request with no header, each refused (D-11).
- [x] T22 [P]: `tests/test_web_accessible.py`: every interactive element a real control or an
      explicit role, and every badge, status and difference event carrying a text label (AC-17,
      AC-18).

## In a real browser

- [x] T23: `tests/test_web_browser.py`, marked slow: the table at 5,000 rows against the
      three-second and two-hundred-millisecond budgets, an inline edit driven by keyboard alone with
      the annotation read back from the store, and a failing save keeping the typed value.
- [x] T23b [P]: An annotation survives a later run that also changes the property's price, which is
      the test AC-5 asks for by name.
- [x] T23c [P]: An area note written here is the note the spreadsheet export's second sheet carries
      (AC-19).

## Finishing

- [x] T24: `fastapi` and `uvicorn` added as dependencies, and the fourteen-package cost noted where
      somebody will read it.
- [x] T25: Document the interface in the README: what the six surfaces are, that it is localhost
      only, and what the map needs.
- [x] T26: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T27: `/spec-flow:converge`, then the manifest stamp.

## Added while building

- [x] T28: `store.db.connect(shared=...)` and `Store.open(shared=...)`: SQLite refuses a connection
      used from a thread other than the one that opened it, and a web server hands requests to
      worker threads. Lifting the check is safe only where access is serialized, so the interface
      holds a lock around every request and is the one caller that passes it. Record the change in
      feat-001's manifest.
- [x] T29: Two defects found by reading a real property's page and its terminal counterpart: the
      same source row was listed once per run it was seen in, which is what a bad merge looks like;
      and an enriched boolean printed as `False` in the terminal instead of `no`.
- [x] T30: Writing a drawn shape back into the file, through the core's edit operation, with the
      comments and the untouched filters surviving and a refused edit leaving the file alone
      (AC-2, AC-3).
- [x] T31: Two note boxes: the installation's on the settings page, and a search's own on its page,
      each saying above the box that its text goes to the model with every description (feat-009's
      change `model-notes`).
- [x] T32: A defect: a textarea built by the shared element builder with `value=` drew empty,
      because a textarea holds its text as content rather than in an attribute. The criteria box on
      a search page was built that way, so a search with three rules showed none, and the "Save the
      criteria" button under it would have written the empty box back over them. Fixed in the
      builder rather than at the call site, with a regression test in the real-browser suite
      (feat-010/AC-24).
- [x] T33: The criteria box gained two folded references beside it: what each of the four severities
      does to what you see, and every field a condition may name with its type and, where the set is
      closed, its values. A list of field names was half an answer: `cooling == "swamp cooler"`
      names a real field and compares it to a word that can never be true, and nothing on the page
      said so (feat-010/AC-24).
- [x] T34: The place-notes panel says what it is for and stopped being a box you can silently miss
      with. It offers the towns and counties this store actually has properties in, because a note
      only reaches a property's row when it matches that property's own town as the source spells
      it, and "Portales, NM" typed into a blank box matched nothing. It also shows the note already
      written for the selected place, rather than starting empty every time.

## Change: criteria built rather than typed (`changes/built-not-typed/`)

- [x] T35: `rules/phrase.py`: an expression as rows and back. `readable` flattens a chain of
      comparisons; `compose` writes rows as the text a saved search stores. The check is a round
      trip rather than a guess, because rows that quietly mean something else would be saved over
      what somebody wrote (feat-008/AC-24, AC-28).
- [x] T36: `rules/namespace.py`: a human name for every field and for the values whose stored word
      is not the word a person says. Declared in the core, because both surfaces need them and a
      second copy would drift (AC-30). Record the change in feat-008's manifest.
- [x] T37: `api.py`: a rule arriving with `parts` has its expression composed; a rule going out
      carries its rows, or `null` when it is not rows (AC-28, AC-31).
- [x] T38: The criteria surface becomes a builder: a card per criterion, a row per condition,
      dropdowns that follow the field, add and remove for both, and eight one-click suggestions
      (AC-28, AC-29, AC-32).
- [x] T39: The plain-language pass: a property's page uses the core's labels rather than the field
      names, and the three page introductions say what the page is for rather than what the file
      format is (AC-30).
- [x] T40: A defect found while building it: the filter boxes saved on every blur, so tabbing
      through a page wrote an empty `sqft:` into a file nobody had edited. A field is now written
      only when it changed, and clearing one removes the key rather than writing an empty one.
- [x] T41 [P]: `tests/test_rules_phrase.py`: every shape people write round-trips unchanged, every
      shape that is not rows is refused rather than approximated, and every comparison the builder
      offers composes into something the engine accepts.
- [x] T42 [P]: `tests/test_web_parity.py`: rows saved through the browser land as the expression
      somebody would have typed, an unfinished condition is refused with the criterion named, and
      one that is not rows comes back as text.
- [x] T43: `uv run ruff check .` and the full suite green, then `/spec-flow:converge` and the
      manifest stamp.
- [x] T44: `store/migrations.py` and `store/schema.py`: the `annotations` table gains `judgment` at
      schema version 8, nullable, holding `keep` or `pass` and nothing else. Migration only, no
      backfill: every annotation that existed before this is undecided, and leaving it empty says so.
- [x] T45: `store/models.py`: `judgment` joins `ANNOTATION_FIELDS` and the closed set lives beside
      it as `JUDGMENTS`, so it is carried by `content()` and inherits the survival guarantees the
      listing store already tests (AC-33).
- [x] T46: `store/core.py`: a value that is not `keep`, `pass` or empty is refused, naming what is
      accepted. `judgment_of` takes the union across everything merged into a listing, reading the
      constituents' annotations rather than moving them, so `supersede` needed no change at all.
- [x] T47: `api.py`: the core decides what is hidden and says so. `results` gained `include_passed`
      mirroring `include_dropped`, every row carries its `judgment` and a `hidden_by_default` the
      core computed, and the payload carries the count. `passed()` is the read the command line
      needs, since it has no results table to hang a toggle on.
- [x] T48: `web/static/results.js`: a `pass` / `passed` button in the row that both sets and clears
      the judgment (AC-34); a "show properties you passed on" checkbox beside the existing one for
      disappeared; rows honour the core's `hidden_by_default` rather than testing the judgment
      themselves (AC-35); the count line reports the number hidden beside the disappeared one
      (AC-36). Every row is still sent once, so the toggle costs no request.
- [x] T49: `cli/main.py`: `annotate --judgment keep|pass|none`, where `none` is how a person says
      undecided where there is no way to type an absence, and a `passed` command that lists what has
      been passed on with the verdict beside it (AC-39).
- [x] T50: `tests/test_store_history.py`, beside the annotation survival tests it belongs with
      rather than a new file: a judgment survives three later runs and a disappearance
      (`feat-010/AC-33`), a merge keeps it through `supersede`, and an unrecognised value is refused.
- [x] T51: `tests/test_web_endpoints.py`: a passed property is marked hidden by the core and not by
      the page, the count comes from the core, every row is still sent either way
      (`feat-010/AC-35`, `feat-010/AC-36`), and the same control clears it (`feat-010/AC-34`).
- [x] T52: `tests/test_rules_namespace.py`: a criterion naming `judgment` is refused as a field that
      does not exist, so the separation between the tool's tests and the person's conclusions is
      pinned (`feat-010/AC-38`).
- [x] T53: `tests/test_web_endpoints.py`: both surfaces answer the same question the same way
      (`feat-010/AC-39`), which is the assertion that catches the predicate drifting back into a
      surface. `tests/test_web_parity.py` gained the route entry, which is what failed first and
      made the point unprompted.
- [x] T54: `tests/test_store_history.py`: a price cut does not un-pass a house, and the change is
      still compared and still reported (`feat-010/AC-37`) — hiding changed the view and nothing else.
- [x] T55: `uv run ruff check .` clean and 1,193 tests green, then `/spec-flow:converge` and the
      manifest stamp.

## Found in use

- [x] **T56: every link to a record that had been merged into another returned a 500.** Found while
      the owner was working through the merge review queue, which is precisely the person who
      follows those links.

      The listing page assembles a property from its own history, which a merged constituent still
      has, and then asked for its extracted fields through `extracted_for`, which consulted
      `latest_snapshots` and raised "no such listing" for anything not currently representing a
      property. The two disagreed about what "this listing exists" means, and the disagreement took
      the page down rather than degrading it.

      That is the wrong record to lose. Product invariant 2 keeps a merged listing traceable to the
      rows it was built from and its provenance visible, which is the whole basis for inspecting a
      merge and undoing it. 1,195 of the owner's listings were superseded at the time, so this was
      not an edge case; it was most of the links on the page he was working from.

      Fixed in `api.py`: a caller holding a snapshot passes it, so the page uses the one it already
      found instead of asking a set that was never going to contain it. That also stops a full scan
      of every latest snapshot running once per page view. Pinned by
      `tests/test_web_endpoints.py::test_a_record_merged_into_another_still_has_a_page`, citing
      `feat-010/AC-9`, verified red before green.
- [x] T57: `api.review_queue`: every queued pair with each record's photograph flag, address, price,
      size and sources, assembled in the core so both surfaces read one answer (AC-41). A record
      whose latest snapshot cannot be found is summarised as far as it can be rather than dropped:
      a pair missing half its evidence is still a pair somebody has to rule on.
- [x] T58: `web/static/matches.js` and `app.css`: both records on the card, photograph first, with
      a same-shaped placeholder where none is stored (AC-40). `web/wire.py` becomes a pass-through.
- [x] T59: `cli/main.py` and `cli/render.py`: `matches list` prints the same addresses, prices and
      sources instead of a table of identifiers (AC-41).
- [x] T60: `tests/test_cli_operations.py`: a queued pair carries both properties rather than two
      identifiers, and whether each has a photograph matches what the store actually holds
      (`feat-010/AC-40`); and both surfaces review the same queue from one core answer
      (`feat-010/AC-41`). Asserted through the terminal on purpose: if the summary were built in the
      page, a browser-only test would pass while the two surfaces drifted apart.
