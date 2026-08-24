# Plan — Spreadsheet export (feat-011)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

Two things were measured before anything was designed: what the library actually does with the text
this tool holds, and how much of the brief's thirty-two column sheet this build can honestly fill.
Both changed the design.

### The library

`openpyxl` 3.1.5, probed against the cases this feature will actually hit:

| what was tried | what happened |
|---|---|
| `cell.value = "=1+1"` | **openpyxl records it as a formula.** `data_type` comes back `f`. |
| the same, with `data_type` forced to `s` | survives a save and reload as the literal text `=1+1` |
| a hyperlink on a plain-text address cell | survives, target intact |
| forty thousand characters in one cell | **silently truncated to 32,767 and no error raised** |
| a control character (`\x0b`) in a value | `IllegalCharacterError` at write time, killing the export |
| em dashes, accents, degree signs, curly quotes | round-trip byte for byte |

- **M-1: the formula problem is the library's default, not an edge case.** Anything starting with
  `=` becomes a formula unless the cell is told otherwise. The security requirement says no cell is
  written in a form a spreadsheet application will evaluate, so **every text cell has its type
  forced**, rather than the ones somebody remembered to check.
- **M-2: the cell limit truncates in silence.** The spec asks for truncation "with the truncation
  visible", and the library's own behaviour is the opposite, so the truncation has to happen here,
  before the value is handed over, with a marker on the end.
- **M-3: one control character ends the export.** Descriptions come off the web. They are cleaned
  before they reach a cell, or a single bad byte in one listing costs the whole workbook.
- **M-4: the dangerous cases are rare in real data and that is not a reason to skip them.** Of the
  263 real descriptions committed as a fixture, zero contain a control character and zero begin with
  `=`, `+`, `-` or `@`. The longest is 4,006 characters, comfortably under the cell limit. All three
  guards are still built, because "it has not happened yet" is what every one of these looks like
  the day before it happens.

### The sheet

The brief's default template has thirty-two columns. A live run over Portales, 83 properties, one
source, with enrichment run, says how many of them this build can fill and why the rest are empty.
The answer splits three ways, and the split is the design:

| | columns | why they are empty |
|---|---|---|
| **filled from data** | Status, Property, Town/Area, County/Region, Price, $/sq ft, Price History & DOM, Beds, Baths, Sq Ft, Year Built, Acres, Listing URL | not empty: 77% to 100% of rows |
| **filled when the description says so** | Construction/Roof/Features (11%), HVAC/Heat (6%), Water Source (5%), Sewer/Septic (5%), Gas (0%) | listings rarely mention them, which is a fact about listings |
| **filled by the enrichment pass** | FEMA Flood Zone, Principal Aquifer | empty until `homescout enrich` has run, and 83 of 83 after it |
| **filled by the enrichment pass, with a key** | Internet | needs an FCC token as well; 0 of 83 without one |
| **waiting on the person** | Rank, Town Analysis Notes, Red Flags, Summary, Verdict, Next Step | empty until somebody writes something, which is correct |
| **nothing in this product fills them, ever** | Garage/Outbuildings, Annual Taxes, Crime/Safety, Fire/Egress/Terrain, Sewage & Reclaimed-Water Exposure | see M-5 |

- **M-5: five columns are structurally empty, and the spec named two of them.** The spec's last edge
  case said Crime/Safety and Fire/Egress/Terrain stay in the default set although no free national
  source supplies them. Three more are in the same position and were not mentioned: **Garage and
  Outbuildings**, which no source returns and which description extraction does not recover,
  **Annual Taxes**, which no free national source supplies, and **Sewage and Reclaimed-Water
  Exposure**. The pre-build check routed that back into `spec.md`, which now names all five. They
  remain in the default set for the reason the spec already gave, which is that the sheet must stay
  recognizable, and they are filled only by the person's own notes. D-9 is what to do about saying
  so.
- **M-6: wildfire hazard and elevation exist, and still do not go in Fire/Egress/Terrain.** Both are
  already enriched, and both bear on fire and on terrain, so the tempting move is to fill that
  column from them. It is the wrong move: Fire/Egress/Terrain is a column the person writes notes
  in, and putting a machine's summary there overwrites their work with an opinion nobody asked for.
  The same objection this project makes to guessing a field applies to guessing what a column is
  *for*. So the values are offered as their own columns instead, `Wildfire Hazard` and
  `Elevation (ft)`, which any template may name and which the default does not, and the notes column
  stays the person's.

## Design decisions

### D-1: layout

A new package, `src/homescout/export/`, above everything and below the two surfaces. It reads and
writes nothing but the file it produces.

| file | holds |
|---|---|
| `export/columns.py` | every column that may appear in a template: its name, how a row gets its value, and what kind of thing it is. |
| `export/templates.py` | the built-in `default`, template files as configuration, and the load-time check that every named column exists. |
| `export/rows.py` | one run's results turned into rows, with annotations, extracted values and enriched values gathered in bulk. |
| `export/text.py` | the three guards: forced text, control characters, and the cell limit. |
| `export/workbook.py` | the xlsx: two sheets, the address hyperlink, and the atomic write. |
| `export/delimited.py` | the comma-separated form of the same rows. |
| `export/__init__.py` | `export_search`, the one thing the surfaces call. |

### D-2: a column is a declaration, not a branch

`columns.py` holds one entry per column, and the entry knows how to get its own value:

```python
Column("Water Source", kind=TEXT, source=extracted("water_source"))
Column("Wildfire Hazard", kind=TEXT, source=enriched("wildfire_hazard"))   # not in `default`
Column("$/sq ft",      kind=NUMBER, source=derived(price_per_sqft))
Column("Verdict",      kind=TEXT, source=annotated("verdict"))
```

The writer walks the template and asks each column for its value. It contains no column names at
all, which is what makes AC-7's "adding or reordering columns requires no code change" true, and
what makes AC-6's rejection possible: an unknown column is a name that is not in this table, and the
message can list what is.

Every column also declares where its value comes from, which is what lets the export report at the
end how many columns were empty and *why*: nobody has annotated, the enrichment pass has not been
run, or nothing in this product fills that column. M-5 is why that report is worth having.

### D-3: templates are files, and `default` is not one

`default` is built into `columns.py`, as the brief's thirty-two names in the brief's order, and a
test compares the generated header row against that list character for character. It is not a file,
because a file can be edited and the default is a promise about a document somebody already has.

Anything else is a file, `<root>/templates/<name>.yaml`:

```yaml
columns: [Rank, Property, Town/Area, Price, Acres, Water Source, Verdict, Listing URL]
```

Read with the same round-tripping YAML the saved searches use, and checked when it is loaded rather
than when a cell is written: a template naming `Wells` is refused before a single row is built, with
the message naming `Wells` and listing what exists. A saved search points at one with the
`export.template` key it already has.

### D-4: three guards on every piece of text, and none of them optional

From M-1, M-2 and M-3, applied in `export/text.py` to every string that reaches a cell:

1. **Control characters are removed.** The ones XML cannot carry, which is what the library refuses.
   Removed rather than escaped, because they carry no meaning in a listing description and a run
   that dies over one is worse than a description missing an invisible byte.
2. **Text is cut at the cell limit, visibly.** At 32,764 characters plus an ellipsis, so the marker
   is inside the limit rather than pushing past it. The library's own truncation is silent, so this
   one has to happen first.
3. **The cell type is forced to text.** Every string cell, not the suspicious ones. A cell whose
   text begins with `=`, `+`, `-`, `@`, a tab or a carriage return is exactly the case this stops,
   and deciding per cell is how one gets missed.

The comma-separated form cannot force a cell type, because it has none. There, a value whose first
non-whitespace character is one of those gets a leading apostrophe, which is what a spreadsheet
application reads as "this is text". Non-whitespace on purpose: a leading space does not stop Excel
evaluating what follows it, and checking only the very first character is how the guard gets walked
around.

**That is the one place AC-12's "the same values" is not literally true**, and it is deliberate. The
alternative is a format that hands a spreadsheet an expression to evaluate, which the security
requirement forbids in the same document. So AC-12 is satisfied as "the same columns and the same
values, with each format's own protection applied", the test asserts equality of the unguarded
values and asserts the guard separately in each format, and the difference fires for none of the 263
real descriptions measured. Raised at the pre-build check rather than discovered in a test.

### D-5: the address links, and a property with no link is not a broken one

The Property cell carries the address as its text and the listing URL as its hyperlink, styled so it
looks like a link. A property whose only source row came from somewhere with no link is written as
plain text with no hyperlink at all, which is the spec's own edge case: a cell that looks like a
link and goes nowhere is worse than a cell that does not look like one.

The URL is checked before it becomes a hyperlink, the way the digest already checks one: `http` and
`https` only. A listing URL is source-supplied text and a hyperlink is a thing somebody clicks.

### D-6: nothing is overwritten, and a failure leaves nothing behind

Two rules, and they are different rules.

**An existing file is not replaced unless asked.** `homescout export` refuses a path that exists,
names it, and says that `--force` will replace it. That is AC-8's second branch taken explicitly:
the alternative reading, writing `sheet-2.xlsx` beside it, quietly accumulates files nobody asked
for and leaves a person unsure which one is current.

**A failure leaves no partial file at the destination.** The workbook is built in memory and written
to a temporary file beside the target, then moved into place, which on Windows is the same atomic
replace the digest already uses. A disk that fills up halfway through leaves last week's sheet
intact rather than a corrupt file with this week's name.

The Windows case the spec names is the file being open in Excel, which makes the replace fail with a
permission error. It is caught and reported as what it almost always is: the file is open, close it.

### D-7: export reads, and that is enforced rather than promised

AC-9 and AC-11 are two halves of one property, and both are testable rather than assertable:

- **It never writes to the store.** A test hashes every table in the database before and after an
  export and compares. Not a spot check of annotations: every table.
- **There is no import path.** A test asserts that nothing in `homescout/export/` calls
  `load_workbook`, opens a file for reading, or imports a reader, using the same source-scanning
  technique the credential test in the source adapters already uses.

### D-8: rows are gathered in bulk, once

A sheet over five thousand properties is five thousand of everything, and the obvious version asks
the store per property per column. So the row builder collects, in this order and each in one pass:
the snapshots, the annotations, the rule verdicts, the enriched values, and the cached model
extractions. Deterministic extraction is computed per row because it is regular expressions rather
than a query, which the previous feature measured.

The thirty-second budget in the non-functional requirements is then a budget on writing a file
rather than on talking to a database.

### D-9: an empty column says which kind of empty it is

Not in the sheet, which must stay recognizable, but in what the command prints and in `--json`:

```
83 properties written to portales.xlsx
  4 columns are empty because nothing in this tool fills them:
      Garage/Outbuildings, Annual Taxes, Crime/Safety, Sewage & Reclaimed-Water Exposure
  4 columns are empty because the enrichment pass has not been run for these properties:
      FEMA Flood Zone, Internet, Principal Aquifer, Fire/Egress/Terrain
  6 columns are empty because nothing has been annotated yet
```

M-5 is the reason. A person opening a thirty-two column sheet with eleven blank columns has three
different questions, and "run `homescout enrich`", "write some notes" and "no free source supplies
this" are three different answers. Getting that wrong costs somebody an afternoon looking for a bug
in the tool.

### D-10: what this feature does not own

- **Producing the values.** Extraction is feat-009 and enrichment is feat-007. This arranges them.
- **Editing an annotation.** That is the browser interface (feat-010) and the `annotate` command.
- **Reading a spreadsheet.** There is no import path and there will not be one (AC-11).
- **Filling the four structurally empty columns.** They are the person's own notes, by design.

## Verification approach

- **The default header row is compared against the brief's list**, in order, as a single string, so
  a reordering or a renamed column fails loudly.
- **Both formats are written and read back**, rather than asserted about in memory. A test writes a
  workbook, reloads it with the library, and checks the cell types, the hyperlink targets and the
  text.
- **The dangerous cells are real cells.** A property whose description begins `=cmd|'/c calc'!A1`
  and whose notes carry a control character, written to both formats, reloaded, and checked to be
  text in one and apostrophe-guarded in the other.
- **Non-ASCII goes through both formats.** Em dashes, accents and degree signs, which the corpus
  measured as present and which a comma-separated file on Windows loses without a byte-order mark.
- **The store is compared before and after**, table by table.
- **Five thousand properties are exported and timed**, marked slow.
- **A run with zero results still produces a workbook**, with headers and no rows.
