# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-52 and AC-53.

**User story.** As the person reading the table, I want to put away the columns I am not using on
this pass, so that the ones I am using fit on the screen together.

**User story.** As the person reading the table, I want to scroll sideways with a scrollbar, so that
reaching the far columns is not a matter of selecting text and dragging.

- AC-52: A column can be hidden from this screen, by right-clicking its heading and by the keyboard,
  and brought back from a chooser that lists every column. Hiding is remembered alongside the order
  and the widths, and a column comes back where it was rather than on the end. It changes what this
  screen draws and nothing else: every column stays in the answer and in the spreadsheet. The
  control column cannot be hidden.
- AC-53: The table's own box ends within the window, so the horizontal scrollbar on its bottom edge
  is reachable, and the page behind it does not scroll. Its height is measured from where the box
  actually falls rather than assumed, so it stays right as the controls wrap and the window changes.

## MODIFIED

- **AC-46.** Was: a column the tool never fills is arranged after the columns it does fill, and is
  marked as one for the person to fill in themselves. Now: every column is either filled by this
  tool or written by the person, and its heading says which. There is no third kind, and the five
  columns that were one are annotation columns now: the mark that said "yours to fill in" sat on
  columns that could not be typed into, which is the promise this fixes rather than restates.

## REMOVED

Nothing.
