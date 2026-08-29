# Implementation plan — listing store and snapshot history

Realizes `spec.md` in this folder. Requirements live there; this document is the how, and is
expected to be revised as the code teaches us things the spec did not.

## Design decisions

### D-1. Layout: one package, layers as subpackages, source outside `spec/`

```
pyproject.toml
src/homescout/
  __init__.py
  store/            <- this feature
  sources/          <- feat-002, feat-005
  merge/            <- feat-006
  enrich/           <- feat-007
  rules/            <- feat-008
  extract/          <- feat-009
  cli/              <- feat-003
  web/              <- feat-010
  export/           <- feat-011
tests/
  test_store_*.py
data/                 <- runtime only, gitignored: the database and stored images
```

Layers depend downward only, per the constitution. `store` depends on nothing above it, which is
what makes this feature buildable first and testable without a network.

### D-2. Python 3.13, pinned; `uv` manages it

The brief chose Python and `uv`. The machine has 3.14.6, which is newer than the wheel coverage of
the listing libraries this project will depend on later (`homeharvest` pulls in `pandas`). Pinning
3.13 in `.python-version` avoids discovering that in feat-002, when it would be a surprise rather
than a decision. `uv` fetches the interpreter, so nothing needs installing by hand.

Revisit when the source adapters land and their real constraints are known.

### D-3. Standard-library `sqlite3`, raw SQL, no object-relational mapper

The whole point of this feature is a small set of tables with unusually strict rules about what may
be written to them. An object mapper adds a layer of indirection over exactly the discipline that
must not be subverted, and it is a dependency that will outlive its usefulness. A thin repository
module over hand-written SQL is smaller, and makes the append-only rules legible at the point they
are enforced.

### D-4. Append-only is enforced by the database, not by convention

Every history table (`raw_listings`, `listing_snapshots`,
`listing_events`) carries `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE(ABORT)`.

This is the single most important decision in the plan. AC-2 says an attempt to update a recorded
observation must fail; making it fail in the database rather than in a code path means it stays
true for code written years from now by someone who has not read the constitution, and it stays
true for a person poking at the file with a SQLite browser. It also makes AC-2's test trivial and
honest: issue an `UPDATE` and assert the exception.

### D-5. One complete snapshot row per listing per run

`listing_snapshots` carries a full copy of every compared field, for every matching listing, on
every run. Append-only, one row, no reconstruction.

An earlier draft of this plan recorded a lightweight observation every run and a full copy only on
change, roughly twenty times smaller. The pre-build check rejected it against the constitution, and
on reflection the smaller design was the wrong trade regardless. Answering "what did run R see"
would have required combining two tables, which introduces a state where they disagree, in the one
component every other feature trusts and whose corruption is unrecoverable because no source can
tell us last month's price. Simplicity is worth more here than storage.

On size: the expected load is a county run weekly, in the hundreds of listings, which is a few
hundred megabytes over years. The multi-gigabyte case only appears at the specification's ceiling
of 5,000 listings run daily, sustained for years. If that ever becomes real, the constitution now
binds the guarantee rather than the layout, so changing the storage is an ordinary decision rather
than an amendment.

### D-6. The compared field set is declared, not inferred

One module-level constant lists the fields a difference event may name. AC-6 says a field the tool
does not compare never appears in a `changed` event; deriving the set from whatever a source
happened to return would make that unenforceable and would make every source schema change look
like a market event. Adding a field to the set is a deliberate edit with a test.

### D-7. Canonical listings are superseded, never rewritten, which is how annotations survive

`listings` rows carry an immutable id and a nullable `superseded_by`. A merge writes a **new**
listing row and points its constituents at it; an unmerge clears the pointer and retracts the merged
row. Nothing is deleted and no annotation ever moves.

This is what makes AC-16 true by construction rather than by careful bookkeeping: annotations are
attached to a listing id permanently, so a merge-and-undo cycle cannot lose one, because it never
touches one. The merged listing presents the union of its constituents' annotations.

Merging itself is feat-006's; this feature provides the supersession mechanics and the guarantee.

### D-8. Run identity is a generated identifier, and only completed runs are baselines

`runs` rows carry a generated unique id (not a timestamp, so the same-second edge case is a
non-issue) and a `status` of `running`, `completed`, or `failed`.

This also answers the spec's open question: snapshots are written **incrementally** as each
source returns, and the run becomes `completed` in a final transaction. An interrupted run leaves
its rows in place, marked `running`, where they are visible for debugging but are excluded from
every comparison (AC-19). Choosing this over a single end-of-run commit means a long run that dies
at 90 percent has not thrown away 90 percent of its network work, which matters when every request
is deliberately slow.

### D-9. Time is UTC text, sortable

All timestamps are ISO-8601 UTC with a `Z` suffix, stored as text. Lexicographic order equals
chronological order, which keeps the comparison queries simple, and the values are readable when
someone opens the file directly. AC-23 falls out of never storing a local time at all.

### D-10. Schema version in `PRAGMA user_version`, forward-only migrations

A version integer plus an ordered list of migration functions. Opening an older file migrates it
forward; opening a newer one refuses with both version numbers named (AC-22). Eleven further
features add tables to this file, so this exists from the first commit rather than being retrofitted.

### D-11. Write-ahead logging and an explicit busy timeout

WAL mode plus `busy_timeout`, because the browser interface and a scheduled command will hold this
file open at the same time on a machine where that is the normal case. A lock that outlasts the
timeout is surfaced as a message naming the likely cause, not as a raw database error.

### D-12. Stored images live on disk, not in the database

One preview image per listing at `data/photos/<first two characters of id>/<id>.<ext>`, with the
path and retrieval time recorded in the database. Keeping binary data out of the file keeps the
comparison queries fast and keeps the database small enough to copy. Retrieval is feat-002's job;
this feature owns the storage contract and the guarantee that a failed later retrieval never
replaces a good image with nothing.

## Task breakdown

See `tasks.md`. Ordering follows the dependency chain: schema before writers, writers before the
comparison, comparison before the derived history. Tasks marked `[P]` touch disjoint files and
depend on no sibling in their group.

## Verification approach

Tests are pytest, under `tests/`, matching the workspace's declared `tests/**/test_*.py`. Every
test that verifies a criterion names its trace token `feat-001/AC-N` in the test's docstring, which
is how criterion coverage is computed.

**Seams.** Two, and no test reaches past either into internals:

1. `homescout.store` — the module's public functions. Every behavioral criterion is exercised here.
2. A raw `sqlite3` connection to the same file — used only by the criteria that are *about* the
   database's own guarantees (AC-2, AC-14), where the point is that the protection holds even for a
   caller who bypasses the module.

| Criteria | Seam | How |
|---|---|---|
| AC-1, AC-3, AC-4, AC-20, AC-21 | store API | Build fixture runs, compare, assert the event sets and their reproducibility |
| AC-2, AC-14 | raw connection | Issue `UPDATE` and `DELETE` against history tables, assert they abort |
| AC-5, AC-6 | store API | Fixture runs differing in one field at a time |
| AC-7, AC-8, AC-9 | store API | Fixture runs with per-source outcomes set to success and failure |
| AC-10, AC-11 | store API | Observe, skip, observe again; assert presence, events and readability |
| AC-12 | store API | A source row carrying a contradictory days-on-market value |
| AC-13 | store API | Resolve a listing to its source rows and assert attribution |
| AC-15, AC-16, AC-17 | store API | Annotate, run, merge, unmerge, assert identical content throughout |
| AC-18, AC-19 | store API | Complete and interrupted runs, assert baseline selection |
| AC-22 | store API | Open files stamped older and newer than current |
| AC-23 | store API | Timestamps around a daylight-saving transition |
| AC-24 | store API | One source returning a duplicate within one response |
| AC-25 | store API + filesystem | Store an image, mark disappeared, assert retention; fail a later retrieval, assert the good image survives |
| AC-26 | store API | Write area notes, run, assert unchanged and untouched by the run |

Performance criteria are measured by a test that builds 5,000 synthetic listings and asserts the
write and comparison bounds from the spec's non-functional requirements. It is marked slow and
excluded from the default run, because a test suite that takes a minute stops being run.

Test commands name explicit paths, never a bare directory:

```
uv run pytest tests/test_store_schema.py tests/test_store_history.py tests/test_store_diff.py
uv run pytest -m slow tests/test_store_performance.py
```

## Deviations from the constitution

None. D-5 previously deviated from non-negotiable 1 and was rejected by the pre-build check. The
plan now writes a full snapshot per listing per run, and the non-negotiable has separately been
reworded to bind the recoverability guarantee rather than a table layout.

## What a pass is doing (`changes/what-a-pass-is-doing/`)

**A second table rather than a column on `runs`.** `runs` answers "was there a run and what did it
find", and it is the anchor for snapshots, events and the whole comparison. What is being added
answers "is something happening now and what has it said", and it exists for the five operations
that have no run row at all. Widening `runs` would have meant a row for an extraction pass with a
`search_name` that is not a search, which makes every query over runs wrong by one row.

**A search run gets a row in both, and the new one carries the run id.** Not duplication: a reader
asking what is happening gets one answer covering every operation, and a reader asking what a run
found gets `runs` exactly as before. The link is what stops those becoming two accounts of one
thing.

**Touched on a schedule, not only when it speaks.** The obvious implementation is to treat the last
progress line as the heartbeat, and it does not work here: extraction says one line at the start and
then nothing for the length of the pass, which is minutes, by design. So the recorder touches the
row on a clock of its own while it is open. The threshold for reading a row as stopped is a multiple
of that interval rather than a number chosen separately, so the two cannot drift apart.

**Stopped is computed on read, never written.** The only process that could write "this stopped" is
the one that was killed. So it is a reading of `updated_at` against the clock, and it is reported as
its own state: never completed, because the work did not complete, and never failed, because nothing
observed a failure. This is also why the existing gap in `runs` (a killed run says "running" for
ever) stops being visible in practice, since the pass row for that run is subject to this rule.

**Operational, and the one thing here that may be pruned.** Nothing computes a difference over time
from these rows and no annotation refers to them, so age may remove them without losing anything
non-negotiable 1 protects. Said out loud in the spec because every other table in this store is
append-only history and a reader is entitled to assume this one is too.
