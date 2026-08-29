# Proposal: browser-interface

**Trigger:** The reading of the interface that produced the two changes before this one. The table
opens on every column it has, which is forty-three of them and about seven thousand four hundred
pixels, roughly five screens on the window it was read on. The columns somebody actually decides
with are scattered among them.

**Summary:** Nothing is hidden until you hide it, one right-click at a time, and the chooser that
brings a column back is a flat list of forty-three tick boxes with no grouping, no search and no
starting points. So the table's default state is one nobody would choose: the address, the price
and the fire hazard are four screens apart, and getting to a usable arrangement is thirty separate
decisions that have to be made again on every new saved search.

Three named views fix the default without taking anything away. **Deciding** is the dozen columns a
person reads a row with. **Hazards** is what this household is actually filtering for, which is the
reason the enrichment pass exists. **Everything** is what the table does today and is one press
away. The table opens on Deciding, and every column is still in the answer, still in the
spreadsheet, and still one tick from being back.

**The chooser gets the grouping it already has the data for.** Every column declares where its value
comes from, and the table already uses that to say what an empty cell means: reported by the
listing, worked out here, read out of the description, public data about the place, or yours to
write in. Those five are what the forty-three sort into, and they are the answer to "where is the
flood zone in this list". The chooser lists them flat and makes the person read all of them.

**What this must not do is overwrite an arrangement somebody built.** A remembered arrangement wins
over the default view, always. Views are where you start, not what you are held to: hiding or
showing a single column afterwards leaves the view behind and says so rather than silently
reasserting itself.

## Blast radius

- **Requirements affected here:** AC-45 (the arrangement is remembered per browser and per search,
  and a control returns it to the declared one) and AC-52 (a column can be hidden and brought back
  from a chooser that lists every column). Both by modification; neither loses a guarantee.
- **Design decisions affected:** none reversed. AC-45's rule that this is a view preference and is
  never written to the workspace is what decides where the views live, which is the browser.
- **Already-built code affected:** `web/static/results.js` (the opening arrangement, the chooser,
  one control in the "which columns" group) and `app.css`. Nothing else.
- **No server change and no core change.** The views name columns the answer already declares and
  the grouping uses the origin it already declares. If any of this needs an API change it has been
  designed wrong, which is the same test the change before this one used.
- **Not a change to the spreadsheet.** The export writes every column it always did. A view is what
  this screen draws, in this browser, and AC-52 already says so.

## What this is not

Not a way to lose a column. Everything stays in the answer, the export and the chooser, and
"Everything" restores the current behaviour in one press.

Not a lock. A view is a starting point and stops applying the moment somebody arranges past it.

Not a set of views somebody has to maintain. Three, named for what a person is doing rather than for
what the data is, and a column added later lands in Everything and in whichever view names it.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
