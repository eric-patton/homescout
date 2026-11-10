## ADDED

- AC-59: For valid active results ranges, route each collected row's own coordinates to the
  saved location for `to`, or from it for `from`, using saved provider/profile/options and
  configured endpoint. Include historical results, merge stand-ins and revealed disappeared
  rows, without Louisiana, collection polygon, provenance or duration restrictions. Both
  surfaces expose the shared core, including CLI --json. No listing-source requests occur.
- AC-60: Cache exact listing coordinates and destination/routing identity, excluding bounds,
  names, collection duration and geometry. Retain unrounded minutes, status, fetch time and
  30-day freshness in SQLite. Fresh repeats and bound-only edits need no lookups. Retained
  stale estimates are labelled; failed refreshes preserve prior values/timestamps. Church cache
  entries are incompatible. Null, malformed, negative or nonfinite routes never become zero.
- AC-61: Automatic background calculations reuse pass exclusion, separate connections and
  progress; completed batches publish immediately. Shared routing pacing, bounded batches,
  bounded retries, no redirects and sanitized failures protect credentials/quota. Unconfigured
  or unlocatable rows are explicitly unavailable. Changed area references are rejected before
  starting work and incompatible cache keys cannot be reused. Repeated requests deduplicate;
  failures require explicit retry. Live credential/coordinate verification needs approval.

## MODIFIED

None.

## REMOVED

None.
