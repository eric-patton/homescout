# Proposal: browser-interface

**Trigger:** Reading the interface back. In the workspace this was read against, 737 of 951
properties have been passed on. Every one of them was passed one row at a time, each through a
dialog. Passing is the daily work of this table and it has the throughput of an exception.

The same shape on the search builder, from the other direction: four independent save buttons on one
long form, and a lede that warns you about them ("Nothing is saved until you press a save button, and
each panel saves only itself"). That sentence is an apology for the design. Nothing marks a panel as
having unsaved changes and nothing stops somebody leaving with three of the four unsaved.

**Summary:** Two capabilities the surfaces are missing, both about the cost of ordinary work.

**Rows can be passed or kept in a batch.** A range of rows can be selected, and one action applies to
all of them. The dialog asks once for the batch rather than once per row, the reason it collects is
written to each of them, and one undo takes the whole batch back. Everything AC-48 requires of
passing one property is required of passing forty: it says what it does, it is reversible, and
dismissing it by any means leaves every row exactly as it was.

**The builder says what is unsaved and does not let it go quietly.** The four panels stay, because
they save four genuinely different parts of a definition and one save button over all of them would
write parts nobody touched. What changes is that a panel with unsaved changes says so, and leaving
the page with any of them says so before it happens.

## Blast radius

- **Requirements affected here:** AC-34 and AC-48 (setting a judgment, and the confirmation), by
  modification. AC-3's guarantee about round-tripping a definition is untouched and is the reason
  the four panels stay four.
- **The core gains one operation:** setting a judgment on several properties at once. It is a core
  operation rather than a browser loop, because product invariant 5 says both surfaces reach every
  capability, and because forty separate writes is forty chances to end up half done with no record
  of which half.
- **The command line gains it too**, or AC-22's enumeration is broken.
- **Already-built code affected:** `api.py`, `cli/main.py`, `web/app.py`,
  `web/static/results.js`, `web/static/search.js`, `app.css`.

## What this is not

Not a change to what passing means. It hides a property from a view and nothing else, it is still an
annotation written only by a person, and it is still reversible.

Not one save button on the builder. Four panels that save four parts of a file is right; four panels
that give no sign which of them is dirty is what is wrong.

## Status
- [ ] delta reviewed (analyze)
- [ ] implemented & verified
- [ ] folded into spec.md
