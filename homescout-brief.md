# HomeScout — Implementation Brief

**Status:** pre-spec. Hand to `/spec-flow:flow` as the discovery input.
**Working name:** `homescout` (rename freely)

---

## 1. Problem

Consumer real-estate portals (Zillow, Redfin, Realtor.com) are built for
browsing one property at a time. There is no view that puts every listing in a
region into one table with every field visible, no way to filter on derived or
external data (flood zone, broadband availability, aquifer), and no way to save
a carefully-tuned search and re-run it on a schedule.

The current workaround is manual: run searches on Redfin, open each listing,
copy fields into a spreadsheet, then hand-research flood/internet/water/crime
per property. This takes hours per batch and goes stale immediately.

## 2. What we're building

A local-first property search monitor. It pulls listings from multiple free
sources, merges them, enriches them with public geospatial data, applies
user-defined rules, and tracks changes over time. Two surfaces over one core:
a local web UI (for map drawing and review) and a CLI (for scheduled/agent use).

## 3. The load-bearing design decision

**This is a monitor, not a scraper.**

Almost everything valuable is a diff over time, not a field in any API response:

- how new a listing is
- price cuts and price *increases*
- back-on-market / re-listed after a failed contract
- sold twice in a short window
- disappeared from results

No free source exposes reliable price history. So every run writes an
append-only snapshot of every matching listing, and "new / changed / gone" is
computed locally by diffing snapshots.

Consequences that must hold in the design:

- Source-side freshness filters (`past_days`, etc.) are an *optimization*, never
  the source of truth for "new."
- A source failing degrades a run; it must never corrupt history or delete
  listings. Absence from one source's response is not "sold."
- Snapshots are immutable. Corrections go in as new rows.

## 4. Decisions already made

| Question | Decision |
|---|---|
| Replace the spreadsheet or feed it? | **Both.** Annotations live in the app; xlsx export is a required, first-class feature, not an afterthought. |
| Scope for v1? | **General-purpose.** No market-specific hardcoding. New Mexico is the first real use, not the design target. |
| How do scheduled runs report? | **Both.** A JSON digest file for an AI agent to read, plus an email digest. |
| Language | Python (all viable free sources are Python-only), managed with `uv`. |
| Store | SQLite, single file. |
| UI | FastAPI + Leaflet + Leaflet.draw, served on localhost. Plain HTML/vanilla JS — no SPA framework, no second build toolchain. |

## 5. Architecture

Six layers. CLI and UI are both thin wrappers over the core library — **no
business logic in either surface**.

```
sources/ → merge/ → store/ → enrich/ → rules/ → surfaces (cli/, web/)
```

### 5.1 Sources

One adapter per provider, all satisfying the same interface:

```python
class Source(Protocol):
    name: str
    def capabilities(self) -> SourceCapabilities: ...   # which filters push server-side
    def search(self, query: NormalizedQuery) -> list[RawListing]: ...
```

Every returned row is tagged `source` + `fetched_at`. The runner asks each
adapter what it can filter server-side, pushes those, and applies the rest
locally.

v1 adapters:

| Adapter | Backing | Notes |
|---|---|---|
| `realtor` | `homeharvest` (pip) | Best structured schema. Accepts zip/city/"city, state"/county/state/address+radius. Filters: beds, baths, sqft, price, lot_sqft, year_built, property_type, listing_type, sort, limit (10k cap, chunk with date_from/date_to). `extra_property_data=True` adds tax history + schools at O(n) request cost. |
| `zillow` | `pyzill` (pip) | Takes a bounding box natively (`ne_lat/ne_long/sw_lat/sw_long`). Hard cap ~500 results per query regardless of pagination — split the bbox to get more. |
| `redfin` | CSV download endpoint | No library. Results-page "Download All" is a GET with the search params; 350-row cap, and only available where the local MLS permits download. Must degrade gracefully when unavailable. |

Adding a fourth source must mean writing one adapter, not touching the core.

**Politeness is a requirement, not a nicety.** Per-source rate limiting with
backoff, configurable delay, honest user agent, retry with jitter on 403/429.
Default to slow.

### 5.2 Merge

The messiest part of the project. Budget real time here.

The same house appears on all three sources with different address formatting
(`1747 S Roosevelt Rd 10 1/2` vs `1747 South Roosevelt Road 10 1/2`).

- Parse/normalize with `usaddress`.
- Primary key attempt: normalized street + ZIP.
- Tiebreak/confirm: lat/long within ~50m.
- APN/`parcel_number` when present is the strongest signal — prefer it.

Rules:

- **Never destroy source rows.** Canonical records are built *on top of* raw
  rows, with a source array. When a merge is wrong you must be able to see why.
- Ambiguous matches are flagged for manual resolution in the UI, not guessed.
- Manual merge/unmerge decisions persist and are respected by future runs.

### 5.3 Store (SQLite)

Sketch — refine during spec:

- `searches` — saved search definitions (see §6)
- `runs` — run id, search id, started/finished, per-source status + counts
- `raw_listings` — per-source, per-run, as fetched
- `listings` — canonical current state, merged
- `listing_snapshots` — append-only, the diff substrate
- `enrichment` — keyed by rounded lat/long + provider; cached hard, never
  re-fetched on cache hit
- `annotations` — user judgment attached to canonical listing: rank, verdict,
  red flags, summary, next step, free notes. **Must survive re-runs, merges,
  and unmerges.**
- `merge_decisions` — manual overrides

### 5.4 Enrich

Separate pass, separately schedulable, individually failure-tolerant. One dead
endpoint marks that field stale and the run continues.

All national in coverage (required by the general-purpose scope):

| Provider | Gives |
|---|---|
| FEMA National Flood Hazard Layer (ArcGIS REST) | Flood zone at a point |
| FCC National Broadband Map / BDC | Providers, technology, max down/up |
| USGS principal aquifers map service | Whether the point is over a principal aquifer |
| USFS Wildfire Risk to Communities | Wildfire hazard |
| USGS/NED elevation | Elevation |
| Census TIGER | County/place/ZCTA boundaries for area resolution |

Verify current endpoints at implementation time; treat each as a plugin with a
declared cache key and TTL (most are effectively infinite).

### 5.5 Rules

User criteria as **data, not code** — stored in the saved-search file, tunable
per search, diffable in git.

```yaml
rules:
  - id: stale-listing
    when: "dom > 180"
    severity: flag
  - id: price-raised-late
    when: "price_raised_after_days > 120"
    severity: flag
  - id: unreliable-water
    when: "water_source == 'well' and not over_principal_aquifer"
    severity: flag
  - id: no-fiber
    when: "upload_mbps < 100"
    severity: drop
```

Severities: `drop` (excluded from results), `flag` (shown with a badge),
`boost`/`demote` (affects default sort).

Expression evaluation must be sandboxed — no `eval`. Use a restricted
expression parser over a fixed field namespace, with a clear error when a rule
references an unknown or not-yet-enriched field.

## 6. Saved search schema

Hand-editable YAML, git-trackable, round-trips losslessly through the UI.

```yaml
name: nm-fiber-acreage
description: Acreage with real internet, no flood zone
areas:
  - {type: polygon, name: north-portales, geometry: {...GeoJSON...}}
  - {type: city, value: "Las Cruces, NM"}
  - {type: county, value: "Roosevelt County, NM"}
  - {type: zip, value: "88130"}
  - {type: radius, center: "Portales, NM", miles: 25}
exclude_areas:
  - {type: polygon, name: roswell-east-of-main, geometry: {...}}
filters:
  price: {min: 200000, max: 700000}
  beds: {min: 3}
  baths: {min: 2}
  sqft: {min: 1500}
  lot_acres: {min: 1}
  year_built: {min: 1980}
  property_type: [single_family, farm]
  listing_type: [for_sale, pending]
  listed_within_days: 30        # local, computed from our own history
sources: [realtor, zillow, redfin]
rules: [...]
export:
  template: default             # column set for xlsx
```

**Geography is two-stage:** coarse query the sources accept (city / county /
ZIP / bbox), then `shapely` point-in-polygon locally against the drawn areas.
Both the UI and CLI feed the same GeoJSON into the same code path. Exclusion
polygons let a user encode "not the east side of town" as geometry rather than
as a mental note.

## 7. CLI contract

Every command takes `--json` and returns stable exit codes. This is what makes
it agent-usable.

```
homescout search list
homescout search new <name>
homescout search edit <name>
homescout search validate <name>

homescout run <name> [--json]
homescout run --all [--json]
homescout diff <name> --since <date|last-run> [--json]

homescout enrich [--stale] [--search <name>] [--json]
homescout export <name> --format xlsx|csv [--template <name>] [--out <path>]
homescout serve [--port 8080]
```

`run --all --json` emits a **digest**, not the dataset:

```json
{
  "run_id": "...", "started_at": "...", "finished_at": "...",
  "searches": [{
    "name": "nm-fiber-acreage",
    "sources": {"realtor": "ok", "zillow": "ok", "redfin": "unavailable"},
    "counts": {"matched": 47, "new": 3, "changed": 5, "gone": 1},
    "new": [{...compact listing...}],
    "price_changes": [{"id": "...", "from": 449000, "to": 435000, "direction": "down"}],
    "status_changes": [...],
    "gone": [...],
    "newly_flagged": [{"id": "...", "rules": ["stale-listing"]}]
  }]
}
```

A hundred lines, not five megabytes. That file is what a scheduled Claude Code
job reads.

## 8. UI scope (v1)

Served on localhost. Screens:

1. **Map / search builder** — Leaflet + Leaflet.draw. Draw and name polygons,
   add cities/ZIPs/counties/radii, set filters and rules, save.
2. **Saved searches** — list, run now, last-run summary, edit, duplicate.
3. **Results table** — every column, sortable, client-filterable, rule badges,
   **inline-editable annotations** (rank/verdict/flags/next step).
4. **Listing detail** — photos, full description text, enrichment panel, source
   links, snapshot/price history timeline, merge provenance.
5. **Run history / diff** — what changed since any prior run.

Annotations being editable in the results table is what lets this replace the
spreadsheet rather than merely produce one.

## 9. xlsx export

First-class, required. Column templates are config, with a `default` template
matching the current hand-built consolidated sheet:

> Rank, Status, Property, Town/Area, County/Region, Price, $/sq ft, Price
> History & DOM, Beds, Baths, Sq Ft, Year Built, Acres, Construction/Roof/
> Features, Garage/Outbuildings, HVAC/Heat, Water Source, Sewer/Septic, Gas,
> FEMA Flood Zone, Internet, Principal Aquifer, Annual Taxes, Crime/Safety,
> Fire/Egress/Terrain, Sewage & Reclaimed-Water Exposure, Town Analysis Notes,
> Red Flags, Summary, Verdict, Next Step, Listing URL

Requirements: address cell hyperlinks to the listing; unstructured fields
(HVAC, water source, sewer, gas, roof) are extracted from listing description
text where possible and left blank rather than guessed where not; a second
sheet for area/town notes; re-export must not clobber user edits made in the
app.

## 10. Scheduling

Windows Task Scheduler (primary target — dev runs Windows, Windows Terminal, no
WSL) invoking `homescout run --all --json --out <path>`, then:

- the JSON digest lands in a known location for an agent to pick up
- an email digest goes out via SMTP (credentials from env/`.env`, never in
  code or config committed to git)

Email digest should be readable on a phone: new listings with thumbnail, price,
address, key flags, link. Suppress entirely when nothing changed.

## 11. Non-goals for v1

- Commercial use or redistribution of scraped data
- Rental search
- Automated valuation / investment modeling
- Multi-user, auth, or hosting beyond localhost
- Mobile app
- Anything requiring MLS/IDX credentials or a paid data API

## 12. Risks

| Risk | Mitigation |
|---|---|
| Address matching produces bad merges | Never destroy source rows; flag ambiguity for manual resolution; persist manual decisions |
| A source changes its API/markup and breaks | Adapter isolation; per-source status in every run; degrade, don't fail |
| Getting rate-limited or blocked | Conservative defaults, backoff, configurable delay, optional proxy support |
| Enrichment endpoints move or throttle | Plugin per provider, hard caching, stale-marking rather than run failure |
| Rule expressions become an injection surface | Sandboxed restricted parser over a fixed namespace; no `eval` |
| Scope creep into a general proptech platform | Non-goals list above is binding for v1 |

**Legal posture:** scraping these sites is against their terms of service. This
is a personal-use tool: low volume, throttled, not republished, not
commercialized, and kept clear of anything work-adjacent. Note this in the
README so the constraint travels with the code.

## 13. Suggested phasing

1. **Core + one source.** `realtor` adapter, SQLite store, snapshot/diff,
   CLI `run`/`diff` with `--json`. Prove the monitor loop.
2. **Search definitions + geography.** YAML schema, area resolution, two-stage
   polygon filtering, `search` commands.
3. **Remaining sources + merge.** `zillow`, `redfin`, address normalization,
   merge with manual-resolution queue.
4. **Enrichment + rules.** Provider plugins with caching; sandboxed rule engine.
5. **UI.** Map/draw, search builder, results table, annotations, detail, diff.
6. **Export + scheduling.** xlsx templates, email digest, Task Scheduler setup,
   documented agent contract.

Each phase should end with something runnable.

## 14. Open questions for spec

- Photo handling — cache locally, hot-link, or skip? (affects store size)
- How much structured extraction from free-text descriptions is worth it (HVAC,
  water source, sewer, roof), and should an LLM pass be optional-but-supported?
- Do annotations need history/audit, or is last-write-wins fine?
- Should `gone` listings be archived and hidden, or stay visible with a
  `disappeared` status? (a listing that vanishes and returns is signal)
- Multi-machine sync — out of scope, or is the SQLite file just git-tracked?
