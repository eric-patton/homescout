# Recorded Realtor.com responses

Captured from `https://www.realtor.com/frontdoor/graphql`, by the same client the adapter uses: an
honest user agent, `rdc-client-name: homescout`, no token.

- `geography_city.json` — the geography lookup for "Portales, NM", all 16 suggestions as returned.
  Captured 2026-08-23.
- `search_city.json` — a for-sale area search for the same place, keeping the first 12 results for
  repository size, with `total` left at the source's own figure so the paging and ceiling behaviour
  stay exercisable. Captured 2026-08-30.
- `search_bathrooms.json` — a for-sale search of Santa Fe, NM, kept for one thing only: it is a
  market whose properties use every shape the source's bathroom fields come in. Five results,
  picked one per shape rather than by position, and the file says which is which. Captured
  2026-08-30.

Each file records the trimming inside itself as well.

These exist so a change in the source's response shape shows up as a fixture that no longer matches
reality, rather than as a test that quietly still passes against a stale idea of the schema. When a
test starts failing here, re-record before assuming the code is wrong.

**They cannot catch a field the request never asks for.** A recording is made by the adapter's own
selection set, so a field left out of the request is absent from the recording, and every test
reading the recording agrees with the omission. That is how the bath count stayed a whole bathroom
short of its own description for months: `baths_3qtr` was never asked for, so nothing offline could
notice it missing. The check that closes that hole has to talk to the live source, and does, in
`test_sources_live.py`.

Re-record by pointing the same queries at the live source and saving what comes back. Nothing here
is generated or hand-edited beyond the trims noted above.
