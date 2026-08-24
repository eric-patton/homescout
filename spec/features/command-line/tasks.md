# Tasks — Command line and run orchestration

Glyphs: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` not applicable · `[H]` needs a
human. `[P]` marks a task that can run alongside its peers.

Decisions referenced below are the `D-N` sections of `plan.md`.

## Core vocabulary

- [ ] **T1 — Failure kinds.** `src/homescout/errors.py`: `HomescoutError`, `InvalidInput`,
      `PreconditionNotMet`, each carrying an actionable message. Nothing else. (D-6)
- [ ] **T2 — Exit codes.** `src/homescout/cli/codes.py`: `ExitCode` as an `IntEnum` (success 0,
      degraded 1, invalid input 2, precondition 3, internal error 4), `code_for(exception)` mapping
      the two core errors plus the store's `NoBaselineError` and `StoreLockedError`, and
      `worst_of(codes)` implementing the precedence rule. (D-6)

## Ports

- [ ] **T3 [P] — The saved-search port.** `src/homescout/search.py`: `SearchProblem(location,
      message)`, the `SearchDefinition` and `SearchCatalog` protocols, `InMemorySearch` and
      `InMemoryCatalog`, and `register_catalog` / `catalog_for` mirroring the source registry.
      `InMemorySearch.keeps` keeps everything. (D-3)
- [ ] **T4 [P] — The ambiguous-match port.** `src/homescout/matches.py`: `AmbiguousMatch(id,
      listing_ids, agreed, conflicted, noticed_at)`, the `MergeQueue` protocol (`pending`, `get`,
      `record`), `InMemoryQueue`, and its registry. No resolution logic here. (D-4)
- [ ] **T5 [P] — One run at a time.** `src/homescout/claim.py`: `claim_run(directory, search_name,
      run_id)` as a context manager over `msvcrt.locking` on Windows and `fcntl.flock` elsewhere.
      Byte 0 is the lock; the holder's run id and start time are written after it and are readable
      by a process that failed to take the lock. Failure raises `RunInProgress(PreconditionNotMet)`
      carrying both. (D-8)

## The loop

- [ ] **T6 — Pair a row with the property it became.** Widen `Store.record_observations` to return
      one canonical listing id per input row, in input order. Update the docstring, add a test in
      `tests/test_store_history.py` citing `feat-001/AC-4` for a response repeating one identifier,
      and record the change under "Later changes by other features" in
      `spec/features/listing-store/feature.md`. (D-10)
- [ ] **T7 — The run loop.** `src/homescout/runner.py`: for each configured source, read its
      capabilities, ask one query per area, drop a repeat across areas but never inside one
      response, apply the undeclared filters locally (keeping a row whose field is absent), apply
      the definition's exact test, record observations, record the per-source outcome. Then complete
      the run and compare. Returns `RunOutcome(run, comparison, sources)` where each source entry
      carries its outcome, row count, truncation, and its applied-by-source and applied-locally
      field lists. Covers AC-28 and AC-29. (D-9, D-12, D-14)
- [ ] **T8 — Preview images.** Inside the loop: for each recorded property with no stored image,
      call the adapter's `preview` and hand the bytes to `Store.store_preview_image`, and for no
      other property. Skipped entirely under `--no-images`. One image in memory at a time. Covers
      AC-27. (D-11)
- [ ] **T9 — The digest.** `src/homescout/digest.py`: the document of D-13 from a `RunOutcome` or a
      `Comparison`, with every key always present, the per-property summary, and days on market read
      from the store's local history. (D-13)
- [ ] **T10 — The facade.** `src/homescout/api.py`: `open_workspace`, `run_search`, `run_all`,
      `changes`, `list_searches`, `show_search`, `validate_search`, `create_search`, `edit_search`,
      `annotate`, `pending_matches`, `resolve_match`. `resolve_match` supersedes for "same" and
      records the verdict either way. Nothing else in this module. (D-2, D-4)

## The surface

- [ ] **T11 — Human rendering.** `src/homescout/cli/render.py`: one function per result the facade
      returns. Plain text, computed column widths, no colour, no dependency. (D-17)
- [ ] **T12 — The command line.** `src/homescout/cli/main.py`: the parser and every subcommand of
      AC-20 (`run`, `changes`, `searches list|show|validate|create|edit`, `annotate`,
      `matches list|resolve`, `enrich [--stale] [--search NAME]`, `export [--search NAME]`,
      `serve [--port N]`), the global `--db`, `--json`, `--output`, `--delay` and `--version`, UTF-8
      stream rewrapping, `--output` parent checked before any work, `--delay` validated through the
      source layer's own policy before anything is fetched, top-level translation of every exception
      to a code, and `run()` as the console entry point. `enrich`, `export` and `serve` exit with the
      precondition code naming what is missing. No option accepts a credential, and `serve` gets no
      option that could move it off localhost. Add `[project.scripts] homescout =
      "homescout.cli.main:run"` to `pyproject.toml`. Covers AC-30. (D-5, D-7, D-14, D-15a)

## Tests

- [ ] **T13 [P] — Fakes.** `tests/cli_fakes.py`: an in-memory catalog builder over feat-002's
      `StubSource`, a temporary-store fixture, and `invoke(args, ...)` returning
      `(exit_code, stdout, stderr)`. (D-18)
- [ ] **T14 — The loop.** `tests/test_run_loop.py`: AC-4 through AC-9 — the filter split and its
      report, a row kept when its field is absent, the cross-area repeat rule against the
      within-response rule, previews fetched once and not re-fetched, a degraded run that still
      records, an all-failed run that marks nothing gone, and the run record's contents.
- [ ] **T15 [P] — The digest.** `tests/test_digest.py`: AC-10 through AC-12 — one entry per search,
      the separate change sets, price direction, flagged present and empty, and size as a function
      of what changed rather than of how much matched.
- [ ] **T16 [P] — The claim.** `tests/test_run_claim.py`: AC-26 — a second run declines with the
      precondition code while a real subprocess holds the lock, the message names the run in
      progress and its start time, and the next run proceeds after that process is killed.
- [ ] **T17 — The machine contract.** `tests/test_cli_contract.py`: AC-1 through AC-3, AC-17, AC-20,
      AC-21 — machine output parses, streams stay separate, the codes are stable, non-ASCII survives
      on Windows, `--output` behaves in all three cases, human output is the default, every command
      is reachable, AC-30's delay reaches the session and its out-of-range value is refused, AC-31's
      parser carries no credential option, and importing the command module neither loads `requests`
      nor costs more than the measured budget.
- [ ] **T18 — The operations.** `tests/test_cli_operations.py`: AC-13 through AC-16, AC-18, AC-19,
      AC-22 through AC-25 — comparisons and their reproducibility, no baseline, unknown name,
      one bad definition among many that does not stop the good ones, annotation through both
      surfaces, ambiguous matches through both surfaces, the identical-store-state test, the import
      ban and syntax-tree check, and the internal-error path leaving the previous run usable.
- [ ] **T19 — Live.** `tests/test_cli_live.py`, marked `slow`: one real search over a real place run
      twice through `main(["run", ...])`, asserting the second digest reports no new properties and
      the run record names the source's outcome.

## Finish

- [ ] **T20 — Gate.** `uv run ruff check .`, `uv run pytest -q`, `uv run pytest -m slow -q`, then
      `node scripts/validate.mjs`. Then the code-against-spec audit (`/spec-flow:converge`).
