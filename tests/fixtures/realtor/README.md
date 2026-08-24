# Recorded Realtor.com responses

Captured 2026-08-23 from `https://www.realtor.com/frontdoor/graphql`, by the same client the
adapter uses: an honest user agent, `rdc-client-name: homescout`, no token.

- `geography_city.json` — the geography lookup for "Portales, NM", all 16 suggestions as returned.
- `search_city.json` — a for-sale area search for the same place. The source reported 87 matches
  and returned all 87; the file keeps the first 12 for repository size, with `total` left at the
  source's own figure so the paging and ceiling behaviour stay exercisable. The trimming is
  recorded inside the file too.

These exist so a change in the source's response shape shows up as a fixture that no longer matches
reality, rather than as a test that quietly still passes against a stale idea of the schema. When a
test starts failing here, re-record before assuming the code is wrong.

Re-record by pointing the same two queries at the live source and saving what comes back. Nothing
here is generated or hand-edited beyond the trim noted above.
