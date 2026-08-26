# Tasks — Spreadsheet export (feat-011)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## What a column is

- [x] T1: `export/columns.py`: one entry per column, each knowing its kind and how a row gets its
      value, and the built-in `default` template as the brief's thirty-two names in order (D-2, D-3,
      AC-1).
- [x] T2: The three derived columns, `$/sq ft`, `Acres` and `Price History & DOM`, each empty when
      its inputs are (AC-5, the unknown-price edge case); plus `Wildfire Hazard` and `Elevation (ft)`
      as columns a template may name and the default does not (M-6).
- [x] T3: `export/templates.py`: template files as configuration, the load-time check that every
      named column exists, and a message naming the one that does not (D-3, AC-6, AC-7).
- [x] T4 [P]: `tests/test_export_columns.py`: the default header row against the brief's list
      character for character, a non-default template, and an unknown column refused by name
      (AC-1, AC-6, AC-7).

## Writing text nothing will evaluate

- [x] T5: `export/text.py`: control characters removed, the cell limit cut visibly, and the forced
      text type, applied to every string rather than to the suspicious ones (D-4, M-1, M-2, M-3).
- [x] T6 [P]: `tests/test_export_safety.py`: a description beginning `=cmd`, notes carrying a
      control character, and text past the cell limit, in both formats, written and read back
      (security NFR, the formula and truncation edge cases).

## The workbook

- [x] T7: `export/rows.py`: one run's results as rows, with annotations, verdicts, enriched values
      and cached extractions gathered in bulk (D-8, AC-2, AC-10).
- [x] T8: `export/workbook.py`: the properties sheet, the areas sheet, the address hyperlink, and a
      property with no link written as plain text (D-5, AC-3, AC-4).
- [x] T9: The atomic write and the refusal to replace an existing file without `--force`, with the
      file-is-open-in-Excel case reported as itself (D-6, AC-8, reliability NFR).
- [x] T10 [P]: `export/delimited.py`: the same rows, comma separated, with a byte-order mark so a
      spreadsheet application on Windows reads the text correctly (AC-12, AC-13).
- [x] T11 [P]: `tests/test_export_workbook.py`: both sheets, the hyperlink target, a row per
      canonical listing, dropped properties absent, an empty search still producing a workbook
      (AC-2, AC-3, AC-4, the zero-results edge case).
- [x] T12 [P]: `tests/test_export_values.py`: an undetermined value is an empty cell with no
      placeholder, a merged property is one row, and the current annotations are the ones written
      (AC-5, AC-10, the merged-property edge case).

## Reading only

- [x] T13 [P]: `tests/test_export_readonly.py`: every table in the database hashed before and after
      an export and compared, and a source scan asserting nothing in the package reads a workbook
      (D-7, AC-9, AC-11).

## The surface

- [x] T14: `api.export` stops reporting itself unbuilt and does the work, returning what was written
      and which columns were empty and why (D-9). Record the change in feat-003's manifest.
- [x] T15: The `export` command gains `--to`, `--format`, `--template`, `--force` and
      `--include-dropped`, with `--json` and the usual exit codes. Record the change in feat-003's
      manifest.
- [x] T16 [P]: `tests/test_export_command.py`: the command end to end, the refusal to overwrite, and
      the empty-column report (AC-8, D-9).

## Finishing

- [x] T17 [P]: Five thousand properties exported and timed, marked slow (performance NFR).
- [x] T18: `openpyxl` added as a dependency, with the reason in `pyproject.toml`'s vicinity or the
      README rather than nowhere.
- [x] T19: Document export in the README: the two formats, the template file, and which columns are
      structurally empty and why (M-5).
- [x] T20: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T21: `/spec-flow:converge`, then the manifest stamp.

## Added while building

- [x] T22: A defect found by reading a real exported sheet: `central heating and air conditioning`
      recorded the heating and lost the cooling, because the pattern wanted `heat and air` exactly.
      Fixed in `extract/patterns.py` with a regression test citing `feat-009/AC-2`, and recorded in
      feat-009's drift ledger.

## Change: a county either way (`changes/a-county-either-way/`)

- [x] T-county-1: `export/columns.py`: `County/Region` becomes derived, reading the listing's county
      first and the looked-up one second, with the plain name in the cell either way so that one
      county does not sort as two (`feat-011/AC-14`).
- [x] T-county-2: `export/columns.py`: `County (looked up)` added outside the default sheet, holding
      only what the public record said, so which cells were borrowed stays answerable
      (`feat-011/AC-15`). The promised 32-column sheet is unchanged.
- [x] T-county-3: `tests/test_export_columns.py`: the listing's word wins, the lookup fills a blank,
      a borrowed county is spelled exactly like a stated one, neither knowing is an empty cell, and
      the looked-up column keeps its own answer (`feat-011/AC-14`, `feat-011/AC-15`).
