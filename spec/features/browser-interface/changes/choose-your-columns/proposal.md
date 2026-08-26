# Proposal — browser-interface

**Trigger:** The person reading the statewide table: "would be nice to be able to right click a
column title and deselect it to hide it, if not needed, to save room"; "would also be nice to have a
scroll bar at the bottom, currently i have to highlight and drag over to be able to see all of the
columns"; and, of the blank columns, "am i to understand that fully blank comments are for us to add
notes to?"

**Summary:** Three things, and the third is a question that only has a good answer after a fix.

**Columns can be hidden.** Forty-two of them is more than anybody needs in front of them at once,
and the ones that matter for a given pass through the table are a different handful each time.
Hiding is by right-click, which is what was asked for, and by Delete on a focused heading so it is
not mouse-only. The chooser beside it is what brings them back, because a control that only removes
things is a trap. What is hidden is remembered with the order and the widths, and where a column
comes back is where it was.

**The sideways scrollbar is reachable.** It existed all along, on the bottom edge of the table's own
box, and that edge sat below the bottom of the window: the table's height was `100vh` minus a
constant and the constant was short by a wrapped controls row. So a table nearly seven thousand
pixels wide had no visible way to scroll sideways and the only way to reach the far columns was to
select text and drag. Measured now rather than guessed.

**The answer to the question is now yes, for all of them.** Five columns were a third kind, neither
filled by this tool nor writable by a person: the household's own spreadsheet headings, carried so
the sheet stayed recognizable. The results table drew them empty on every row and marked them as the
person's to fill in, and there was no way to fill them in. That mark was a promise the page could not
keep, and it is the reason the question was asked at all. They become annotation fields, like every
other column a person writes.

## Blast radius

- **Requirements affected here:** the table's controls, and AC-46, whose subject no longer exists.
- **The listing store (feat-001) gains five annotation fields** and a migration, on exactly the
  terms `judgment` was added on: written only by a person, never by a run, surviving every merge and
  re-export. The store's own reader and writer are now built from the field list rather than naming
  each field, which is what let this go wrong twice in one afternoon.
- **The spreadsheet export (feat-011)** points those five columns at the new fields. Its own spec has
  said all along that they "are filled only by the user's own notes"; that was a fidelity defect,
  not a change, so it is fixed as one and the sixth column origin is retired.
- **The command line (feat-003)** gains the five as flags, derived from the same list, so the two
  surfaces cannot drift.
- **Nothing writes a machine's opinion into them**, which the export spec requires and which
  remains true: they are annotations, and annotations are written by people.

## What this is not

Not a column chooser that forgets: a hidden column is hidden on this screen, in this browser. Every
column is still in the answer, still in the spreadsheet, and still there when the arrangement is
reset.
