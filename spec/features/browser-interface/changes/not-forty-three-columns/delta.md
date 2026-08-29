# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-74 and AC-75.

**User story.** As the person reading a thousand rows, I want the table to open on the columns I
decide with, so that the address and the price are not four screens apart on a table I have not
arranged yet.

**User story.** As the person putting columns away, I want the chooser sorted by where a value comes
from, so that finding the flood zone is looking in one place rather than reading forty-three names.

- AC-74: The results table opens on a named view rather than on every column it has. Three exist:
  the columns a property is decided with, the columns about what a place is next to, and all of
  them. Which one is in force is shown in words with the number of columns it draws, and changing
  it is one control. Everything a view leaves out is still in the answer, still in the spreadsheet,
  and still one tick away in the chooser, which is AC-52's guarantee unchanged.

  **A remembered arrangement wins over the view, always.** A person who has arranged this table
  opens it as they left it, and the view decides only what a table nobody has arranged yet looks
  like. That is what makes this a default rather than a redesign of somebody's screen: AC-45 says
  the arrangement is remembered per browser and per saved search, and this changes what is
  remembered on the first visit and nothing about a later one.

  **What is remembered is the set of columns, and the view's name is a label on it.** A view is
  applied at two moments and no others: when there is nothing remembered at all, and when a person
  picks one. It is never recomputed from its name on a later visit. Two things follow and both are
  required. A person who deviates from a view keeps every other column exactly as the view left it,
  rather than having the thirty the view was hiding reappear because only the one they touched was
  written down. And a release that changes what a view contains does not silently rearrange a table
  somebody is already using, because nothing reads the view's list again once its result has been
  remembered.

  **A view is a starting point and not a lock.** Hiding or showing a single column afterwards leaves
  the view rather than being reasserted by it, and the control says so rather than continuing to
  claim a view the table is no longer showing.

  A view naming a column this answer does not declare draws the columns it does declare and says
  nothing about the rest: a view is a list of names, so a release that renames or retires a column
  narrows a view. The table draws the view's remaining named columns, raises nothing, and is never
  left blank.

  The number said beside the view's name is counted against the columns this answer declares, not
  against a number written down here, so it stays true as columns are added and retired.

  Both the control and the chooser are operable from the keyboard, like everything else on this
  surface.

- AC-75: The chooser groups every column by where its value comes from, under the same five names
  the table already uses to say what an empty cell in that column means: reported by the listing,
  worked out by this tool, read out of the description, public data about the place, and yours to
  write in. The words are the core's, declared once with the columns themselves, so the chooser and
  the heading tooltips cannot come to describe the same column differently.

  The grouping is the answer to "where in this list is the flood zone", which a flat list of
  forty-three names makes somebody read all of them to answer. Each group says how many of its
  columns are shown, and can be shown or put away as a group, from the pointer and from the
  keyboard, because "all the public data" and "everything I write in myself" are the two most
  common of those thirty decisions.

## MODIFIED

- **AC-45.**
  - Was: the arrangement of the columns is remembered per browser and per saved search, and a
    control returns it to the declared arrangement.
  - Now: the same, and what a table nobody has arranged yet opens on is a named view (AC-74) rather
    than every declared column. The control that returns the arrangement returns it to that view.
    The passage about where a newly declared column appears is stated once rather than twice; it
    was folded in duplicate and says the same thing both times.
    Everything else in AC-45 stands unchanged: it is a view preference, it is never written to the
    workspace, two people reading one workspace arrange it independently, and a browser that cannot
    store it opens on the view and behaves identically in every other way.

- **AC-52.**
  - Was: a column can be hidden from this screen, by right-clicking its heading and by the keyboard,
    and brought back from a chooser that lists every column.
  - Now: the same, and the chooser groups what it lists by where each value comes from (AC-75)
    rather than presenting forty-three names in one flat list. Every guarantee stands: hiding is
    remembered alongside the order and the widths, a column comes back where it was rather than on
    the end, it changes what this screen draws and nothing else, and the control column cannot be
    hidden.

## REMOVED

Nothing. No column stops existing, no column leaves the answer or the spreadsheet, and the table's
current arrangement is one press away by name.
