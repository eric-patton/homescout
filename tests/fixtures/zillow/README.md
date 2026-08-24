# Recorded Zillow responses

Captured 2026-08-24 from `https://www.zillow.com/async-create-search-page-state`, by the same
client the adapter uses: an honest user agent, no cookie, no key. Note the method: this endpoint
takes a `PUT` with a JSON body. The `GetSearchPageState.htm` address every write-up names answers
404 with four hundred kilobytes of Zillow's own error page.

- `search_box.json` — a for-sale search over a box around Portales, New Mexico. The site reported
  68 matches and returned all 68 as map results; the file keeps the first four for repository size,
  with `totalResultCount` left at the site's own figure so the ceiling and splitting behaviour stay
  exercisable.

The map results are the whole box, each carrying a full `hdpData.homeInfo`. That is why the adapter
reads them rather than paging the list results, and it is the reason one request is one box.

These exist so a change in the response shape shows up as a fixture that no longer matches reality,
rather than as a test that quietly still passes against a stale idea of the schema. When a test
starts failing here, re-record before assuming the code is wrong.
