# Proposal — browser-interface

**Trigger:** Asked for directly, while working through a statewide run of nearly a thousand
properties: a filter button on each column heading that opens a plain text search, and an easy way
to clear every filter at once.

**Summary:** The table has one search box and it searches everywhere. Typing `taos` into it finds
properties in Taos, properties whose description mentions Taos, and properties whose listing agent
works in Taos, and there is no way to say which of those was meant. The same box cannot express two
conditions at all: "in Ruidoso, and single-storey" is two searches and the second undoes the first.

So each column gets its own. A heading carries a button, the button opens a box, and what is typed
in it narrows the table to the rows whose value in that column contains that text. Several columns
can be narrowed at once and the conditions add up. Nothing is deleted and nothing is decided: a
filter changes which rows are drawn and nothing else, exactly as the search box already does.

Two things follow from that, and both are the reason this is written down rather than just built.

**Every filter is visible in words.** A row that is not on screen for a reason nobody can see is
the worst failure this table has. So the active filters are listed above the table, in plain
language, each with its own way to lift it, and one button lifts them all. The whole-table search
box is listed there too, because it is a filter and a person who cannot find their rows should have
one place to look rather than two.

**A filter matches what the cell shows, not what the store holds.** A price reads `$425,000` on
screen and is the number 425000 underneath, and somebody typing what they can see is not wrong. A
column this tool could not fill reads "not known", so typing that finds exactly the properties
nobody could determine it for, which is a question that has been asked out loud twice.

## Blast radius

- **The results table only.** One screen, one file, plus its stylesheet.
- **No core change, no store change, no request.** The rows are already in the browser: this is the
  same array the sort and the existing search box work on, and AC-7's no-round-trip guarantee
  covers it unchanged.
- **AC-7 is extended, not replaced.** The whole-table search stays exactly as it is.
- **Nothing is remembered.** Unlike the column arrangement, a filter lasts the visit. A saved
  narrowing that silently reapplied itself on the next open would hide rows for a reason set days
  earlier, which is precisely the failure the visible list is there to prevent.
- **Not a saved search's filter.** A saved search's own filters decide which properties are
  collected and are written to its file; these decide what is drawn on one screen in one browser.
  The words are the same and the things are not, so the page says which one it means.

## What about the command line?

Invariant 5 asks that every capability be reachable from both surfaces. This is the same class of
thing as the sort, the whole-table search box, the column widths and the wrap toggle: a way of
looking at rows already fetched, not an operation on the store. None of those has a command-line
counterpart and none should. What the command line reaches, it reaches unchanged.
