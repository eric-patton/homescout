## ADDED

None.

## MODIFIED

AC-17:

Was: A property's block is resolved from its coordinates through the FCC's keyless block
service, paced like every other request this feature makes, and cached like every other
enriched value.

Now: A property's 2020 census block is resolved from its coordinates through the FCC's keyless
block service, with the keyless Census coordinate geocoder as fallback after a failed or
unusable FCC lookup. After the first FCC failure, that provider uses Census for the remaining
lookups in the pass; a new provider tries FCC again. Both use the existing paced session and
its bounded network policy, without file-API credentials. A lookup must identify one valid
15-digit block in a known state, with any supplied state agreeing with its prefix. An
ambiguous or unusable answer is a failure, never a known negative. If both services fail,
the reported reason names both, and cached broadband values remain intact. Successful values
are cached as before and availability still comes only from the loaded FCC state index.

## REMOVED

None.
