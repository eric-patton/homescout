# Census fallback for broadband block lookups

Approved by the user on 2026-10-05 after repeated broadband failures. The FCC block service
returned HTTP 400 with an internal database authentication error for both NM and LA points.
The Census coordinate geocoder returned the failing NM property's 2020 block, which joined to
the already downloaded FCC index and yielded its advertised speeds. This changes AC-17's
FCC-only requirement rather than repairing code that failed to follow it.

Scope: AC-17, plan D-12, the broadband resolver and provider, offline tests and README. The
primary FCC lookup remains first; after its first failure a provider uses Census for the rest
of that pass. New provider instances try FCC again. Both services stay keyless and use the
existing paced session, timeouts, retry bounds and body limits. The fallback requests the 2020
geography and validates a unique block and consistent state. If both fail, no cached value is
replaced. State indexes remain explicitly downloaded by the user.

Operational authorization: wait for the current enrichment pass to finish, reload the idle
server, then start a normal enrichment pass that retries missing data and skips fresh cache.

