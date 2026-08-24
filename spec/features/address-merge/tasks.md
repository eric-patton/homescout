# Tasks — Address matching and merge review (feat-006)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

`[P]` marks tasks that can be worked in any order against each other. A test written against code
that does not exist yet is not one of them.

## Reading an address

- [x] T1: `merge/address.py`: parse one address into its parts, expand and re-abbreviate street
      types and directionals, fold a number suffix back into the number, and treat `000` / `TBD` as
      no number at all (D-2, M-2, M-4, AC-2).
- [x] T2: A parser that raises leaves a row with no address key rather than no row, and an
      address longer than the bound is truncated before parsing rather than after (D-2, D-14, M-3,
      AC-22).
- [x] T3: The address key: number, street name, unit and ZIP, and nothing weaker (D-3, AC-1).
- [x] T4: `tests/test_merge_address.py`: the brief's own example pair, the number-suffix split, the
      land placeholders, the parser refusing, and every real formatting difference the corpus
      contains (AC-1, AC-2, AC-3, AC-22).

## Comparing two rows

- [x] T5: `merge/signals.py`: what agreed, what conflicted, and what could not be checked, in terms
      a person can act on (D-4, D-5, AC-9).
- [x] T6: Coordinates: distance, the configurable tolerance defaulting to the brief's fifty metres,
      and values that are obviously wrong treated as absent (D-8, AC-6, AC-7).
- [x] T7: Parcel numbers: normalized before comparison, decisive in both directions when both sides
      have one, and neither confirming nor ruling out when only one side does (AC-4, AC-5).
- [x] T8: `merge/compare.py`: the outcome table, with `ambiguous` the easy one to reach (D-7, AC-8).
- [x] T9: `tests/test_merge_compare.py`: every scenario in the spec, with the spec's own values
      (AC-1, AC-3, AC-4, AC-5, AC-6, AC-8).

## The queue and the decisions

- [x] T10: Schema version 5: `merge_decisions`, append-only, keyed by the sorted pair (D-9). Record
      the change in feat-001's manifest.
- [x] T11: `store.record_merge_decision` and `store.merge_decisions`, with the latest decision for a
      pair winning (D-9, AC-11).
- [x] T12: `merge/queue.py`: the real review queue behind the port `matches.py` already declares,
      backed by the store (AC-9, AC-10, AC-23).
- [x] T13: A recorded decision is consulted before any automatic signal, in both directions, and
      keeps its pair out of the queue forever (D-9, AC-12, AC-13).
- [x] T14: Contradictions: new evidence against a recorded decision is recorded and surfaced, and
      changes nothing (D-10, AC-14).
- [x] T15: `tests/test_merge_decisions.py`: a decision that contradicts the automatic conclusion in
      both directions, a pair that never returns, and a contradiction that surfaces without acting
      (AC-11, AC-12, AC-13, AC-14).

## The pass

- [x] T16: `merge/candidates.py`: buckets by address key and by rounded coordinate cell, so a run is
      bounded by bucket size rather than by its own size (D-6, the performance requirement).
- [x] T17: `merge/pass_.py`: compare, merge what is `matched`, queue what is `ambiguous`, leave both
      records intact until a person decides (AC-10, AC-19).
- [x] T18: Connected components: every pair compared before anything is merged, a component
      containing a `distinct` pair queued whole rather than merged, and a row matching more than one
      existing record queued rather than joined (D-13, AC-20, AC-21).
- [x] T19: The run loop runs the pass after recording observations, and the digest reports how many
      pairs are waiting (AC-23). Record the changes in feat-003's manifest.
- [x] T20: `tests/test_merge_pass.py`: the corpus reducing to the right number of properties with
      no wrong merge, several orderings agreeing, a chain with a contradiction in it queued whole,
      and a single-source installation needing no merge at all (D-13, AC-19, AC-20, AC-21).

## What the store already guarantees

- [x] T21: `tests/test_merge_store.py`: a merge-and-undo cycle leaving every source row byte for
      byte as it was, both annotations intact, and the provenance naming every row and its signal
      (AC-15, AC-16, AC-17, AC-18).

## Finishing

- [x] T22 [P]: The performance test: 5,000 rows, comparisons near-linear rather than quadratic,
      marked slow (the performance requirement).
- [x] T23 [P]: Document merging in the README: what merges, what gets asked, and how to answer.
- [x] T24: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T25: `/spec-flow:converge`, then the manifest stamp.
