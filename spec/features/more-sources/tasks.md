# Tasks — Zillow and Redfin sources (feat-005)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

`[P]` marks tasks that can be worked in any order against each other. A test written against code
that does not exist yet is not one of them.

## Shared

- [x] T1: `sources/boxes.py`: halve a bounding box along its longer side, and refuse to halve one
      already below the minimum span (D-3, AC-3, AC-5).
- [x] T2: `tests/test_sources_boxes.py`: the halves cover the original exactly and overlap nowhere,
      repeated halving stays roughly square, and a box at the floor cannot be cut (D-3).

## Zillow

- [x] T3: `sources/zillow/queries.py`: the request body, the endpoint as configuration with an
      environment override, and the filter table the body is built by walking (D-6, D-7, M-1).
- [x] T4: `sources/zillow/normalize.py`: one `hdpData.homeInfo` to one `ListingFields`, with the
      site's own payload retained (AC-10).
- [x] T5: `sources/zillow/__init__.py`: capabilities, one request per box reading the map results,
      and the ceiling walk cutting by box (D-2, D-4, AC-1, AC-2).
- [x] T6: A box over the ceiling is subdivided and the union returned with duplicates removed;
      a box still over after the smallest permitted cut is truncated, naming the ceiling (AC-3,
      AC-5).
- [x] T7: `tests/test_sources_zillow.py`: against recorded responses, the request built from the
      declaration, the normalization, subdivision past 500 distinct properties, pacing, and
      truncation (AC-1, AC-2, AC-3, AC-4, AC-5, AC-10).

## Redfin

- [x] T8: `sources/redfin/queries.py`: the query string, the endpoint as configuration, the filter
      table, and the box rendered as a `poly` ring (D-6, D-7, M-3).
- [x] T9: `sources/redfin/normalize.py`: one CSV row to one `ListingFields`, with a column that
      cannot be read named rather than silently dropped (AC-10, the changed-columns edge case).
- [x] T10: `sources/redfin/__init__.py`: capabilities, one download per box, the inferred total, and
      the row cap reported as truncation (D-5, AC-1, AC-9).
- [x] T11: A response that is not a CSV download at all is `unavailable` with what came back named;
      the site's standing notice about withheld listings is carried on every result (D-8, AC-7).
- [x] T12: `tests/test_sources_redfin.py`: against recorded responses, the ring, the filters, the
      inferred total and its split, the cap as truncation, the notice on every result, and each
      shape of refusal (AC-1, AC-7, AC-9, AC-10).

## Together

- [x] T13: Register both in the source registry, and nothing else (AC-12, non-negotiable 9).
- [x] T14: The shared adapter-interface tests run against all three adapters rather than one (AC-1).
- [x] T15: `tests/test_sources_no_core_change.py`: neither new package imports the store, the run
      loop or the merge layer, and no core module imports either of them (D-11, AC-12).
- [x] T16: A run naming all three sources completes with one of them unavailable, is recorded as
      degraded, and marks nothing as disappeared (AC-8, AC-12).
- [x] T17: Neither adapter mentions a token, a password, or an authorization header (AC-11), and
      neither fetches a preview whose scheme is not `http` or `https` (D-12).

## Finishing

- [x] T18 [P]: `tests/test_sources_live.py` gains one real query against each site, marked slow
      (M-1, M-3, and the reason both are configuration).
- [x] T19 [P]: Record the narrowing of AC-7 in this feature's own notes, with the measurement behind
      it (D-8, M-5).
- [x] T20 [P]: Document both sources in the README: what each accepts, what each caps at, and what
      Redfin's notice means.
- [x] T21: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T22: `/spec-flow:converge`, then the manifest stamp.

## Not built: a picture for a house only Redfin has (`changes/a-picture-for-a-house-only-redfin-has/`)

- [x] T-picture-0: measured, built, and taken back out (`feat-005/AC-11`). "Is there any way to get
      the pictures from Redfin listings (or maybe just these listings are having issues?)"

      They were not having issues. All six named were carried by this source alone, and this
      source's download has no photograph in it. The property's own page does, in the standard tag,
      at a better size than either other source hands over, and every piece of it worked: the
      parser, the host check, nine offline tests, six real properties fetched end to end.

      Then it was pointed at the real site through the tool's own session and every request came
      back `403`. Measured across three properties: the page refuses
      `homescout/0.1.0 (personal listing monitor)`, refuses a bare `homescout/0.1.0`, refuses a
      request naming nobody, and serves Chrome. The CSV endpoint answers `200` to that same agent
      throughout. The site hands its data to a program that admits to being one and refuses that
      program the page a person reads.

      The only way through is to claim to be a browser. That is the single thing `politeness.py`
      is built to make impossible, and a thumbnail does not buy it. Leaving the code in to fail
      quietly would have been worse than not writing it: twelve properties, four attempts each with
      backoff, nightly, against a site already refusing us, which is the exact shape of traffic that
      gets a client blocked.

      Reverted rather than disabled, so there is no dead path to switch back on by accident. What is
      kept is the measurement, on `fetch_preview` and in the change folder, in place of the older
      note that explained the absence with a judgment about what a photograph is worth. That
      judgment was wrong and it was the reason nobody looked. The fact is not wrong.

## Defect: a search for farms was a search for vacant land

- [x] T-kind-1: `sources/redfin/queries.py`: kind is not declared and not sent
      (`feat-005/AC-14`, `feat-005/AC-1`).

      Found by pulling a thread. Six properties had no photograph, which read as a picture problem,
      and every one of them turned out to be raw land that the search had never asked for.

      This source's property-type parameter takes codes for house, condo, townhouse, multi-family,
      land, other, manufactured and co-op. **There is no code for a farm.** So `farm` had been
      mapped onto land as the nearest thing, and a search for `[single_family, farm]` went out as
      `uipt=1,5`, which is this site's way of saying houses and vacant lots.

      The parameter itself works, which is what made this invisible. Measured on one box: asked for
      houses, three hundred and forty-nine rows and not one lot; asked for houses and farms, four
      lots. Nothing was broken at the site's end and nothing failed. The adapter asked a question
      nobody had asked and then declared it had narrowed by kind, so the caller did not check.

      Kind now follows lot size, three fields up in the same file and undeclared for the same
      reason: a narrowing this source cannot express honestly is one the caller has to do itself.
      The declaration and the request are one set by construction, so not-claimed and not-sent
      cannot drift apart.

      The cost is real and worth naming. This source has the lowest cap of the three, and it now
      spends some of it on condos and mobile homes that are discarded here. A filter that quietly
      means something else is worse than a filter that costs rows.

      The table of codes is kept rather than deleted, with the note on it, because the mapping is
      true about the site and the next person to reach for it should find the reason rather than
      write the table again.

- [x] T-kind-2: `tests/test_sources_redfin.py`: two tests replaced, because they agreed with it
      (`feat-005/AC-14`). One asserted that `uipt` was exactly `1,5`, which is the bug written down
      as an expectation: it reads as the adapter speaking the site's vocabulary, which it was, while
      asking for something else. Replaced by what is now true, plus the collision itself asserted,
      so that if this site ever grows a code for a ranch there is a test that says where to look.

- [x] T-kind-3: `tests/test_run_loop.py`: the other end of the contract (`feat-005/AC-14`,
      `feat-003/AC-7`). A source that says it did not narrow by kind, and a run that drops the lot
      and the mobile home and keeps the house and the ranch. Beside it, the rule that makes the fix
      safe: a property whose kind nobody recorded is kept. Dropping those would trade six lots for
      an unknown number of houses, which is the worse error by a long way.

- [x] T-kind-4: measured against the real site before and after, on one box in the east mountains.
      Realtor was checked too and is clean: it honours the same filter exactly, and the wrong-typed
      rows in the workspace all came from a `portales` test search that carried no kind filter.
