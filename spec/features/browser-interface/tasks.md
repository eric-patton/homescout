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
