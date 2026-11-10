# Results drive-time ranges

Approved by Guildboard card #3 on 2026-11-09. This is a behavior change.
Narrow the complete collected pool by any chosen saved drive-time destinations, independently
of collection provenance or collection duration. Included search areas remain additive.
Changes touch results.js, common.js, fire.js, api.py and guarded background routing endpoints.
No saved-search schema change is needed; references derive from search and routing identity.
Card #2 owns collection-duration editing. Merge it first when available and recheck references.

The card resolves the user decisions: inclusive optional bounds; all active conditions must
match; immediate filtering; automatic missing-estimate calculation; confirmed matches shown
progressively with pending/unavailable counts; transient same-search navigation state only.
Live routing needs separate approval. Eric's review gates delivery; deployment belongs to #4.
