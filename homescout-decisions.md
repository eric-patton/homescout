# HomeScout — Decisions log

Companion to `homescout-brief.md`. Records answers to the brief's §14 open
questions and any later decisions that change scope or architecture. The brief
stays as written; this file is where it gets amended.

**Read this alongside the brief when specifying.** Where the two disagree, this
file wins.

---

## D1. Free-text field extraction (§14, question 2)

**Decision: optional add-on, off by default, two interchangeable backends.**

- Deterministic pattern matching is the always-on baseline and requires no
  configuration.
- An LLM extraction pass is a separate, opt-in enrichment provider, enabled
  per saved search.
- Two backends, selected by config:
  - OpenAI, credentials read from the `OPENAI_API_KEY` environment variable.
  - A local model served by LM Studio.
- Both speak the same OpenAI-compatible request shape, so this is one client
  with a configurable base URL and model name, not two code paths. Adding a
  third compatible endpoint later must not require new extraction code.
- Results cache per listing keyed on a hash of the description text, so a given
  description is processed at most once regardless of how many runs see it.
- The brief's rule is unchanged and binding on both backends: a field is left
  blank rather than guessed. Extracted values carry their provenance
  (`pattern` or `llm`) and are distinguishable from source-provided data.
- With extraction disabled, the tool must be fully functional and require no
  API key, no network calls to any model provider, and no local model runner.

## D2. Photo handling (§14, question 1)

**Decision: store every photo URL, download and keep exactly one thumbnail per
canonical listing.**

- Full galleries are served from the source by URL in the listing detail view.
- One small preview image per listing is downloaded and stored on disk, so that:
  - the email digest renders a picture that always loads, independent of
    whether a source permits hotlinking, and
  - a listing that has disappeared still has something to look at, which
    matters because vanish-and-return is a signal this tool exists to catch.
- Thumbnail fetching is subject to the same per-source rate limiting and
  politeness rules as listing fetches, and a failed thumbnail fetch degrades
  that listing only. It never fails a run.
- Thumbnails live outside the database, on disk, referenced by path. They are
  local data and are not committed to git.

## D3. Disappeared listings (§14, question 4)

**Decision: remain visible, marked with a `disappeared` status.**

- Not archived, not hidden, not deleted.
- Filterable out of the results table by the user, and excluded from the default
  view if that proves noisy in practice, but always reachable.
- A listing that disappears and later returns must be recognizable as the same
  canonical listing, with both events visible in its timeline.
- Reminder of the brief's §3 constraint: absence from one source's response is
  never on its own grounds to mark a listing gone.

## D4. Annotation history (§14, question 3)

**Decision: last-write-wins, with an updated-at timestamp. No audit trail in
v1.**

- Listing data already has full history through snapshots. User annotations do
  not need the same treatment.
- The brief's hard requirement stands: annotations survive re-runs, merges, and
  unmerges.
- Not a non-goal, just deferred. The schema should not make adding annotation
  history later painful.

## D5. Multi-machine sync (§14, question 5)

**Decision: out of scope for v1. The SQLite file is not git-tracked.**

- Saved-search YAML files are git-trackable and that is the intended sharing
  mechanism, consistent with brief §6.
- The database, thumbnails, exports, and `.env` are local data and are
  gitignored.
- No sync, replication, or cloud storage layer in v1. Consistent with the
  non-goal of multi-user and hosting beyond localhost.

## D6. Process

**Decision: full-product specification before implementation.**

The whole six-phase product is specified up front rather than phase by phase.
The brief's §13 phasing remains the intended build order, and each phase must
still end with something runnable.

## D7. Environment

Confirmed on the development machine at the time of writing:

- Windows 11, PowerShell / Windows Terminal, no WSL. Windows is the primary
  target, per brief §10.
- `uv` 0.12.1, Python 3.14.6, git 2.54.0.
