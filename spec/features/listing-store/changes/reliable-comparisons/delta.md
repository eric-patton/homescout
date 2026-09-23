# Delta: Reliable comparisons across search edits and merges

## ADDED

- A run records a digest of the observation scope it used: areas, excluded areas, filters that
  affect source queries or local inclusion, and sources. Editing those starts a new comparison
  series; editing prose, rules, export settings, or a display-only freshness window does not. The
  first completed run of a new revision establishes
  its baseline and reports that reset explicitly, without calling prior properties new or gone.
  Later runs compare only with completed runs of that revision. Legacy runs without a recorded
  revision remain readable and are not silently claimed to match the new definition.
- A completed run fixes the canonical identity used to compare its observations. Later merge and
  unmerge decisions do not change a comparison that names that run as its target. Historical runs
  whose identity cannot be reconstructed with certainty are labeled as legacy rather than silently
  presented as frozen.
- A property-field change is verified against observations from the same source at the two chosen
  comparison points. When one site replaces another without a comparable pair, the comparison
  reports the handoff as
  `unverified` rather than a price rise, cut, status change, or `unchanged` assertion.

## MODIFIED

- **Difference event vocabulary**
  - Was: A comparison has exactly five event kinds: new, changed, unchanged, gone, returned.
  - Now: It also has `unverified`, for a known property's source handoff with no same-source
    observation on the baseline side. This is counted and shown separately.
- **AC-20, reproducible comparisons**
  - Was: Repeated comparisons between fixed times are identical after later runs.
  - Now: Repeated comparisons between fixed runs are identical after later runs and later merge or
    unmerge decisions, using the search revision and identity recorded for the target run.

## REMOVED

- None.
