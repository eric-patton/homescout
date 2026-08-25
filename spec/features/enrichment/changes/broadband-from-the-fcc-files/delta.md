# Delta — enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

New requirements, written as full spec requirements. Each acceptance criterion here takes the next
stable id when folded into `spec.md`: AC-15 through AC-21.

**Vocabulary.** A **broadband index** is a local table of what fixed internet service the FCC
records as available in each census block of one state, built from that state's own published files
and kept beside everything else in the store. A **block** is the census block a property's
coordinates fall in, which the FCC will name for a point without a credential.

**User story.** As the person running searches, I want to know what internet a rural property can
actually get, so that a house I would otherwise like is not one I cannot work from.

**User story.** As the person running searches, I want to be told which state's data I am missing
rather than to see an empty column, so that filling it is one command rather than an investigation.

- AC-15: A census block in a loaded state with no filed residential service is recorded as a known
  negative rather than as a missing value, in the same way a point outside a mapped flood zone is.
  The FCC was asked and its answer was that nobody has filed service there, which is a different
  thing from nobody having looked.
- AC-16: Broadband service is answered from a locally held index of the FCC's published availability
  files, keyed by census block, rather than from a per-property request to any service. Building the
  index for a state is an explicit action, never a side effect of an enrichment pass.
- AC-17: A property's block is resolved from its coordinates through the FCC's keyless block
  service, paced like every other request this feature makes, and cached like every other enriched
  value.
- AC-18: The recorded values are the best advertised residential download and upload speeds in that
  block and the providers that offer them. Every surface that shows them says the figure is for the
  block rather than for the property, and says advertised rather than measured.
- AC-19: Satellite service is excluded from the reported speeds and named separately if at all,
  because it is available almost everywhere and including it would report every rural property as
  served while saying nothing about what it can get.
- AC-20: The FCC's file API is reached with the account name and the token it requires, both read
  from the environment or the uncommitted `.env` and neither ever from a saved search or committed
  config. With either absent the provider is not configured, makes no request, and its values read
  as missing rather than as a failure.
- AC-21: A property whose state has no index loaded is reported as that, naming the state and what
  would load it, and is distinct both from a provider that is not configured and from a provider
  that failed.

## MODIFIED

- **AC-12 — national coverage**
  - Was: Every provider covers the whole country. A test asserts a successful lookup at locations in
    geographically distant states, for every provider this installation can run. A provider that is
    not configured is skipped by name rather than silently passed over.
  - Now: Every provider covers the whole country. A test asserts a successful lookup at locations in
    geographically distant states, for every provider this installation can run. A provider that is
    not configured is skipped by name rather than silently passed over. Broadband covers the country
    a state at a time: every state can be indexed and the test asserts that, while a state nobody
    has indexed reads as an unloaded state rather than as a gap in coverage.

- **Edge case — the broadband provider has no token**
  - Was: It reports itself as not configured, makes no request, and its values read as missing
    rather than as a provider failure, because nobody asked and nothing broke.
  - Now: It reports itself as not configured, makes no request, and its values read as missing
    rather than as a provider failure, because nobody asked and nothing broke. The same is true with
    a token but no account name, since the FCC requires both. A third state sits between those and
    working: credentials present, no index loaded for the state a property is in, which names the
    state rather than reading as either of the other two.

- **Security (non-functional requirement)**
  - Was: Broadband is the exception and was not one when this was written: the FCC's national map
    now requires an API token, so that provider is absent by default, makes no request without one,
    and is enabled by putting a token in the environment or the `.env` file, where every other
    secret in this product lives.
  - Now: Broadband is the exception and was not one when this was written. The FCC's national map
    now requires an account, and its API wants two values rather than one: the account name and the
    token, sent as headers. Both are read from the environment or the uncommitted `.env`, where
    every other secret in this product lives, and the provider is absent by default and makes no
    request without both. What is downloaded is a public dataset and is written where the database
    lives, which is local data and is never committed.

## REMOVED

- The broadband provider as a per-point request against
  `https://broadbandmap.fcc.gov/api/public/map/location` — that endpoint does not exist and answers
  405 to every request. Nothing in the spec named the address; what is removed is the implied shape,
  and AC-16 replaces it.
