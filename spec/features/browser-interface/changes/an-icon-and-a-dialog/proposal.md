# Proposal — browser-interface

**Trigger:** The person running searches looked at the concerns column as built and asked for it to
be built differently: "a more normal looking icon button with maybe a magnifying glass or something
with a number tag showing how many, like a facebook notification count thing would look. Clicking it
should open a modal that shows the results instead of showing it in the table."

**Summary:** The count and the panel from `changes/what-the-model-made-of-it/` both land in the wrong
place. The count is a bare number in a cell full of other bare numbers, and reads as one more
measurement of the house rather than as a thing to press. The assessment opens as a row inside the
table, which is a body of prose living inside a grid built to be read across.

Neither is a bug. Both were specified that way and built that way, and looking at the result is what
showed that the shape was wrong. That is what this change is for.

**An icon carrying a count, rather than a count.** A magnifying glass with the number of concerns
riding on it as a small badge, which is the shape a person already knows means "there are this many
things here, press to see them". It reads as a control at a glance, which a right-aligned `2` in a
column between Tags and Town does not.

The three facts the column has to keep apart survive the change and are in fact easier to draw:
nothing has assessed this property (an empty cell), it was assessed and raised nothing (the icon, no
badge), and it raised this many (the icon with a badge). The zero that AC-86 had to argue for stops
being a number that must be shown and quietly present, and becomes the absence of a badge, which is
what a person reads as "nothing to see" without being taught.

**A dialog, rather than a row.** Pressing it opens the assessment over the page instead of inside
the table. Three reasons, in the order they matter:

1. **Prose does not belong in this grid.** Every cell in this table is `white-space: nowrap` on
   purpose, because a data row is read across. The panel had to opt out of that, and it also
   inherited the table's fixed 25px line height, which is a row height rather than a line height and
   which set the assessment's own sentences a full line apart. That is what the person saw and
   reported as double spacing. It is a symptom of prose in a grid, not a styling slip, and it goes
   away when the prose leaves the grid.
2. **The reading is not the deciding.** The table is where a hundred and fifty rows get compared.
   Reading what a model made of one house is a single-subject act with its own attention, and the
   interface already has a shape for that: this product opens a dialog for the photographs and for
   the pass question. This is the same kind of thing.
3. **It stops the row from moving.** An opened row changes the height of the virtual window and
   pushes everything below it down. A dialog changes nothing behind it, so closing it leaves the
   reader exactly where they were, on the row they were looking at.

**Blast radius, inside this feature.** Two acceptance criteria change and none is removed: AC-86 on
what the cell draws, AC-87 on what pressing it opens. The column stays an ordinary declared column,
so nothing about sorting, filtering, hiding or the chooser moves, and feat-011's spreadsheet header
is untouched again. The measurement AC-53 makes of row heights gets simpler rather than harder: the
detail row that had to be added to its parent's height stops existing.

Two defects were found while looking and are fixed alongside, in the defect lane rather than here,
because neither is a change to what was intended:

- The running marker draws the word `null` beside itself whenever exactly one pass is running.
  `replaceChildren` turns a null argument into a text node, where the element builder this codebase
  uses everywhere drops it.
- The assessment's prose inherits the table's row line height. Fixed at the root by the dialog, and
  pinned by a test so the next thing that puts prose in a cell does not meet it again.
