# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Five acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-42 through
AC-46.

**User story.** As the person reviewing results, I want a way back to a property on each site it was
found on, so that I can add it to the shortlist I keep on the site I actually use.

**User story.** As the person reviewing results, I want to see the photograph next to the address,
so that the houses I can rule out by looking at the roof take one glance rather than one click each.

**User story.** As the person reviewing results, I want to move a column to where I am looking and
make it wide enough to read, so that a table forty-two columns wide is one I can actually work in.

**User story.** As the person reviewing results, I want a column nobody fills to look different from
a column that is empty, so that I stop concluding the tool knows nothing about fire.

- AC-42: The results table offers a link to the property on every site it was found on, each named by
  its site, rather than one address for a record assembled from several. Where only one address is
  held, the cell behaves as before. A test covers a record with two.
- AC-43: The results table can show each property's stored photograph beside its address, off by
  default and turned on from the same row of controls as the other two view toggles. The picture is
  the one this tool stored, so drawing the table asks nothing of any listing site, and a property
  without one holds the same space so that the addresses stay in a straight line.
- AC-44: A column can be moved to another position and set to another width, by pointer and by
  keyboard, and doing either changes nothing about what the column holds or what it is called. A
  test asserts the keyboard reaches both.
- AC-45: The arrangement of the columns is remembered per browser and per saved search, and a
  control puts it back to the declared arrangement. It is a view preference and is never written to
  the workspace, so two people reading the same workspace arrange it independently. Where the
  browser cannot store it, the table opens in the declared arrangement and every other part of this
  page behaves identically; a test covers the storage being unavailable.
- AC-46: A column the tool never fills is arranged after the columns it does fill, and is marked as
  one for the person to fill in themselves, so that an empty cell under it is not read as an answer.

## MODIFIED

- **AC-20's neighbours: the results table's view toggles.** Was: two, for disappeared listings and
  for passed properties. Now: three, the third being the photograph. The count line is unchanged and
  still reports only what is hidden, because showing photographs hides nothing.

## REMOVED

Nothing.
