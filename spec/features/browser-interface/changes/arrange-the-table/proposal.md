# Proposal — browser-interface

**Trigger:** The person reviewing results, reading the statewide table, in these words: "may be
helpful to have a thumbnail, to be able to 'x' if it has a flat roof"; "i don't see a way to adjust
the column width, or reorder the columns"; "it does say not known for fire for all listings; same
for sewage, crime, taxes"; and "it would be helpful to have a redfin link for these, to be able to
add them to a list".

**Summary:** The table is forty-two columns wide and fixed. Every column is the same width whatever
it holds, they come in one order that cannot be changed, and the columns nothing fills sit in the
middle of the ones that do. The consequence is not cosmetic: a reader concluded from `Fire/Egress/
Terrain` being empty on every row that the tool had no fire data at all, when in fact two columns of
it were sitting thirty columns to the right, off the edge of the screen. A table you cannot arrange
is a table that decides for you what you are allowed to notice.

Three changes, all to the same surface.

**Where to see it.** The `Listing URL` cell shows one link per site the property was found on, named
by site, using the addresses the listing store now carries per source row. A merged record is one
row here and up to three pages out there, and they are not interchangeable: the person keeping a
shortlist on one site can only add that site's page. Where the store has only one, the cell reads
exactly as it does today.

**The photograph.** An optional column of the stored thumbnail beside each address. Not on by
default, because the table's whole design is a tight row and sixty rows in the DOM, and a picture
row is two and a half times taller. On, it is the difference between opening forty listings to see
which have flat roofs and running an eye down one column.

**Arranging the columns.** Drag a heading to move a column, drag its right edge to size it, and the
arrangement is remembered. Both are also on the keyboard, because AC-17 does not have an exception
for new controls. Columns nothing fills are arranged last by default and marked, so an empty cell
under one reads as "mine to write" rather than "the tool found nothing".

## Blast radius

- **Requirements affected here:** the results table's contents and its controls. The `show gone` and
  `show passed` toggles are the pattern the photograph toggle follows.
- **Depends on the listing store's `a-page-per-site` change** for the per-source addresses, and on
  nothing else new.
- **The stored picture is already there.** The store keeps one per property for the digest and
  serves it at `/api/listings/{id}/image`; 1,075 of the 1,083 rows in the current table have one.
  Nothing is fetched from a listing site to draw this table.
- **The arrangement is this browser's, not the workspace's.** It is a view preference, and writing it
  into the store would make one person's arrangement the other person's. It is also the one thing
  here that may be lost without anything being lost: with storage unavailable the table opens in its
  declared arrangement and everything else behaves identically.
- **The command line (feat-003) is not asked to grow a column arranger.** Invariant 5 is about
  capability, not about presentation, and how wide a column is drawn is presentation. What the
  command line does gain, from the listing store's change, is the per-site addresses.
- **Two defects fall out of this work and are fixed in the defect lane, not here.** The row height
  the table's arithmetic assumed and the height the stylesheet gave a row disagreed by four pixels,
  which walked the rows out from under the scrollbar and put the last few out of reach; and the
  element builder treated only six named `on...` attributes as event listeners, so `ondblclick` on
  an editable cell was written into the DOM as an inline handler that defined a function and
  discarded it. Neither changes what the spec asks for, so neither gets a delta.

## What this is not

Not a column chooser: every column is still present and still reachable. Not a change to what any
column holds or what it is called; the table and the spreadsheet still agree about that, which is
what stops the two drifting apart.
