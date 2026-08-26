## Why

The brief settled early that this tool both replaces the spreadsheet and feeds it. The replacement
half is the browser interface; this is the feeding half, and it is required rather than optional
because months of accumulated judgment and the expectations of whoever else reads the sheet both
live in that format. The default column template reproduces the existing hand-built consolidated
sheet exactly, so the output is recognizable as the same document rather than as a new one. The
problem brief is in `research.md`.

## Vocabulary used in this feature

- A **template** is a named, configurable column set. `default` reproduces the brief's column list.
- The **properties sheet** carries one row per canonical listing. The **areas sheet** carries the
  user's notes about towns and regions rather than about individual properties.

### The default column list

Reproduced here rather than referred to, because AC-1 is a comparison and a criterion whose target
lives outside the spec cannot be checked. Thirty-two columns, in this order, as the hand-built sheet
has them:

> Rank, Status, Property, Town/Area, County/Region, Price, $/sq ft, Price History & DOM, Beds,
> Baths, Sq Ft, Year Built, Acres, Construction/Roof/Features, Garage/Outbuildings, HVAC/Heat,
> Water Source, Sewer/Septic, Gas, FEMA Flood Zone, Internet, Principal Aquifer, Annual Taxes,
> Crime/Safety, Fire/Egress/Terrain, Sewage & Reclaimed-Water Exposure, Town Analysis Notes,
> Red Flags, Summary, Verdict, Next Step, Listing URL

## User stories

- As the person running searches, I want the familiar consolidated sheet generated from current
  data, so that I stop maintaining it by hand.
- As whoever opens the sheet, I want the address to link to the listing, so that the spreadsheet is
  a way into the properties rather than a dead end.
- As the person running searches, I want my area and town observations in the same workbook, so that
  the context travels with the properties.
- As the person running searches, I want to choose which columns appear without editing code, so
  that a sheet for a different purpose is a settings change.
- As the person running searches, I want re-exporting to be safe, so that I never hesitate before
  regenerating.
- As the person running searches, I want fields nobody could determine left blank, so that the sheet
  never asserts something the data does not support.

## Behavior & scenarios

- **Scenario: the default sheet**
  - Given a search with results and annotations
  - When it is exported with the default template
  - Then the properties sheet contains exactly the brief's column list, in that order, one row per
    canonical listing

- **Scenario: the address links**
  - Given an exported properties sheet
  - When the address cell of any row is followed
  - Then it opens that property's listing

- **Scenario: area notes travel with the properties**
  - Given a search with recorded area and town notes
  - When it is exported
  - Then the workbook contains a second sheet carrying those notes

- **Scenario: an undetermined field**
  - Given a property whose water source could not be determined
  - When it is exported
  - Then that cell is empty, and contains no placeholder text, no default, and no guess

- **Scenario: re-export is safe**
  - Given a workbook produced by a previous export, at the same path
  - When an export is run again to that path
  - Then the previous file is not silently replaced: either a new file is written or the overwrite
    is explicitly confirmed, and in neither case is any annotation held in the app altered

- **Scenario: the app is the source of truth**
  - Given annotations edited in the app after a previous export
  - When the export is run again
  - Then the new workbook carries the current annotations, and nothing in the previous workbook
    influences the app's data

- **Scenario: a different column set**
  - Given a template naming a subset of columns in a different order
  - When it is used
  - Then the properties sheet contains exactly those columns in that order, and no code changed

- **Scenario: exporting as plain text**
  - Given the same search exported in the comma-separated format
  - When it is produced
  - Then it carries the same columns and values as the spreadsheet's properties sheet, without the
    link formatting and without the second sheet

## Acceptance criteria

- [ ] AC-1: The default template reproduces the brief's column list exactly, in the stated order. A
      test compares the generated header row against that list.
- [ ] AC-2: One row is produced per canonical listing included in the search's results, and
      properties excluded by a `drop` rule do not appear unless explicitly requested.
- [ ] AC-3: The address cell of every row is a working link to that property's listing.
- [ ] AC-4: The workbook contains a second sheet carrying area and town notes.
- [ ] AC-5: A value that could not be determined produces an empty cell, with no placeholder text
      and no substituted default.
- [ ] AC-6: Every column in a template maps to a declared field, and a template naming an unknown
      field is rejected at load time with a message naming it.
- [ ] AC-7: Templates are configuration. Adding or reordering columns requires no code change, and a
      test exercises a non-default template.
- [ ] AC-8: An export to an existing path does not silently overwrite it. Either a distinct file is
      written or the overwrite is explicitly requested.
- [ ] AC-9: Export never modifies any annotation, listing, snapshot, or other stored data. A test
      compares the store before and after an export for equality.
- [ ] AC-10: The exported workbook reflects the app's current annotations at the moment of export.
- [ ] AC-11: There is no import path. The tool never reads a spreadsheet back as a source of data.
- [ ] AC-12: The comma-separated format carries the same columns and values as the properties sheet.
- [ ] AC-13: Text containing characters outside the ASCII range, which property descriptions
      routinely contain, is written and read back correctly in both formats.
- [ ] AC-14: `County/Region` holds the county the listing named. Where the listing named none and
      the public record can say which county contains the property's location, it holds that county
      instead, as the plain name with no marker appended, so that the two spellings of one county
      sort and group together. Where neither can say, it is empty. Two of the three listing sites
      never send a county, so without the fallback a quarter of the column is blank and the blank
      means one site's silence rather than a property with no county.
- [ ] AC-15: A column outside the default sheet, `County (looked up)`, holds only what the public
      record said, so which cells in `County/Region` were borrowed stays answerable by comparing the
      two.

## Edge cases & errors

- A search with zero results. A workbook is still produced, with headers and no property rows,
  rather than an error or an absent file.
- A property with no listing link, which happens when its only source row came from a source that
  does not expose one. The address cell is plain text rather than a broken link.
- A cell's text is longer than the spreadsheet format permits, which long descriptions and notes can
  be. It is truncated at the limit with the truncation visible, rather than producing a corrupt
  file.
- Text beginning with a character a spreadsheet application interprets as a formula. It is written
  so that it displays as text and is not evaluated.
- The output path's directory does not exist, or the file is open in another application, which is
  the normal Windows case. The failure is reported in terms naming the likely cause.
- Two properties merged into one canonical listing. One row appears, and the columns that differ
  between sources show the canonical value rather than a concatenation.
- A property whose price is unknown. The price cell is empty and the derived price per square foot
  cell is also empty, rather than zero.
- Five of the default columns are structurally empty: Garage/Outbuildings, Annual Taxes,
  Crime/Safety, Fire/Egress/Terrain, and Sewage & Reclaimed-Water Exposure. No free national source
  supplies any of them and description extraction does not recover them, so they are filled only by
  the user's own notes. They remain in the default set because the sheet must stay recognizable, and
  nothing writes a machine's opinion into a column the user keeps notes in.

## Non-functional requirements

- Performance: exporting 5,000 properties completes in under thirty seconds and produces a file a
  spreadsheet application opens without warning.
- Security: no cell content is written in a form a spreadsheet application will evaluate. Listing
  and note text is data.
- Reliability: a failure partway through leaves no partial file at the destination path.
- Accessibility: the sheet conveys nothing by color alone; any status shown by fill is also present
  as text in a column.

## Open questions

None.
