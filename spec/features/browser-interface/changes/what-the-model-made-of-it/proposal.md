# Proposal — browser-interface

**Trigger:** The person running searches, after reading the first full assessment pass over all 155
properties still in play, asked what was actually needed from them. The answer was this: an
assessment is readable from a terminal and from the raw API and from nowhere a person looks.

Asked how it should appear, they chose a count that expands: "one narrow column showing how many
concerns a property has, coloured when any is serious, empty when there are none. Clicking a row
opens the full assessment underneath it."

**Summary:** 155 assessments exist and the table does not know they are there. That is the whole of
this change, and it was deliberately left until somebody had read real ones: what is worth showing
about an assessment in a table that is already forty-three columns wide is a question of taste, and
guessing it before anybody had seen the output would have been guessing.

Now the output is known, and so is the shape of it. An assessment is one or two sentences of
account, about one concern per property, and 55 of the 155 have none at all. That distribution is
what makes a count the right column: most rows are blank, a blank row is a real answer, and the
number is small enough to read without a second glance.

**One column, and the detail on demand.** The column says how many concerns, marked when any of them
is serious and when the assessment no longer describes the property. Pressing a row opens the whole
assessment beneath it: the account, each concern with the evidence it came from, what the pictures
showed, what to check before visiting, and what could not be determined.

**The table already supports this and I checked before proposing it.** Rows are measured after they
are drawn and the offset ladder is built from the measured heights, so a taller row is a solved
problem rather than a fight with the virtual window. This would have been a much larger change
against a table with fixed row heights, and it is worth writing down that it is not.

**What the table carries and what it fetches.** The results answer gains a count, a worst severity
and whether it is stale, which is three small values per row. The assessment's text is fetched when
a row is opened, because the table already sends 2.7MB for this workspace and adding 155
assessments' prose to every page load to show what is usually one of them is the wrong trade.

## Blast radius

- **Requirements affected here:** two added, for the column and for the expansion. AC-45 (the
  arrangement is remembered) and AC-52 (a column can be hidden and brought back) apply to the new
  column unchanged, which is the point of their being general.
- **Design decisions affected:** none reversed. The column-origin grouping gains a sixth origin,
  because an assessment is a genuinely different kind of claim from a reported field, a computed
  one, one read out of the description, public data, or the person's own note.
- **Already-built code affected:** `web/static/results.js` (the column, the expansion, one line in
  the height measurement), `app.css`, `api.py` (three values per row in the results answer), and
  `store/core.py` (one query that summarises many assessments at once rather than one per row).
- **Nothing about the assessment itself changes.** feat-013 produces it; this draws it.
- **It still decides nothing.** The column sorts and filters like any other, which is a person
  arranging their own table. Nothing here keeps, passes, hides or reorders on the model's say-so.

## What this is not

Not a second opinion column. There is one concern count, and the assessment behind it, and the
person's own `rank`, `verdict`, `red flags` and `next step` stay exactly where they are and exactly
whose they are. Read side by side is the entire point.

Not a summary in the table. The one-line verdict was offered and not chosen, and the reason it was
not is sound: long text in a virtual table competes for width with the columns somebody actually
decides on.

## Status
- [ ] delta reviewed (analyze)
- [ ] implemented & verified
- [ ] folded into spec.md
