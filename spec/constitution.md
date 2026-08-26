# Constitution — HomeScout

The non-negotiable principles every spec, plan, and task in this project must respect.

## Mission

A local-first property search monitor for personal use. It pulls listings from multiple free
sources, merges them into one canonical record per property, enriches them with public geospatial
data, applies user-defined rules, and tracks how each listing changes over time. It exists to
replace hours of manual searching and spreadsheet maintenance with a scheduled, diffable run.

## Non-negotiables

1. **This is a monitor, not a scraper.** Almost everything valuable is a difference over time, not
   a field in any response. Every run records what it observed of every matching listing, such that
   the exact state at any past run remains recoverable and nothing already recorded is ever
   rewritten. New, changed, and gone are computed locally by comparing those records. This binds the
   guarantee, not the table design.
2. **Snapshots are immutable.** Corrections are written as new rows. Nothing rewrites history.
3. **Source-side freshness filters are an optimization, never the source of truth for "new."**
4. **A failing source degrades a run. It never corrupts history and never deletes listings.**
   Absence from one source's response is not evidence that a property sold.
5. **Never destroy source rows.** Canonical merged records are built on top of raw per-source rows
   and carry a source array, so a wrong merge can always be inspected and undone.
6. **Ambiguous merges are flagged for a human, never guessed.** Manual merge and unmerge decisions
   persist and are respected by every future run.
7. **User annotations survive re-runs, merges, and unmerges.** Losing a user's judgment is the one
   failure this tool cannot have, because it is what the tool replaces.
8. **No business logic in the CLI or the web interface.** Both are thin wrappers over one core
   library. Anything either surface can do, the other can do.
9. **Adding a source means writing one adapter, not touching the core.**
10. **Politeness is a requirement, not a nicety.** Per-source rate limiting with backoff, a
    configurable delay, an honest user agent, and retry with jitter. Default to slow.
11. **No `eval`.** Rule expressions are parsed by a restricted evaluator over a fixed field
    namespace, with a clear error when a rule names an unknown or not-yet-enriched field.
12. **Behavior is specified before it is built.** No requirement ships without an acceptance
    criterion.

## Tech & architecture defaults

- Languages / frameworks: Python, managed with `uv`. FastAPI for the local server. Plain HTML and
  vanilla JavaScript with Leaflet and Leaflet.draw for the map. No single-page-app framework and
  no second build toolchain.
- Architecture style: one core library with six layers, in order:
  `sources` to `merge` to `store` to `enrich` to `rules`, then the two surfaces (`cli`, `web`).
  Layers depend downward only.
- Data & integration defaults: a single SQLite file. Geospatial work uses `shapely`; address
  parsing uses `usaddress`. External data comes only from free, public sources, national by default. A source
  covering only part of the country is permitted only where a location outside its coverage is
  reported as not applicable rather than as an answer.
- Platform: Windows is the primary target (Windows Terminal, PowerShell, no WSL). Nothing may
  assume a POSIX-only path, shell, or scheduler. Scheduling targets Windows Task Scheduler.
- Optional AI extraction speaks the OpenAI-compatible request shape with a configurable base URL,
  so the hosted and local backends are one code path.

## Security & compliance

- **Personal use only.** Scraping these sites is against their terms of service. This tool is low
  volume, throttled, not republished, not commercialized, and kept clear of anything
  work-adjacent. The README must state this so the constraint travels with the code.
- Secrets (SMTP credentials, `OPENAI_API_KEY`) are read from the environment or a `.env` file that
  is never committed. No secret appears in code, in a saved search, or in any committed config.
- The tool binds to localhost. There is no authentication, no multi-user model, and no hosting
  beyond the local machine, so it must never listen on a public interface by default.
- Nothing requiring MLS or IDX credentials, and no paid data API.
- The database, downloaded images, and exports are local data and are never committed to git.

## Quality bar

- Testing expectation: tests for core paths, with the snapshot-diff engine and the address merge
  logic held to a higher bar than the rest, since they are where a silent error destroys trust in
  everything downstream. Every acceptance criterion is covered by a test.
- Reliability minimum: any single external failure (a source, an enrichment provider, a thumbnail
  fetch, the extraction model) degrades one field or one source's contribution and is reported in
  the run's per-source status. It never aborts the run and never leaves the database inconsistent.
- Observability minimum: every run records which sources succeeded, which failed, and how many
  listings each contributed. A run's outcome is never silent.
- Accessibility: the browser interface is keyboard usable and readable. No formal conformance
  target, since it is a single-user local tool.
- Review expectation: the pre-build consistency check passes before implementation starts, and the
  code-against-spec audit passes before a feature is done.

## Out of scope (project-wide)

- Commercial use or redistribution of collected data
- Rental search
- Automated valuation or investment modeling
- Multi-user support, authentication, or hosting beyond localhost
- A mobile application (the email digest is the phone surface)
- Anything requiring MLS/IDX credentials or a paid data API
- Multi-machine sync or replication of the database
