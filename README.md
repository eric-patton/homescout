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

Early, and it runs unattended. The listing store and its snapshot history, the source adapters
with one working Realtor.com adapter, the command line with its run loop, saved searches with their
geography, criteria, public-data enrichment, and scheduling with its digests are built and tested.
Address matching, more sources, field extraction, the browser interface and spreadsheet export are
specified and not yet built.

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

## Saved searches

A saved search is one YAML file in a `searches/` directory beside the database. Hand-edit it, commit
it, and run it by its file name:

```
homescout searches create nm-acreage     # writes searches/nm-acreage.yaml, commented
homescout searches validate nm-acreage   # every problem at once, each with a line number
homescout run nm-acreage --json
```

```yaml
name: nm-acreage
description: Acreage with real internet
areas:
  - {type: county, value: "Roosevelt County, NM"}
  - {type: zip, value: "88130"}
  - {type: radius, center: [34.18, -103.35], miles: 25}
  - type: polygon
    name: north-of-the-highway
    geometry: {type: Polygon, coordinates: [[[-103.4, 34.2], [-103.3, 34.2],
                                             [-103.3, 34.3], [-103.4, 34.2]]]}
exclude_areas:
  - {type: polygon, name: east-side, geometry: {...}}
filters:
  price: {min: 200000, max: 700000}
  beds: {min: 3}
  lot_acres: {min: 1}
  property_type: [single_family, farm]
  listing_type: [for_sale, pending]
  listed_within_days: 30
sources: [realtor]
rules: []
export:
  template: default
```

A property qualifies if it falls inside **any** area and inside **none** of the exclusions.

Geography happens in two stages, because no listing site accepts a shape you drew. Each source is
asked for the smallest thing it does accept that **contains** your areas: the named place itself, a
box, or a circle around a drawn shape. Everything that comes back is then tested against the real
geometry here, so a coarse query is never your problem. A property a source returned without
coordinates is kept and counted as not locatable, rather than being dropped as though it had failed
a test nobody could run.

Two details worth knowing:

- **GeoJSON is longitude first**, and a radius `center` written as a pair is latitude first, like
  every map application. Both are checked, and a swapped pair is reported as one.
- **`listed_within_days` is measured from when this tool first saw a property**, never from a
  source's own field, and it never removes anything from a run. It narrows what you are shown.
  Filtering a run by freshness would stop recording older properties, and a property that stops
  being recorded is one this tool can only later describe as having disappeared.

## Criteria

A saved search can carry criteria: your own judgments, written as data, applied to every property in
every run.

```yaml
rules:
  - {id: stale-listing, when: "dom > 180", severity: flag}
  - {id: price-raised-late, when: "price_raised_after_days > 120", severity: flag}
  - {id: unreliable-water, when: "water_source == 'well' and not over_principal_aquifer", severity: flag}
  - {id: no-fiber, when: "upload_mbps < 100", severity: drop}
  - {id: acreage, when: "lot_sqft > 200000", severity: boost}
```

Four severities. `drop` excludes a property from results without deleting it, and you can always ask
what was dropped and by which criterion. `flag` badges it. `boost` and `demote` move it up or down
the default order, which is boosts minus demotes, ties broken by first sighting.

**A value nobody knows is not a failure.** A criterion that depends on something unfetched is
*undetermined*: it does not fire, it excludes nothing, it changes no ordering, and the run reports
which field was missing. That is the difference between "this house has slow internet" and "nobody
has looked".

The expression language has comparisons, `and` / `or` / `not`, arithmetic, `in` over a literal list,
and `is null` to ask whether a value is known at all. It has no function calls, no attributes, no
indexing, and no assignment, because it is not a programming language and nothing you write in it
becomes code. Names come from a fixed list: the listing fields, values derived from this tool's own
history (`dom`, `is_new`, `price_cut`, `price_raised_after_days`), and the enriched and extracted
values that arrive with later features. A criterion naming something else is refused before the run,
with the available names listed.

## Public data about a location

The questions that decide a rural property are not listing fields. `homescout enrich` asks five free
public services what is true at each property's coordinates, caches every answer against a rounded
location, and never asks twice:

```
homescout enrich                 # everything that has never been asked about
homescout enrich --stale         # only what has aged past its lifetime
homescout enrich --search nm-acreage --json
```

| What | Where it comes from | Fills |
| --- | --- | --- |
| Flood zone | FEMA National Flood Hazard Layer | `flood_zone` |
| Elevation | USGS National Map | `elevation_ft` |
| Principal aquifer | USGS principal aquifers | `over_principal_aquifer` |
| Wildfire hazard | USFS wildfire hazard potential | `wildfire_hazard` |
| Boundaries | Census TIGERweb | the shapes a saved search's named areas resolve to |
| Broadband | FCC National Broadband Map | `upload_mbps`, `download_mbps`, `broadband_provider` |

**Broadband needs a key and the rest do not.** The FCC's national map requires an API token, so that
provider is off unless `HOMESCOUT_FCC_TOKEN` is set in your environment or `.env`. Without one it
makes no request and reports itself skipped, which is different from failing.

**Three states, not two.** A value is *fresh* (cached and current), *stale* (cached, past its
lifetime, still used and still labelled), or *missing* (never fetched). Missing is never rendered as
a negative answer: a property whose aquifer nobody looked up does not read as "not over an aquifer",
and a criterion that names it is undetermined rather than false.

One service being down costs that one column. Every other provider is asked normally, the pass
completes, and whatever was already cached stays exactly where it was.

Endpoints are configuration, because they move: FEMA's had already moved by the time this was built.
Override any of them with `HOMESCOUT_ENRICH_<PROVIDER>_URL`.

## Running on a schedule

A monitor that has to be remembered is not a monitor. `docs/scheduling.md` has the whole setup for
Windows Task Scheduler: one command to create the task, one to remove it, and the environment
mistake that makes a task work by hand and do nothing at three in the morning.

The short version:

```
homescout run --all --json --deliver
```

`--deliver` writes the digest to `HOMESCOUT_DIGEST_PATH` (by default `digest.json` beside the
database) and sends an email. Without the flag a run prints its results and writes nothing, so
running one by hand never mails you.

**The email only arrives when something happened.** New, changed, gone, back, or newly flagged.
A digest that arrives every night whether or not anything happened trains you to ignore it, which
costs more than sending nothing. The file is written either way, because "the run happened and
found nothing" and "the run did not happen" are different facts and an automated reader needs to
tell them apart.

Each property in the email carries its price, address, notable criteria, a link, and the preview
image this tool stored itself, attached to the message rather than loaded from the listing site. So
it renders whether or not a source permits that, it still renders for a property that has since
disappeared, and opening the email tells nobody anything.

Email is optional. With no account configured, runs still happen and the digest is still written.
To turn it on, copy `.env.example` to `.env` beside your database and fill in the mail account.
**No credential is ever read from a saved search, a committed file, or a command-line argument**,
and there is no option to pass one: arguments are visible to every other process on the machine,
and Task Scheduler stores them as plain text.

## Exit codes

Every command takes `--json` and returns one of five codes. They are a contract: a scheduled task
decides whether to wake somebody from the number alone, so they do not change casually.

| Code | Meaning |
| --- | --- |
| 0 | Success. |
| 1 | Degraded. It completed and recorded what it saw, but at least one source or delivery failed. |
| 2 | Invalid input: usage, an unknown name, or a saved search that does not validate. |
| 3 | Cannot proceed yet: nothing to compare against, a run of that search already going, the database in use, or a command whose feature is not built. |
| 4 | Internal error. |

One invocation that produces several settles on the worst of them, in that order: 4, then 2, then
3, then 1, then 0. Running every saved search is the usual way that happens.

With `--json`, the structured document is the entire contents of standard output and everything
else is on standard error, so a caller never has to disentangle them.
