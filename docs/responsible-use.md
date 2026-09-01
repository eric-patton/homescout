# Responsible use

**HomeScout is a personal-use tool, and that constraint is not decorative.**

Scraping the listing sites this tool reads from is against their terms of service. HomeScout is
built to stay on the right side of the only thing that makes that defensible: it is low volume, it
is deliberately slow, it is throttled per source with backoff, it identifies itself honestly, and
nothing it collects is republished, redistributed, or used commercially.

It requires no MLS or IDX credentials and no paid data API, by design, so it never touches an
agreement anybody signed.

## Do not

- Raise the request rate or remove the pacing floor.
- Publish, sell, or redistribute the data it gathers.
- Use it for commercial purposes, or for anything work-adjacent.
- Run it against a site's terms in a jurisdiction where that carries more weight than it does for
  personal research.

If you find yourself wanting to remove a limit here, the honest move is to buy a data licence
instead.

## Where the restraint actually lives

The paragraph above is a claim. These are the places in the code that make it true, so it can be
checked rather than taken on trust.

**A floor a caller cannot lower.** `sources/politeness.py` permits a per-source delay anywhere in
`DELAY_RANGE_SECONDS = (1.0, 60.0)` and nowhere else, and ships at `DEFAULT_DELAY_SECONDS = 3.0`,
three times the floor. A configuration asking for less raises `ConfigurationError` rather than
being quietly clamped, because a floor a caller could lower is not a floor.

**No unpaced path to the network.** An adapter is handed a `PacedSession` and nothing else. It
cannot make an unpaced request, cannot retry without jitter, and cannot announce itself as
something it is not, because no code path exists that would let it. Splitting one query into forty
pieces therefore cannot become a burst.

**Retries wait rather than hammer.** Backoff starts at 5 seconds and caps at 120, over at most 3
attempts, and only for the statuses that mean "not now": 403, 408, 429, and the 5xx family.

**A separate budget per source.** Pacing is keyed per source and per enrichment provider, so one
subsystem cannot spend another's politeness. A county-wide public-data backfill is a different
relationship from a listing query, and the code treats it as one. Public-data providers are paced
at their own documented 1 second rather than at this tool's slower default.

**It says who it is.** Listing requests carry `homescout/0.1.0 (personal listing monitor)`.
Public-data requests carry `HomeScout (a personal house-search tool; one household)`. Neither
pretends to be a browser.

**Bounded reads.** Response bodies are read in chunks and abandoned past a limit rather than
trusting a `Content-Length` the other side supplies.

**Nothing collected leaves the machine.** The database, stored images, exports and any `.env` stay
out of version control. Saved searches are YAML and are the only thing meant to be committed.
