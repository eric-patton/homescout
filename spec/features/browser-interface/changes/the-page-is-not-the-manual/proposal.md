# Proposal: browser-interface

**Trigger:** Reading the interface back: every page opens with a paragraph of prose above the
controls, and on the results table it is five lines. The writing is good. The placement is not: it is
read once and is furniture for ever after.

**Summary:** The same shape in four places. The results table prints its instructions above the
controls on every visit. The search builder repeats the same two-line explanation of what a criterion
does inside every criterion, fifteen times on the search this was read against. The settings surface
is eight sections in one scroll with the things you configure once interleaved with the things you
come back to run, and the actions are seventh. And the landing page's overview strip changes shape,
because three of its five figures only appear when their count is not zero, so it is two figures wide
most mornings and four on the mornings something needs attention.

None of this is a case for less writing. The privacy explanations on the settings surface are among
the best writing in the product and every word of them earns its place at the moment somebody is
deciding. What is wrong is that all of it is at the same weight as the controls, and permanently.

So: instructions go behind a disclosure that says what it holds, open on the first visit to a surface
and closed after. Repeated explanation is said once above the thing it explains. The settings surface
splits into what you configure and what you run, which is what its own name in the navigation has
always said. And a figure that can be zero is drawn at zero rather than removed, so the strip is the
same shape every morning and a count going from nothing to something is a number changing rather
than a tile appearing.

## Blast radius

- **Requirements affected here:** AC-1 (a tenth surface), AC-24 (the criterion builder's
  explanation), and the overview strip, which no criterion currently describes and which this
  delta writes down for the first time. AC-25 and the scenario about turning on something that
  is off need no change, because the surface they say "here" about keeps its address and
  everything they name.
- **Already-built code affected:** `web/static/results.js`, `search.js`, `settings.js`,
  `searches.js`, `web/wire.py` for the new page, `app.css`.
- **No core change.** Every one of these is what a surface draws.
- **Nothing is removed.** Every sentence that exists still exists and is still one press away; the
  settings surface keeps every section it configures, and the ones it runs are on a page of their
own that the navigation already promised.

## What this is not

Not less explanation. A disclosure that hides something a person needs is worse than a paragraph
they have read. What goes behind one is what is true every visit and useful on the first.

Not a menu. Disclosures are open where the thing they explain is being set up for the first time.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
