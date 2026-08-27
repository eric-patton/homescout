# Proposal — browser-interface

**Trigger:** In his words: "when scrolling down a tall list in the table view, the headers stay
sticky/frozen at the top for a while, but eventually it stops doing that for some reason. I want
them to stay visible at all times no matter how far down you scroll."

**Summary.** This is a defect, and the spec was silent on the thing it broke, which is why it needs
writing down as well as fixing. The headings were stuck and they let go partway down.

The cause is one sentence: a sticky cell is stuck to its own table and no further. The table draws
sixty rows of a thousand and put them in the right place with a transform, and a transform moves
paint, never layout. So the table really was sixty rows tall, the headings held for sixty rows, and
then they slid away with it. Measured on the fixture: 939 pixels out of the box by the end of the
list.

The shape of the failure is what makes it worth a criterion rather than a quiet fix. A heading that
never sticks is a thing you notice immediately and work around. A heading that sticks for four
hundred rows is a thing you trust, and the first you know of it is a screen of prices, acreages and
years with nothing above them, at the far end of a list where you have long since lost count of
which column is which.

Fixed by giving the table its real height back: the rows the window is not drawing are now blank
rows with a height, above and below the ones it is. Blank rows are layout. The table is as tall as
the list it stands for, so the headings are stuck to something that reaches the bottom.

## Blast radius

- **The results table only**, and only how the undrawn rows are accounted for. The drawn rows, the
  row-height arithmetic, the widths, the keyboard and every row lookup are untouched.
- **The blank blocks are their own row groups**, so `#body` still holds the drawn rows and nothing
  else. Every test and every lookup that reads a row keeps working, and nothing reading the page
  aloud meets a row that is not a property.
