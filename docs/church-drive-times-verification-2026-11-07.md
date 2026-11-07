# Church drive times: implementation and live verification

Implemented and deployed on 2026-11-07. Runtime code commit: `44a498a`, including `54934f2`
and `5e179cf`. Documentation and audit commits following it do not change runtime code.

## Delivered behavior

- `Drive to Church (min)` is a numeric results column beside Price and part of the Deciding view.
  Existing browser column arrangements are preserved. Click the heading to sort either direction.
  Empty values stay last in both directions.
- Estimates drive from the Louisiana house to Old Zion Hill Baptist Church, 25890 LA-442,
  Independence, LA 70443, using the existing saved church center: 30.5771925204, -90.57493594311.
  These are routing estimates without live traffic, not measured trips.
- The optional `church_drive` provider uses the existing routing credential. It sends coordinates
  and driving parameters only, in batches of at most 100 houses and one destination. Provider
  failure preserves saved values. Missing or unavailable routes stay empty with a reason.
- Six-decimal location keys distinguish road access. Saved coordinate versions and nonretracted
  merge constituents are included, so older result rows and new merged houses also have values.
  Houses not returned in the latest search retain the value when revealed in the table.
- The existing nightly enrichment job picks up new locations and refreshes 30-day-old estimates.
  Result/detail reads and exports only read the cache. Property detail includes route status,
  fetched date and freshness.
- CLI: `homescout enrich --provider church_drive --json`. Provider selection is also accepted by
  the existing guarded enrichment endpoint. Custom export templates can include the numeric column.
  The established default spreadsheet and browser export keep their existing column set.

Routing follows the [openrouteservice matrix API](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/)
and its [hosted limits](https://giscience.github.io/openrouteservice/hosted-api-restrictions).
Results credit openrouteservice by HeiGIT and OpenStreetMap under CC BY-SA 4.0.

## Tests

- Full Windows default suite: **1,735 passed, 4 skipped, 126 slow/live tests deselected**.
- Eight focused slow enrichment/export performance tests passed.
- The 23 church tests cover direction, numeric conversion, bounded batching, fresh cache reuse,
  stale-value retention, null/malformed durations, credential source and redaction, HTTPS,
  individual provider selection, old coordinate versions, new merges, retracted records,
  disappeared result rows, HTTP detail, CSV/XLSX values, sorting and saved column arrangements.
- Mac production-host focused check: **22 passed, 1 skipped** in the final church test file.
  The skipped case needs Node on the SSH PATH; its actual shipped JavaScript functions passed on
  Windows and are covered by the cross-platform CI suite.
- Python lint, JavaScript syntax checks, affected specification validation and diff checks passed.
- Existing Starlette test-client deprecation warning remains unrelated to this feature.

## Deployment and fetched data

The clean Mac checkout at `/Users/eric/repos/homescout` was fast-forwarded to the runtime code
commit. Locked dependencies were synchronized. The existing loopback service was restarted only
after its under-way endpoint reported idle, and launchd restored a healthy interface each time.
The nightly wrapper already invokes enrichment; its schedule and other services were unchanged.

Verified SQLite backup before deployment:
`/Users/eric/HomeScout/backups/before-church-drive-times-2026-11-07.db`.

Two successful backfill passes filled current locations, then saved coordinate versions and merge
constituents. Final coverage:

| Scope | Houses/rows | With saved minutes | Blank |
| --- | ---: | ---: | ---: |
| Current Louisiana canonical houses, including merge stand-ins | 1,066 | 1,066 | 0 |
| `la-near-church` results, including not-returned rows | 758 | 758 | 0 |
| `la-one-offs` results, including not-returned rows | 9 | 9 | 0 |

The church-search values ranged from 3.5 to 76.4 minutes. One-off values ranged from 4.0 to
81.5 minutes. Result scopes overlap, so these counts must not be added together.

A fully cached repeat pass completed in 1.154 seconds with zero routing requests and zero new
lookups. Final results and numeric field types were checked through both loopback HTTP and the
normal Windows-to-Mac Tailscale address. Detail returned the church destination, numeric minutes,
`estimated`, `fresh` and the saved fetch timestamp. Live custom CSV and XLSX exports of the latest
one-off run each carried seven numeric drive times, using temporary output files and templates.

## Preservation and verification limits

All rows of **22 historical and user-data tables** were hashed in row order and compared with the
verified backup. All matched, including 260,473 raw rows, 138,646 snapshots, 1,304 annotations,
2,940,490 rule verdicts, assessments, merge decisions, runs, photos, deliveries and identities.
Enrichment values and operational pass journals are the intended changed tables.

The browser plugin host was unavailable and reported no connected browsers. No visual browser
verification was claimed, and no separate automation browser or cwin browser control was used.
Sorting and saved arrangement behavior were executed through the shipped JavaScript functions;
deployed data, detail and export behavior were checked through the real server.

Existing unrelated specification drift remains recorded in the prior ledgers. This change adds
no contradictions or unresolved findings within its own scope.

## Local operational evidence

Evidence stays beside the production database, outside git:

- `church-drive-backfill-2026-11-07.json` and `.log`
- `church-drive-backfill-2-2026-11-07.json` and `.log`
- `church-drive-verification-final-2026-11-07.json`
- `church-drive-results-final-2026-11-07.json`
- `church-drive-export-verification-2026-11-07.json`
- `church-drive-preservation-final-2026-11-07.json`

The final results file supersedes the earlier verification file's intermediate result-table counts.
