# Save drive times to Old Zion Hill Baptist Church

The user authorized implementation, push, deployment and backfill on 2026-11-07. This is a
behavior change: drive-time search polygons currently store an area, not a route time per house.

Add an optional `church_drive` provider using the existing openrouteservice credential and the
church center already used by the saved Louisiana search: 30.5771925204, -90.57493594311.
Only Louisiana listing coordinates are transmitted, with no address, notes or listing identity.
Use a one-destination matrix in bounded batches to backfill thousands of houses within free quotas.
Keep the existing immutable snapshots and annotations intact. The existing nightly enrichment
pass fills new homes and refreshes aged estimates. Browser and export changes have their own deltas.
