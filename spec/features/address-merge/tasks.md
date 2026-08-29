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

## Defect: the matching key undid the rule about units

- [x] T-unit-1: `merge/address.py`, `merge/signals.py`: a unit on one side only reaches a person
      (`feat-006/AC-24`, `feat-006/AC-3`, `feat-006/AC-9`).

      The module says it in its own docstring: "A unit on one side only is not a disagreement,
      because one source breaking it out and another folding it into the line is the ordinary case."
      The check at the top of `_addresses` honours it and requires a unit on both sides before
      calling a conflict. Then the matching key, four lines down, is built from number, street,
      unit and postal code, so a unit on one side made the keys differ and the comparison returned
      `disagreed` anyway. The rule was stated, implemented, and then undone by the key.

      `disagreed` is the expensive place for this to land. It routes to `unrelated`, which is the
      one outcome that is never queued and never shown, so the pair does not surface anywhere: not
      as a merge, not as a question, not as a count in the digest. It is the only silent branch in
      the table and this was falling into it.

      Measured on the real workspace: the review page held **two** pairs. Sixty-seven more were
      sitting in `unrelated`, metres apart, at identical prices, one site carrying a lot number and
      the other not. `103 Vail Loop` against `103 Vail Loop Lot 21`, seven hundred thousand dollars,
      thirty-six metres, twice in the list. The queue now holds seventy-one.

      The key keeps the unit, because it is also the blocking key and two units of one building
      should not share a bucket. A second key without the unit tells the two failures apart: keys
      that differ on number or street are a contradiction, keys that differ only on a unit one side
      omitted are something that could not be checked. `unknown` rather than `agreed`, so the pair
      goes to a person instead of being merged, which is what was asked for.

- [x] T-unit-2: `tests/test_merge_compare.py`: the case the existing test is named after
      (`feat-006/AC-24`). `test_a_unit_on_one_side_only_is_not_a_disagreement` puts `Unit B` on both
      sides, once in the line and once in the field, so it proves the two spellings agree and says
      nothing about a unit only one source carries. That gap is why this survived. The new test uses
      the shape the real rows arrive in, one source's own unit field against nothing, and is checked
      against the unfixed comparison.

      Two guards beside it, because the risk of this change is over-reach in the other direction: a
      different house number on the same street stays `unrelated`, and two lot numbers that differ
      stay `distinct`. Widening what counts as a question must not widen what counts as the same
      house, or a duplicate in a list is traded for a price history that is fiction.

- [x] T-unit-3: measured end to end against a copy of the real workspace, before and after, through
      `run_pass` and the same `/api/matches` the review page reads.
