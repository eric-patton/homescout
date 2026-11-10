## ADDED

- AC-111: Results hide drive-time controls without attached drive-time areas. Otherwise zero
  through all included or excluded locations can be selected, each labelled by name, address
  and to/from direction, with independent optional nonnegative finite minimum/maximum minutes.
  Blank is unset, zero is valid, bounds are inclusive and minimum above maximum has an inline
  error. Invalid drafts apply no numeric filter for that area. No bounds means no constraint.
- AC-112: All active ranges and all existing results filters must match across the complete
  collected pool before virtual scrolling. Cross-area listings qualify irrespective of which
  area collected them, polygon membership or collection duration. No search is rerun or expanded.
  Missing/pending/failed routes never match numerically. Show only confirmed matches and a
  prominent incomplete notice with separate pending/unavailable counts, incremental batches,
  safe failure details and explicit retry without an automatic failure loop.
- AC-113: Removable chips, individual clearing and Clear all include drive-time constraints.
  Table, map pins and map list share the active filters during same-search navigation, retaining
  sorting and full-pool counts, with unmappable matches distinguished. A fresh visit or search
  switch resets transient filters. Duration-only area edits retain route identity; changed or
  removed destinations and stale responses cannot apply to the wrong search/location. No new
  persisted filter settings. State survives same-visit redraws. Show provider credit and explain
  estimates have no live traffic. Automatic calculations are debounced and deduplicated.

## MODIFIED

- Performance: Was every filter is local. Now numeric filtering remains local once values are
  available; missing estimates use responsive background work and qualified progressive results.

## REMOVED

None.
