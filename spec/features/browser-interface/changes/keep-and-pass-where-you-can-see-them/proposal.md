# Proposal — browser-interface

**Trigger:** The person reading the statewide table, in four messages while using it: "would be
helpful to have a toggle to wrap long fields so things like Description and Town Analysis Notes can
have a max width"; "for some reason scrolling changes the column widths"; "I'm still not seeing the
'x' to hide something. Should be the first thing on a row"; and "would be very nice to be able to
'favorite' stuff too easily", plus "the pass needs a confirmation modal".

**Summary:** Four changes to the same surface, and one bug.

**Long text can wrap.** Every cell is a single line cut off at the column's width, which for a
description or a town note means the column is a place a sentence starts and nothing more. Wrapping
is clamped to a fixed number of lines rather than left to grow, because every row being the same
height is what lets a thousand of them be placed by arithmetic instead of measured, and that is the
whole design of this table.

**Keeping and passing get a column of their own, first.** They were inside the address cell, after
the address and after however many badges a property carried, so on a narrow column they sat past
the right edge. It was reported twice as a missing feature that had already been built. A control
nobody can find is a control that does not exist.

**Passing asks first.** A house leaves the table on one click on a 26-pixel row, and a mis-aimed
click is exactly the accident worth one question. Keeping does not ask: it hides nothing and the
same button undoes it.

**Keeping is surfaced at all.** The store has held `keep` since the judgment was added and no
surface has ever written one, so the shortlist a person works from after reading a table of a
thousand could not be built. This is the missing half of a field that already exists, not a new kind
of state.

## Blast radius

- **Requirements affected here:** the results table's controls and its view toggles, which go from
  three to four.
- **The core (feat-003's other half) gains one operation.** `kept` mirrors `passed`, because
  product invariant 5 does not let the browser have a list the command line cannot ask for. The
  command line gains `homescout kept` and the interface `/api/kept`; both read one core function.
- **The listing store is untouched.** `keep` is already a value of a field that already exists, with
  the migration already run, so this writes a value the store has always accepted.
- **The rule engine stays untouched**, on the same grounds as when the judgment was added: a
  criterion must not be able to read your own conclusions.
- **The defect fixed alongside it** is the column widths jumping while scrolling, which is this
  change's own regression from the arrangement work and is fixed in the defect lane.

## What this is not

Not a fifth state and not a rating. The judgment still holds `keep`, `pass`, or nothing, and a
property is one of those at a time.
