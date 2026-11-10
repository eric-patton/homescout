# Adjust an existing drive-time area

Trigger: approved Guildboard card #2. This changes intended behavior, extending the existing recalculation flow with arbitrary minute adjustments and explicit cancellation.

Within this feature, extend AC-25 and the existing drive-time plan and tasks. Reuse shared validation, routing cache and atomic YAML edit. Do not introduce an identity derived from duration or geometry, or alter results filters. Card #3 may introduce stable area IDs independently; this change preserves an optional existing ID and does not require it.
