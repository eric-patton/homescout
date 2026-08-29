# Proposal — browser-interface

**Trigger:** "In the table when you wrap text, it is still cutting off text if it is too long. It
should just make the row as tall as it needs to be to show the wrapped text."

**Summary.** "Wrap long text" clamped every cell to three lines and left the rest in the cell's
tooltip. That is a control that does not do what it says, and the person using it read it exactly
that way: she turned wrapping on to stop text being cut off, and it was still cut off.

The clamp was not arbitrary. Every row being the same height is what lets a thousand of them be
placed by arithmetic rather than measured, which is what keeps this table interactive at five
thousand rows, and it is written down in the spec as the reason. So the way to grant the request is
to stop assuming and start measuring: a row that has been drawn once carries its measured height,
a row that has not is a guess, and the guess only ever decides where the scrollbar sits.

Two consequences fall out of that and both belong in the spec rather than in a comment.

**The height of the whole table changes as somebody scrolls into rows nobody has seen.** That is
what a scrollbar over unmeasured content is, everywhere such a thing exists, and pretending
otherwise would mean measuring a thousand rows before drawing one.

**The row under the top of the window must not move while that happens.** Correcting the heights of
the rows above the window moves everything below them, so the scroll position is corrected by
exactly as much. A correction that shoves the line somebody is reading off the screen is worse than
the estimate it is correcting.

## Blast radius

- **The results table only, and only while wrapping is on.** With wrapping off, every row is one
  height and is placed by division, exactly as before. That path is untouched.
- **A row is now as tall as its tallest cell**, which on a table of forty-four columns including a
  full listing description means a row can be several hundred pixels tall. That is what was asked
  for, said plainly: the answer to a row too tall to read is to narrow or hide the column that is
  making it tall, both of which this table already does.
- **The overscan is a distance rather than a count** when rows can differ. Twelve rows either side
  of the screen is a sensible cushion at twenty-six pixels a row and four thousand pixels of
  invisible table at three hundred.
