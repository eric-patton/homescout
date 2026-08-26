# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Five acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-47 through
AC-51.

**User story.** As the person reading the table, I want long text to wrap so a column can be a place
I read a description rather than a place one starts.

**User story.** As the person reading the table, I want the control that hides a house to be in the
same, obvious place on every row, so I can work down a list without hunting for it.

**User story.** As the person reading the table, I want to mark the houses worth keeping as cheaply
as I can dismiss the ones that are not, so that a shortlist is something I build while reading
rather than a second job afterwards.

**User story.** As the person reading the table, I want the spreadsheet from the page I am already
on, so that taking the list to someone else is one click and not a trip to another screen to be told
a file path.

- AC-47: Long text can be made to wrap, from the same row of controls as the other view toggles.
  Wrapping is clamped to a fixed number of lines and every row stays the height of every other row,
  because the table places rows by arithmetic rather than measuring them; text past the clamp stays
  reachable in the cell's tooltip and on the property's own page.
- AC-48: Passing on a property asks for confirmation first, in a dialog on the page rather than the
  browser's own, which says what passing does and that it is reversible. Dismissing it by any means,
  including the keyboard, leaves the property exactly as it was. Keeping a property asks nothing:
  it hides nothing and the same control undoes it.
- AC-49: Keeping and passing are the first thing on a row, in a column of their own that cannot be
  moved or displaced, so the controls are in one place on every row of every arrangement. A kept
  property is on the shortlist and is hidden from nothing; the table can be narrowed to the
  shortlist alone, and the number kept is reported alongside the number hidden. The shortlist is
  readable from the command line as well, which is product invariant 5 applying to it exactly as it
  applies to the passed list.
- AC-51: Every photograph a listing carried can be looked through, one at a time and at the size
  the window allows, from the stored thumbnail on the results table and from the property's own
  page. These pictures are the listing site's rather than this tool's, so nothing is asked of any
  listing site until somebody opens the gallery, and the gallery says where they come from: it is
  the one place in this product where looking at a property is not free of the site it was found on.
  A listing that carried none says so rather than opening an empty gallery. A median property in the
  current search carries thirty-eight of them, and until now only the first could be seen without
  going to the listing site.
- AC-50: The spreadsheet can be downloaded from the results table itself, in either format the
  export writes, without going to another screen and without being told a path to go and find. It is
  the same core operation the terminal calls and still writes its copy into the workspace, so a
  sheet taken from the browser and a sheet taken from the terminal are one file made one way. A
  format the export does not write is refused in words rather than written.

## MODIFIED

- **AC-20's neighbours: the results table's view toggles.** Was: three, for disappeared listings,
  passed properties and photographs. Now: four, the fourth being wrapped text. Only the toggles that
  hide something report a count.
- **AC-34.** Was: the results table sets a property's judgment in one action from the row, without
  opening the property and without typing. Now: the same, from a column of controls that is first on
  every row, and with the one action that takes a property out of the table asking first (AC-48).

## REMOVED

Nothing.
