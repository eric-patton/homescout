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

## Change: arrange the table (`changes/arrange-the-table/`)

- [x] T61: `web/static/results.js`: the `Listing URL` cell draws one named link per site the property
      was found on, from the row's `links`, falling back to the single address where that is all
      there is (`feat-010/AC-42`). `web/static/listing.js`: the provenance table's source name is
      that source's own page.
- [x] T62: `api.results` carries the per-site addresses and whether a stored photograph exists, the
      second from one query for the whole table rather than one request per row (`feat-010/AC-42`,
      `feat-010/AC-43`). `store.listings_with_preview_images` is that query.
- [x] T63: `web/static/results.js`: a "show photos" toggle draws the stored thumbnail beside each
      address, off by default, with an empty box of the same size where there is no picture
      (`feat-010/AC-43`). Nothing is fetched from a listing site to draw it.
- [x] T64: `web/static/results.js`: headings drag to reorder and their right edge drags to resize,
      with Alt and the arrows doing the first and Alt-Shift the second, so neither is mouse-only
      (`feat-010/AC-44`, `feat-010/AC-17`). Widths live on a `colgroup`, so a resize is one style
      change rather than one per visible cell.
- [x] T65: `web/static/results.js`: the arrangement is kept per browser and per search, every read
      and write guarded, with a "reset columns" control (`feat-010/AC-45`). Columns nothing fills
      are arranged last and marked in words as well as in style (`feat-010/AC-46`).
- [x] T66: `tests/test_web_surfaces.py`: a merged record offers both sites' addresses
      (`feat-010/AC-42`); a row says whether a picture exists and the table draws the stored one
      (`feat-010/AC-43`); the unfilled columns are arranged last and marked (`feat-010/AC-46`).
      `tests/test_web_browser.py`: the keyboard moves and sizes a column (`feat-010/AC-44`), and the
      table opens with storage throwing on every access (`feat-010/AC-45`).

### Defects fixed alongside it

- [x] T67: **The rows were drifting out from under their own scrollbar.** The virtual window placed
      rows every 22 pixels; the stylesheet asked for 26; and because `height` on a table cell is
      only a floor, the floated corner marker on the editable cells took the rendered row to 43. So
      each drawn row sat seventeen pixels below where the scrollbar said it was, compounding down
      the table until the last rows were past the end of the scroll range and could not be reached.

      Three causes, three fixes: the marker is positioned rather than floated; the cells' line height
      is set from the same custom property as their height, so the row is exact rather than a
      minimum; and the row height is published by the script and read by the stylesheet, so there is
      one of it. Pinned by `tests/test_web_browser.py` citing `feat-010/AC-20`, which measures a
      drawn row against the number the placement uses rather than against 26, so it still means
      something after somebody changes the height deliberately.

- [x] T68: **A handler this page built could silently never run.** The shared element builder treated
      six named `on...` attributes as listeners and passed everything else to `setAttribute`, which
      turns a function into a string: an attribute holding `() => edit(...)` is an inline handler
      whose whole body defines an arrow function and discards it. Accepted, present in the DOM, and
      doing nothing. Double-clicking a cell to edit it had been built that way.

      Fixed in `common.js` for any `on...` whose value is a function, rather than by adding a seventh
      name to the list, because the eighth would have inherited it. Pinned by
      `tests/test_web_browser.py` citing `feat-010/AC-17`, asserting on the builder rather than on
      one cell.

- [x] T69: **The pass control had no styles at all.** It shipped with the judgment change and drew as
      a default browser button in a 26-pixel row, which is part of why the person reading the table
      asked for a feature that already existed. Styled small and quiet, reading `pass` or `passed`
      so the state is legible without colour (`feat-010/AC-18`), and sized so it cannot make the row
      taller than the row.

## Change: keep and pass where you can see them (`changes/keep-and-pass-where-you-can-see-them/`)

- [x] T70: `web/static/results.js` and `app.css`: a "wrap long text" toggle, clamped to three lines,
      with the clamp on a box inside the cell rather than on the cell (`feat-010/AC-47`). A table
      cell cannot clip its own height, so without the inner box a wrapped description takes its row
      with it and the rows stop being the same height as each other.
- [x] T71: `web/static/results.js`: keeping and passing move into a control column that is first,
      fixed width, unmovable and undisplaceable (`feat-010/AC-49`). Enter keeps and Delete passes
      from the keyboard, so the destructive one is not under the key used to move on.
- [x] T72: `web/static/results.js`: passing asks first, in a `dialog` shown with `showModal` rather
      than a `confirm()`, which would stop every pending save on the page behind it
      (`feat-010/AC-48`). Keeping asks nothing.
- [x] T73: `api.py`, `cli/main.py`, `cli/render.py`, `web/app.py`: `kept` beside `passed`, both from
      one core function, reachable as `homescout kept` and `/api/kept` (`feat-010/AC-49`, product
      invariant 5). `web/static/results.js`: an "only what you kept" filter and a kept count.
- [x] T74: `tests/test_web_browser.py`: the columns stay put while the table is scrolled
      (`feat-010/AC-44`); a wrapped row is the height the placement uses (`feat-010/AC-47`); the
      question is asked and the keyboard's dismissal of it leaves the property alone, and answering
      it passes the house (`feat-010/AC-48`); keeping takes one press and no question
      (`feat-010/AC-49`); the controls are first and cannot be displaced (`feat-010/AC-49`).
      `tests/test_web_surfaces.py`: both halves of the judgment read from the core, and keeping
      hides nothing.

### Defect fixed alongside it

- [x] T75: **The columns changed width as the table was scrolled**, which was this feature's own
      regression from the arrangement work. `table-layout: fixed` derives its columns from the first
      row it can find whenever the table's own width is `auto`, and the first row in this table is
      whichever row the scroll position last put in the DOM. Fixed by telling the table its width,
      the sum of the declared columns, so the `colgroup` is the only thing the layout comes from.
      Pinned by `tests/test_web_browser.py` citing `feat-010/AC-44`, which measures the same row's
      cells at three scroll positions.
- [x] T76: `web/app.py` and `web/static/results.js`: the sheet downloads from the results page, as a
      plain link so the browser's own download does the work, in either format (`feat-010/AC-50`).
      Declared after `/api/export/templates`, which would otherwise be read as a saved search of
      that name. `tests/test_web_endpoints.py` covers the download, the refused format, and that the
      two overlapping paths still tell each other apart.
- [x] T77: `web/static/results.js`: a column the person writes in themselves is blank when empty
      rather than reading "not known". Everywhere else in this product an empty cell means nobody
      could determine the value; in an annotation column nobody was ever going to, and printing it a
      thousand times down the Rank column said the tool had failed at something it was not doing.
- [x] T78: `web/static/common.js`: a gallery both pages share, opened from the results table's
      thumbnail and from the property page's stored photograph, with the arrows and Escape working
      and only the picture on screen and its two neighbours requested (`feat-010/AC-51`). It says in
      the dialog that the pictures come from the listing site, because everywhere else on these
      pages looking at a property costs that site nothing and here it does not. The addresses are
      fetched for the one property being opened rather than carried on every row.
      `tests/test_web_browser.py` moves through a gallery and asserts the empty case says so.
- [x] T79: `web/static/common.js`: a photograph's address is upgraded to `https` when this page is
      itself served over `https` (`feat-010/AC-51`). Every address the sites hand over is stored as
      `http`, and a browser refuses an `http` image on an `https` page before the request is made,
      so over Tailscale the gallery would have been a row of broken frames. The hosts all answer on
      `https`; the upgrade is conditional so nothing that would have loaded stops loading.
- [x] T80: `web/static/common.js`: the gallery asks for the full-size rendition (`feat-010/AC-51`).
      What the sites hand over is a thumbnail address and a small one: Realtor's ends in `s` and
      answers at 120 by 80 pixels, which is a picture you cannot see a roof line in; the same
      address ending in `o` is the original at 1024 by 683. Zillow's `-p_e` is 596 wide against 1536
      uncropped. Written as a table of rules per host, checked against eight real stored addresses
      that all answered, with a fallback to the stored address on any load failure and no rewriting
      at all for a host with no rule, signed map tiles among them.

## Change: choose your columns (`changes/choose-your-columns/`)

- [x] T81: `web/static/results.js`: the table keeps the full declared order and a set of hidden
      names, and draws the difference (`feat-010/AC-52`). Right-click offers to hide a column or open
      the chooser; Delete on a focused heading hides it; the chooser lists every column and brings
      any of them back where it was. Hiding is remembered with the order and the widths. The control
      column is not offered.
- [x] T82: `web/static/results.js`: the table's height is measured from where its box actually falls
      rather than assumed, and the page behind it is stopped from scrolling (`feat-010/AC-53`). The
      horizontal scrollbar lives on that bottom edge, and the edge was below the bottom of the
      window, so a table seven thousand pixels wide had no visible way to scroll sideways.
- [x] T83: `store/models.py`, `store/schema.py`, `store/migrations.py`: five annotation fields for
      the household's own headings, and `SCHEMA_V9` to hold them. `store/core.py`: the annotation
      reader and writer are built from the field list rather than naming each field one at a time.
- [x] T84: `api.py` gains `annotation_fields`, and both surfaces read their field lists from it
      (`feat-010/AC-46`, product invariant 5): the terminal's flags and the interface's allowed
      request keys were two hand-written copies of one list.
- [x] T85: `export/columns.py`: the five point at the new fields and the `unfilled` origin is
      retired, having no members left. `web/static/results.js`: they join the editable set, and a
      heading says which kind of column it is.
- [x] T86: `tests/test_web_browser.py`: a column hides and comes back where it was
      (`feat-010/AC-52`); the controls cannot be hidden (`feat-010/AC-49`); the table ends inside the
      window with a scrollbar and the page does not scroll (`feat-010/AC-53`); and one of the five
      headings takes a value that reaches the store (`feat-011/AC-5`).

### Defects fixed alongside it

- [x] T87: **The same property was shown twice, and the merged record not at all.** A run records
      its verdicts and snapshots against the records it observed and *then* merges what turned out
      to be the same house, so between a merge and the next run the run's results name the halves.
      Each half carried only the sites it happened to be seen on, which is why a property whose
      Zillow record this tool holds, and has merged, offered only a Realtor link. Measured on the
      statewide run: 1,083 rows for 964 properties, 266 of them halves, and the 147 merged records
      absent. Fixed in `export/rows.py` where the rows are assembled, so the sheet and the table
      cannot differ, with `store.live_listing_id` exposed for it. Pinned by
      `tests/test_export_values.py` citing `feat-011/AC-2`, which is the criterion that says one row
      per canonical listing.
- [x] T88: **A merged record had no photograph.** The picture is stored against whichever record was
      observed when it was fetched and merging never moves anything, so a merged property showed as
      having none while both its halves had one. `store.get_preview_image` falls back to a
      constituent's, on the read side only.
- [x] T89: **The annotation reader dropped any field added to the table.** It named its columns one
      at a time, so a value written to a new field went in and came back as nothing, which reads
      exactly like the write having failed. Built from the field list now, as the writer is.
- [x] T90: `web/static/results.js`: the town note is writable from the row (`feat-010/AC-19`). It is
      the one editable cell that is not about the property it sits on, so it saves to the town
      rather than to the house and every other row in that town takes it immediately; the cell says
      so before it is opened. Somebody who writes a note, sees it on one of the nine houses they
      have open in that town and concludes it went in wrong is right to conclude that.
      `tests/test_web_browser.py` types one and asserts the neighbouring rows take it.

### Defect: an edit in a column past the fold was thrown away as it opened

- [x] T91: **Putting focus in the editing box destroyed it.** Focusing the box scrolls the table
      sideways to bring it into view, scrolling is what redraws the virtual window, and a redraw
      replaces every row including the one being edited. So the box opened and vanished in the same
      frame, and every column past the right edge of the screen could not be typed into at all. It
      was reported as the new writable columns not working; they were working, and so was Verdict,
      and neither could be reached.

      `window_` now holds still while a box is open in the table, and an abandoned edit takes its
      box out before asking for a redraw, so the guard is never left reading an edit nobody is
      making. Pinned by two tests in `tests/test_web_browser.py` citing `feat-010/AC-5`: one edits a
      column that starts off screen, one escapes an edit and asserts the table starts redrawing
      again.

      The existing edit tests could not have caught it. They read the box in the same tick as the
      keypress, and the scroll that destroyed it is asynchronous, so they held a box that was about
      to be thrown away and asserted against it happily. The new test waits first, deliberately.

### Defect: double-clicking a cell had never opened it, and the box was the wrong shape anyway

- [x] T92: **Selecting a cell redrew the whole window**, which replaced every row in the table. So
      the first click of a double-click destroyed the element the second click needed to land on,
      and a browser only reports a double-click when both halves hit the same element. Double
      -clicking a cell therefore did nothing at all, on every editable column, and never had.

      Selecting is two attributes on two cells and now sets exactly those, redrawing only when the
      row wanted is not on screen. Pinned by two tests in `tests/test_web_browser.py` citing
      `feat-010/AC-5`, one of which drives the browser's own input pipeline rather than dispatching
      events from inside the page: a dispatched `dblclick` asserts that the handler works, not that
      the browser ever calls it, which is precisely how this survived every existing test.

- [x] T93: A cell holding prose opens into a box the size of a note (`feat-010/AC-4`), anchored over
      the row and naming the property, fixed to the window so the table cannot clip or scroll it.
      "Steep gravel drive, one way out, and the turnaround is too tight for a fire truck" is what
      goes in Fire/Egress, and a twenty-six pixel line is not where anybody writes it. Enter makes a
      new line; the button, Ctrl with Enter, or clicking away all keep what was written; only Escape
      discards. Rank keeps its single line, being a number.
- [x] T94: Keeping and passing both ask why (`feat-010/AC-54`), which is the thing a person knows at
      the moment they decide and reconstructs badly a week later. Passing asks before acting, with
      the cursor already in the box; keeping records the keep first and offers the box afterwards,
      so a shortlist still costs one press. Empty is a complete answer. The reason lands in
      `Verdict`, which has always meant what the person concluded, so it exports and prints beside
      the kept and passed lists with nothing new needed to read it. Four tests in
      `tests/test_web_browser.py` cover both directions, the empty answer, and Escape.

## Change: on the fire map (`changes/on-the-fire-map/`)

- [x] T95: `web/static/fire.html` and `fire.js`: a seventh surface drawing every located property on
      the wildfire hazard model, with the model's own legend written into this tool rather than
      fetched, a control to turn the layer down, and a count that says how many properties have no
      location and are therefore not on it (`feat-010/AC-55`, `feat-010/AC-1`).
- [x] T96: `web/static/fire.js`: a pin keeps or passes on its property, asking the same question
      about why and writing to the same place as the table (`feat-010/AC-56`). Nothing on the page
      is scored, ranked, hidden or coloured by distance from anything, and a test asserts the page
      contains no such arithmetic: that would be a criterion with no rule behind it.
- [x] T97: `enrich/settings.py` and `api.hazard_layers`: the map's address is derived from the one
      the wildfire provider already uses, because an ArcGIS service that answers about a point at
      `identify` draws the same data at `exportImage`. No second address to keep current, and
      pointing the provider elsewhere moves the map with it.
- [x] T98: `enrich/hazard.py`, `api.hazard_tile` and `/api/hazard/{layer}`: the tiles are fetched by
      this machine and kept on disk, not by the browser.

      Two reasons, and both were found by looking rather than by reasoning. Chrome refuses the
      cross-origin image outright (`ERR_BLOCKED_BY_ORB`), so the first version of this page drew the
      properties over nothing at all and every request came back `net::ERR_ABORTED`; and a browser
      reaching out to a federal server is a second thing talking to the outside world, which this
      product's privacy statement does not describe. Fetching it here is the statement unchanged: a
      public enrichment endpoint, asked by the machine that already asks it.

      Kept forever, because the model is republished every few years, so the same part of the state
      costs that server nothing to look at twice. Four requests at once rather than the providers'
      one-second spacing, which would take half a minute to draw one screen.
      `tests/test_web_hazard.py` covers the rectangle and size being four numbers and two numbers
      and nothing else, the cache, an answer that is not a picture, and the served headers.
## Change: filter a column (`changes/filter-a-column/`)

- [x] T99: `web/static/results.js`: every sortable heading carries a filter button, always drawn
      rather than appearing on hover, and it opens a box of plain text that narrows that column as
      it is typed into (`feat-010/AC-57`, `feat-010/AC-7`). Reachable without a pointer as well:
      `f` on a focused heading, and an item on the heading's right-click menu under the one that
      hides it (`feat-010/AC-17`).

      Filters on several columns all hold at once, which is the whole reason for having them: "in
      Ruidoso" and "single storey" is a question the one box at the top cannot ask, because the
      second answer replaces the first.

- [x] T100: `web/static/results.js`: a filter is matched against the cell as it is displayed rather
      than as it is stored (`feat-010/AC-57`, `feat-010/AC-10`). A price reads $425,000 and is held
      as 425000, and somebody typing what is in front of them is not wrong; a column nothing could
      be found for reads "not known", so typing that finds exactly those rows, which is a question
      that has been asked out loud more than once. A column the person writes in themselves is the
      exception: an empty one there was never unknown, because nobody set out to determine it.

- [x] T101: `web/static/results.js` and `app.css`: every filter in force is written out above the
      table, each with its own control to lift it, and one control lifts them all including the
      whole-table search box (`feat-010/AC-57`, `feat-010/AC-18`).

      This is the part that is not a convenience. A table silently missing four hundred rows is the
      worst thing this screen can do, so the reason is on screen in words the whole time, and a
      person whose rows have gone missing has one thing to press rather than a column filter here
      and a search box up there. It is also why a filter on a column that has since been hidden
      stays in the list: hiding a column must not take the reason its rows are gone with it.

- [x] T102: `web/static/results.js`: the narrow columns are wider by the width of the button now on
      every heading. A column headed "B..." says nothing about whether it is beds or baths, and the
      two of them are next to each other.

- [x] T103: `tests/test_web_browser.py`: three real-browser tests — a column narrowed from its own
      button, with the filter named above the table and absent from this browser's storage; one
      press lifting every filter, the search box included; and the match being against what the cell
      shows, which covers the price, the "not known" and the upper and lower case alike.
## Change: how far, and which way (`changes/how-far-and-which-way/`)

- [x] T104: `web/static/fire.js`: a scale in the corner that follows the zoom, in miles, because
      everything else on this page that talks about distance is in miles (`feat-010/AC-58`).

- [x] T105: `web/static/fire.js` and `app.css`: a ruler with two ends and a middle, all draggable,
      reading its own length (`feat-010/AC-58`, `feat-010/AC-17`). Carrying the middle takes both
      ends with it, so a length is set once and then held up against one thing after another. The
      arrow keys move whichever handle has the keyboard, in steps taken from what is on screen: a
      step of a fixed number of degrees is a jump off the map at one zoom and nothing at all at
      another. Feet below a fifth of a mile, because "0.03 miles" is a number nobody pictures.

- [x] T106: `enrich/wind.py`: a station's wind rose, from Iowa State's archive of hourly airport
      observations (`feat-010/AC-59`). Sixteen directions, each carrying how often the wind came
      from it and how often it did so at fifteen miles an hour and over, which is the half that
      moves a fire.

      Not a forecast, and that is the whole design. Thursday's wind is a fact about Thursday; a
      house is a longer question. The archive computes the rose from every hourly reading a station
      has, so thirty years of Taos is one request rather than a dataset to keep current.

      Two seasons and only two, because the archive answers about one named month or about all of
      them and nothing in between. April is the default: in New Mexico it is both the windiest month
      and the middle of fire season.

      Kept on disk for good, and asked exactly once. The request is a query across tens of thousands
      of rows and takes ten seconds of somebody else's public machine, for an answer that summarises
      decades. Three at a time, fewer than the map tiles, because a tile is a file and this is work.

- [x] T107: `api.wind_stations`, `api.wind_rose`, `/api/wind/stations/{name}` and
      `/api/wind/rose/{network}/{station}`: fetched by this machine and never by the browser, which
      is the privacy statement unchanged rather than gaining a line (`feat-010/AC-59`).

      Which states to ask about comes from the properties themselves rather than from what the
      search is called: a search named "nm-statewide" that turned up a house over the Colorado line
      gets Colorado's stations too. A state that will not answer is named and does not take the
      others with it.

- [x] T108: `web/static/fire.js` and `app.css`: the roses drawn, in a layer of their own between the
      fire and the properties, at a fixed number of pixels rather than as a shape on the ground
      (`feat-010/AC-59`, `feat-010/AC-18`).

      Only the stations on screen are asked about, nearest the middle first, so somebody looking at
      Taos waits ten seconds for Taos rather than four minutes for New Mexico. Violet, because this
      page already spends red through green on the hazard model and blue, gold and pink on what the
      person decided, and a rose in any of those reads as one of those.

      Two bugs here that only a pointer finds, both recorded because neither is visible in the
      source. A large negative `zIndexOffset` paints a marker behind the map's own surface, so every
      click at a rose landed on the tile underneath it: the roses drew perfectly and could not be
      opened. And clearing the layer to redraw it takes any open bubble with it, because opening one
      pans the map and a pan is what triggers the redraw. Both are covered by a test that hit-tests
      the middle of a rose and then opens it.

- [x] T109: `web/static/fire.js`: the sentence that a direction is where the wind comes **from**,
      in the legend and again in every bubble, with what it means for a fire spelled out
      (`feat-010/AC-59`). Read the other way round, every conclusion this overlay supports is
      exactly inverted, and a rose is drawn the way somebody who has not seen one will read
      backwards. `tests/test_web_wind.py` asserts the page says it more than once.

- [x] T110: `tests/test_web_wind.py` and `tests/test_web_browser.py`: the parse pinned by the one
      check that catches a shifted column, which is that sixteen directions and the calm account for
      exactly a hundred percent of the time; north being north; the hard-wind bands read off the
      archive's own labels rather than counted in from the right; a table of the wrong shape being a
      failure rather than a wrong rose; the caching; a state that will not answer; and, in a real
      browser, the scale following the zoom, the ruler measuring and moving, and a rose being
      reachable by a pointer and opening into what it recorded.

- [x] T111: `tests/test_web_browser.py`: the map's "scores nothing" guarantee re-aimed
      (`feat-010/AC-56`). It was asserted by banning the word "distance" anywhere in the page, which
      stopped being the same claim once the page grew a ruler somebody drags and an overlay that
      asks about the stations nearest the middle of the screen. Both measure distances; the
      difference is who is measuring and what it decides. The ban now sits on the function that
      turns a property into a pin, along with an assertion that the one reason a property is left
      off is the person's own judgment.


## Change: which way it pushes (`changes/which-way-it-pushes/`)

- [x] T112: `web/static/fire.js`: every arm turned round to point the way the wind pushes, and the
      words turned with it (`feat-010/AC-59`).

      The overlay was drawn as a wind rose, which points into the wind the way a weather vane does.
      That convention is right and it is read backwards by everybody who was never taught it. The
      question that ended it came from the person the page is for, straight after reading the two
      sentences written to stop exactly that question: "if a petal is very long on the East side,
      does that mean FROM the East or TO the East?"

      Explaining harder was the alternative and it had already been tried, in the legend and again
      in every bubble. What settles it is the cost of being misread here, which is not shared by
      anything else on this map: "from the west" and "toward the west" name opposite sides of a
      house as the side to worry about.

      One half-turn, in `pushes()`, and every direction a reader sees goes through it. `wind.py` and
      the cached answers are untouched: a record of facts should hold what meteorology recorded, and
      the turn belongs to the drawing.

- [x] T113: `web/static/fire.js`: one head, on the longest arm (`feat-010/AC-59`). Sixteen heads at
      this size is a smudge, and the job of a head here is to answer "which end of this is the
      pointed end" once. The glyph went from 64 pixels to 72 to make room for it without shortening
      the arms, and the head is the arm's own colour rather than the hard-wind violet, because a
      head in the darker colour reads as another quantity and it is not a quantity.

- [x] T114: `tests/test_web_wind.py` and `tests/test_web_browser.py`: both halves pinned against
      each other (`feat-010/AC-59`). Arms pointing downwind under a caption saying "from" is the
      same wrong answer with a second voice agreeing, so the words are checked for the new
      vocabulary *and* for the absence of the old, and the drawing is measured in a real browser:
      the fixture's wind comes out of the west, so the shape furthest from the middle of the glyph
      must sit east of it. Read off the geometry, not off the caption, because the caption is the
      half that was never wrong.

## Defect: the headings let go partway down a long list

- [x] T115: `web/static/results.js` and `app.css`: the rows the window is not drawing are now blank
      rows with a height, above and below the drawn ones, instead of a transform on the drawn ones
      (`feat-010/AC-53`).

      Found in use, at the far end of a thousand rows: "the headers stay sticky/frozen at the top
      for a while, but eventually it stops doing that for some reason."

      One sentence of cause: a sticky cell is stuck to its own table and no further. The window
      draws sixty rows and placed them with a transform, and a transform moves paint and never
      layout, so the table really was sixty rows tall and the headings held for sixty rows. Blank
      rows are layout.

      The blank blocks are their own row groups, so `#body` still holds the drawn rows and nothing
      else and every row lookup in the page and in the suite keeps working. They are hidden from
      anything reading the page aloud, because they are not rows: they are the shape of the rows
      that are not here.

      The regression test makes the scroller short on purpose, so the drawn window is a small
      fraction of the list whatever size the machine running it opened its browser at. Against the
      unfixed page the headings measured 939 pixels outside the box at the end of the list.


## Change: just show arrows (`changes/just-show-arrows/`)

- [x] T116: `web/static/fire.js`: the wind rose replaced by one arrow per station
      (`feat-010/AC-59`).

      The last change turned the rose's arms around to point downwind. This is the rest of it, and
      the reason the rose was still wrong is not taste: a rose answers "what is the spread of wind
      direction at this station", which has sixteen numbers in the answer, and the question on this
      page has one direction in it. The drawing of one direction is an arrow. Every reading of the
      rose had to be done twice, find the longest arm and then read its direction, and the person
      the page is for said so: "it would be more intuitive for me if it just showed actual arrows."

      Length carries what the sixteen arms carried, at a coarser grain: longer where the wind more
      often does the same thing, with a floor, because below half an arrow stops having a direction
      and becomes a smudge with a point on it. The sixteen figures are still in the bubble.

- [x] T117: `web/static/fire.js`: the hard wind gets a second arrow only where it pushes somewhere
      else (`feat-010/AC-59`). "It normally pushes east, and when it blows hard enough to move a
      fire it pushes north" is two facts about one place and both decide which side of a house to
      worry about. Drawn always, the second arrow would sit on the first saying nothing, which is
      decoration shaped like an answer. Both halves of that rule are pinned in
      `tests/test_web_browser.py`, because a rule with only its positive half tested is a rule that
      quietly becomes unconditional.

- [x] T118: one arrow, one closed outline, with `paint-order: stroke` putting the white edge
      outside the colour (`feat-010/AC-59`). A stroked line with a triangle on the end would be two
      shapes, two white edges, and a visible seam where they meet, over a raster that is red in
      some places and green in others.

## Change: names on the map (`changes/names-on-the-map/`)

- [x] T119: `enrich/ground.py`: county outlines and town names from the Census, cached per state
      for ever (`feat-010/AC-60`). Outlines simplified on the server to about a kilometre, which
      takes a state from a megabyte to seventeen kilobytes and is the only version honest about
      what it is: a line on a map rather than a survey document.

      Urban areas rather than incorporated places for the town names. Places would give every
      incorporated village in the state, hundreds of them; an urban area is drawn round where
      people actually are, so New Mexico has thirty-seven and the list reads as "the towns". It is
      also the only free national answer to how big a town is that does not need a key, which the
      Census population API now does.

- [x] T120: `enrich/ground.py`: a thirty-year rainfall average per county from NOAA
      (`feat-010/AC-61`). Fire hazard is modelled from fuel and terrain and says nothing about how
      dry a place is, and in this state that is most of what somebody buying land is deciding on:
      San Juan is 8.7 inches a year and Mora is 18.2, and no column in this tool said so.

      An average, not a year, because a year here is a story about one monsoon. The record refuses
      a range ending in a year it does not hold, so it is asked from 1895 to last year and sliced
      here; a gap is marked with a large negative number and is dropped rather than averaged in,
      which is the difference between a county at twelve inches and a county at minus one.

- [x] T121: `web/static/fire.js`: the names drawn over the fire layer, not under it
      (`feat-010/AC-60`, `feat-010/AC-61`). Underneath is where the basemap's own names already
      are, and a raster opaque enough to read is a raster that hides them: the moment this map
      becomes useful it also becomes anonymous.

      Dark letters with a white outline rather than a white box, because forty white boxes over a
      hazard map hide the hazard, and the hazard is what the page is for. The labels take no
      pointer at all: a name sitting over a town would otherwise make every house in that town
      impossible to open, and that fault looks exactly like a mis-click.

- [x] T122: `web/static/fire.js`: a name that would land on another is not drawn (`feat-010/AC-60`).
      Counties go down first and towns give way, because somebody who cannot read "Albuquerque" can
      still see they are in Bernalillo. A skipped town does not cost the next town its turn, or a
      screen with one crowded corner would draw five names where it has room for ten.

## Change: the list under the map (`changes/the-list-under-the-map/`)

- [x] T123: `web/static/fire.js`, `app.css`: the properties on screen, as a list under the map
      (`feat-010/AC-62`). Asked for in one sentence: "if when looking at the map view, it could
      show the list below it." A pin is very good at where and says nothing until it is opened.

      Its own plain table and not the results grid: that one is virtual-windowed, resizable,
      filterable and sticky-headed, and every one of those exists to survive a thousand rows. This
      never holds more than four hundred and lives under a map.

      The address is a button that opens the pin where it stands rather than travelling to it. The
      pin is already on screen, which is what being in this list means, and a map that jumps
      whenever a row is read loses the place somebody was looking at.

- [x] T124: `app.css`: the numeric cells are `numeric` and not `figure` (`feat-010/AC-62`).
      `figure` was the obvious name and it is taken: it is the dashboard's stat card, `display:
      block` and all, which turned every cell in the new table into its own row. Found by looking
      at the page, which is the only way that one was ever going to be found.

## Change: words of our own (`changes/words-of-our-own/`)

- [x] T125: `web/static/results.js`, `app.css`: a Tags column, shown as chips and set from a
      chooser (`feat-010/AC-63`). Deliberately not a box to type a comma-separated list into: that
      is how a vocabulary of eight words becomes fourteen, half of them typos of the other half,
      with nothing on the page ever saying so. The store folds case for the same reason; this is
      the half that stops the second spelling being typed at all.

- [x] T126: `web/static/results.js`: what is ticked is its own list of words (`feat-010/AC-63`).
      It was a set of keys into the vocabulary, and the vocabulary is refreshed in the background,
      so a word typed a moment before that refresh landed was dropped on save: the box was ticked,
      the word was on screen, and it was gone. Found by the browser test, not by using the page.

- [x] T127: `web/static/results.js`: `replaceChildren` spread rather than handed an array
      (`feat-010/AC-63`). `el` flattens arrays, which is exactly why the DOM's own method reads as
      though it would; handed one it stringifies it, and the chooser filled with "[object
      HTMLLabelElement]" where the tick boxes should be. Also found by the test.

## Defect: two overlays at once were two five hundreds

- [x] T128: `web/app.py`: the one-request-at-a-time lock made to actually serialise
      (`feat-010/AC-64`).

      Found by switching on the county names and the wind together on the real map, which is the
      first time anything in this product asked the database two questions at the same time. Both
      requests read the run's properties, their cursors interleaved on the single connection, and
      sqlite refused both: "bad parameter or other API misuse", seen as two five hundreds and an
      overlay that silently never appeared.

      The lock was there and had never worked. `with app.state.lock:` around an `await`, over a
      reentrant lock, in an async middleware: the middleware runs on the event loop's own thread,
      so a second request arriving while the first was suspended took the same lock and went
      straight through. It reads exactly like one request at a time. Nothing failed for months
      because nothing asked two questions at once.

      Now a plain lock, acquired off the event loop so that waiting does not stop this process
      answering at all, and released in a `finally` because a request that raises still has to let
      the next one in.

      Two routes are exempt and named in one list: a hazard tile and a wind rose never open the
      store, and holding a global lock through ten seconds of somebody else's archive would turn
      the wind overlay from three at a time into one at a time for no reason. A list rather than a
      flag per route, so adding a route is not also a chance to opt out of the store's only
      protection by accident.

      The test counts overlap rather than racing and hoping: four requests, and the number ever
      inside the read at once must be one. A test that fires two and asserts both succeeded passes
      on a fast machine with the bug still in place. Checked against the old code, where it fails.

## Change: this one on the fire (`changes/this-one-on-the-fire/`)

- [x] T129: `web/static/listing.js`, `listing.html`, `app.css`: one property on the hazard layer,
      on its own page (`feat-010/AC-65`).

      Built after the page is on screen and not during the build of it: a map handed an element
      that is not in the document yet measures it as zero by zero and comes out grey, which is a
      fault that only ever shows on a real page.

- [x] T130: `web/static/common.js`: the hazard tile layer moved out of the fire map
      (`feat-010/AC-55`, `feat-010/AC-65`). Two pages draw it now, and the conversion from
      Leaflet's tile coordinates to the service's rectangle in metres is exactly the thing that
      gets written twice and then diverges by half a tile, with no way to say which page is right.
      The contract test that pins "this tool's own route, never the far server" now reads the
      shared definition and checks all three pages for the far server's address.

## Defect: the page called it rain and the record counts snow

- [x] T131: `web/static/fire.js`, `enrich/ground.py`, `api.py`: "rain and snow" everywhere the
      figure is shown or described (`feat-010/AC-61`).

      Found by the person the page is for, in one question: "does rainfall include snow?" It does.
      The national record measures frozen precipitation by melting it, so the figure has always
      included snow as the water it melts down to, and the word on the page was wrong from the
      first draft.

      The reason it matters is not tidiness. Taos reads 17.7 and San Juan reads 8.7, and read as
      rain that is "twice as wet"; most of the gap is snow that fell on a mountain, which is a
      different fact about living there. So the legend now says snow is counted as the water it
      melts down to, and that an inch on the map is roughly a foot of snow.
