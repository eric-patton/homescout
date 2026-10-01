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

## Defect: the review page kept the first list it worked out

- [x] T-queue-1: `merge/queue.py`, `store/core.py`, `merge/pass_.py`: a queue works its questions
      out again whenever the store has moved since it last did (`feat-006/AC-9`, `feat-006/AC-23`).

      The questions are derived rather than stored so that they can never be stale, and then the
      queue derived them once per object and kept them. That is harmless for a command, which lives
      for one invocation. The browser interface holds one queue for as long as the server is up,
      and every run writes through a connection of its own: one started from the page goes through
      `api.open_beside`, and the scheduled one is another process. Neither can reach the
      interface's queue to clear it, so the review page went on showing the pairs from whenever the
      server started.

      Measured on the real workspace on 2026-09-12, with a server up since 2026-09-10: 246 pairs on
      the review page, 277 worked out fresh from the same database.

      `store.comparison_mark` is the newest snapshot, the newest run and when the last one finished,
      and the newest listing event, which every merge and every undo of one writes. The queue
      remembers it when a pass fills it and compares before each read. The pass tells the queue
      again at the end, after its own merges, so a run's own merges do not read as somebody else's
      change and cost the comparison a second time.

- [x] T-queue-2: `tests/test_merge_pass.py`: a queue read before a run on another connection sees
      what that run queued (`feat-006/AC-9`), checked against the unfixed queue, where it fails.
      Beside it a guard for the other direction (`feat-006/AC-23`): with nothing moved, a second
      read does not run the comparison again, because the front page counts the queue on every
      visit and the interface serves one request at a time.

- [x] T-queue-3: measured against a copy of the real workspace: 277 pairs on the first read, a
      second read in about a millisecond (the check itself is a hundredth of one), and after a merge
      made through a second connection the next read works the list out again and the merged pair
      is gone (276). The slow merge suite is unchanged.

## Defect: a numbered highway had no street name

- [x] T-highway-1: `merge/address.py`: a road whose whole name is a number keeps its type, once, in
      front (`feat-006/AC-1`, `feat-006/AC-2`). `Highway 445`, `Hwy 445 Hwy` and `Highway 445 N`
      all read as `hwy 445`.

      Found on a real run over eight Louisiana houses on 2026-09-30. Realtor and Zillow wrote
      `51131 Highway 445` and Redfin wrote `51131 Hwy 445 Hwy`. The name rule strips every street
      type unless that leaves nothing, and here it left `445`; then the land rule ("a name made only
      of subdivision words or numbers is no name") read a bare number as no name. So all three rows
      had no key, one house stayed three records, and nothing was queued, because a row with no key
      is never matched on coordinates alone (AC-8). Three of the eight houses were on highways.
      New Mexico rarely showed it because its listings write `NM Highway 236`, and the `nm` keeps a
      name standing.

      The type goes back only when the name would otherwise be one bare number, and only when the
      line carried a type at all, so a parcel description (`Block 2 Lot 3`) still has no name.

- [x] T-highway-2: `tests/test_merge_address.py`: the three real spellings of three highway houses,
      and a trailing direction, each one key (`feat-006/AC-1`, `feat-006/AC-2`). Checked against the
      unfixed code, where all four cases fail. The corpus and land tests are unchanged and green.

      Not covered and not changed: the parser reads `12 Road 4250` with `4250` as a unit, so
      `Road 4250` and `Rd 4250` still key apart. That is the parser's reading rather than this rule,
      it was so before, and no source in the corpus writes a road that way.

## Defect: a record merged this run was invisible to the review queue

- [x] T-standin-1: `store/core.py` `merged_stand_ins`, `merge/pass_.py` `candidates_from`: a live
      record a merge has written, and no run has observed yet, is compared through the newest
      snapshot of what was merged into it (`feat-006/AC-9`).

      Found on a live run on 2026-09-30. Realtor and Zillow put 51131 Highway 445 at one spot and
      merged; Redfin put it 316 metres away, an ambiguous pair, and the pair never reached the
      queue. Matching reads each property's newest snapshot, and a merge writes a record with no
      snapshot, because snapshots are what runs observe. So until the next run that record was
      not a candidate at all, and any question its merge left open waited for a run that, for a
      paused search, might never come. On a copy of the workspace the same day, 16 merged records
      were in that state; finding them costs 8 ms.

      A stand-in, not a snapshot: nothing is written, and the snapshot used still names the record
      it was taken of. The next run gives the merged record its own and the stand-in stops being
      read.

- [x] T-standin-2: `tests/test_merge_pass.py`: the three real rows for 51131 Highway 445, two that
      merge and one too far away, and the queue holding the pair between the merged record and the
      third straight after the pass (`feat-006/AC-9`). Checked against the unfixed pass, where the
      queue is empty.
