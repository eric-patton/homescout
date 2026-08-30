# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## MODIFIED

### AC-86 — what the cell draws

**Was:**

> The results table carries a column saying how many concerns the assessment raised about each
> property. It is marked when any of them is serious, and marked differently when the assessment no
> longer describes the property because what it was assessed from has changed. A property with no
> concerns shows nothing rather than a zero, and a property never assessed shows nothing rather than
> an absence, because those are different facts and neither is a number.
>
> (…the paragraphs on it being an ordinary column, on the declaration versus the default
> spreadsheet, and on it being in the opening view.)

**Now:**

The results table carries a column for what the assessment made of each property, drawn as a control
rather than as a measurement: a magnifying glass carrying the number of concerns as a badge, the way
a count riding on an icon is read everywhere else as "there are this many things here, press to see
them". It is marked when any concern is serious, and marked differently when the assessment no
longer describes the property because what it was assessed from has changed.

Three facts stay apart, and the drawing is what keeps them apart:

- **Nothing has assessed this property**: the cell is empty. An absence is not a count.
- **It was assessed and raised nothing**: the icon, with no badge. This is a real answer and 55 of
  the first 155 properties were it. It is drawn rather than left blank so that "read, and clear" can
  never be mistaken for "not read", and it carries no zero, because a badge showing `0` is a thing
  a person has to be taught to read and an unbadged icon is not.
- **It raised concerns**: the icon with the number on it.

It is an ordinary column: it hides, comes back from the chooser, sorts and filters exactly as every
other column does, which is AC-45 and AC-52 applying to it without being restated. Its value is
still the number, so a sort orders by how much was raised and a filter tests the count, whatever the
cell happens to draw. It joins the chooser under an origin of its own, because what a model made of
a property is a different kind of claim from a value a source reported, one this tool computed, one
read out of a description, public data about the place, or something the person wrote.

**Ordinary means it joins the declaration every column is declared in, and not the default
spreadsheet.** Those are already two different things: forty-four columns are declared and the
default sheet uses thirty-two. Joining the declaration is what makes sorting, filtering, hiding and
the chooser work without a special case; staying out of the default sheet is what leaves
feat-011/AC-1's header exactly as it was. Anybody who wants the count in a sheet puts it in a
template, which is what feat-011/AC-7 says a template is for.

**It is in the view the table opens on.** A count somebody has to go and un-hide is a count they
will not see, and this one exists only where a person is deciding.

**Neither mark is a colour.** Found by the pre-build check against this feature's own accessibility
requirement, which is that nothing is conveyed by colour alone: the first drawing of this made a
serious count a red badge and an ordinary one blue, and that was the whole of the difference. A
serious count is now squared where an ordinary one is round, and a stale assessment is drawn dashed,
so a shape and a texture rather than two colours. Both are said in words too, because the badge is
hidden from a screen reader.

**Why this and not a number.** A right-aligned integer in a column standing between Tags and Town is
read as one more measurement of the house, like beds or square feet. It is not a measurement; it is
a door. Drawing it as a control is the whole of the difference, and it costs nothing, because the
sortable, filterable value underneath is unchanged.

### AC-87 — what pressing it opens

**Was:**

> Pressing the count opens the assessment for that property beneath it, in the table, without
> leaving the page. What opens is the whole of it: the account of the property, every concern with
> the evidence it came from, what each picture showed, what to check before visiting, and what could
> not be determined. Pressing again closes it, and it opens from the keyboard the same way, because
> the cell is already reachable that way.
>
> (…the paragraphs on the count and not the row, on the person's own judgment, on staleness, and on
> fetching the text when a row is opened.)

**Now:**

Pressing it opens the assessment for that property in a dialog over the page, without leaving the
page. What opens is the whole of it: the account of the property, every concern with the evidence it
came from, what each picture showed, what to check before visiting, and what could not be
determined. It closes with its own control, with Escape, and by pressing outside it, which is how
every other dialog in this interface closes. It opens from the keyboard the same way, because the
cell is already reachable that way, and focus moves into it when it opens and back to the control it
came from when it closes.

**Over the page rather than inside the table.** Three reasons, and the first is the one that was
learned by looking:

- **Prose does not survive this grid.** Every cell here is deliberately `white-space: nowrap`,
  because a data row is read across, and every cell takes the table's line height, which is a *row*
  height of 25px rather than a line height. A paragraph inheriting it is set a full line apart, and
  that is not a styling slip to correct in place: it is what a table configured for one-line cells
  does to prose, and the next thing that puts prose in a cell would meet it again.
- **The reading is not the deciding.** The table exists to compare a hundred and fifty rows. Reading
  what a model made of one house is a single-subject act, and this interface already opens a dialog
  for exactly that kind of act, for the photographs and for the question asked before a house is
  passed on.
- **Nothing behind it moves.** An opened row changes the height of the virtual window and pushes
  every row below it down the page. A dialog leaves the table untouched, so closing it puts the
  reader back on the row they were looking at rather than somewhere near it. This also removes the
  one place where AC-53's measurement had to account for a second row belonging to a first.

**The control and not the row.** Pressing a row already means two things here: it moves the cell
focus, which is what makes a writable column typable, and with shift held it extends the range AC-81
acts on. A third meaning on the same press would have taken one of those away, and the one it would
have taken is the one somebody already reported losing.

**The person's own judgment stays visibly theirs.** What is drawn is labelled as the model's and
dated, and nothing in it is written into `rank`, `verdict`, `red_flags`, `summary`, `next_step` or
the rest, which remain the user's own as feat-013/AC-6 requires. Somebody reading a concern must be
able to tell instantly that they are reading an opinion rather than their own note.

**An assessment that no longer describes the property says so before its content.** Reading a stale
assessment as current is the one way this misleads rather than merely disappoints.

**The text is fetched when the dialog is opened rather than sent with the table.** The results
answer for this workspace is already 2.7MB, and adding every assessment's prose to every page load
to show what is usually one of them is the wrong trade. The count in AC-86 is three small values per
row and travels with the table.

## ADDED

Nothing. Both criteria already exist; this changes what they require.

## REMOVED

Nothing.
