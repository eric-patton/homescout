# Delta: named-addresses

> The change expressed against the current spec as explicit operations.

## ADDED

### Vocabulary

- A **named address** is one street address a search asks for by name: one house, wanted whatever
  the search's filters and exclusions say. It sits beside the areas, not among them, because an area
  admits everything inside it and a named address admits exactly one property.

### User story

- As the person running searches, I want to name specific houses in a search, any number of them,
  so that a house somebody sent me is watched and judged beside everything else without drawing a
  shape around it and wading through its neighbours.

### Scenarios

- **Scenario: a named house comes back, and only that house**
  - Given a search naming `52150 Taylor Dr, Loranger, LA 70446`, and a source that lists that house
    and two others within half a mile
  - When it is run
  - Then that house is in the run, and the two neighbours are not

- **Scenario: a named house the filters would have hidden**
  - Given a search whose filters say built 1990 or later and under $500,000, and which names a house
    built in 1978 and listed at $560,000
  - When it is run
  - Then the house is in the run, and the search's criteria judge it like any other property

- **Scenario: a named house nobody lists**
  - Given a search naming an address that no source currently lists
  - When it is run
  - Then the run completes normally and reports that address as not found by any source

- **Scenario: the same house, spelled three ways**
  - Given a search naming `33063 Hwy 43, Independence, LA 70443`, and three sources that list it as
    `33063 Highway 43`, `33063 Highway 43` and `33063 Hwy 43 Hwy`
  - When it is run
  - Then all three rows are kept as that address, and become one property

### Acceptance criteria

- AC-15: A definition may carry `addresses`, a list of any number of street addresses. Each entry is
  either a line of text (`202 Marguerite St, Folsom, LA 70437`) or a mapping with `address`, an
  optional `reason` under AC-14's rules, and an optional `at: [latitude, longitude]` that places the
  address when the lookup cannot. A definition needs at least one area or one named address, and
  either alone is enough. The list survives a load and a save under AC-8 and changes as a readable
  difference under AC-12.

- AC-16: Each named address without an `at` is placed by the boundary provider this feature already
  delegates to (AC-13), through one more question on the same port: where is this street address.
  The answer is cached, so a repeat run performs no new lookup for an address already placed; an
  `at` pair is used as written and nothing is looked up for it. Placing happens once per run, before
  any source is asked, and never inside the filtering loop.

- AC-17: Validation checks the list's shape and fetches nothing (AC-9 unchanged). It reports, each at
  its location in the file: an entry that is neither text nor a mapping carrying `address`; an empty
  address; an address longer than 200 characters; an `at` that is not two numbers, is out of range,
  or has latitude and longitude swapped (the check a radius centre already gets). It gives a notice,
  which never stops a run, for the same address named twice (then looked for once), and for a list
  of more than 50, saying how many queries per run they add.

- AC-18: For each source in the search, every placed address is asked for with a coarse query that
  contains a circle of half a mile around its point, in whatever form that source accepts (AC-4's
  resolution, unchanged). None of the search's filters are sent with it. A source that takes a
  listing status is asked once each for sale, pending and contingent, whatever the search's own
  listing types are, so a named house that goes under contract is still seen; a source that takes no
  status is asked once without one, and its report says so. A status a source rejects degrades that
  source's contribution as any failed query does. Addresses whose circles overlap may share one
  query. A source is unavailable for the search only when it can express neither an area nor a
  named address.

- AC-19: Of the rows an address's query returns, the only ones kept for it are those whose address
  matches the named one under the address matcher's normalized key (feat-006: house number, street
  name, unit and ZIP code), so `Hwy 43 Hwy` and `Highway 43` are one address. Two exceptions, both
  taken from the address matcher's own rules: a unit or lot that only one side carries does not
  separate them (feat-006's AC-24), while two different units do; and when the person left the ZIP
  code out, the one the lookup answered with is used, or with no lookup (an `at` was given) the ZIP
  is left out of the comparison. Every other row that query returned is discarded unrecorded, as a
  row outside a drawn area is (AC-5).

- AC-20: A property kept under AC-19 is in the run whatever the search's filters and exclude areas
  say, including the freshness filter of AC-11. The search's criteria judge it exactly as they judge
  every other property, and a criterion that drops it sets it aside with its reason, where a person
  can see it. A property that is both at a named address and inside an area is one property,
  recorded once.

- AC-21: Every run reports each named address: whether it could be placed and the address the lookup
  matched (so a placement in the wrong town is visible), and which sources found it and which did
  not. A named address no source lists is reported as not found. That is an
  ordinary answer: it never fails the run and is never silent. An address that could not be placed
  (the lookup had no match, or could not be reached) is reported as not looked for, with `at` named
  as the way to place it by hand, and the rest of the search runs.

- AC-22: The browser interface's search editor shows a search's named addresses with their reasons,
  and can add them (one, or many pasted one per line) and remove them, writing through the same edit
  operation `homescout searches edit --set addresses=[...]` uses (AC-7, AC-8). Before an address is
  added, the editor says it will be sent once to the Census geocoder to be placed. The run status on
  screen carries the per-address report of AC-21. (Shared with feat-010, as AC-14 was.)

### Edge cases

- The lookup cannot place an address: new construction, a rural route, a misspelling. The run
  reports it as not looked for and names `at` as the remedy (AC-21); it is not a validation failure,
  because validation fetches nothing.
- The lookup places an address more than half a mile from where the sites put the house. No source
  finds it, and the report shows the address the lookup matched, which is the cue to give `at`.
- A named address with a unit (`12 Main St Apt 4`). The unit is part of the comparison, so the other
  units in the building are not kept; a listing of the same building with no unit at all still is.
- An `at` pair places the query only. It is never written onto a listing as that listing's
  coordinates.
- A named house is sold or withdrawn. It stops being found and follows the store's ordinary rules:
  disappeared on the ordinary evidence, never marked sold without a positive observation.
- Two sources spell the named house differently, or give it different coordinates. Each row is
  kept by address under AC-19, and whether they become one property is the address matcher's
  decision, as for any two rows.

### Non-functional

- Politeness: a named address costs at most one query per source per listing status per run, and
  addresses whose circles overlap share one. Placing costs one lookup per address per cache
  lifetime.
- Privacy: a named address leaves the machine once per cache lifetime, as text, to the Census
  geocoder, and nowhere else. The listing sites are sent the circle around it, never the address.

## MODIFIED

- **AC-1: the file shape**
  - Was: A definition is a hand-editable text file supporting a name, a description, areas, exclude
    areas, filters, a source list, rules, and export settings, matching the shape given in the brief.
  - Now: A definition is a hand-editable text file supporting a name, a description, areas, named
    addresses (AC-15), exclude areas, filters, a source list, rules, and export settings, matching
    the shape given in the brief plus the named addresses.

- **AC-3: what qualifies**
  - Was: A property qualifies if it falls inside any area and inside no exclude area. A test covers a
    property inside two overlapping areas and one inside both an area and an exclusion.
  - Now: A property qualifies if it falls inside any area and inside no exclude area, or if it is at
    one of the search's named addresses (AC-19, AC-20), whatever the exclusions say. A test covers a
    property inside two overlapping areas, one inside both an area and an exclusion, and a named
    address inside an exclusion.

- **Vocabulary: definition**
  - Was: the complete saved search: name, description, areas, exclude areas, filters, sources,
    rules, and export settings.
  - Now: the complete saved search: name, description, areas, named addresses, exclude areas,
    filters, sources, rules, and export settings.

## REMOVED

Nothing.
