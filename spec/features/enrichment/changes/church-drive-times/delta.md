# Church drive times delta

## ADDED

- AC-56: An individually selectable, optional `church_drive` provider saves numeric
  `church_drive_minutes` from each Louisiana house to Old Zion Hill Baptist Church, 25890 LA-442,
  Independence, LA 70443, at latitude 30.5771925204, longitude -90.57493594311. The estimate uses
  openrouteservice driving-car without live traffic, converted from seconds to minutes to one
  decimal. It also saves `church_drive_status`: `estimated`, `route unavailable` or `outside coverage`.
  Outside Louisiana the minutes remain empty and no routing request is sent. Missing coordinates
  retain the normal unlocatable report. State eligibility comes from the latest canonical snapshot.
  Newly merged houses use the latest constituent snapshot until observed again. Enrich all saved
  Louisiana coordinate versions of live eligible houses and their merge constituents, so older
  saved-search result rows also retain an estimate. Exclude retracted records.
  Both surfaces can select providers: CLI `enrich --provider NAME` (repeatable) and guarded
  `POST /api/enrich` with a `providers` list; omitted selection retains the existing full pass.
- AC-57: The provider uses the existing `HOMESCOUT_ORS_API_KEY` from the environment or the .env
  beside its attached database. Missing credentials skip it clearly. Only coordinates and driving
  parameters go to the configured HTTPS service. Requests are paced, bounded and sent without
  redirects; credentials and response bodies never enter errors. Unrecognized, nonfinite, negative
  or malformed durations are failures, never zero. A null route remains empty with an explicit status.
- AC-58: Results use six-decimal location cache keys, a 30-day lifetime and the existing fetched
  timestamp/fresh/stale/missing states. Fresh results make no requests. Failed refreshes preserve old
  values. The generic pass accepts an optional streaming batch-fetch hook without naming a provider,
  persists completed batches and continues other providers after failure. Matrix batches contain at
  most 100 origins and one church destination. A provider may supply additional saved locations;
  these share the same cache and deduplication as the normal latest-location pass.
  A known unsnappable-origin error isolates bad points
  without discarding other houses. The endpoint is overridable like existing enrichment endpoints.

## MODIFIED

None.

## REMOVED

None.
