# macOS host for unattended HomeScout

The user approved moving HomeScout to the always-on Mac Mini on 2026-10-14, preserving all data,
boot startup, Tailscale access, and the nightly email. Windows remains available while the Mac is
verified. This changes the scheduler platform requirement, not search or delivery semantics.

Add macOS deployment documentation and generated launchd jobs. The interface is supervised at boot;
the nightly job invokes the existing command line at 03:00, then enrichment, and exits. Both run as
the workspace owner. Secrets stay in the uncommitted workspace configuration and never enter a plist
or command argument. Explicit database paths avoid launchd's different environment.

Shared platform constraints are updated on main. The photo-path compatibility defect belongs to
listing-store AC-25 and is fixed without a data migration. This is a one-time transfer with two
independent workspaces during verification, not multi-machine synchronization.
