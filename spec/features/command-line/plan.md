# Implementation plan — Command line and run orchestration

Feature `feat-003`. Depth `mvp`. Depends on the listing store (`feat-001`) and the source adapters
(`feat-002`), both done.

This is the feature that turns "can fetch listings" into "did fetch listings, and here is what
moved". It owns three things: the run loop that drives sources into the store, the digest shape
that says what changed, and the machine contract (structured output plus stable exit codes) that a
Windows scheduled task and an automated agent drive without reading English.

## What was measured before deciding

Four things were checked against the real code and the real platform rather than assumed.

1. **Detecting whether another run is still alive.** The obvious design for "one run at a time" is a
   file holding a process id, plus a liveness probe. On Windows, `os.kill(pid, 0)` was measured to
   return without terminating the target (CPython 3.13 special-cases signal 0), so the probe itself
   is safe. It is still the wrong primitive: a pid file left by a killed process needs a staleness
   policy nobody can tune correctly (a legitimately slow paced run over a county outlives any
   timeout a crashed run should not), and process ids are reused. An operating-system file lock was
   measured instead: a second process's non-blocking claim fails immediately with
   `PermissionError`, can still read the holder's metadata from an unlocked byte of the same file,
   and the lock is released by the operating system when the holder is killed without cleanup. It
   needs no staleness policy at all. See D-8.

2. **Startup cost.** `python -c "import homescout.store, homescout.sources"` completes in 120-132 ms
   of total process time, of which 46 ms is this package's own imports, and `requests` is *not*
   loaded (the sources package defers its transport import until a session is actually built). The
   non-functional requirement that a scheduled task spend its time on network pacing rather than on
   process startup is therefore already satisfied, and the thing that would break it is an eager
   import of `requests` from the command layer. See D-15.

3. **The comparison engine already refuses to invent disappearances.** `store/diff.py` guards its
   `gone` events with `target.all_sources_succeeded`, and its baseline query takes the latest
   snapshot from *any* completed run at or before the cutoff rather than only the baseline run's
   own rows. Two consequences shaped this plan: a run where every source failed can be completed
   safely, because it neither marks anything gone nor erases the previous state it would otherwise
   become the baseline for; and the run loop needs no absence logic of its own. AC-6 is satisfied by
   handing the store honest per-source outcomes, which is the only thing the loop has to get right.

4. **Pairing a fetched row with the property it became.** `Store.record_observations` returns
   canonical listing ids with repeats collapsed, so its result is shorter than its input whenever a
   source repeats an identifier inside one response. Storing a preview image needs the pairing, and
   zipping a collapsed list against the original rows would silently attach images to the wrong
   properties from the first repeat onward. See D-10, which widens that return rather than
   reconstructing the store's identity rule in a second place.

## Design decisions

### D-1 — The run loop is a core layer, not part of the command

Non-negotiable 8 and product invariant 5 say the same thing twice: neither surface holds business
logic, and anything one surface can do the other can do. That is only structurally true if the
command layer has nothing to hold. The layout:

```
src/homescout/
  records.py        # existing
  store/            # existing (feat-001)
  sources/          # existing (feat-002)
  errors.py         # NEW  the two failure kinds every surface has to distinguish
  search.py         # NEW  the saved-search port, an in-memory catalog, the catalog registry
  matches.py        # NEW  the ambiguous-match port and an in-memory queue
  claim.py          # NEW  one run at a time per saved search
  runner.py         # NEW  the run loop
  digest.py         # NEW  the digest shape and its rendering to a plain dictionary
  api.py            # NEW  the core operations both surfaces call
  cli/
    __init__.py
    main.py         # NEW  argument parsing, stream discipline, exit codes
    render.py       # NEW  human rendering
    codes.py        # NEW  the five exit codes
```

Layers depend downward only, as the constitution requires: `cli` sees `api`, `api` sees
`runner`/`digest`/`search`/`matches`/`store`, `runner` sees `sources` and `store`.

### D-2 — One facade, `api.py`, is the seam both surfaces enter through

Every command is one call into `homescout.api`. The browser interface (feat-010) will call the same
functions with the same arguments. This is what makes AC-18 a test rather than a promise: performing
an operation through `api` directly and through `main([...])` must leave the store in an identical
state, which is trivially true when the second is a thin call to the first, and impossible to fake
when it is not.

The facade is deliberately small: `open_workspace`, `run_search`, `run_all`, `changes`,
`list_searches`, `show_search`, `validate_search`, `create_search`, `edit_search`, `annotate`,
`pending_matches`, `resolve_match`, plus `enrich`, `export` and `serve` for the three commands whose
features are not built (D-5) and two helpers a surface needs to ask a question with, `database_path`
and `moment`. Nothing else, and a test holds it to exactly that list: a command that needs something
outside it is logic drifting upward into the surface.

The facade also translates the store's own errors into the two deliberate kinds, so the command
layer never imports the store to find out what went wrong. That is what lets the exit-code mapping
know only about `InvalidInput` and `PreconditionNotMet`, and it is what makes the import ban in D-16
absolute rather than nearly absolute.

### D-3 — Saved searches arrive through a port, not a file format

Saved searches and geography (`feat-004`) depends on this feature, not the other way round, which is
the right order: this feature defines the contract a saved search must satisfy, and that feature
supplies the hand-editable file and the two-stage geography behind it. So the run loop never sees
YAML. It sees:

```python
class SearchDefinition(Protocol):
    name: str
    sources: tuple[str, ...]          # which adapters this search uses
    def queries(self) -> tuple[SearchQuery, ...]: ...   # coarse, one per area
    def keeps(self, fields: ListingFields) -> bool: ... # the exact local test
    def problems(self) -> tuple[SearchProblem, ...]: ...

class SearchCatalog(Protocol):
    def names(self) -> tuple[str, ...]: ...
    def load(self, name: str) -> SearchDefinition: ...
    def create(self, name: str) -> SearchDefinition: ...
    def edit(self, name: str, changes: Mapping[str, object]) -> SearchDefinition: ...
```

`SearchProblem` carries `location` (a file path and line, or any locator the catalog understands)
and `message`, because AC-16 requires enough location detail to fix a definition by hand and this
layer must carry it through without knowing what it means.

`keeps` is where feat-004's exact point-in-polygon test will live. The in-memory catalog that ships
here keeps everything, which is the honest behavior for a definition with no geometry.

A registry mirrors the source registry (`register_catalog(name, factory)`), so feat-004 adds a file
catalog without this feature being touched. With no catalog registered, `names()` is empty and every
name is unknown, which is exactly AC-15's behavior and not a special case.

### D-4 — The ambiguous-match queue is a port for the same reason

AC-24 and AC-25 require listing queued ambiguous matches with the signals that agreed and
conflicted, and resolving them as the same or as different properties, indistinguishably from the
browser. Nothing queues an ambiguous match yet: that is address matching (`feat-006`), and there is
no table for it. So `matches.py` defines `AmbiguousMatch(id, listing_ids, agreed, conflicted,
noticed_at)` and a `MergeQueue` protocol (`pending`, `get`, `record`), ships an in-memory queue, and
feat-006 supplies the store-backed one.

The *decision* stays here, in `api.resolve_match`, not in the queue: resolving as the same property
calls `Store.supersede(..., decided_by="human")`, resolving as different records that verdict so a
later run does not re-queue it. Both surfaces call that one function, which is what makes AC-24's
"indistinguishable in the store" true by construction.

### D-5 — Every command in the brief exists from day one; a command whose feature is unbuilt reports the precondition code

AC-20 requires the commands to exist and be reachable. Three of them belong to features not yet
built: enrichment (`feat-007`), export (`feat-011`), and the local server (`feat-010`). They are not
omitted and they do not pretend. They parse their arguments, validate them, and exit with the
precondition code and a message naming what is missing.

The reasoning is the machine contract itself: the surface *is* the contract, and an automated caller
must be able to discover it without keeping a version matrix. "Valid, but cannot proceed yet" is
precisely what AC-3 defines the precondition code to mean, so this needs no new concept.

### D-6 — Exactly five exit codes, with the numbers fixed here

| Code | Name | Meaning |
|---|---|---|
| 0 | success | Everything asked for was done |
| 1 | degraded | Completed, with at least one source `failed` or `unavailable` |
| 2 | invalid input | Usage, an unknown name, or a saved search that fails validation |
| 3 | precondition | Valid, but cannot proceed yet (no baseline, run in progress, store locked, feature unbuilt) |
| 4 | internal error | Anything unexpected |

Invalid input is 2 because that is what `argparse` already exits with on a usage error, so a bad flag
and an unknown search name land in the same class without fighting the parser. The remaining codes
avoid the shell's reserved range (126 and above).

Precedence when one invocation produces several, which `run --all` can: internal error, then invalid
input, then precondition, then degraded, then success. Invalid input beats degraded deliberately: a
source that failed is weather, a definition that does not parse is a file a human must edit, and the
second deserves to wake someone. Precondition sits above degraded for the same reason at one remove:
a search that did not run at all is worse news than one that ran with a source down.

The order is asserted to account for every code. The first draft of this list left the precondition
code out of it, and a code missing from the order falls through to success, which is how a run of
every saved search that managed none of them could have reported that everything was fine.

The mapping lives in one place. The core raises `InvalidInput` or `PreconditionNotMet` (new, in
`errors.py`), the store's existing `NoBaselineError` and `StoreLockedError` map to precondition, and
`main` translates. No command body chooses a number.

### D-7 — The structured document owns the primary stream; everything else is on the secondary one

AC-2 is a stream rule, so it is enforced at the one place streams are created. `main` takes
`stdout`/`stderr` as parameters (defaulting to the process's), the core never prints, and the render
layer is the only module that writes. With machine output requested, exactly one `json.dumps` reaches
stdout and every progress line, warning and diagnostic goes to stderr.

Two Windows specifics, from the spec's own edge cases:

- Both streams are rewrapped as UTF-8 with `newline="\n"`, because the console's default encoding on
  Windows is not UTF-8 and property descriptions routinely carry characters outside ASCII. The
  document is written with `ensure_ascii=False`, so it stays readable rather than escaping into
  `\uXXXX` soup.
- `--help` prints to stdout and exits 0 even when machine output was requested. Help is a usage
  request, not a result, and there is nothing structured to say about it.

### D-8 — One run at a time per saved search, enforced by an operating-system file lock

Settled by decision od-1 on 2026-08-23: the second run **declines**, it does not wait. A scheduled
task reads the precondition code and runs again on its next tick, rather than queueing behind a
manual run somebody left open. Two runs back to back would also fetch the same listings twice for
almost no new information, against non-negotiable 10.

The mechanism is `claim.py`: a file per saved search beside the database, whose first byte is locked
non-blocking for the run's lifetime (`msvcrt.locking` on Windows, `fcntl.flock` elsewhere), with the
holder's run id and start time written to the bytes after it. A second process fails to take the
lock, reads the metadata it could not lock, and reports which run is in progress and when it
started.

This is chosen over a process-id file because the operating system releases the lock when the holder
dies for any reason, including being killed and including the machine losing power. That is the one
property a hand-rolled staleness rule cannot get right: any timeout short enough to release a
crashed run's claim is short enough to steal a slow one's. Both halves were measured (see
measurement 1). AC-26's "a stale claim does not block the next run forever" is then not a feature to
implement but a consequence of the primitive.

### D-9 — A local filter never drops a property for a field the source did not provide

Each source declares which filters it applies on its own side; whatever is left over the run loop
applies locally to that source's rows (AC-7). That raises a question the spec does not answer: what
happens to a row with no price when the search filters on price?

It is kept. The tool must never claim a property failed a test it could not run, and product
invariant 10 already says an undeterminable field is empty rather than guessed. Dropping the row
would silently delete a property on the strength of a missing field, which is the same shape of
error as treating absence as evidence. The consequence is visible (a property with no price appears
under a price filter) and correctable; the alternative is invisible.

This is the same family as feat-004's "not locatable" rule for a property with no coordinates, which
formalizes the marking. Until then, the row is kept unmarked. AC-28 states the rule, so it is a
promise rather than an implementation detail.

Two filters are never applied here at all, and are pushed or not applied (AC-32). The freshness
filter, because freshness is computed from local history and a local test on it would have nothing
honest to read. And the **listing status**, which the first run of the loop found the hard way: a
saved search asks for what is for sale, a source that cannot apply that returns everything, and a
local status test then drops the very property that just went pending. The store would see nothing
where the source had told us something, and could only report it as an unexplained disappearance.
A status filter shapes what is asked for; it must never hide what came back.

### D-10 — Recording observations returns one listing id per row

`Store.record_observations` currently returns distinct listing ids with repeats collapsed. It will
return one id per input row instead, in input order, so a caller can pair a row with the property it
became. The collapsed list is `dict.fromkeys(...)` away for anyone who wants it, so nothing is lost,
and the pairing that preview storage needs becomes exact instead of approximate.

This is a change to another feature's built code. It changes no behavior of the store and no
acceptance criterion of feat-001 (whose spec never states the return value), so it is recorded in
that feature's manifest under "Later changes by other features", the way the `records.py` move was,
and covered by a test there.

Without it, the run loop would have to re-derive the store's private identity rule to know which row
became which listing, which is a second implementation of the one rule this project cannot afford to
have two of.

### D-11 — A preview image is fetched once per property and never again while a copy is on disk

Feat-002's plan left a caller contract on record: the run calls the adapter's preview retrieval once
per returned row and hands the result straight to the store. This plan adds the only sensible
condition: **only for a property with no stored image**.

At the shipped pacing of three seconds per request, fetching an image for every row of every run
would cost roughly four and a half minutes per hundred properties, every night, to re-download
pictures already on disk. The enrichment rule in product-global says a cache hit is never re-fetched;
this is the same rule applied to images. `--no-images` skips the step entirely, for a first run over
a whole county where the images are worth deferring.

The failure contract is feat-002's: preview retrieval cannot raise, so a missing image costs that
row's image and nothing else. AC-27 states both halves: fetched once, and skippable without changing
anything else a run records.

### D-12 — Sources run one at a time, and a repeat across areas is dropped while a repeat inside one response survives

Sources are queried sequentially. Parallelism would buy wall-clock time across different hosts but
would complicate failure attribution and force a second database connection, and pacing means a run
is slow by design anyway.

A search with several areas asks each source once per area. A property returned by two of those
queries is our own overlapping ask and is dropped, keeping the first. A property repeated *inside*
one response is the source contradicting itself and both rows are recorded, which is feat-002's page
rule one level up and the store's rule one level down. Getting this backwards is the exact defect
both of those layers already caught once, so AC-29 states it rather than leaving it to memory.

### D-13 — The digest is one document shape, and its size is a function of what changed

The digest is a plain dictionary rendered as JSON. One shape covers a run, a run of everything, and a
comparison, so an automated reader parses one thing:

```
{ "homescout": {"digest_version": 1, "generated_at": ...},
  "kind": "run" | "comparison",
  "searches": [
    { "name", "run_id", "baseline_run_id", "started_at", "finished_at",
      "outcome": "ok" | "degraded" | "failed" | null,
      "sources": [ {"source", "outcome", "rows", "truncated", "detail",
                    "applied_by_source": [...], "applied_locally": [...]} ],
      "counts": {"matched", "new", "changed", "gone", "returned", "flagged"},
      "new": [...], "price_changes": [...], "status_changes": [...],
      "other_changes": [...], "gone": [...], "returned": [...], "flagged": [] } ] }
```

Alongside `searches` the document carries `skipped`: the saved searches that did not validate, each
with its problems and their locations. That is what makes AC-16's answer for a run of everything
readable rather than inferred from a missing entry.

Every key is always present, so a reader never branches on shape. For a comparison, `sources` is
empty and `outcome` is null.

The change sets are the only unbounded part, and each holds a small per-property summary (id,
address, city, state, postal code, price, beds, baths, sqft, url, stored image path, first observed,
days on market) rather than the full record, which is already in the store. `unchanged` has no set at
all, only a count. That is what makes AC-11 true: over N properties of which K changed, the size is a
function of K.

`flagged` is always present and always empty until the rule engine exists, which AC-12 requires
explicitly so the shape does not depend on that feature.

The only part of the document that differs between two identical requests is `generated_at`, which is
the envelope rather than the answer. AC-13's reproducibility is therefore asserted over everything
else, and a run's request counts are deliberately *not* carried: they are not persisted, so a
comparison could never report them, and a field present in one rendering and absent in another is
exactly the branch on shape this document exists to avoid.

Days on market comes from `Store.history`, which computes it from this tool's own first observation.
The record also carries a `days_on_market_source` field holding whatever the site claimed. It is
never used here: product invariant 7 says freshness is computed from local history, and that field
exists only so a source's own claim stays visible as evidence.

`applied_by_source` and `applied_locally` per source is AC-8: the source's opinion and the tool's,
told apart, which is what someone debugging a surprising result actually needs.

**Feat-012 consumes this.** Scheduling and digests writes this document to a path and renders the
email from it. The image path and the per-property summary exist because that email needs them.

### D-14 — Failure is settled before it can become history

- An unexpected error inside a run marks the run `failed` and re-raises. A failed run is never a
  comparison baseline (the store's own rule), so the previous completed run stays usable, which is
  AC-22.
- A run where every source failed is still *completed*, because measurement 3 showed a completed run
  with no observations neither marks anything gone nor erases the state it would be a baseline for.
  It records every source's failure and exits degraded, which is what the spec's scenario asks for.
- `--output` is checked before any work: if the parent directory does not exist, that is invalid
  input and nothing runs, because discovering it after an hour of throttled requests is the failure
  the spec's edge case is about. A write that fails afterwards (permissions, a full disk) is an
  internal error, reported on the secondary stream. The primary stream is left exactly as it would
  have been: a command asked for readable output does not suddenly emit a structured document
  because a file could not be opened, which would contradict AC-21.
- A comparison against a future date is invalid input.

### D-15 — No new dependencies, and `requests` must stay out of startup

`argparse` and `json` are in the standard library. Nothing is added.

Measurement 2 showed the whole import graph costs about 130 ms of process time and does not pull in
`requests`. That property is load-bearing for the startup requirement and easy to lose to one
top-level import, so it is a test: a subprocess imports the command module and asserts `requests` is
absent from `sys.modules`.

A console entry point (`homescout = "homescout.cli.main:run"`) is added to `pyproject.toml`, because
Windows Task Scheduler needs a command to invoke.

The database is found by `--db`, else `HOMESCOUT_DB`, else `homescout.db` in the working directory.

`--version` is kept, because a machine caller pinning a contract needs to know which build answered.
No `--quiet`: progress already goes to the secondary stream, where a scheduled task either reads it
or redirects it.

**No option ever accepts a credential** (AC-31). Command arguments are visible to other processes and
are stored in plain text in Windows Task Scheduler's configuration, so the mail and extraction
credentials that later features need come from the environment. The parser is tested for this rather
than trusted with it, because the option that breaks the rule will be added by a future feature in a
hurry.

### D-15a — The pacing delay is reachable from the command line

Non-negotiable 10 requires a configurable delay, and until now nothing in the product could set one:
the source layer accepts a politeness configuration, but no caller ever built one, so every user got
the shipped three seconds. The run loop is the first thing that constructs a session, which makes
this the feature where "configurable" becomes true or stays theoretical.

`--delay SECONDS` is a global option. It is validated through the source layer's own
`SourcePolicy.validated`, so the permitted range (1.0 s to 60.0 s) is enforced in one place rather
than restated here, and a value outside it is invalid input reported before anything is fetched
(AC-30). Unset, the shipped default applies.

Nothing else about politeness is exposed. Retries, backoff, jitter and the body-size limits stay
where feat-002 put them, and the user agent is not configurable at all, by that feature's own audit.

### D-16 — "No business logic in the command layer" is checked mechanically

AC-19 is written as a review criterion, which at this depth still needs a test. Two checks, both
cheap and both catching the real failure mode:

1. **An import ban.** Modules under `homescout/cli/` may import `homescout.api`,
   `homescout.digest`, `homescout.errors` and the standard library. Importing `homescout.store` or
   `homescout.sources` fails the test. If the command layer cannot reach a store or a source, it
   cannot decide anything about one.
2. **A syntax-tree check.** Every `if`, `while`, conditional expression and comprehension guard in
   `homescout/cli/` is parsed, and none of their test expressions may read an attribute named in
   `FIELD_NAMES` (`price`, `beds`, `listing_status`, and the rest). Rendering a price is the command
   layer's job; branching on one is not.

The second check is an approximation and the test says so: it catches `if row.price > x`, not a
decision laundered through a local variable. Combined with the import ban, the surface where that
could happen is small enough to review by eye.

### D-17 — Human output is plain text, no colour, no dependency

The accessibility requirement says human output must be readable in a plain terminal and convey
nothing by colour alone, so it conveys nothing by colour at all. Rendering is a handful of functions
in `render.py` computing column widths. No table library, no colour library.

Human output is the default (AC-21): with machine output not requested, no structured document is
emitted at all, and the primary stream is prose.

### D-18 — Tests drive the loop through fakes that already exist

`tests/sources_fakes.py` from feat-002 already provides a fake clock whose sleep advances it, a fake
transport, and a stub source with a known population and a configurable ceiling and failure point.
The run loop's tests reuse them, so a full run in a test takes milliseconds and involves no network
and no real waiting. A new `tests/cli_fakes.py` adds an in-memory catalog builder and a helper that
invokes `main([...])` against captured streams and returns the exit code.

One slow, live test runs a real search over a real place through `main(["run", ...])` end to end,
because the previous feature's most valuable checks were the ones that touched the real source.

## Task breakdown

Tests come before or with the code they cover; the constitution's quality bar requires every
acceptance criterion covered, and `implement` checks that mechanically.

- [ ] T1 — `src/homescout/errors.py`: `HomescoutError`, `InvalidInput`, `PreconditionNotMet`. The two
      kinds every surface has to tell apart, with the message carried on the exception.
- [ ] T2 — `src/homescout/cli/codes.py`: the five exit codes as an `IntEnum`, the exception-to-code
      mapping, and the precedence rule from D-6. Tested in isolation.
- [ ] T3 [P] — `src/homescout/search.py`: `SearchProblem`, `SearchDefinition` and `SearchCatalog`
      protocols, `InMemorySearch`/`InMemoryCatalog`, and the catalog registry.
- [ ] T4 [P] — `src/homescout/matches.py`: `AmbiguousMatch`, the `MergeQueue` protocol, the in-memory
      queue, and the queue registry.
- [ ] T5 [P] — `src/homescout/claim.py`: `claim_run(directory, search_name)` as a context manager,
      over `msvcrt` and `fcntl`, raising `RunInProgress` (a `PreconditionNotMet`) carrying the
      holder's run id and start time.
- [ ] T6 — Widen `Store.record_observations` to return one listing id per input row (D-10), update
      its docstring, add a test in `tests/test_store_history.py` citing `feat-001/AC-4`, and record
      the change in `spec/features/listing-store/feature.md`.
- [ ] T7 — `src/homescout/runner.py`: the per-source loop. Capabilities, one query per area, the
      cross-area repeat rule, the local filter (D-9), the exact geometry test, recording
      observations, the per-source outcome. Returns a `RunOutcome` carrying the run record, the
      comparison, and the per-source application report.
- [ ] T8 — Preview retrieval inside the loop (D-11): one image per property that has none, through
      the adapter's uncrashable `preview`, straight into `Store.store_preview_image`.
- [ ] T9 — `src/homescout/digest.py`: the document of D-13, built from a `RunOutcome` or a
      `Comparison`, plus the per-property summary and the days-on-market lookup.
- [ ] T10 — `src/homescout/api.py`: the twelve operations of D-2, each one a call into the runner,
      the digest, the store, the catalog, or the queue.
- [ ] T11 — `src/homescout/cli/render.py`: human rendering for every result the facade returns.
- [ ] T12 — `src/homescout/cli/main.py`: the parser, the subcommands of AC-20, stream discipline and
      UTF-8 rewrapping (D-7), `--output` handling (D-14), the top-level failure translation, and the
      `run()` console entry point. Add the entry point to `pyproject.toml`.
- [ ] T13 [P] — `tests/cli_fakes.py`: the in-memory catalog builder, a store fixture, and
      `invoke(...)` returning `(exit_code, stdout, stderr)`.
- [ ] T14 — `tests/test_run_loop.py`: the filter split, the application report, the cross-area repeat
      rule, previews, degraded and all-failed runs, and the run record's contents.
- [ ] T15 [P] — `tests/test_digest.py`: the shape, the separate change sets, and the bounded size
      with N large and K zero.
- [ ] T16 [P] — `tests/test_run_claim.py`: a second claim declines while a real subprocess holds the
      lock, and succeeds after that process is killed.
- [ ] T17 — `tests/test_cli_contract.py`: machine output, stream separation, exit codes, non-ASCII
      output, `--output`, human output by default, every command reachable, and the startup checks
      of D-15.
- [ ] T18 — `tests/test_cli_operations.py`: comparisons and their reproducibility, no baseline,
      unknown name, invalid definition, annotation, ambiguous matches, the two-surfaces-agree test,
      the no-business-logic checks of D-16, and the internal-error path.
- [ ] T19 — `tests/test_cli_live.py`, marked slow: one real search over a real place, run through
      `main(["run", ...])` twice, asserting the second run's digest reports no new properties.
- [ ] T20 — `uv run ruff check .`, the full suite, and the slow suite. Then `/spec-flow:converge`.

No task marked `[P]` depends on a sibling: T3, T4 and T5 are independent modules, T13 depends only on
what T3 provides and is written after it, and T15/T16 test modules whose tasks precede them.

## Verification approach

Every criterion, the seam its test enters through, and the token that test carries.

| Criterion | Seam | How it is verified |
|---|---|---|
| AC-1 | `main([...])` | Every subcommand run with `--json`; stdout parses with `json.loads` and no preprocessing |
| AC-2 | `main([...])` with captured streams | stdout is exactly one document; every progress line appears on stderr |
| AC-3 | `cli.codes` | The five codes are asserted by name and number, and the precedence rule is table-tested |
| AC-4 | `main(["run", ...])` | Stub sources all-ok exits 0; one failing source exits 1 |
| AC-5 | `api.run_search` + store | With a failing source, observations are recorded and a comparison is produced |
| AC-6 | `api.run_search` + store | With every source failing, no listing's presence becomes `disappeared` |
| AC-7 | `runner` with a stub declaring a partial `applies` | The query sent carries only declared filters; the rest are applied to the returned rows |
| AC-8 | `RunOutcome` / digest | `applied_by_source` and `applied_locally` per source match the declaration |
| AC-9 | `store.get_run` after a run | Run id, search, start, finish, and per-source outcome and row count |
| AC-10 | `main(["run", "--all", "--json"])` | One document, one entry per search, each with name, sources, counts, changed subset |
| AC-11 | `digest.build` | N=5000 unchanged and N=100 unchanged differ only in the matched count; K=0 stays under a fixed byte bound at both sizes |
| AC-12 | `digest.build` | Price changes carry before, after and direction; status changes, gone, returned and flagged are separate sets; flagged is present and empty |
| AC-13 | `main(["changes", ...])` | Against the previous run and against a date; the same request repeated after a later run gives a document identical but for `generated_at` |
| AC-14 | `main(["changes", ...])` | With no completed run, the message says so and the exit code is 3 |
| AC-15 | `main([...])` | An unknown name is reported, the known names are listed, exit code 2 |
| AC-16 | `main(["searches", "validate", ...])` | A catalog reporting problems: each problem and its location is printed, nothing is fetched, exit code 2 |
| AC-17 | `main([..., "--output", path])` | The document is at the path; a missing parent directory is invalid input before any work; a failing write is reported and exits 4 |
| AC-18 | `api` vs `main` | The same operation both ways against two fresh stores; a dump of every table is identical once generated identifiers and timestamps are replaced by their first-appearance order |
| AC-19 | source of `homescout/cli/` | The import ban and the syntax-tree check of D-16 |
| AC-20 | `main([...])` | Every command in the list parses and returns a documented code; the unbuilt three exit 3 naming what is missing |
| AC-21 | `main([...])` without `--json` | stdout is prose and contains no structured document |
| AC-22 | `main(["run", ...])` with an injected failure | Exit code 4, and the previous completed run still compares |
| AC-23 | `main(["annotate", ...])` vs `store.set_annotation` | The stored annotation's content is identical for the same values, set individually and together |
| AC-24 | `main(["matches", ...])` | Pending matches list their agreed and conflicted signals; resolving as the same calls `supersede`; resolving as different is recorded and not re-queued |
| AC-25 | `main(["matches", ..., "--json"])` | Both accept machine output and return the same codes as every other command |
| AC-26 | `claim` + a real subprocess | A second run declines with exit code 3 naming the run in progress; after the holder is killed, the next run proceeds |
| AC-27 | `api.run_search` twice | The second run makes no image request for a property already carrying one; `--no-images` makes none at all and records everything else identically |
| AC-28 | `runner` with a stub | A row whose price is absent survives a price filter the source did not apply |
| AC-29 | `runner` with two overlapping areas | One record for the property both areas returned; two for the property one response returned twice |
| AC-30 | `main([..., "--delay", ...])` | The delay reaches the session; a value outside the permitted range is invalid input and nothing is fetched |
| AC-31 | the parser | Every option name in every subcommand is checked against a list of credential-shaped words |
| AC-32 | `runner` with a stub | A freshness filter and a status filter a source does not apply appear in neither list; a property that went pending is recorded as changed rather than gone |

Test files live under `tests/` per `spec/.spec-flow.md` (`tests/**/test_*.py`), and every test names
its criterion as `feat-003/AC-N` in the test name or a comment. The commands:

```
uv run ruff check .
uv run pytest -q
uv run pytest -m slow -q
```

The live test is marked `slow` and excluded by default, as feat-002's are.

## What this hands to the features that depend on it

- **Saved searches and geography (feat-004)** implements `SearchDefinition` and `SearchCatalog` from
  D-3 and registers a file catalog. Its exact geometry test is `keeps`; its validation output is
  `SearchProblem`.
- **Address matching and merge review (feat-006)** implements `MergeQueue` from D-4 and registers a
  store-backed queue. The resolution decision stays in `api.resolve_match`.
- **Scheduling and digests (feat-012)** consumes the document of D-13 unchanged, writes it to a path,
  and renders the email from the per-property summaries and their stored image paths. It inherits
  od-1's answer: a scheduled run that collides with a manual one declines and retries next tick.
- **Browser interface (feat-010)** calls the same twelve facade functions, which is what product
  invariant 5 reduces to in practice.
