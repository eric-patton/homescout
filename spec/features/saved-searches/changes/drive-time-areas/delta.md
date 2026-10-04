# Drive-time areas delta

## ADDED

- AC-25: A `drive_time` area stores an address label, a finite geographic center, positive finite minutes up to 60, direction `to` or `from`, provider `openrouteservice`, generation time, matched address where available, public-place declaration, and valid Polygon or MultiPolygon geometry. Names, reasons and exclusions survive loading, editing and both interfaces. Source queries contain the saved polygon; local containment uses it without geocoding or routing on runs, even with no API key. Changing or refreshing its geometry starts the usual new observation scope.
- AC-26: A shared drive-time preview validates inputs and an explicit public-place declaration before any network call. It geocodes through the existing cache unless a coordinate override is given, sends only the center and driving parameters to the current HeiGIT endpoint, and returns a validated area without writing a search. `HOMESCOUT_ORS_API_KEY` is read from the environment or the workspace `.env` on each uncached lookup. Valid generated areas are cached by exact center, minutes, direction and provider; explicit refresh replaces the cached area only after success. Missing keys, refusals, malformed geometry and failed refreshes are clear errors without credentials or changed saved geometry. No per-listing routing calls occur. Expose the same operation as `searches drive-time ADDRESS --minutes N --direction to|from --public-place [--center LAT LON] [--refresh] --json` and a guarded HTTP endpoint.

## MODIFIED

None.

## REMOVED

None.
