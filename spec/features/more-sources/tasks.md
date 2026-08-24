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
