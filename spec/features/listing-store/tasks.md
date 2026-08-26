# Tasks — listing store and snapshot history

Glyphs: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` not applicable ·
`[H]` needs a human. `[P]` marks a task that can run alongside its group peers.

Each task names the criteria it satisfies. Tests carry the trace token `feat-001/AC-N`.

## Group A — foundation

- [x] **T1. Project scaffolding.** `pyproject.toml` with `uv`, `.python-version` pinned to 3.13,
      `src/homescout/` package layout, pytest and ruff configured, a `slow` test marker registered.
      Verify: `uv run pytest` collects zero tests and exits clean.
- [x] **T2. Database open, create, and version.** Open or create the file, set write-ahead logging
      and a busy timeout, read and write `PRAGMA user_version`, and run forward-only migrations.
      Refuse a file stamped newer than the code, naming both versions.
      Satisfies AC-22. Files: `src/homescout/store/db.py`, `src/homescout/store/migrations.py`.
- [x] **T3. Schema, version 1.** `runs`, `raw_listings`, `listings`, `listing_snapshots`,
      `listing_events`, `annotations`, `area_notes`, `listing_images`, with indexes for the
      comparison queries. All timestamps are ISO-8601 UTC text, so ordering is lexicographic and a
      daylight-saving transition changes nothing.
      Satisfies AC-23. Files: `src/homescout/store/schema.py`.
- [x] **T4. Append-only enforcement.** `BEFORE UPDATE` and `BEFORE DELETE` triggers that abort, on
      every history table. Tests issue the statements through a raw connection.
      Satisfies AC-2, AC-14.

## Group B — writing what a run saw

- [x] **T5. Run lifecycle.** Start a run with a generated id, record per-source outcome and row
      count, complete it in a final transaction. Only completed runs are comparison baselines; an
      interrupted run stays `running` and is excluded.
      Satisfies AC-18, AC-19.
- [x] **T6. Recording source rows.** Write raw rows with their source, fetch time, and the source's
      original payload retained. Handle the same property appearing twice in one response.
      Satisfies AC-13, AC-24.
- [x] **T7. Canonical listings and supersession.** Promote a single source row to a canonical
      listing. Immutable ids, `superseded_by` for merges, retraction for undo. Resolve a listing to
      its source rows.
      Satisfies AC-13. Underpins AC-16.
- [x] **T8. Snapshots.** Write one complete snapshot row per matching listing per run, covering
      every declared compared field, so the state at any past run is one lookup away.
      Satisfies AC-1, AC-6.
- [x] **T9. Presence and the event timeline.** Compute presence from each run's snapshots and per-source
      outcomes: absent everywhere with all sources succeeding becomes `disappeared`; absent with any
      source failed stays `observed`; a disappeared listing observed again returns. Record each
      transition as a dated event. Disappeared listings stay readable and queryable.
      Satisfies AC-7, AC-8, AC-9, AC-10, AC-11.

## Group C — the arithmetic

- [x] **T10. The comparison.** Produce exactly one difference event per listing across two points in
      time: `new`, `changed`, `unchanged`, `gone`, `returned`. Changed events name each differing
      field with before and after; price changes carry an absolute difference and a direction.
      Reproducible for fixed endpoints regardless of what ran in between.
      Satisfies AC-3, AC-4, AC-5, AC-20, AC-21.
- [x] **T11. Locally derived history.** Days on market from first local observation, and the price
      and listing-status timeline. A source's own contradictory value never substitutes.
      Satisfies AC-12.

## Group D — the user's own data

These three touch disjoint files and can run alongside each other. T13 and T14 need only group A;
T12's merge-and-undo behavior also needs the supersession mechanics from T7, which is ordered
earlier.

- [x] **T12. Annotations.** `[P]` Read and write rank, verdict, red flags, summary, next step, and
      free notes against a listing id, with an update time. Never written by a run. Survive merge
      and unmerge by never moving.
      Satisfies AC-15, AC-16, AC-17.
- [x] **T13. Area and town notes.** `[P]` Notes addressed by area rather than by property, with the
      same durability as annotations and never touched by a run.
      Satisfies AC-26.
- [x] **T14. Preview image storage.** `[P]` Store one image per listing on disk with its path and
      retrieval time recorded. Retained through a disappearance. A later failed retrieval never
      replaces a good image. Full-size addresses recorded, images not retained.
      Satisfies AC-25.

## Group E — the unhappy paths and the bar

- [x] **T15. Error surfaces.** A locked file, a missing or empty file, a file from a newer version,
      and a write that fails partway. Each reports a message naming the likely cause, and leaves the
      previous completed run usable as a baseline.
      Covers the spec's edge cases and the reliability requirement.
- [x] **T16. Performance.** A slow-marked test building 5,000 synthetic listings, asserting the
      write and comparison bounds. Excluded from the default run.
      Covers the performance requirement.
- [x] **T17. README with the legal posture.** The constitution requires the personal-use,
      low-volume, not-republished, not-commercialized constraint to travel with the code. No feature
      owns the README and it gets created in this one.
      **Project setup carried by this feature, not part of its scope.** Recorded here so a later
      audit reads it as deliberate rather than as unrequested work. Satisfies a constitution
      requirement, not a criterion of this feature.

## Group F — remediation from the first code-against-spec audit

- [x] **T- [x] **T18. Keep every source row a response contained.** `gap-001`. Two rows carrying the same
      source identifier in one response are currently collapsed to one, so the second row's values
      are discarded. When they differ, that is evidence destroyed, against both AC-24 and the
      project rule that source rows are never destroyed. Record every row; collapse only the
      snapshot and the listing resolution, which is what AC-24 actually asks for.
- [x] **T- [x] **T19. Retain a source's own days-on-market claim.** `gap-002`. The guarantee that our own
      figure is never overwritten currently holds because there is nowhere to put the source's
      value, which means the criterion's own scenario cannot be exercised at all. Keep the source's
      claim as an informational field, uncompared, and prove by test that it never substitutes for
      the locally derived figure.
- [x] **T20. Remove the digest-oriented total from the comparison.** `gap-003`. The comparison
      exposes a combined "matched" count that nothing in this feature's spec asks for; it
      anticipates the run digest, which belongs to the command line feature. Remove it here and let
      that feature define it when it needs it.

## Change: a page per site (`changes/a-page-per-site/`)

- [x] T-link-1: `store/models.py` and `store/core.py`: `SourceLink` carries `listing_url`, read from
      the raw row the query already joins (`feat-001/AC-27`). No migration: the column exists and
      every adapter already fills it.
- [x] T-link-2: `api.py` and `cli/render.py`: the listing answer's source list carries each site's
      address and the terminal prints it, so neither surface has it alone (product invariant 5).
- [x] T-link-3: `tests/test_store_history.py`: a record merged from two sites reports both addresses
      and they differ (`feat-001/AC-27`).
