## Why

The brief calls this the messiest part of the project, and the reason is asymmetry: failing to
merge two rows costs a duplicate line in a table, while wrongly merging them fuses two properties
into one record whose price history is fiction. Everything in this spec follows from taking that
asymmetry seriously. Merge where the evidence is strong, ask where it is not, keep the provider
rows underneath so any decision can be inspected and undone, and never overrule a person. The
problem brief is in `research.md`.

## Vocabulary used in this feature

- A **match outcome** is this feature's verdict on a pair of rows: `matched`, `ambiguous`, or
  `distinct`. Only `matched` merges. `ambiguous` goes to a person.
- The **review queue** holds every `ambiguous` pair awaiting a person's decision.
- A **merge decision** is a person's recorded instruction to join two records or to keep them
  apart. It outranks every automatic signal and persists indefinitely.
- **Provenance** is the record of which provider rows a canonical listing was built from and which
  signal justified joining them.

## User stories

- As the person running searches, I want a house listed on three providers to appear once, so that
  my table is a list of properties rather than a list of listings.
- As the person running searches, I want the tool to ask me when it is unsure rather than pick, so
  that I never discover months later that two properties have been sharing a price history.
- As the person running searches, I want my merge and separation decisions honored forever, so that
  I answer each question exactly once.
- As the person running searches, I want to see why two rows were joined, so that I can tell a
  correct merge from a plausible-looking mistake.
- As the person running searches, I want to undo a merge without losing my notes on either
  property, so that correcting a mistake is cheap.
- As someone searching for acreage, I want land listings with no street address handled, not
  dropped, so that the properties I actually care about are not the ones the tool cannot represent.

## Behavior & scenarios

- **Scenario: the same house, formatted differently**
  - Given two provider rows reading `1747 S Roosevelt Rd 10 1/2` and
    `1747 South Roosevelt Road 10 1/2`, in the same ZIP code
  - When they are compared
  - Then the outcome is `matched`, they resolve to one canonical listing, and the provenance names
    the normalized address and ZIP as the justifying signal

- **Scenario: a parcel number settles it**
  - Given two provider rows whose addresses are formatted so differently that normalization does
    not align them, but which carry the same parcel number
  - When they are compared
  - Then the outcome is `matched`, and the provenance names the parcel number as the justifying
    signal

- **Scenario: a parcel number rules it out**
  - Given two provider rows with identical normalized addresses and ZIP codes but different parcel
    numbers
  - When they are compared
  - Then the outcome is `distinct`, and no merge occurs despite the address agreement

- **Scenario: coordinates confirm a probable match**
  - Given two provider rows with the same normalized street and ZIP, no parcel numbers, and
    coordinates thirty metres apart
  - When they are compared
  - Then the outcome is `matched` and the provenance names both the address and the coordinate
    agreement

- **Scenario: coordinates contradict an address match**
  - Given two provider rows with the same normalized street and ZIP but coordinates several
    kilometres apart
  - When they are compared
  - Then the outcome is `ambiguous`, both records remain separate, and the pair enters the review
    queue with the contradiction stated

- **Scenario: a unit number is not noise**
  - Given two provider rows with the same street and ZIP but different unit designations
  - When they are compared
  - Then the outcome is `distinct`, because different units are different properties

- **Scenario: land with no street address**
  - Given two provider rows for unimproved land, neither carrying a street address, with
    coordinates twenty metres apart and matching lot size
  - When they are compared
  - Then the outcome is `ambiguous` rather than `matched`, and the pair enters the review queue,
    because coordinates alone on a large parcel are not sufficient evidence

- **Scenario: a person resolves an ambiguous pair**
  - Given a pair in the review queue
  - When a person records a decision to merge them, or to keep them apart
  - Then the decision takes effect immediately, the pair leaves the queue, and the decision is
    stored

- **Scenario: a recorded decision survives later runs**
  - Given a person has decided that two records are the same property
  - When any number of later runs observe both, including runs where the automatic signals would
    have said `distinct`
  - Then they remain merged, and the pair does not return to the review queue

- **Scenario: a recorded separation survives later runs**
  - Given a person has decided that two records are different properties
  - When any number of later runs observe both, including runs where the automatic signals would
    have said `matched`
  - Then they remain separate, and the pair does not return to the review queue

- **Scenario: new evidence contradicts a person's decision**
  - Given two records a person decided are the same property
  - When a later run observes different parcel numbers for them
  - Then the person's decision still stands, and the contradiction is surfaced for review rather
    than acted on

- **Scenario: undoing a merge**
  - Given a canonical listing built from provider rows that were merged
  - When the merge is undone
  - Then the original records exist again, each backed by the provider rows it originally had, no
    provider row was altered, and every annotation that existed before the merge still exists with
    its original content attached to the record it originally described

- **Scenario: a third provider joins an existing record**
  - Given a canonical listing already built from two providers' rows
  - When a third provider's row matches it
  - Then it joins the same canonical listing, and the provenance grows to name all three rows

- **Scenario: provenance is inspectable**
  - Given any canonical listing
  - When its provenance is read
  - Then it names every provider row underneath it, the signal that justified each join, and
    whether the join was automatic or decided by a person

## Acceptance criteria

- [ ] AC-1: Two rows whose normalized street addresses and ZIP codes agree, with no contradicting
      signal, produce `matched`. A test uses the brief's own example pair.
- [ ] AC-2: Address normalization is applied before comparison, so that abbreviated and expanded
      street types, directionals, and casing differences do not affect the outcome.
- [ ] AC-3: A fractional or lettered unit designation is preserved through normalization and is
      compared. Rows differing only in unit designation produce `distinct`.
- [ ] AC-4: When both rows carry a parcel number, that comparison decides the outcome: agreement
      produces `matched` regardless of address, disagreement produces `distinct` regardless of
      address.
- [ ] AC-5: When exactly one row carries a parcel number, it neither confirms nor rules out a
      match, and the outcome is decided by the remaining signals.
- [ ] AC-6: Coordinates within the configured tolerance confirm an address-based match. Coordinates
      outside it, when an address match otherwise held, produce `ambiguous` rather than `matched`
      or `distinct`.
- [ ] AC-7: The coordinate tolerance is configurable, and its default is the value named in the
      brief.
- [ ] AC-8: Rows with no usable street address are never `matched` on coordinates alone. The
      strongest outcome available to them without a parcel number is `ambiguous`.
- [ ] AC-9: Every `ambiguous` pair enters the review queue with the specific signals that agreed
      and the specific signals that conflicted, in terms a person can act on.
- [ ] AC-10: A pair in the review queue leaves both records intact and separate until a person
      decides. Nothing is merged provisionally.
- [ ] AC-11: A person's decision to merge or to separate is recorded durably and applied
      immediately.
- [ ] AC-12: A recorded decision is re-applied on every subsequent run and outranks every automatic
      signal, in both directions. A test asserts this for a decision that contradicts what the
      automatic comparison would conclude.
- [ ] AC-13: A pair with a recorded decision never returns to the review queue.
- [ ] AC-14: New evidence that contradicts a recorded decision is surfaced as a flagged
      contradiction and does not alter the merge state.
- [ ] AC-15: No provider row is modified, deleted, or hidden by any merge, separation, or undo. A
      test compares provider rows before and after a merge-and-undo cycle for exact equality.
- [ ] AC-16: Undoing a merge restores the records that existed before it, each backed by the same
      provider rows it had beforehand.
- [ ] AC-17: After a merge followed by an undo, every annotation that existed beforehand exists with
      identical content, attached to the record it originally described.
- [ ] AC-18: Every canonical listing exposes its provenance: every provider row underneath it, the
      signal that justified each join, and whether the join was automatic or human.
- [ ] AC-19: A canonical listing backed by exactly one provider row is a valid state and requires no
      merge, so the feature is usable with a single provider configured.
- [ ] AC-20: Merging is deterministic and order-independent: the same set of provider rows produces
      the same canonical listings regardless of the order the providers returned in, and regardless
      of which run each row arrived in.
- [ ] AC-21: A row that matches more than one existing canonical listing does not join any of them.
      The situation produces `ambiguous` and enters the review queue naming all candidates.
- [ ] AC-22: An address that cannot be parsed at all is retained, compared by the signals that
      remain, and never causes the row to be dropped or the run to fail.
- [ ] AC-23: The review queue is readable, countable, and reportable, so the run digest can say how
      many pairs are waiting on a person.

## Edge cases & errors

- A duplex or a shared driveway where two genuinely different properties carry the identical
  address with no unit designation and coordinates a few metres apart. This is `ambiguous`, and it
  is the case that justifies the whole queue existing.
- A provider corrects a property's address between runs, so a row that previously matched now does
  not. The existing canonical listing is not torn apart automatically; the change is surfaced as a
  contradiction under AC-14.
- A property is relisted under a new provider identifier with the same address. This is a new
  provider row that matches an existing canonical listing and joins it, which is how a relisting
  becomes visible as a status event rather than a second property.
- A rural address with no street number, of the form used for land parcels on a named road. Handled
  under AC-8: never merged on coordinates alone.
- A ZIP code is missing from one row. The address key is incomplete, so the outcome falls to the
  remaining signals and is at best `ambiguous` without a parcel number.
- Coordinates are present but obviously wrong, sitting at zero or at a state centroid. Treated as
  absent rather than as a contradiction, so one bad coordinate does not make every pair ambiguous.
- A person merges two records that both carry annotations. Nothing is discarded; both annotations
  survive, and the undo restores each to its original record.
- A parcel number is formatted differently by two providers, with or without separators. Parcel
  numbers are normalized before comparison, or the comparison is treated as not available rather
  than as a disagreement.
- The review queue grows large on the first run over a new area. This is expected, and the queue
  must remain usable and countable rather than being capped or truncated.

## Non-functional requirements

- Performance: comparing a run of 5,000 rows against existing canonical listings completes within
  the run's overall budget and does not require comparing every row against every other row.
- Security: address and parcel strings are data. Nothing parsed from a provider row is used to
  construct a query, a path, or an expression.
- Reliability: an unparseable or malformed row degrades that row's match quality and nothing else.
  It never fails the merge pass or the run.
- Accessibility: none directly. The queue's presentation belongs to the browser interface.

## Open questions

- Whether the review queue should offer a bulk decision for pairs sharing an obvious pattern is a
  usability question for the browser interface, not a requirement here.
