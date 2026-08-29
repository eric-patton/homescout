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

## Change: five more annotation fields (browser-interface `changes/choose-your-columns/`)

- [x] T-notes-1: `store/models.py`, `store/schema.py`, `store/migrations.py`: `taxes`, `crime`,
      `fire_egress`, `sewage_exposure` and `outbuildings` on the annotation, with `SCHEMA_V9`. On
      exactly the terms `judgment` was added on, which is `feat-001/AC-15`, `feat-001/AC-16` and
      `feat-001/AC-17` applying to them unchanged: written only by a person, never by a run,
      surviving every merge, unmerge and re-export.
- [x] T-notes-2: **Defect.** `store/core.py`'s annotation reader named its columns one at a time, so
      a value written to a field it did not know about went in and came back as nothing. Both the
      reader and the writer are built from `ANNOTATION_FIELDS` now, which is the only place the
      fields are declared.
- [x] T-notes-3: **Defect.** `store.get_preview_image` returned nothing for a merged record, because
      the picture belongs to whichever record was observed when it was fetched and merging never
      moves anything. It falls back to a constituent's picture, on the read side only.
- [x] T-notes-4: `store.live_listing_id` made public, for anything assembling what a person reads:
      an id held from before a merge is still a real record and is no longer the one to show.


## Change: words of our own

- [x] T-tags-1: `store/schema.py` version 10, `store/models.py`, `store/core.py`: tags as two
      tables (`feat-001/AC-28`).

      Two rather than one, so a word exists before anything carries it and outlives the last thing
      that did. That is what makes renaming and deleting real operations on a real thing rather
      than a find-and-replace over a text column, which is what a tag list kept in one comma-joined
      field always turns into.

      `COLLATE NOCASE` on both, and it is the load-bearing part: somebody typing "barn" a week
      after typing "Barn" means the same tag, and a store that disagrees hands them two piles of
      houses that should have been one. The casing first typed is what is kept and shown, read
      through a join to `tags` rather than off the row, or every spelling anybody ever typed would
      reach the sheet.

      No append-only trigger, for the third time in this schema and the same reason as versions 8
      and 9: a tag is the person's own note and the whole point is that they can change their mind.

- [x] T-tags-2: `store/core.py`: rename and delete (`feat-001/AC-29`). A rename onto a name that
      already exists merges the two, which is the only sane reading of the request and what
      somebody fixing a second spelling actually wants; the rows are moved one at a time and the
      collisions dropped, because `ON UPDATE CASCADE` would try to move a property onto a tag it
      already carries and that is the primary key twice. Deleting answers with how many properties
      lost the word, because that is the number somebody wants and the only way to know it
      afterwards would be to have remembered it.

- [x] T-tags-3: `store/core.py`: a merged property gathers its constituents' tags, and removing one
      reaches where it lives (`feat-001/AC-30`, constitution 7). Gathered rather than moved, like
      annotations, because moving is how a person's own data goes missing when a merge is undone.
      Removal has to reach the constituents anyway, or a tag that arrived on one half could be seen
      and never taken off, which reads as the tool ignoring the click.

- [x] T-tags-4: `store/core.py`: clearing every tag off a property (`feat-001/AC-28`). `tag NOT IN
      ()` with nothing in it is not false, it is unknown, so the delete matched no row and asking
      for no tags left every tag exactly where it was. Found by the test that asks for none.

## Defect: a picture went missing down a second merge

- [x] T-image-chain: `store/core.py`: a picture is found however many merges deep it lies
      (`feat-001/AC-25`).

      A merged property reads its picture from its constituents, and that worked for one merge. A
      merge writes a *new* listing and points the old ones at it, so merging an already-merged
      property leaves the picture two links down a chain, and both lookups followed exactly one
      link: the one that answers for a single property, and the one that answers for a whole table
      at once. Both said no photograph about a property whose photograph was on the disk.

      Found while answering why six Redfin properties had no picture. They were not these six. On
      the real workspace, eighteen properties showed none; twelve were Redfin-only, which is that
      source carrying no photographs at all, and the other six were this, every one of them a house
      seen on three sites and merged in two passes. The fix put all six back without a single
      request.

      A recursive walk down the chain rather than a join across one link, which is the shape
      `store/diff.py` already uses for the same reason. `UNION` rather than `UNION ALL`, because
      this walks links a person can create and undo, and a cycle has to end the query rather than
      the process.

- [x] T-image-chain-2: `tests/test_store_history.py`: a picture stored before two merges is still
      found after them (`feat-001/AC-25`). Both answers are asserted, the one for a single property
      and the one for the whole table, because they are separate queries and either could drift
      from the other. Checked against the one-link version, which fails it.

## What a pass is doing (`changes/what-a-pass-is-doing/`)

- [ ] T-pass-1: `store/schema.py`: the table an operation records itself in, and its lines
      (`feat-001/AC-31`). A lifecycle row rather than an observation, the way `runs` already is, so
      it takes the same forward-only trigger: only the outcome may move, and only from running to
      completed or failed. It carries the operation's kind, when it started, when it was last
      touched, when it finished, its terminal state, and its outcome or its failure. A search run's
      row carries that run's id, so the two are one operation rather than two accounts of it. Lines
      are their own table, keyed by the pass and ordered, and bounded the way the in-memory version
      already bounds them.

- [ ] T-pass-2: `store/schema.py`: the migration (`feat-001/AC-31`). This store is opened by a build
      that brings an older file forward, and the installation it has to bring forward is 200MB with
      seven runs in it.

- [ ] T-pass-3: `store/core.py`, `store/models.py`: writing and reading one (`feat-001/AC-31`).
      Beginning one, saying a line, touching it without saying anything, ending it as completed or
      as failed, and reading what is running now and what a named kind last did.

- [ ] T-pass-4: `store/core.py`: a pass not touched recently enough reads as stopped without
      finishing (`feat-001/AC-31`). Computed when the row is read rather than written by anything,
      because the only process that could write it is the one that died. Never reported as
      completed and never as failed, because nothing knows which it was.

- [ ] T-pass-4a: `store/core.py`: every line and every failure is scrubbed of credentials on the
      way in (`feat-001/AC-31`). In the one function that writes, not at each call site, because a
      caller that forgets is the failure this exists to remove. Reuse the extraction layer's own
      stripper rather than writing a second one. A stored line is bounded in length as well as in
      count, because it can carry a snippet of a remote refusal and that snippet is now durable.

- [ ] T-pass-5: `tests/test_store_schema.py`, `tests/test_store_history.py`: the lifecycle, the
      forward-only rule, the stopped-without-finishing reading, and that a pass row is not an
      observation and does not touch one (`feat-001/AC-31`, `feat-001/AC-2`, `feat-001/AC-17`).
      Including that a failure carrying an address with a key in its query string is stored without
      it, asserted against the unscrubbed version, because that is the one thing here that turns a
      momentary string into bytes on a disk that gets backed up.
