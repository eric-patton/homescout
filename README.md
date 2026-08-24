# HomeScout

A local-first property search monitor. It pulls listings from several free sources, merges them
into one record per property, enriches them with public geospatial data, applies criteria you
write, and tracks how everything changes over time.

## Please read this before using or sharing it

**This is a personal-use tool, and that constraint is not decorative.**

Scraping the listing sites this tool reads from is against their terms of service. HomeScout is
built to stay on the right side of the only thing that makes that defensible: it is low volume, it
is deliberately slow, it is throttled per source with backoff, it identifies itself honestly, and
nothing it collects is republished, redistributed, or used commercially.

Concretely, do not:

- raise the request rate or remove the pacing floor,
- publish, sell, or redistribute the data it gathers,
- use it for commercial purposes or anything work-adjacent,
- run it against a site's terms in a jurisdiction where that carries more weight than it does for
  personal research.

It requires no MLS or IDX credentials and no paid data API, by design. If you find yourself wanting
to remove a limit here, the honest move is to buy a data licence instead.

## What it is for

Consumer property portals are built for browsing one house at a time. There is no view that puts
every listing in a region into one table with every field visible, no way to filter on data the
portal has never heard of (flood zone, broadband, aquifer, wildfire risk), and no way to save a
carefully-tuned search and re-run it on a schedule.

More importantly, almost everything worth knowing is a difference over time rather than a field in
any response: how new a listing is, price cuts and price increases, back on market after a failed
contract, sold twice in a short window, quietly disappeared. No free source exposes reliable
history.

So HomeScout is a monitor rather than a scraper. Every run records what it observed, history is
append-only, and new, changed and gone are computed here by comparing those records.

## Status

Early. The listing store and its snapshot history, the source adapters with one working
Realtor.com adapter, and the command line with its run loop are built and tested. Saved searches,
address matching, enrichment, criteria, the browser interface, spreadsheet export and scheduling
are specified and not yet built.

Until saved searches arrive there is no file format to define one in, so `homescout run` has
nothing to run yet. Everything underneath it does work.

The full specification lives in `spec/`. Each feature has its requirements in
`spec/features/<name>/spec.md`; the project-wide rules are in `spec/constitution.md` and
`spec/product-global.md`.

## Working on it

Requires [uv](https://docs.astral.sh/uv/). It fetches the right Python itself.

```
uv sync
uv run pytest
uv run pytest -m slow tests/test_store_performance.py
uv run ruff check .
```

Local data (the database, stored images, exports, and any `.env`) stays out of version control.
Saved searches are YAML and are meant to be committed.

## Exit codes

Every command takes `--json` and returns one of five codes. They are a contract: a scheduled task
decides whether to wake somebody from the number alone, so they do not change casually.

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 1 | Degraded. It completed and recorded what it saw, but at least one source failed or was unavailable. |
| 2 | Invalid input: usage, an unknown name, or a saved search that does not validate. |
| 3 | Cannot proceed yet: nothing to compare against, a run of that search already going, the database in use, or a command whose feature is not built. |
| 4 | Internal error. |

One invocation that produces several settles on the worst of them, in that order: 4, then 2, then
3, then 1, then 0. Running every saved search is the usual way that happens.

With `--json`, the structured document is the entire contents of standard output and everything
else is on standard error, so a caller never has to disentangle them.
