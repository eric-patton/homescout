# Recorded Redfin responses

Captured 2026-08-24 from `https://www.redfin.com/stingray/api/gis-csv`, by the same client the
adapter uses: an honest user agent, no cookie, no key, no region id. The `poly` parameter takes a
ring of longitude-latitude pairs, which is what makes a region lookup unnecessary; the
`location-autocomplete` and `query-location` paths that would have supplied one are refused at the
edge with a 403.

- `search_box.csv` — a for-sale download over a box around Portales, New Mexico. The site returned
  61 properties; the file keeps the first five for repository size, and keeps the header and the
  notice line exactly as they arrived.

Two things in this file are load-bearing and are not decoration:

- **The second line is the site's standing notice** about listings its local MLS does not permit in
  a download. It arrives in every region regardless of what the local rules actually are, so the
  adapter treats it as a caveat to report rather than as a signal to read.
- **There is no count anywhere.** The download does not say how many properties matched, only how
  many it is giving you, which is why the adapter infers that exactly the cap means there are more.

These exist so a change in the download's columns shows up as a fixture that no longer matches
reality, rather than as a test that quietly still passes against a stale idea of the schema. When a
test starts failing here, re-record before assuming the code is wrong.
