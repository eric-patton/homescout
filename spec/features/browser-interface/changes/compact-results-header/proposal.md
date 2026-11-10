# Proposal: browser-interface

**Trigger:** Guildboard card #5, 2026-11-10, from Eric's report. At a 1920x950 window on
la-near-church, everything above the results table took about 600 px, so the table header began
two thirds of the way down and about ten listing rows were visible. The biggest single block was
the Drive time box (about 140 px), and the routing credit was printed twice.

**Summary:** A layout and density change on the Results page only. Nothing is removed.

- The trail, the page heading, the four screens about the search and "How this table works" sit
  on one line.
- The three control groups keep their names, written inline before their controls rather than
  above them.
- The Drive time box becomes a "Drive time" button in the Which rows group. The button's own text
  says which ranges are in force ("Drive time: Church 0-25 min"), when a selected location has an
  entry that cannot be used, and when estimates are being calculated, so nothing active is hidden
  while it is closed. Pressing it opens the same controls inline under the controls row, one line
  per location, pushing the table down. It starts closed on every visit and is not remembered.
- The count line, the yellow drive-time notice, the "Showing only" chips with "clear all filters",
  the Drive to Church note and one copy of the routing credit share one wrapping bar directly
  above the table.
- The yellow notice appears only while results are incomplete (pending or unavailable estimates,
  a calculation running, a failure, or another pass in the way). When every estimate is in, the
  same facts are said in small text inside the Drive time panel instead.

The Map page keeps its Drive time box exactly as it is: the compact form is an option only the
Results page turns on.

## Blast radius

- **Requirements affected here:** one added criterion (AC-114). AC-53 (the table box ends within
  the window), AC-72 (named groups), AC-78 (the disclosure), AC-110 (the Church note and its
  credit), AC-111 to AC-113 (drive-time controls, notice, chips and credit) keep their meaning; how
  each stays satisfied is written in `delta.md`.
- **Already-built code affected:** `web/static/common.js` (an opt-in compact mode of the shared
  drive-time controller), `web/static/results.js`, `web/static/app.css` (rules scoped to the
  Results page). No server, API, matching or calculation change.
- **Other surfaces:** none. What changed, Map and Edit share the trail and tab styles, so every new
  rule is under a Results-only body class.

## What this is not

Not a change to which columns the table shows, to drive-time matching, validation, background
calculation or chips, or to any other page.
