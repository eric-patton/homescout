# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-57.

**User story.** As the person reading a thousand rows, I want to narrow one column at a time by
typing what its value should contain, so that I can ask a question about a particular column
instead of about every column at once.

- AC-57: Every column that can be sorted can be filtered, from a control on its own heading that
  opens a box for plain text. A row is kept when the text appears in what that column shows for it,
  matched without regard to case and against the cell as displayed rather than as stored, so that a
  price typed the way it is printed matches it and "not known" finds the properties nobody could
  determine that column for. Filters on several columns all apply, together with the whole-table
  search box, and are applied in the browser without contacting the server. Every filter in force is
  named in words above the table with its own control to lift it, and one control lifts all of them,
  including the whole-table search. A filter narrows what is drawn and changes nothing else: no
  property is altered, judged or deleted by one, and none of it is remembered past the visit.

## MODIFIED

- **AC-7.** Was: the results table shows every available column, minus the properties the person has
  passed on, and supports sorting and filtering without a round trip to the server for each
  interaction. Now: the same, with the filtering named as two things that both work that way, the
  whole-table search box and the per-column filters of AC-57.

## REMOVED

Nothing.
