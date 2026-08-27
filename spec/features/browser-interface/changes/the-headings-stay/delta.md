# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## MODIFIED

- **AC-53.** Was: the table's box ends within the window and its height is measured rather than
  assumed. Now: that, and the column headings stay on screen for the whole of the list however far
  down it is scrolled. The spec had the box's edges and not its headings, which is how a heading
  that worked for the first sixty rows read as finished.

## ADDED

One edge case: a list long enough that the drawn window is a small fraction of it. That is the
ordinary case here, not the extreme one, and it is where the guarantee has to hold.

## REMOVED

Nothing.
