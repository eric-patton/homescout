# Drive-time area controls delta

## ADDED

- AC-108: The area editor has address, optional coordinate center, minutes (up to 60), direction (to by default), public-place acknowledgment, include/exclude, Preview driving area, Refresh preview and Add drive-time area controls. Preview is visibly not yet added; Add writes only a draft row and Save the areas writes the search. Changes to preview inputs invalidate the preview; stale replies and redraws cannot restore obsolete results. Provider errors retain draft input and all saved areas. The guarded HTTP endpoint calls the shared core operation.
- AC-109: Saved drive-time polygons render separately from editable drawn shapes, preserving exact geometry and provenance through save/reopen. Rows show address, minutes, direction and generation date, permit names, reasons and inclusion/exclusion, and can load their parameters into the preview form for recalculation; no metadata edit silently changes a generated boundary. Explain estimated driving without live traffic, public coordinate transmission, combined include areas, and explicit refresh. Credit openrouteservice by HeiGIT and OpenStreetMap whenever the generated shapes are displayed; exported area provenance identifies the provider and its CC-BY-SA 4.0 result license.

## MODIFIED

None.

## REMOVED

None.
