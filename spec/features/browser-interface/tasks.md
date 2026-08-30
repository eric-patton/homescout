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
      on its own page (`feat-010/AC-66`).

      Built after the page is on screen and not during the build of it: a map handed an element
      that is not in the document yet measures it as zero by zero and comes out grey, which is a
      fault that only ever shows on a real page.

- [x] T130: `web/static/common.js`: the hazard tile layer moved out of the fire map
      (`feat-010/AC-55`, `feat-010/AC-66`). Two pages draw it now, and the conversion from
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

## Defect: the tags could not be reached

- [x] T132: `web/static/results.js`, `export/columns.py`, `app.css`: the tag cell made reachable
      (`feat-010/AC-45`, `feat-010/AC-63`).

      Reported by the person it was built for, the first time she went looking for it: "how do you
      create tags, I'm clicking the field on a row but it's not letting me type." Three separate
      faults, and every one of them on its own was enough to make the feature not exist.

      **It was column thirty-nine of forty-four.** A remembered column arrangement names every
      column there was when it was saved, and anything added afterwards went on the end, which on
      this table is two screens to the right behind a horizontal scrollbar. A new column now goes
      beside the column it is declared beside. Nothing anybody placed themselves moves.

      **It was declared beside `Notes`**, which is right by family and still lands it in the
      thirties. A tag is a label on a house, read down the column the way the address is read, so
      it is declared beside the address. It stays out of the default sheet, which is a promise
      about a document that already exists.

      **It opened on a double press**, like the columns somebody types into. Those need one press
      to mean "select this cell"; this one is not typed into at all, it holds a list, and pressing
      it opens the list. It now opens on a single press, and the heading text above the table says
      so, and an empty cell carries a faint mark rather than being blank: blank is this table's
      word for "nobody has written anything", and what this cell also has to say is that there is
      something here to press.

      The browser test now reaches the control the way she did, with a press on the cell, rather
      than by calling the edit function. Calling it directly is what let a control that could not
      be opened pass a test that said it worked.

## Defect: the server stopped answering while she was using it

- [x] T133: `web/app.py`: wait for a turn without occupying a thread (`feat-010/AC-64`).

      Reported as "did this go down? The site isn't responding anymore", and it had: the process
      up, the port listening, and every request answered with nothing. It stayed that way until it
      was restarted.

      Caused by T128, two commits earlier. That change fixed a real fault - two requests reading
      one database connection at once - by taking the lock in a worker thread. Which serialises
      correctly, and draws from a pool of about forty shared with every synchronous endpoint. A
      page opening is a burst: scripts, stylesheets, settings, results, two overlays, all at once.
      Forty of them park in the pool waiting for the lock, and the request that HOLDS the lock
      cannot then get a thread to run its endpoint in. It never finishes, so it never releases, so
      nobody ever gets a turn, and the deadlock is permanent.

      Now the wait is a non-blocking attempt and a five-millisecond sleep. It takes no thread, it
      costs nothing at all when the lock is free, which is almost always, and it is the only
      version that cannot leak the lock either: the one await happens before the lock is held.
      This tool's own files were added to the list of things that never wait, because a page asks
      for a stylesheet, four scripts and a map library before it asks the database anything.

      Measured on the burst test: thirty-seven seconds and ninety-seven failures before, one and a
      half seconds and none after.

- [x] T134: `tests/test_web_browser.py`: the burst, as a test (`feat-010/AC-64`).

      The test that shipped with T128 fired four requests and said the serialisation worked. It
      did work. Nothing smaller than a burst finds this, so the test is a burst, and it is against
      a real server on a real port rather than the test client: through the test client the fault
      cannot fail the test, it hangs it, and a test that hangs never tells anybody anything. Every
      request carries a deadline for the same reason, because what is being looked for is silence
      rather than an error.

      Checked against the broken version, where it reports ninety-seven of a hundred requests
      unanswered.

## Change: as tall as the text (`changes/as-tall-as-the-text/`)

- [x] T135: `web/static/results.js`, `app.css`: a wrapped row is as tall as its own text
      (`feat-010/AC-47`). "In the table when you wrap text, it is still cutting off text if it is
      too long. It should just make the row as tall as it needs to be to show the wrapped text."

      The clamp of three lines was there for a reason and the reason is real: every row being the
      same height is what lets a thousand of them be placed by arithmetic. So the arithmetic now
      runs on measurements instead of on one number. A running total of row heights, a binary
      search into it for the row at the top of the screen, and a guess for any row that has never
      been drawn, replaced by its measurement the moment it has been.

      The row under the top of the window is held still when a measurement changes what is above
      it. Without that, reading down a wrapped table would keep shoving the line being read off
      the screen as rows nobody has looked at yet turn out to be taller than assumed.

      The floor and the guess are now two different numbers, which they were not. One number meant
      a row with nothing to wrap was as tall as three lines of nothing.

- [x] T136: `web/static/results.js`: overscan by distance rather than by count
      (`feat-010/AC-47`). Twelve rows either side of the screen is a sensible cushion while a row
      is twenty-six pixels and four thousand pixels of table nobody is looking at when a row is
      three hundred.

- [x] T137: `tests/test_web_browser.py`: the row grows and the scrollbar still tells the truth
      (`feat-010/AC-47`). Replaces the test that asserted the opposite. Three things at once,
      because two of them are what the clamp was protecting: nothing in the drawn window needs more
      room than it has, no row is taller than what is in it needs, and the blank standing in for
      the rows that are not drawn agrees with where they are said to be, at the top, partway down
      and at the end. The end matters most: a table whose blank space is off by a pixel a row is a
      table whose last rows cannot be reached.

## Change: the picture in the pin (`changes/the-picture-in-the-pin/`)

- [x] T138: `web/static/fire.js`, `app.css`: the stored photograph in a pin's bubble
      (`feat-010/AC-56`, `feat-010/AC-51`). "She wants the pins on the map when you click them to
      show the thumbnail for the house in that little info popup."

      The stored copy, from this machine, so opening a pin still tells no listing site anything.
      Pressing it opens the whole gallery, which is the one thing here that does ask them, the same
      as the thumbnail on the results table.

      A frame of a fixed height with the picture inside it at its own size or smaller. Two thirds
      of the stored photographs in this workspace are a hundred and twenty pixels across, because
      that is what the site handed over, and one blown up to fill a wider frame reads as a fault in
      this tool rather than as a small photograph.

- [x] T139: `tests/test_web_browser.py`: the picture is this machine's, and loads
      (`feat-010/AC-56`). A real one-pixel image stored for one property, so the assertion is that
      the picture in the bubble actually rendered from this origin rather than that an `img` tag
      exists. And the property beside it, with nothing stored, gets no frame.

## Defect: the overlays made the houses unclickable

- [x] T140: `app.css`, `web/static/fire.js`: nothing over the properties takes the pointer off them
      (`feat-010/AC-59`, `feat-010/AC-60`).

      Reported as "sometimes when i'm interacting with the map, like i zoom, check/uncheck things,
      i become unable to click properties, like when i mouse over, the clicker remains a hand. is
      it just lagging maybe?"

      It was not lagging. Three separate things, all of them the same mistake, and each one on its
      own was enough to make every house on the screen unopenable. Measured on the state at zoom
      seven, of the pins actually on the screen:

      **The county lines. 176 of 176.** The outlines are drawn as non-interactive, which would be
      the end of it if they were shapes in the page. They are not: this map draws on a canvas, and
      a canvas is one element covering its whole pane whatever is painted on it. So a pane of
      county outlines answered for every pixel of the map, found nothing of its own under the
      pointer, and handed the click to the map. This is the one that will have been biting: it is
      a box somebody ticks once and leaves ticked.

      **The wind arrows' boxes. 183 of 185.** An arrow is an icon rather than a shape on the
      ground, so its box is a fixed hundred and twelve pixels at every zoom and nearly all of it is
      empty. Forty-four of those cover a county. A click there opened the station's bubble, which
      is anchored at the station and so opens somewhere else, which is why it read as nothing
      happening rather than as the wrong thing happening.

      **The mark for a station still being read. 167 of 176.** The same canvas trap as the county
      lines, in the wind's own pane, and it stays there after the record has arrived.

      The panes say it now, rather than the layers, because the element that was swallowing the
      clicks belongs to the pane. The arrows put the pointer back on their own ink in the
      stylesheet, with the class doubled up to beat leaflet's `.leaflet-marker-icon.leaflet-
      interactive`, which is what puts `auto` back. The waiting mark loses the tooltip that named
      its station: the dot's job is to say more is coming and the line above the map says how many,
      and neither is worth a screenful of houses that cannot be opened.

      Not fixable by moving the panes below the properties. The properties are drawn by a canvas
      renderer that covers the whole map and answers for every pin on it, so anything under that
      canvas cannot be clicked at all: an arrow moved below the properties is an arrow that can
      never be opened.

- [x] T141: `tests/test_web_browser.py`: what the browser says is under the pointer where a house
      is (`feat-010/AC-59`, `feat-010/AC-60`). The same question asked three times, with nothing
      on, with the county lines on, and with the wind on, and the answer each time has to be the
      thing the properties are drawn on. One station placed a little north of the address the
      fixture's properties share, so its box lands over them and its ink does not, which is the
      case that was wrong. The ink is asserted too: an arrow that cannot be opened is the same
      fault the other way round.

      Checked against each of the three broken versions separately, because one test that passes
      for two of them is a test that will let the third back in.

## Defect: wrapping was remembered and did nothing

- [x] T142: `web/static/results.js`: the table is told it is wrapping after it exists
      (`feat-010/AC-47`). The row height is a property on the document and lands wherever it is set
      from; "is this table wrapping" is a class on the table, and it was being set before the table
      was built. So somebody who left wrapping on came back to a page with the box ticked and
      nothing wrapped, and the only way to get it back was to turn it off and on again. Found while
      measuring the change above, on a real workspace, which is the only place it shows: every test
      that turns wrapping on clicks the box.

## Defect: the results page was sometimes very slow to load

- [x] T143: `web/app.py`: compress an answer worth compressing (`feat-010/AC-66`).

      Reported as "the search results page sometimes takes a really long time to load".

      Sometimes is the whole clue. Measured on this machine the page is the same every time: about
      one and a tenth seconds to assemble a statewide result and a few milliseconds to send it. The
      part that varies is not here.

      The statewide answer is **2663 KB of JSON, sent uncompressed**. On loopback that costs
      nothing. The second person in the household reads it through `tailscale serve`, and
      `tailscale status` says `CurAddr` is empty and `Relay` is `dfw`: there is no direct
      connection, so all two and a half megabytes travel to a relay in Dallas and back. A relay is a
      shared fallback rather than a fast path, and how fast it is on any given evening is the
      difference between a page that opens and a page somebody gives up on.

      Compressed it is 553 KB, which is seventy-nine per cent less, for thirty-six milliseconds.

      Level five rather than the library's nine, chosen by measuring rather than by taste: 553 KB in
      36 ms against 540 KB in 54 ms. Thirteen kilobytes is not worth eighteen milliseconds on every
      request when what is being bought is the time to the first painted row. Added last so it wraps
      the lock, which means the compressing happens after a request has let go of the database
      rather than while another one waits its turn. Pictures are excluded: a stored preview is
      already a JPEG and would only get bigger.

- [x] T144: `tests/test_web_endpoints.py`: what goes over the wire (`feat-010/AC-66`). That it is
      compressed when asked for, that it carries `Vary`, and that the answer is identical once
      unpacked, because compression that changed an answer would be far worse than a slow page.
      Beside it the two things that must stay true: a client that cannot unpack one still gets an
      answer, and a photograph is not compressed twice.

- [x] T145: not done, and written down so it is not rediscovered. The remaining second is on this
      machine and half of it has one cause: `values_for` re-runs the description patterns for every
      property on every request, seven thousand regex matches per page load, because extraction is
      recomputed rather than kept. It is real but it is the smaller half, and it is invisible next to
      a relayed transfer. Worth doing when the workspace is larger or when the transfer is fixed,
      not before: the profile would only be measuring the wrong thing twice.

## Defect: the two pages counted the same search differently

- [x] T146: `web/static/fire.js`: the map hides what the table hides (`feat-010/AC-67`).

      Reported as "why on the results page is it showing 162 properties but when I click on the
      fire map, it is showing 213?"

      Both were right, which is the worst kind of disagreement. Two hundred and seventeen properties
      were still in play and both pages agreed on that. The table then hid the fifty-five that had
      come off the market, which is a checkbox it has and a default somebody chose. The map had no
      such filter, drew all of them, and lost four of its own to having no coordinates. A hundred
      and sixty-two against two hundred and thirteen.

      The arithmetic is the smaller half. The map was pinning fifty-five delisted houses exactly
      like the ones still for sale, with no way to tell them apart and no way to hide them, so
      somebody planning a drive was planning it around houses they could not buy.

      The map now takes the table's rule, the table's checkbox and the table's wording, and says in
      its count what it is holding back. One predicate for the pins and the list under them, rather
      than the pass rule written out in both, which is how they came to be answering different
      questions in the first place.

- [x] T147: `tests/test_web_browser.py`: hidden by default, said out loud, back when asked
      (`feat-010/AC-67`). A real second run that retires a property rather than a flag set in the
      browser, so the state under test is the one the store actually produces. Checked against the
      unfixed page.

## Change: the photograph from above (`feat-010/AC-68`)

- [x] T148: `web/settings.py`, `api.py`, `web/wire.py`: a second background, configured like the
      first (`feat-010/AC-68`). "Can we look into adding the ability to switch between street map
      tiles and satellite tiles for the map too? It is helpful to be able to see the satellite
      view."

      It is, and for this search particularly: the household is looking at rural land, where the
      question is usually what is actually around a property rather than what the roads are called.
      A drawn map cannot answer that and a photograph cannot answer the other one, so this is a
      switch rather than a replacement.

      Configured exactly like the drawn background and for the same reason rather than out of
      symmetry: a tile server is a computer being told which part of the world is being looked at,
      and a second one is a second computer. Same warning, same place, same default of off. Added
      to the written-settings list so the page can turn it on, which is where that decision belongs.

- [x] T149: `web/static/fire.js`: the switch (`feat-010/AC-68`). Two layers rather than one whose
      address is rewritten, because leaflet's attribution follows a layer and the two backgrounds
      are not the same people's work. `maxNativeZoom` on the photograph, so zooming past the depth
      of the imagery stretches the deepest picture there is instead of asking for a tile that does
      not exist and painting nothing: a photograph running out should look like a photograph running
      out, not like the map breaking.

- [x] T150: `web/static/settings.js`: the USGS imagery offered by name (`feat-010/AC-68`,
      `feat-010/AC-25`). The government's own photography of its own country: public domain, no
      account, and the same kind of federal service the fire layer and the broadband map already
      come from, so turning it on adds a background rather than a new kind of relationship. It
      covers the United States only, which is what this tool searches. A different server can still
      be typed in.

- [x] T151: `tests/test_web_browser.py`: the switch, both ways, with the credit following it
      (`feat-010/AC-68`). One background at a time, the properties still on the map afterwards, and
      the map still alive when the tiles answer 404, which they do throughout because the addresses
      resolve to the test's own server: a browser test about tiles that asks somebody for a tile is
      a test that fails on a train. Beside it, the case that decides the shape of the control: with
      nothing configured, nothing is offered.

- [x] T152: `web/settings.py`, `web/wire.py`, `api.py`, `web/static/{fire,settings}.js`: sharper
      imagery, and how deep it goes recorded rather than guessed (`feat-010/AC-68`). "I assume we
      can't get access to higher quality satellite tiles at closer zoom levels?"

      We can, by a lot. Measured at four New Mexico addresses, three of them properties in this
      workspace: the government's cache answers 404 past zoom sixteen at every one of them,
      downtown Albuquerque included, so it is the whole cache rather than a rural gap. Esri's has
      real pictures down to twenty-one everywhere tried. Both services *publish* a maximum of
      twenty-three and neither means it.

      Looked at rather than only counted. At Esri's zoom nineteen over one of the six properties
      the household asked about, individual pinon crowns, a parked vehicle and a neighbouring roof
      are all legible; the same vehicle is about one pixel at the government's deepest. Roughly six
      times finer in practice.

      Esri is offered first and the government's is kept beside it rather than dropped, one button
      each. One is a company's service that can be rate-limited or withdrawn and asks for its credit
      line; the other is public domain and cannot be. A fallback that is a click is worth having.

      The depth is now a setting rather than a constant, because it belongs to the source and the
      two differ by five levels. Asked past its own depth a tile server returns nothing and nothing
      paints as a hole, so a map that goes blank when somebody zooms in reads as broken. The deepest
      real level is written down beside the address and the map stretches that one, so zooming
      further goes soft, which is the honest way for a photograph to run out. Unset means nobody has
      measured that source and the server is asked for whatever the map asks for.

## Change: the list is what you watch (`changes/the-list-is-what-you-watch/`)

- [x] T153: `api.py`: a set-aside search answered as what it was, not as a name
      (`feat-010/AC-69`). `deleted_searches` returns a tuple of strings, which is everything the
      current strip of "Bring back X" buttons can show and nothing a person needs to decide whether
      they want it back. It answers a record instead: description, how many areas, which sources,
      when it last ran, when it was set aside. Read from the kept definition file, which still has
      all of it, rather than stored separately, because a second copy of a search's description is a
      second thing to keep in step.

- [x] T154: `api.py`, `search/definition.py`: `discard_search`, the only operation here that removes
      a file (`feat-010/AC-70`).

      **Resolves the name through `safe_path` and nothing else.** Not `glob`, not a pattern, not the
      way `restore` two functions down does it. That is the pre-build check's one hard finding and
      it is the first line of this task rather than a note at the end of it, because the obvious way
      to write this function is to copy its neighbour and its neighbour is the one that is wrong.
      T169 fixes the neighbour first, so by the time this is written the pattern to copy is the
      right one.

      Refuses a search that is not already deleted, in words, having read that from the catalogue in
      this same request rather than from anything the caller asserts: the reversible step is what
      makes the irreversible one safe to offer, and skipping it would make discarding a one-click
      way to lose an afternoon's drawing. Answers with what survives, counted in the same request,
      for the same reason `delete_search` reports how many runs were kept. It touches one file and
      nothing in the store, and the docstring says so where `delete_search`'s already does, because
      this is the function somebody will one day read while wondering whether it is what deleted
      their history.

- [x] T155: `cli/main.py`, `cli/render.py`: `search discard` on the command line (`feat-010/AC-70`,
      `feat-010/AC-22`). Both surfaces or neither. The terminal's confirmation is the name as an
      argument, which is the same demand the browser makes for the same reason.

      It takes `--json` and returns a stable exit code, like every other command, because product
      invariant 6 says an automated agent can drive this tool without parsing prose and makes no
      exception for the destructive one. Said here rather than assumed: this is the command where a
      caller most needs to tell "removed it" from "refused, it was not deleted" without reading a
      sentence, and the one where guessing wrong is worst.

      **This shipped broken once, inside this task, and the reason is worth keeping.** The parser
      and the core operation were both written and correct; the renderer they hand the answer to
      never landed, so the command raised on the line that prints its result. The whole suite was
      green, because the suite covered the route, the catalogue and the core function and never the
      words the terminal prints. The parity test that enumerates commands passed too: it asks
      whether a command has a route, not whether the command runs. Found by running it. Both
      halves, the refusal and the success, are now exercised end to end by tests in
      `test_cli_operations.py`, one of them on `--json`.

- [x] T156: `web/app.py`, `web/wire.py`: the surface's page route and its two API routes
      (`feat-010/AC-69`, `feat-010/AC-70`, `feat-010/AC-1`). The discard gets a path of its own
      rather than a second meaning for `DELETE /api/searches/{name}`, which already means the
      reversible one: two operations that differ only in whether they can be undone should not
      differ only in a verb. Behind the same host, origin and header guard as every other mutation,
      which already covers it. The page route joins `PAGES` so it is reloadable and bookmarkable
      like the other eight, and a test asserts every surface AC-1 names is reachable, which is what
      was done the last time that count moved.

- [x] T157: `web/static/archive.html`, `web/static/archive.js`: what has been set aside
      (`feat-010/AC-69`, `feat-010/AC-70`). Two lists on one surface, archived and deleted, each
      card saying what the search was rather than only what it was called. The discard asks for the
      name to be typed into the dialog before its button will act, and the dialog says what stays in
      the store above the buttons rather than under them: the sentence has to be read before the
      decision, not after it.

- [x] T158: `web/static/searches.js`: the list holds what is being watched (`feat-010/AC-69`,
      `feat-010/AC-23`, `feat-010/AC-27`). `deletedPanel` goes, the archived toggle goes, the
      archived cards go, and one line arrives in their place saying how many searches are set aside
      and where they are. Not shown at all when there are none, which is the thing the toggle could
      never do: it had to stay on screen after the last archived search came back, because the state
      it held would otherwise have had no way to be turned off.

- [x] T159: `tests/test_web_parity.py`, `tests/test_web_browser.py`: the surface, and a test retired
      (`feat-010/AC-69`). A search deleted from its card is not on the list and is on the set-aside
      surface with its description intact; restored from there, it is back on the list.
      `test_the_archived_toggle_survives_the_last_one_being_brought_back` is about a control this
      change removes, so it goes, and what replaces it is the surface that made the control
      unnecessary.

- [x] T160: `tests/test_web_parity.py`, `tests/test_web_safety.py`: discarding, and everything it
      refuses (`feat-010/AC-70`). Refused without the name, refused for a search that was never
      deleted, and refused for a name that is not a name: `../` in it, a name that resolves outside
      the searches directory, and a name that would match a real file by pattern if anything here
      still used one.

      Then the case that is the whole point, in the shape `test_web_safety.py` already uses for
      hostile input and `test_web_guard.py` for refused writes: fingerprint the store, discard a
      search with runs behind it, fingerprint it again, and assert it did not move. The same
      assertion after a refused discard, because an operation that removes nothing on the way to
      saying no is a different claim from one that removes nothing on the way to saying yes.
      Counting rather than trusting the answer's own summary: the summary is the thing under test.

## Change: like with like (`changes/like-with-like/`)

- [x] T161: `web/static/common.js`: one builder for a search's own navigation (`feat-010/AC-73`).
      Which search this is, and one press to each of the other surfaces about it. Here rather than
      on five pages, because five copies of a navigation is how one of them ends up missing the
      surface added last, which is exactly how the search builder came to reach none of the others.

- [x] T162: `web/static/{results,changes,fire,search}.js`, `web/static/listing.js`: every per-search
      surface uses it (`feat-010/AC-73`). The listing page is the one that needs thinking about: it
      is about a property rather than a search, and the way back has to be to the table it was read
      from rather than to a search picked arbitrarily from the ones the property appears in. So the
      table hands it over in the address when it links, and a property page opened without one
      offers no trail rather than guessing at a search.

      Two defects fixed while in that file, both of them things this task was standing next to.
      Every listing page carried two sections headed "Where it is": the hazard map, and the flood
      zone, aquifer, elevation and speeds. The second is about the public record of the place
      rather than about where the place is, and is now "What is around it". And the map link on
      that page said "the fire map" in its prose, which the naming sweep would have missed because
      it is a sentence rather than a link.

- [x] T163: `web/static/results.js`, `app.css`: the toolbar grouped by the question it answers
      (`feat-010/AC-72`). Which rows, which columns, where else to go. Named groups, all open, no
      menus. The line under them keeps the totals and loses everything else: how many are drawn, out
      of how many the run found, how many are kept. The render time in milliseconds goes, which
      AC-72 now says out loud rather than leaving as a tidy-up somebody later mistakes for an
      accident.

- [x] T164: `web/static/results.js`: one control for the judgment (`feat-010/AC-35`,
      `feat-010/AC-49`). Four answers, one in force: still to decide, kept, passed on, all of them.
      The default answer draws exactly what the two unticked boxes drew, so the table nobody asked
      to change does not change. The careful ordering in `apply` that stopped the two boxes
      contradicting each other goes with them, because a single answer cannot contradict itself.

- [x] T165: `web/static/results.js`: every reason rows are missing, in the one bar
      (`feat-010/AC-36`, `feat-010/AC-57`, `feat-010/AC-20`, `feat-010/AC-49`). The judgment and the
      properties that came off the market join the column filters and the search box as statements
      with their own control to lift them, each carrying the number it is holding back, and "clear
      all filters" clears them too. This is the criterion the bar was built for and the two
      narrowings it was built without: in the workspace this was read against, 737 of 951 rows were
      held back by one of them and the bar was empty.

- [x] T166: `web/static/fire.js`, `app.css`: the map's controls in two groups, and its own name
      (`feat-010/AC-71`, `feat-010/AC-72`). Which properties are drawn, and what is drawn underneath
      them. The three live count regions become one, which AC-72 now requires rather than leaving to
      this task's own judgment: three regions announcing themselves separately are three
      interruptions for one change of state, and to somebody who cannot see that they landed
      together they read as three unrelated events.

- [x] T167: `web/static/{searches,changes,results}.js`, `web/wire.py`: the map called the map
      wherever it is named (`feat-010/AC-71`, `feat-010/AC-51`, `feat-010/AC-58`, `feat-010/AC-59`,
      `feat-010/AC-60`, `feat-010/AC-61`, `feat-010/AC-62`). Every link, the heading, and the page
      title. The six criteria cited alongside AC-71 are the ones the naming sweep rewords and
      nothing else about them moves; they are cited so that nothing counting coverage reads them as
      orphaned. The address moves with the name, which is `od-1` resolved, and T171 is what moves
      it; this task points every link at the new one.

- [x] T171: `web/wire.py`, `web/app.py`: the map's address moves and the old one keeps working
      (`feat-010/AC-71`, `od-1`). `PAGES` gains `/map/{name}` and loses `/fire/{name}` as a page;
      `/fire/{name}` becomes a permanent redirect to it. The target is built from the route template
      and the name that was matched, never reflected from the raw request, because a redirect that
      echoes what it was sent is a redirect that can be aimed somewhere else.

      A test that the old address still lands on the map, and one that the new one is what every
      link in the interface now points at, so the redirect is a courtesy to old bookmarks rather
      than a path this tool still uses.

- [x] T168: `tests/test_web_browser.py`, `tests/test_web_accessible.py`: the groups, the one
      judgment control and the bar (`feat-010/AC-72`, `feat-010/AC-35`, `feat-010/AC-57`). Each
      group reachable and named to something reading the page out, the judgment control's four
      answers each drawing what they say, and the bar naming a judgment narrowing and lifting it.
      Checked against the unfixed page.

## Defect: restoring a search looked for the file by pattern

Found by the pre-build check on `changes/the-list-is-what-you-watch/`, while asking what the new
permanent removal would be written next to. Ordered before T154 rather than after it, because T154
is written in this file beside this function and the wrong pattern is the one currently on offer.

- [x] T169: `search/definition.py`: `restore` resolves the name the way everything else does
      (`feat-010/AC-27`). Every other operation on a saved search goes through `safe_path`, which
      enforces the name rule and then checks the resolved parent really is the searches directory.
      `restore` alone builds a glob pattern from the raw name, `where.glob(f"{name}*")`, and only
      validates the destination afterwards. A pattern is not a name: measured on this workspace's
      own interpreter, Python 3.14.6,

          Path('.../searches/deleted').glob('../../elsewhere/secret*')  ->  ['secret.yaml']

      which is a file two directories outside the folder being searched. The wildcard is what makes
      it match and `restore`'s pattern supplies one.

      **What it can actually do today is nothing, and the reason is worth writing down exactly,
      because it is the reason this is a trap rather than a hole.** Measured by running the
      unfixed logic: the glob finds the file outside, and then `safe_path` is called on the same
      raw name and refuses it, so the move never happens. Every name that can escape the folder is
      a name the check downstream rejects, so no file can be moved or removed through `restore`.

      That check is not there for this. It is there to decide where the file is going, and it
      happens to sit downstream of the search. `restore` is saved by an accident of ordering, and
      an accident of ordering is not a rule: it protects this function and nothing about the
      pattern, which is what somebody copies. The next function written beside it removes what it
      finds, and there is no downstream check that would save that one.

      So this is not a defect that is doing damage. It is the one operation on a saved search where
      the rule the codebase follows everywhere else is not followed, sitting where the most
      dangerous function in the product is about to be written.

      The name is checked before the folder is read, so a name that is not a name is refused by the
      same sentence every other operation refuses it with.

- [x] T170: `tests/test_searches_document.py`: the regression (`feat-004/NFR-security`,
      `feat-010/AC-27`). Beside the test that already covers `load` and `create` for the same rule,
      because `restore` was the operation missing from it.

      Landed in `test_searches_document.py` rather than `test_web_parity.py` as first written: the
      rule belongs to the catalogue, the test above it tests the catalogue directly, and going
      through the API would have tested the route instead of the thing that was wrong.

      **The first version of this test passed against the unfixed function**, which is the whole
      reason the red run is not optional. `UnknownSearch` subclasses `InvalidInput`, so
      `pytest.raises(InvalidInput)` catches both, and the unfixed function raised one or the other
      depending only on whether the escaping pattern happened to match a file. The test reads the
      refusal now: it has to be the name rule ("not a usable name"), not "there is no saved search
      by that name", and explicitly not an `UnknownSearch`. Red on the unfixed function, green on
      the fixed one.

      Beside it, the case that says why the rule exists rather than only that it holds: an ordinary
      restore of an ordinary deleted search still works, with its areas and its comments intact,
      which is AC-27's actual promise and the thing a stricter path resolution could plausibly
      break. Full suite green, 1,280 tests.

## Change: not forty-three columns (`changes/not-forty-three-columns/`)

- [x] T172: `web/static/results.js`: three named views, and the table opens on one
      (`feat-010/AC-74`). Deciding, Hazards, Everything, held as lists of column names and
      intersected with what the answer declares, so a renamed or retired column narrows a view:
      the rest are drawn, nothing is raised, and the table is never left blank.

      **The remembered arrangement is read first and wins.** This decides what a table nobody has
      arranged yet looks like and nothing else, which is the whole difference between a default and
      a redesign of somebody's screen. The existing `remembered()` already tells the two apart:
      what it returns for a search nobody has touched is empty.

      Held in the same stored object as the order, the widths and the hidden set, because it is the
      same kind of thing and a second place to keep a view preference is a second place for it to
      disagree with itself.

      **The view is applied at two moments and no others**: nothing remembered at all, and somebody
      picking one. What is stored is the resulting hidden set, which `remember()` already writes
      whole rather than as a delta; the view's name is one more key beside it and is a label. Never
      recomputed from the name on a later load, because that would put back the thirty-one columns
      somebody had just deviated from, and would let a release that edits a view rearrange a table
      already in use. A stored arrangement carrying no view name is somebody's existing arrangement
      from before this change, and reads as Custom rather than as an invitation to impose a
      default.

- [x] T173: `web/static/results.js`, `app.css`: the control, in the "which columns" group
      (`feat-010/AC-74`, `feat-010/AC-72`). It says which view is in force and how many columns it
      draws, counted against what the answer declares, because "twelve of forty-three" is the fact
      that stops the opening screen being a mystery.

      Hiding or showing one column afterwards drops the view to "Custom" rather than being
      reasserted by it. A view that quietly put a column back after somebody hid it would be a
      control fighting the person using it, and the two ways of hiding a column (the chooser and
      the right-click) both have to do this or one of them lies.

- [x] T174: `web/static/results.js`: the chooser grouped by where a value comes from
      (`feat-010/AC-75`). Five groups under the words the core declares with the columns, which the
      table already reads for the heading tooltips, so the chooser and the tooltip cannot describe
      the same column differently. Each group says how many of its columns are shown and can be
      shown or put away as a group: "all the public data" and "everything I write in myself" are
      the two most common of the thirty decisions this replaces.

      The origin reaches the browser already; nothing new is asked of the server, which is the test
      that this has been designed in the right place.

- [x] T175: `tests/test_web_surfaces.py`: the views and the grouping (`feat-010/AC-74`,
      `feat-010/AC-75`, `feat-010/AC-45`, `feat-010/AC-52`, `feat-010/AC-17`).

      That the table opens on a view and not on forty-three columns. That a remembered arrangement
      is read first and is not overwritten, which is the assertion that keeps this a default, and
      that a stored arrangement with no view name is read as Custom rather than replaced. That
      deviating from a view keeps the rest of it: hide one column of the twelve, reload, and the
      other thirty-one are still hidden, which is the case where the wrong implementation is
      silently and exactly backwards. That one hide or show drops the control to Custom. That a view
      naming a column the answer does not declare draws the rest, raises nothing and leaves no blank
      table. That every declared column is still in the chooser and still in the answer. That the
      group headings are the core's words rather than a second set written here. And that the view
      control and the group toggles are reachable and operable from the keyboard, which
      product-global requires of this whole surface.

      The reload case is in `tests/test_web_browser.py` rather than here, because it is a property
      of a page: it needs real storage, a real reload, and the arrangement read back the way a
      browser reads it. Checked against a deliberately wrong implementation first, and the first
      attempt at breaking it did not fail the test, because after deviating the view is already
      Custom and there is nothing left to recompute from. The implementation that actually loses
      somebody's arrangement is the one where deviating keeps the view's name, and that is what the
      red run had to use.

## Defects: four things found by reading the interface back

- [x] T176: `web/static/fire.js`: the map counts what the table counts (`feat-010/AC-67`). The
      passed and the disappeared were counted over the rows the map can draw, so a search with
      properties that have no coordinates said "22 passed on, hidden" where the table said "737
      passed on, hidden" in the same words. The same words carrying a different number is worse
      than different words would be. Counted over every row the run found now; how many have no
      location is the one thing only this page can say and is still said separately.

- [x] T177: `web/static/results.js`: a picture that has loaded is not asked for again
      (`feat-010/AC-43`). The virtual window replaces every visible row on each redraw and a redraw
      happens on every scroll, so a fresh element each time was a fresh load each time and the
      thumbnails blinked between blank and loaded while somebody scrolled. Kept by property and
      reused; an element can only be in one place at a time, which is exactly true of a row drawn
      once per window.

- [x] T178: `web/static/listing.js`, `app.css`: a merge event's records are readable
      (`feat-010/AC-9`). The detail printed a comma-joined run of thirty-two-character identifiers
      straight into a table cell, where it overflowed and was clipped mid-identifier: neither
      readable nor complete. The count is what somebody wants; the identifiers wrap underneath for
      whoever is chasing one.

- [x] T179: `web/static/search.js`: the builder opens on the areas it is for (`feat-010/AC-2`). The
      view was a fixed point at zoom eleven, which for a search covering a state opens inside one of
      its own polygons: a flat wash of colour with no edge on screen and nothing to say it is a
      shape. Fitted to the drawn shapes when there are any, and left alone when there are not,
      because a search with no geometry has nothing to fit to and a new one has nothing at all.

## Change: say what you count (`changes/say-what-you-count/`)

- [x] T180: `web/static/{searches,results,changes,fire}.js`: every total says what it counts
      (`feat-010/AC-76`). Four screens, four populations, one noun on all of them, which is what
      made four correct numbers read as a fault. No number is recomputed; the words beside it
      change.

- [x] T181: `web/static/common.js`, `{listing,changes,results,fire}.js`: a property with no address
      is named for what is known about it (`feat-010/AC-77`, `feat-010/AC-9`, `feat-010/AC-11`).
      One builder in the shared file, because four surfaces name a property and four copies is how
      one of them keeps printing the identifier. The identifier stays on the page and stays the way
      to ask for the property again; it stops being the thing a person is asked to read.

- [x] T182: `tests/test_web_surfaces.py`: both (`feat-010/AC-76`, `feat-010/AC-77`).

## Change: the page is not the manual (`changes/the-page-is-not-the-manual/`)

- [x] T183: `web/static/common.js`, `app.css`: a disclosure that names what it holds
      (`feat-010/AC-78`). Open the first time somebody is on a surface and closed after, remembered
      per browser like every other view preference. Built once because four surfaces want one.

- [x] T184: `web/static/results.js`, `search.js`: the instructions and the criterion explanation
      (`feat-010/AC-78`, `feat-010/AC-24`). The table's five lines go behind the disclosure. The
      criterion explanation is said once above the list rather than inside each of fifteen.

- [x] T185: `web/static/settings.js`, `web/wire.py`: what is configured and
      what is run become two surfaces (`feat-010/AC-79`, `feat-010/AC-1`). The settings surface
      keeps its address and its subject and the tools move to `/tools`, so no bookmark breaks and
      no redirect is needed: splitting into two new addresses would have cost somebody their
      bookmark for nothing. Nothing about what any section does changes; a thing to run that needs
      something configured says so and links to it, and settings links to the tools. One script
      drawing one of two pages rather than a second file: they share every panel builder, and two
      copies of those would be two places for a setting to be edited in.

      Two things this turned up in its own new page. The tools section repeated the page's lede
      almost word for word, which is the fault this change is about, appearing in the change that
      fixes it. And "needs a model configured above" was true while this was seventh on the settings
      page and is not any more, so it says where instead of pointing at nothing.

- [x] T186: `web/static/searches.js`: a figure that can be zero is drawn at zero (`feat-010/AC-80`).
      A count appearing is harder to notice than a count changing, which is backwards for a strip
      whose job is saying whether anything needs you today. A figure that does not apply to this
      installation at all is still absent.

- [x] T187: `tests/test_web_surfaces.py`, `test_web_contract.py`: the disclosure, the split and the
      strip (`feat-010/AC-78`, `feat-010/AC-79`, `feat-010/AC-80`, `feat-010/AC-1`).

## Change: work the table (`changes/work-the-table/`)

- [x] T188: `api.py`: one operation setting a judgment on several properties (`feat-010/AC-81`).
      In the core rather than a loop in the browser: forty separate writes is forty chances to end
      up half done with no record of which half, and product invariant 5 says both surfaces reach
      every capability. Answers with how many were changed.

- [x] T189: `cli/main.py`, `cli/render.py`, `web/app.py`: the same from both surfaces
      (`feat-010/AC-81`, `feat-010/AC-22`). `--json` and a stable exit code, like everything else.

- [x] T190: `web/static/results.js`, `app.css`: selecting a range and acting on it
      (`feat-010/AC-81`, `feat-010/AC-34`, `feat-010/AC-48`, `feat-010/AC-6`). Shift with a press
      for a range from the pointer, shift with the arrows from the keyboard. The dialog asks once
      and says how many. The reason is written to each of them. The same control undoes the batch.
      A batch that does not entirely succeed marks the rows that were not written, keeps what was
      being set on them, and never shows them as saved, which is AC-6 over forty rows.

- [x] T191: `web/static/search.js`, `app.css`: a panel says when it is unsaved (`feat-010/AC-82`).
      Four panels stay four, because they write four different parts of a definition and one button
      over all of them would write parts nobody touched, which AC-3 forbids. Leaving the page with
      any of them dirty is refused until it is confirmed.

- [x] T192: `tests/test_web_parity.py`, `test_cli_operations.py`, `test_web_surfaces.py`: the batch
      from both surfaces, its refusal, and the unsaved warning (`feat-010/AC-81`, `feat-010/AC-82`).

## Come back to it (`changes/come-back-to-it/`)

- [x] T193: `api.py`: what is under way becomes part of the overview (`feat-010/AC-83`,
      `feat-010/AC-84`, `feat-001/AC-31`). Read from the store, so a pass started from a terminal or
      by the scheduled job is in the answer and a restarted server does not lose it. Widening the
      overview rather than adding an operation is what satisfies invariant 5 without a new command:
      `overview` is already on both surfaces and already takes `--json`. It reports running searches
      today and reports every pass after this.

- [x] T193a: `api.py`: starting a pass already under way is refused, in the core (`feat-010/AC-85`,
      `feat-010/AC-14`). Computed from what the store says, so the refusal holds across processes
      and the browser will not start an extraction while the nightly job is running one. Names what
      is running and when it began. The one-at-a-time decision leaves `web/runs.py`, which is where
      AC-14 says it should never have been.

- [x] T194: `web/runs.py`, `web/app.py`, `web/wire.py`: the tracker records to the store instead of
      to a dictionary, and one endpoint says what is running (`feat-010/AC-83`, `feat-010/AC-84`).
      The per-process memory goes away rather than being kept alongside, because two answers to one
      question is how they come to disagree.

- [x] T195: `cli/main.py`, `cli/render.py`: a long command records itself the same way
      (`feat-001/AC-31`, `feat-010/AC-83`). What it prints is unchanged. This is the half that makes
      the nightly job visible in a browser, which is the whole point of putting it in the store.

- [x] T196: `web/static/settings.js`, `web/static/searches.js`: asking on load and rejoining
      (`feat-010/AC-83`). The tools surface asks about each of its passes; the list of searches keeps
      asking while a run is under way instead of drawing one frozen badge. Nothing is drawn when
      nothing is running.

- [x] T197: `web/static/common.js`, `app.css`: the marker every screen carries (`feat-010/AC-84`).
      One ask on one schedule in the shared frame, not one per surface. It names what is running,
      reaches the screen showing its progress, and removes itself when the pass ends without a
      reload.

- [x] T198: `web/static/common.js`, `web/static/settings.js`: a pass that stopped without finishing
      is shown as that (`feat-010/AC-83`). Never as running and never as completed. The browser
      reads the store's own answer rather than deciding it.

- [x] T199: `tests/test_web_surfaces.py`, `tests/test_web_parity.py`, `tests/test_cli_operations.py`,
      `tests/test_web_background.py`: rejoining after a reload, the marker appearing and going away,
      a terminal-started pass visible in the browser, and a killed pass reading as stopped
      (`feat-010/AC-83`, `feat-010/AC-84`, `feat-010/AC-13`, `feat-001/AC-31`).

## What the model made of it (`changes/what-the-model-made-of-it/`)

- [x] T200: `store/core.py`: summarise many assessments in one query (`feat-010/AC-86`). How many
      concerns, the worst severity, and what each was assessed from, for a list of properties. One
      query rather than one per row: a table of a thousand asking per row is the shape that turns a
      column into a wait.

- [x] T201: `api.py`: three values per row in the results answer (`feat-010/AC-86`). The count, the
      worst severity, and whether it is stale. Not the prose: the answer is already 2.7MB for this
      workspace, and sending 155 assessments' text on every page load to show what is usually one of
      them is the wrong trade.

- [x] T201a: `export/columns.py`: the column joins the declaration and not the default sheet
      (`feat-010/AC-86`). Declared, so the table sorts, filters, hides and chooses it with no special
      case; out of `DEFAULT`, so feat-011/AC-1's header test is untouched and that feature needs no
      change. Forty-three declared and thirty-two in the default sheet is already the arrangement.

- [x] T202: `web/static/results.js`, `app.css`: the column (`feat-010/AC-86`). Marked when anything
      is serious, marked differently when stale, and empty both when nothing was raised and when
      nothing was assessed, because those are different facts and neither is a zero. An ordinary
      column otherwise: hides, returns from the chooser, sorts and filters.

- [x] T203: `web/static/results.js`: a sixth origin in the chooser (`feat-010/AC-86`,
      `feat-010/AC-75`). What a model made of a property is not a reported value, a computed one, one
      read out of a description, public data, or the person's own note.

- [x] T204: `web/static/results.js`, `app.css`: pressing the count expands the row
      (`feat-010/AC-87`, `feat-010/AC-81`). The count and not the row: a press on a row already moves
      the cell focus, and with shift extends the batch range, and a third meaning would have taken
      one of those away. The account,
      each concern with its evidence, what the pictures showed, what to check, and what could not be
      told. Fetched when opened. The virtual window already measures rows and builds its offsets from
      what it measured, so a taller row needs one line in the measurement to count the detail with
      its parent rather than a new mechanism.

- [x] T205: `web/static/results.js`, `app.css`: it is visibly the model's (`feat-010/AC-87`,
      `feat-013/AC-6`). Labelled and dated, next to but never inside the person's own columns, and a
      stale assessment says so before its content rather than after it.

- [x] T206: `tests/test_web_surfaces.py`, `tests/test_assessment.py`: the column's three states, the
      summary query, and that nothing drawn here is written into an annotation (`feat-010/AC-86`,
      `feat-010/AC-87`).

- [x] T207: `tests/test_web_browser.py`: the row opens and closes in a real browser and the table
      below it still measures (`feat-010/AC-87`, `feat-010/AC-53`). The one claim about this that
      only a real browser can check, and the table's own height rule is exactly what an expanding
      row threatens.
