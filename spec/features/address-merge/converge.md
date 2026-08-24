<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — Address matching and merge review

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-24

baseline: spec sha256:689a73f74264 · plan sha256:ffc7f3d0bfd3 · tasks sha256:0d8def6698c9

implemented: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13,
AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23

- opened gap-001 [unrequested] code:"a street type or a compass point that disagrees is neither a
  match nor a mismatch"

  Evidence: `merge/address.py` `_street_name` and `key`, `merge/signals.py` `_addresses`. The
  address key is built from the house number, the street name, the unit and the postal code, and
  deliberately not from the street type or the directional. A pair that agrees on everything in the
  key and disagrees about the street type is `matched`; the disagreement is reported as something
  that could not be checked rather than as a conflict.

  AC-2 asks for normalization so that "abbreviated and expanded street types, directionals, and
  casing differences do not affect the outcome". That covers `Rd` against `Road`. It does not cover
  `Ave` against `St`, and the corpus has that: one house, one price, one floor area, coordinates
  thirty-eight metres apart, called an avenue by one source and a street by two.

  Why it is built this way: the corpus contains four such pairs out of forty-six. Treating a
  differing street type as a mismatch leaves all four as permanent duplicates, silently. Treating it
  as corroboration costs one thing, and the corpus shows exactly what: `612 E 17th Ln` and
  `612 E 17th St` share a key and are two different houses. They are not merged, because their
  coordinates are a hundred and two metres apart and the coordinate check catches them. That is the
  trade, and it is the right way round: the failure mode of this design is a question, and the
  failure mode of the other is a wrong merge nobody sees.

  Routed: a human decision, and the recommendation is to legitimize it as an addition to AC-2 rather
  than remove it. Raised in the pre-build check as C-2 before any of it was written, so it is a
  choice on the record rather than something the code drifted into. Recorded, not self-applied.

- opened gap-002 [partial] spec:"AC-4 When both rows carry a parcel number, that comparison decides
  the outcome" and "AC-5 When exactly one row carries a parcel number, it neither confirms nor rules
  out a match"

  Evidence: `merge/signals.py` `_parcels` and `merge/compare.py` `decide`, both built and both
  tested. What is missing is not the code: **no source supplies a parcel number.** Zero of the 140
  rows in the corpus carry one, from any of the three shipped adapters, because none of them returns
  it in a search response.

  So the strongest signal the brief names has never once run outside a test, and will not until a
  source supplies one or somebody adds a per-property detail fetch. Both criteria are satisfiable
  only against rows constructed for the purpose, which is what their tests do.

  Why it is not a contradiction: the behavior the criteria describe is exactly what the code does
  when the input exists. Nothing here is wrong; the input is absent.

  Routed: no remediation task, because there is nothing to build in this feature. Recorded so that
  the parcel path is not read as load-bearing when it has never fired, and so that the first
  investigation of a bad merge does not start by looking at it. Raised in the pre-build check as
  C-1.

verdict: open 2 (missing 0, partial 1, contradicts 0, unrequested 1)

## What was checked and found clean

- **The corpus is the test, and it came out of the product.** 140 rows from three real sources over
  one town, 46 keys shared by two or three of them, committed with the properties made up and every
  disagreement between the sources exactly as it arrived. It reduces to 73 properties with 44
  merges and 10 questions, and every one of the ten is a judgment a person can make and this code
  cannot: land parcels with no address, and houses whose sources put them a hundred metres apart.
- **Matches chain, and a chain with a contradiction in it does not merge.** The pre-build check
  raised this as Blocking against the first draft of the plan, which compared pairs and merged them
  one at a time. Nothing is merged now until every candidate pair has been compared, the matches
  form connected components, and a component merges only when **every** pair inside it agreed. Order
  independence is then structural rather than careful, and the spec's duplex edge case and its
  "matches more than one existing record" criterion land in the same place because they are the same
  situation.
- **A person's answer outranks the signals in both directions, and is tested that way.** A decision
  that agrees with the automatic conclusion proves nothing about whose answer wins, so both tests
  drive a decision that contradicts it. The decisions are in the database rather than in a queue
  object, and a test closes and reopens the store to prove it.
- **The questions are derived and the answers are stored.** A stored queue would go stale, still
  asking about two rows whose evidence has since changed; a stored answer must never go stale,
  because it is a person's judgment. So the queue works its own contents out from what is recorded,
  which is also why `homescout matches list` in a fresh process finds what last night's run queued.
- **Nothing this feature does can destroy anything.** Merging is the store's `supersede`, which
  writes a new record over the old ones and leaves them where they were. A test merges the whole
  corpus and undoes all forty-four merges, and every one of the 140 source rows is byte for byte
  what it was, with both annotations still on the records they described.
- **Five thousand rows are not compared against each other.** 12.5 million possible pairs, and the
  pass looks at under twenty thousand of them, in three and a half seconds, because rows are
  bucketed by address key and by rounded coordinate cell. A first run that fills the queue with six
  hundred questions holds all six hundred rather than capping, which is the spec's own edge case.
- **The parser was measured before it was designed around.** `usaddress` reads the Southwest's
  `S Avenue B` as a directional with no name at all, and raises outright on real land descriptions.
  Both are worked around rather than discovered later: the street name is derived by subtraction
  rather than read from the label, and every call is wrapped so a row that cannot be parsed keeps
  its text and loses only its key.
