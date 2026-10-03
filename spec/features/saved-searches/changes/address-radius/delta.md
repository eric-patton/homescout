# Address-centered radius delta

## ADDED

- AC-23: A radius area accepts a nonempty `address` and a positive finite `miles` value, with an
  optional `center: [latitude, longitude]` override. Coordinate centers and named-place centers
  remain supported. Radius names and reasons survive loading and editing. Before source queries,
  address centers without coordinates use the existing cached street-address lookup once per
  cache lifetime, never once per listing. Listings are checked by great-circle distance locally.
  An unresolved address yields no query for that area and an unknown local verdict, never an
  unrestricted query or a source-side street-address lookup. Other areas continue normally.
- AC-24: A shared radius-preview operation validates an address and mileage before making any
  lookup, returns the input address, matched address, resolved center and mileage, and changes no
  saved-search file. It is reachable through `searches radius ADDRESS --miles N --json` and a
  guarded browser endpoint. An unmatched address produces a clear error and no invented center.

## MODIFIED

None.

## REMOVED

None.
