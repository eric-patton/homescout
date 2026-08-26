# Product-global — HomeScout

Cross-cutting requirements owned by no single feature.

## Vision

One table containing every listing in a region, with every field visible, filterable on data the
listing sites do not expose, and honest about what changed since the last time you looked.

## Glossary

- **Source**: one listing adapter (`realtor`, `zillow`, `redfin`). All satisfy the same interface
  and declare which filters they can push server-side.
- **Raw listing**: a single row exactly as one source returned it, tagged with its source and the
  time it was fetched. Never edited, never deleted.
- **Canonical listing**: the merged record for one physical property, built on top of one or more
  raw listings and carrying the list of raw rows it was built from.
- **Run**: one execution of a saved search across its configured sources, recording per-source
  success or failure and per-source counts.
- **Snapshot**: an immutable row capturing a canonical listing's state at the end of one run. The
  substrate every difference is computed from.
- **Merge**: the process of deciding that raw listings from different sources describe the same
  property. A **merge decision** is a human override of that process, and it persists.
- **Enrichment**: an external public data value attached to a location rather than to a listing
  (flood zone, broadband service, aquifer, wildfire hazard, elevation), cached by rounded
  coordinates and provider.
- **Saved search**: a hand-editable YAML definition of areas, filters, sources, rules, and export
  settings. The unit a run operates on.
- **Area**: one geographic component of a saved search: a drawn polygon, a city, a county, a ZIP
  code, or a radius around a point. **Exclude areas** subtract from the result.
- **Rule**: a user-authored condition over listing and enrichment fields, with a severity of
  `drop`, `flag`, `boost`, or `demote`.
- **Annotation**: user judgment attached to a canonical listing (rank, verdict, red flags, summary,
  next step, free notes). Authored by the user, never by a source.
- **Digest**: the compact summary of what changed in a run, emitted as JSON for an automated reader
  and as email for a human.
- **Disappeared**: a canonical listing that stopped appearing in results without being observed as
  sold. A status, not a deletion.
- **Days on market (DOM)**: days since a listing was first observed by this tool, computed from
  local history rather than taken from any source.

## Global non-functional requirements

- Performance: a scheduled run over a typical county completes unattended within the pacing its
  rate limits imply, with no manual intervention. The results table remains usable at several
  thousand rows.
- Security: the server binds to localhost only. No authentication, and therefore no listening on a
  routable interface by default. Secrets are read from the environment, never from stored config.
- Accessibility: the browser interface is fully keyboard operable and legible at default zoom. No
  formal conformance level is claimed.
- Reliability: no single external failure can abort a run, corrupt history, or delete a listing.
  Every partial failure is visible in that run's per-source status.
- Privacy / data handling: all data stays on the local machine. The only outbound traffic is
  requests to listing sources, public enrichment endpoints, the optional extraction model, and the
  SMTP server used for the digest. Collected data is not republished or redistributed.

## Product invariants

1. Snapshot and raw-listing history is append-only. No feature may update or delete a historical
   row; corrections are new rows.
2. Every canonical listing is traceable to the raw source rows it was built from, and that
   provenance is visible in the interface.
3. A user annotation, once saved, survives every subsequent run, merge, unmerge, and re-export.
4. A listing is only marked as no longer available on positive evidence. Absence from one source's
   response is never sufficient.
5. Every capability is reachable from both the command line and the browser, because both are thin
   wrappers over the same core library.
6. Every command-line command accepts `--json` and returns a stable exit code, so an automated
   agent can drive the tool without parsing prose.
7. Freshness ("new", "days on market", "price cut") is always computed from local history, never
   read from a source field.
8. Rule expressions are evaluated by a restricted parser over a fixed field namespace. No user
   input reaches a general-purpose interpreter.
9. Optional components (AI extraction, email digest, any individual enrichment provider) are
   absent-by-default: with none of them configured, the tool is fully functional.
10. A field that could not be determined is empty. It is never filled with a guess.

## Cross-cutting constraints

- Per-source result ceilings that the query planner must work around, not ignore: `realtor` caps at
  10,000 results per query (chunk by date range); `zillow` caps at roughly 500 per bounding box
  (split the box); `redfin` caps at 350 rows and is only available where the local MLS permits CSV
  download, so it must degrade to unavailable rather than fail.
- Every source request passes through per-source rate limiting with backoff, jitter, a configurable
  delay, and an honest user agent. This applies to image downloads as well as listing queries.
- Geography resolves in two stages: a coarse query in whatever form a source accepts (city, county,
  ZIP, bounding box), then an exact local point-in-polygon test against the saved search's areas.
  The command line and the browser feed identical GeoJSON into the same code path.
- Enrichment providers cover the whole country by default. A provider whose source covers only
  part of it is permitted, and must report a location outside that coverage as not applicable:
  a third state, distinct both from a value it determined and from a value nobody obtained, so
  that partial coverage can never be read as an answer. Each provider declares a cache key and
  a time-to-live, and a cache hit is never re-fetched.
- Storage is one SQLite file. Downloaded images live on disk beside it, referenced by path.
- Scheduling targets Windows Task Scheduler invoking the command line. No daemon, no service, no
  always-on process.
