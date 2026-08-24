# Plan — Zillow and Redfin sources (feat-005)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

Both sites were probed before anything was designed, because what they return decides what the code
looks like and because the last two features that skipped this step found out the hard way that the
public internet moves. Measured on 2026-08-24, with this tool's own user agent
(`homescout/0.1.0 (personal listing monitor)`) and nothing else: no browser impersonation, no
cookies carried in, no key.

| | Zillow | Redfin |
|---|---|---|
| endpoint | `PUT https://www.zillow.com/async-create-search-page-state` | `GET https://www.redfin.com/stingray/api/gis-csv` |
| geography it takes | `mapBounds`, a box | `poly`, a ring of longitude-latitude pairs |
| what comes back | JSON: `cat1.searchResults.mapResults`, each with a full `hdpData.homeInfo` | CSV with a header row, a standing notice row, and one row per property |
| the true total | `cat1.searchList.totalResultCount` | not reported at all |
| observed ceiling | 502 and 503 rows for boxes matching 2,067 and 20,181 | exactly 350 |
| filters that work | price, beds, baths, size, lot, year, home type, status | price, beds, baths, size, year, home type. **Not lot size.** |
| credential | none | none |

Five things came out of that hour, and each one changes the design.

- **M-1: the Zillow endpoint every write-up names is gone.** `GetSearchPageState.htm` answers 404
  with Zillow's own error page, 437 kilobytes of it, which a careless adapter would try to parse.
  The endpoint that answers today is a `PUT` with a JSON body to
  `/async-create-search-page-state`. Same shape of finding as FEMA's moved flood service in
  location enrichment (feat-007), and the same conclusion: the address is configuration.
- **M-2: `mapResults` is the whole box in one request.** For a box matching 68 properties, the map
  results carried all 68, each with a complete `homeInfo`; `listResults` carried 41, one page of
  two. So this adapter reads the map results and makes **one request per box**, and never paginates.
  That is both simpler and more polite than the obvious implementation.
- **M-3: Redfin takes a polygon, so there is no region to look up.** Its `location-autocomplete` and
  `query-location` paths are refused at the CDN (403, CloudFront's own error page), which would have
  been a hard blocker for the region-id approach. Passing `poly` works with no region id, no market,
  and no prior request, and a ring is exactly what a bounding box already is.
- **M-4: Redfin's cap is silent.** 350 rows and no count anywhere in the response. A query matching
  four thousand properties and a query matching exactly three hundred and fifty are byte-identical
  in shape. So the adapter has to infer: getting exactly the cap means there are more.
- **M-5: Redfin cannot say when a region's listing service forbids downloads.** This is the finding
  that changes a criterion, and it is worth stating in full. Every response, everywhere, carries the
  same line: *"In accordance with local MLS rules, some MLS listings are not included in the
  download"*. It is boilerplate. A box over Springfield, Illinois returns two properties; a box over
  Portales, New Mexico, a town of twelve thousand, returns sixty-one. The restriction is real,
  and the response does not mention it. See D-8.

## Design decisions

### D-1: layout

Two adapter packages beside the first one, and one shared file for the thing they both need.

| file | holds |
|---|---|
| `sources/boxes.py` | halving a bounding box, and when to stop. Both new sources cut this way. |
| `sources/zillow/__init__.py` | the adapter: capabilities, one request per box, the ceiling walk. |
| `sources/zillow/queries.py` | the request body and the filter table, and the endpoint as configuration. |
| `sources/zillow/normalize.py` | one `homeInfo` to one `ListingFields`. |
| `sources/redfin/__init__.py` | the adapter: capabilities, one download per box, the ceiling walk. |
| `sources/redfin/queries.py` | the query string, the filter table, and the endpoint as configuration. |
| `sources/redfin/normalize.py` | one CSV row to one `ListingFields`. |

Nothing outside `sources/` is touched, and inside `sources/` nothing that already existed is
touched. That is AC-12, and how it is checked is D-11.

### D-2: both adapters take a bounding box, and only a bounding box

`accepts_areas = (BoundingBox,)` for both. The saved-search geography (feat-004) already turns a
named place, a radius or a drawn shape into a box that contains it, and the exact local test then
removes what falls outside. That is AC-6 exactly, and it is why neither adapter contains a
geocoder.

**Redfin would take the drawn shape itself**, and that is worth writing down rather than
discovering again later. Its `poly` parameter is a ring, not a rectangle, and the adapter
vocabulary already has a `Polygon` area that today exists only so an adapter can decline it. Making
use of it would mean one more branch in `SearchArea.coarse_for`, which is core, and the spec's AC-6
asks for the box. Not built. Recorded here because the pay-off is real: an exact shape on the source
side would waste far less of the 350-row cap on properties the local test is about to discard.

### D-3: the ceiling machinery is reused unchanged, with a different way to cut

`ceiling.collect()` (feat-002) already does the whole procedure: ask, read the count, split if it is
over the cap, recurse, and turn "still too big and can no longer be cut" into an honest truncation.
Realtor.com cuts by listing date. These two cut by geography, and `boxes.halve()` is the only new
part:

```python
def halve(box: BoundingBox) -> tuple[BoundingBox, BoundingBox] | None:
    """Cut along the longer side, so repeated halving stays roughly square."""
```

It returns `None` when either side is already below `MIN_SPAN_DEGREES` (0.002, about two hundred
metres), which is what turns "a single tower with six hundred units" into a truncation rather than
an infinite descent.

The spec's coastline edge case needs nothing further: the walk only recurses into a half whose own
reported total is over the ceiling, and an empty half reports zero. Splitting stops where the
properties stop, without anyone writing a rule about water.

### D-4: Zillow reads the map results, and one request is a whole box

`Page(rows=mapResults, total=totalResultCount)`, with `page_size` set to the ceiling so the walk
never asks for a second page it would not use. The count is the true total even when the rows are
capped, which is precisely what the walk needs to decide to split: 20,181 reported, 503 delivered,
split.

The ceiling is declared as **500** rather than 503. It is not a documented number and the two
observations disagree; declaring the smaller one means the walk splits slightly more often than it
strictly must, which errs toward completeness. Erring the other way silently loses properties.

### D-5: Redfin infers its total, because the response will not say

```python
total = len(rows) + 1 if len(rows) >= CAP else len(rows)
```

Getting exactly the cap means "there are more" and nothing else can be honestly concluded, so that
is what is reported. The walk then splits, and each half either comes back under the cap (a real
count) or splits again. A market with exactly 350 properties in it costs one unnecessary split;
that is the price of never presenting a capped result as complete, and it is the right way round.

`num_homes=350` is sent explicitly rather than relying on the default, so the number the adapter
believes and the number it asks for cannot drift apart.

### D-6: what each adapter declares it filters

Verified by measurement rather than by reading anybody's documentation: a filtered request was
issued and the returned extremes were checked against it. Albuquerque went from 1,980 matches to 360
with a minimum price of exactly $500,000 and a minimum of four bedrooms.

| field | Zillow | Redfin |
|---|---|---|
| price_min / price_max | `filterState.price.{min,max}` | `min_price` / `max_price` |
| beds_min / beds_max | `filterState.beds.{min,max}` | `num_beds` / `max_num_beds` |
| baths_min | `filterState.baths.min` | `num_baths` |
| sqft_min / sqft_max | `filterState.sqft.{min,max}` | `min_listing_approx_size` / `max_listing_approx_size` |
| lot_sqft_min / lot_sqft_max | `filterState.lotSize.{min,max}`, in square feet | **nothing works** (M-6) |
| year_built_min / year_built_max | `filterState.built.{min,max}` | `min_year_built` / `max_year_built` |
| property_types | the home-type booleans, set false to exclude | `uipt` |
| listing_status | the status booleans | `status` |
| listed_since | `filterState.doz` | not offered |

Each row was issued against the real endpoint and the returned extremes checked against what was
asked. Albuquerque went from 1,980 matches to 360 at a minimum price of exactly $500,000 with four
bedrooms; a minimum of 3,000 square feet returned a minimum of exactly 3,000; three bathrooms
returned three; the home-type booleans reduced the returned types to `SINGLE_FAMILY` alone. The one
row that says nothing works says so because it was tried three ways.

Two units worth writing down, because both are the kind of thing that produces a filter that
appears to work: Zillow's **lot filter takes square feet and its response reports acres**
(`lotAreaValue` with `lotAreaUnit`), and Zillow's `baths` filter is a minimum only.

Anything not in a table here is never sent and is reported back as still needing local filtering,
which is the interface's whole contract. Adding a row means measuring that the request changes,
which is what the test for it does.

### D-7: endpoints and pacing

Both addresses are configuration with an environment override, for the same reason enrichment's
are: this is the second feature in a row where a documented endpoint had already moved.
`HOMESCOUT_SOURCE_ZILLOW_URL` and `HOMESCOUT_SOURCE_REDFIN_URL`.

Pacing is the layer that already exists, per source, unchanged. Nothing here lowers a delay, and the
subdivision walk issues its pieces through the same paced session as everything else, which is what
AC-4 asks a test to observe.

### D-8: what Redfin can honestly say about availability

AC-7 asks for the outcome `unavailable` "when the region does not permit downloads". M-5 says the
response does not carry that fact. So the criterion as written cannot be satisfied against the real
endpoint, and pretending otherwise would mean inventing a signal, most likely a row-count threshold,
which would report a genuinely quiet market as a policy restriction and vice versa. That is worse
than not answering.

What is built instead:

- **`unavailable` for the refusals that do exist and are unambiguous.** A response that is not a CSV
  download at all: the stingray error envelope (`{}&&{"errorMessage": ...}`), an HTML block page, a
  403 from the edge. Each names what came back. These are real and they are what "Redfin will not
  give you this" looks like when it is machine-readable.
- **Every Redfin result carries the site's own notice in its detail, every time.** Not as a
  truncation, because truncation that is always on stops meaning anything, but as the standing
  caveat it actually is: this source's contribution is never known to be complete, the site says so
  on every response, and so does the run's per-source report.
- **The row cap is truncation** (AC-9), because that one is observable.

This narrows AC-7 and is recorded as a change against this feature's own spec, in `feature.md`,
the way the FCC's broadband key was recorded in location enrichment. The user-visible promise the
criterion was protecting still holds: a coverage gap is never presented as a quiet market, because
the notice is on every result.

### D-9: no credentials, and none available to leak

Neither site was asked for one and neither adapter has a place to put one. Both were probed with no
cookie jar, no session warm-up and no key, and both answered. A test asserts that neither adapter's
module mentions a token, a password, or an authorization header, which is the version of AC-11 that
stays true after somebody tries to fix a block by adding one.

### D-10: what this feature does not own

- **The ceiling walk, the politeness layer, the run loop, the store.** All of them already work and
  none is touched. If any of them had needed to change, that would have been the finding.
- **Merging a Zillow row with a Realtor.com row for the same house.** Address matching (feat-006) is
  the next feature and this one deliberately stops short of it: three sources returning the same
  property three times is exactly the input that feature needs to exist for.

## Verification approach

- **The interface tests run against all three adapters**, not two, by parametrizing the ones that
  already exist. That is AC-1, and it is what makes "the fourth source is cheap" a fact rather than
  a hope.
- **Recorded responses**, captured from the real endpoints on the day they were measured, so a site
  changing its shape fails a test here rather than quietly producing empty results.
- **The subdivision test asserts more than five hundred distinct properties** from an area over the
  ceiling, which is AC-3 stated as a number, and asserts the requests were paced rather than burst,
  which is AC-4.
- **The no-core-change test asserts the dependency direction**, which is the durable half of
  AC-12: the two new adapter packages import nothing from the store, the run loop or the merge
  layer, and no core module imports either of them. Plus the behavioural half the criterion asks
  for by name: a run naming all three sources succeeds with both new adapters reaching it only
  through registration. See D-11 for the version of this that was rejected.
- **Live tests, marked slow**, one query each against both real sites, because the failure this
  whole plan is built around is a site that moved.

## Added after the pre-build check

### D-11: the no-core-change test does not read the git diff

The first draft of this plan proposed asserting AC-12 by reading this feature's own diff and
checking that it touches no file in the store, the run loop, the politeness layer or the adapter
interface. That is a truthful check exactly once. The next feature to land moves the baseline, and
from then on the test either fails for reasons that have nothing to do with these two adapters or
has to be pinned to a commit that gets staler every week.

What replaces it says the same thing durably: **the dependency direction**. The two new packages
import nothing from `homescout.store`, `homescout.runner`, or `homescout.matches`, and nothing in
the core imports either of them. A source that needed the core to change would have to reach for it,
and reaching for it is what is checked. The behavioural half of AC-12 (a run naming all three
sources, with both new adapters supplied only through registration) is a separate test and is what
the criterion asks for in its own words.

### D-12: a source-supplied URL is only ever fetched when it is `http` or `https`

The one place a listing site's own text becomes an outbound request from this machine is the preview
image, and both new adapters have one. The first adapter already restricts it, and the rule is
inherited rather than reinvented: a preview whose scheme is anything else is no preview, and a
response whose content type is not an image is no preview either. Written down here because the two
new adapters are the first chance to forget it.

### D-13: a note forward to spreadsheet export

Redfin's rows arrive as CSV and are written into the store as ordinary text. Nothing here is at
risk from that. Spreadsheet export (feat-011) is: a cell whose value begins with `=`, `+`, `-` or
`@` is a formula to Excel, and these values come from listing sites. That is that feature's problem
to solve and it is recorded here because this is the feature that first lets such a value in.

### D-14: one vocabulary for property type and status, and the adapters translate into it

A criterion says `property_type == 'single_family'` and the merge that arrives next feature compares
properties across sources. Neither works if one source says `SINGLE_FAMILY`, another says
`Single Family Residential`, and a third says `single_family`.

The first adapter's own values are already the tool's vocabulary, so the vocabulary is theirs:
`single_family`, `condo`, `townhouse`, `multi_family`, `land`, `farm`, `mobile`, `apartment`, and
`for_sale`, `pending`, `contingent`, `sold`, `off_market` for status. Each new adapter carries a
table in both directions: the site's name in, the tool's name out, and the query's name translated
on the way to the site.

A value the table does not know stays as the source wrote it rather than being dropped or guessed
at. A property type nobody has seen before is a fact about the market; a silently empty one is a
fact about this code.
