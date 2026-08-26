# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

New requirements, written as full spec requirements. Each acceptance criterion here takes the next
stable id when folded into `spec.md`: AC-33 through AC-39.

**Vocabulary.** A **judgment** is the person's own decision about whether a property is still worth
their attention. It holds `keep`, `pass`, or nothing at all. Nothing is the starting state and means
undecided, which is a different thing from `keep`: one is a house nobody has looked at and the other
is a house somebody looked at and kept. A property whose judgment is `pass` is **passed**, and a
passed property is hidden from the default results view and from nowhere else.

**User story.** As the person running searches, I want to say no to a property once and stop seeing
it, so that the houses I have already ruled out do not cost me the same attention every night as the
ones I have not seen.

**User story.** As the person running searches, I want to see what I passed on when I ask, so that a
decision I made in a hurry is one I can go back and check rather than one that has vanished.

**User story.** As the person running searches, I want saying no to be one click rather than a
sentence I have to type, so that clearing a table of forty houses is a thing I actually do.

- AC-33: A property carries a judgment of `keep`, `pass`, or unset. It is an annotation: written
  only by a person, never by a run, and surviving every subsequent run, merge, unmerge and
  re-export, which is the listing store's AC-15, AC-16 and AC-17 applying to it unchanged.
- AC-34: The results table sets a property's judgment in one action from the row, without opening
  the property and without typing. Setting it again to the same value clears it back to unset, so
  the control that passes a house is the control that un-passes it.
- AC-35: A passed property is absent from the results table by default, and present when "show
  passed" is asked for. A test covers both.
- AC-36: When passed properties are hidden, their number is reported, in the same place and the same
  form as the count of disappeared listings already hidden. A table that is quietly shorter than the
  run that produced it is not acceptable; the difference has to be visible without being asked for.
- AC-37: Passing a property changes what is displayed and nothing else. It is still observed by
  every run, still snapshotted, still compared, still counted in a run's totals, and still reported
  as new, changed, gone or returned in the digest. A test asserts a passed property still appears in
  a run's comparison.
- AC-38: A criterion cannot name a judgment. The rule engine's declared namespace gains nothing from
  this change, so a person's conclusion can never become an input to the tool's own tests.
- AC-39: The judgment is settable and readable from the command line as well as the browser, and the
  command line can list what has been passed, satisfying product invariant 5.

**Edge cases added.**

- A property is passed and then a later run observes a price cut on it. It stays passed and stays
  hidden, and the change is still recorded and still reported in the digest. Hiding is about
  attention, not about the record, and a house you said no to does not become a house you said yes
  to because it got cheaper. Un-passing it is one action away.
- A passed property is merged with an unpassed one. The merged record is passed if either
  constituent was, on the grounds that a decision to stop looking at a house should not be undone by
  the tool noticing that two records were the same house all along.
- Every property in a search is passed. The table is empty and says so, naming the number hidden and
  how to see them, rather than reading as a search that found nothing.
- An unknown judgment value arrives from a hand-edited database or an older client. Rejected on
  write with the accepted values named, in the same way an unknown severity in a criterion is.

## MODIFIED

- **AC-7 — what the results table shows** (written as AC-9 when this delta was drafted, which was
  the wrong number: AC-9 is the listing detail. Corrected at the fold against the spec itself.)
  - Was: the table shows the properties a run kept, with every column, sortable and filterable.
  - Now: the same, minus the properties the person has passed, which are shown when asked for. The
    existing "show gone" control and this one are the same pattern and sit together.

## REMOVED

Nothing. No existing behavior is withdrawn by this change.
