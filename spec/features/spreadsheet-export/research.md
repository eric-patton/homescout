# Research — spreadsheet-export

## Discovery input

From `homescout-brief.md` sections 4 and 9:

- The question of whether this tool replaces the spreadsheet or feeds it was answered "both".
  Annotations live in the app, and export is a required, first-class feature rather than an
  afterthought.
- There is an existing hand-built consolidated sheet whose exact column set is given in the brief,
  running from Rank and Status through the physical fields, the researched fields, the analysis
  columns, and finally the listing link. The default template must reproduce it.
- Three requirements are stated explicitly: the address cell links to the listing, a second sheet
  carries area and town notes, and re-exporting must not clobber edits made in the app.
- The columns for heating, water source, sewer, gas, and roof come from description extraction and
  are to be left blank rather than guessed.

## Problem brief

### Problem statement

Someone who has spent months building a comparison spreadsheet struggles to adopt a new tool
because their accumulated judgment lives in that sheet and the people they share it with expect
that format, which results in either abandoning the history or maintaining both by hand. A solution
should produce that exact sheet on demand from the app's own data, with the app remaining the place
edits are made, without a re-export ever costing the user work they have already done.

### Target users

- **The person running searches** (primary): needs the familiar sheet, and needs it to be generated
  rather than maintained.
- **Whoever they share it with** (secondary): opens a spreadsheet and expects it to behave like one,
  including working links.

### Jobs to be done

- Produce the existing consolidated sheet from current data, on demand.
- Keep area and town observations alongside the property rows.
- Configure which columns appear, without editing code.
- Re-export freely, without fear of losing anything.

### Success signals

- The generated sheet is recognizable as the same document as the hand-built one.
- Nobody maintains two copies of the same judgment.
- Re-exporting is a safe, boring operation.

### Constraints

- Column templates are configuration, with a default matching the brief's column list exactly.
- The address cell links to the listing.
- A second sheet carries area and town notes.
- Fields that could not be determined are blank, never guessed.

### Explicitly out of scope

- Producing the extracted and enriched values that fill the researched columns (feat-007, feat-009).
- Editing annotations, which happens in the browser interface (feat-010).
- Any import path. The spreadsheet is an output, not a second source of truth.

### Open questions

None blocking.
