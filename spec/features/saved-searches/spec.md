## Why

A search is the thing a person actually tunes: an area, some filters, some criteria, some
sources, refined over weeks and re-run unchanged. The interesting part is the area, because no
source accepts the shape anyone actually means. This feature owns the definition file and the
two-stage geography that turns "north of this road, but not the east side of town" into a coarse
source query plus an exact local test. The problem brief is in `research.md`.

## Vocabulary used in this feature

- An **area** is one geographic component of a search: a polygon, a city, a county, a ZIP code, or
  a radius around a point. An **exclude area** is one that subtracts.
- **Coarse resolution** is turning the search's areas into whatever form a source will accept.
  **Exact filtering** is testing each returned property against the search's real geometry
  afterwards.
- A **definition** is the complete saved search: name, description, areas, named addresses,
  exclude areas, filters, sources, rules, and export settings.
- A **named address** is one street address a search asks for by name: one house, wanted whatever
  the search's filters and exclusions say. It sits beside the areas, not among them, because an area
  admits everything inside it and a named address admits exactly one property.

## User stories

- As the person running searches, I want to draw the area I care about and have properties outside
  it never reach my table, so that a coarse source query does not become my problem.
- As the person running searches, I want to exclude a part of town as geometry, so that I stop
  re-applying the same exclusion by eye on every pass.
- As the person running searches, I want to edit the definition in a text file and review the
  change like any other change, so that I can see what I altered last week.
- As the person running searches, I want a definition validated before a run starts, so that a typo
  does not cost me an hour of throttled requests.
- As the person running searches, I want the map and the file to be two views of one definition, so
  that using one never destroys what I did in the other.
- As the person running searches, I want to name specific houses in a search, any number of them,
  so that a house somebody sent me is watched and judged beside everything else without drawing a
  shape around it and wading through its neighbours.

## Behavior & scenarios

- **Scenario: a coarse query, then an exact test**
  - Given a search whose area is a drawn polygon inside one county
  - When it is run
  - Then sources are queried using a form they accept that fully contains the polygon, and every
    returned property outside the polygon is removed before results are produced

- **Scenario: an exclusion**
  - Given a search with an area covering a town and an exclude area covering its east side
  - When it is run
  - Then properties inside the town and outside the exclusion appear, and properties inside the
    exclusion do not, regardless of which source returned them

- **Scenario: several areas**
  - Given a search with a city, a ZIP code, and a radius around a point
  - When it is run
  - Then a property inside any one of them qualifies, subject to the exclusions

- **Scenario: a property with no coordinates**
  - Given a search whose areas include a drawn polygon, and a property a source returned without
    coordinates
  - When exact filtering runs
  - Then the property is not silently dropped; it is retained and marked as not locatable, so it is
    visible as an unresolved case rather than an absence

- **Scenario: a definition round-trips**
  - Given a definition containing comments, key ordering, and a polygon drawn earlier
  - When it is loaded into the browser interface and saved again with one filter changed
  - Then every other part of the definition is unchanged, and the geometry is not degraded or
    re-approximated

- **Scenario: validation before a run**
  - Given a definition with an unknown source name and a malformed polygon
  - When it is validated or run
  - Then both problems are reported with enough location detail to fix them by hand, and no
    source is contacted

- **Scenario: the two surfaces agree**
  - Given the same definition
  - When it is run from the command line and from the browser interface
  - Then the identical geometry reaches the identical code path and the results are the same

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

## Acceptance criteria

- [ ] AC-1: A definition is a hand-editable text file supporting a name, a description, areas,
      named addresses (AC-15), exclude areas, filters, a source list, rules, and export settings,
      matching the shape given in the brief plus the named addresses.
- [ ] AC-2: Areas support polygon, city, county, ZIP code, and radius forms, and a named polygon
      keeps its name.
- [ ] AC-14: Every area carries an optional reason: why it is searched, or why it is left out, in
      the person's own words. It survives a load and a save exactly as a name does, and every
      surface that can show an area can show it.

      A name says which shape this is. A reason says why anybody drew it, and only the second one
      settles anything when the decision is questioned later, which is the moment it is always
      wanted and never to hand. Written as a comment it reaches no screen, so the tool can say a
      county is excluded and what the exclusion is called and never why, and somebody asking why a
      whole town has no houses in it has to be sent to a file.

      Offered on areas as well as exclusions, because "why is this town in" is the same question
      asked the other way round. Absent and empty are one state: a reason nobody wrote reads as
      unwritten rather than as a blank that looks like an answer.
- [ ] AC-3: A property qualifies if it falls inside any area and inside no exclude area, or if it
      is at one of the search's named addresses (AC-19, AC-20), whatever the exclusions say. A test
      covers a property inside two overlapping areas, one inside both an area and an exclusion, and
      a named address inside an exclusion.
- [ ] AC-4: Coarse resolution produces a source query that fully contains every area in the
      search, so exact filtering can only remove properties, never need to add them.
- [ ] AC-5: Exact filtering removes every returned property whose location falls outside the
      search's geometry, regardless of which source returned it or what that source filtered.
- [ ] AC-6: A property without usable coordinates is retained and marked as not locatable rather
      than being dropped or assumed to qualify.
- [ ] AC-7: The command line and the browser interface pass identical geometry into the same
      resolution and filtering code. A test asserts identical results from both entry points for one
      definition.
- [ ] AC-8: A definition loaded and re-saved without modification is unchanged, including geometry
      precision and any parts the interface does not itself edit.
- [ ] AC-9: Validation reports every problem it can find in one pass, each naming its location in
      the file, and a definition that fails validation is never run.
- [ ] AC-10: Validation rejects an unknown source name, a malformed or self-intersecting polygon,
      a filter range whose minimum exceeds its maximum, and an area type it does not recognize.
- [ ] AC-11: A local freshness filter expressed in days is evaluated against the tool's own first
      observation, never against a source's freshness field.
- [ ] AC-12: Definitions are plain text files that produce a readable difference when changed, and a
      change made through the interface produces a difference confined to what was changed.
- [ ] AC-13: Resolving a named city, county, or ZIP code to a boundary is delegated to the
      enrichment feature's boundary provider rather than implemented here, so there is one
      implementation and one cache. A test asserts that a repeat run of the same search performs no
      new boundary lookup.
- [ ] AC-15: A definition may carry `addresses`, a list of any number of street addresses. Each
      entry is either a line of text (`202 Marguerite St, Folsom, LA 70437`) or a mapping with
      `address`, an optional `reason` under AC-14's rules, and an optional `at: [latitude,
      longitude]` that places the address when the lookup cannot. A definition needs at least one
      area or one named address, and either alone is enough. The list survives a load and a save
      under AC-8 and changes as a readable difference under AC-12. Named addresses are part of what
      a run observes, so they belong to the search's observation scope (feat-001's AC-32): changing
      the list starts a new comparison series, as changing an area does, while a search that names
      none keeps the scope it had before.
- [ ] AC-16: Each named address without an `at` is placed by the boundary provider this feature
      already delegates to (AC-13), through one more question on the same port: where is this
      street address. The answer is cached, so a repeat run performs no new lookup for an address
      already placed; an `at` pair is used as written and nothing is looked up for it. Placing
      happens once per run, before any source is asked, and never inside the filtering loop.
- [ ] AC-17: Validation checks the list's shape and fetches nothing (AC-9 unchanged). It reports,
      each at its location in the file: an entry that is neither text nor a mapping carrying
      `address`; an empty address; an address longer than 200 characters; an `at` that is not two
      numbers, is out of range, or has latitude and longitude swapped (the check a radius centre
      already gets). It gives a notice, which never stops a run, for the same address named twice
      (then looked for once), and for a list of more than 50, saying how many queries per run they
      add.
- [ ] AC-18: For each source in the search, every placed address is asked for with a coarse query
      that contains a circle of half a mile around its point, in whatever form that source accepts
      (AC-4's resolution, unchanged). None of the search's filters are sent with it. A source that
      takes a listing status is asked once each for sale, pending and contingent, whatever the
      search's own listing types are, so a named house that goes under contract is still seen; a
      source that takes no status is asked once without one, and its report says so. A status a
      source rejects degrades that source's contribution as any failed query does. Addresses whose
      circles overlap may share one query. A source is unavailable for the search only when it can
      express neither an area nor a named address.
- [ ] AC-19: Of the rows an address's query returns, the only ones kept for it are those whose
      address matches the named one under the address matcher's normalized key (feat-006: house
      number, street name, unit and ZIP code), so `Hwy 43 Hwy` and `Highway 43` are one address.
      Two exceptions, both taken from the address matcher's own rules: a unit or lot that only one
      side carries does not separate them (feat-006's AC-24), while two different units do; and
      when the person left the ZIP code out, the one the lookup answered with is used, or with no
      lookup (an `at` was given) the ZIP is left out of the comparison. Every other row that query
      returned is discarded unrecorded, as a row outside a drawn area is (AC-5).
- [ ] AC-20: A property kept under AC-19 is in the run whatever the search's filters and exclude
      areas say, including the freshness filter of AC-11. The search's criteria judge it exactly as
      they judge every other property, and a criterion that drops it sets it aside with its reason,
      where a person can see it. A property that is both at a named address and inside an area is
      one property, recorded once.
- [ ] AC-21: Every run reports each named address: whether it could be placed and the address the
      lookup matched (so a placement in the wrong town is visible), and which sources found it and
      which did not. A named address no source lists is reported as not found. That is an ordinary
      answer: it never fails the run and is never silent. An address that could not be placed (the
      lookup had no match, or could not be reached) is reported as not looked for, with `at` named
      as the way to place it by hand, and the rest of the search runs.
- [ ] AC-22: The browser interface's search editor shows a search's named addresses with their
      reasons, and can add them (one, or many pasted one per line) and remove them, writing through
      the same edit operation `homescout searches edit --set addresses=[...]` uses (AC-7, AC-8).
      Before an address is added, the editor says it will be sent once to the Census geocoder to be
      placed. The run status on screen carries the per-address report of AC-21. (Shared with
      feat-010, as AC-14 was.)

## Edge cases & errors

- A polygon crosses a county or state line, so no single coarse source query contains it. It is
  resolved as several coarse queries whose union contains the polygon.
- A named place is ambiguous, such as a city name occurring in several states. Validation reports
  the ambiguity and the candidates rather than picking one.
- A named place cannot be resolved at all. Validation fails naming the place; the run does not
  proceed with that area silently omitted.
- An exclude area covers the entire area. The search is valid and matches nothing, and reports that
  it matched nothing for that reason.
- A polygon is drawn with a very large number of vertices. It is accepted, and exact filtering
  remains within the run's performance budget.
- A radius is given in miles around a point that cannot be resolved. Reported as a validation
  failure on that area.
- Two areas overlap heavily, so sources return the same property from both coarse queries. It
  appears once.
- The lookup cannot place a named address: new construction, a rural route, a misspelling. The run
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
- Two sources spell a named house differently, or give it different coordinates. Each row is kept by
  address under AC-19, and whether they become one property is the address matcher's decision, as
  for any two rows.

## Non-functional requirements

- Performance: exact filtering of 5,000 properties against a search's geometry completes in under
  two seconds, including polygons with many vertices.
- Security: geometry and place names are data. Nothing in a definition is executed, and the rules
  section is evaluated only through the restricted parser owned by the rule engine.
- Reliability: a boundary lookup that fails leaves the affected area unresolved and reported, and
  does not corrupt the definition or the run record.
- Accessibility: none directly. The map surface belongs to the browser interface.
- Politeness: a named address costs at most one query per source per listing status per run, and
  addresses whose circles overlap share one. Placing costs one lookup per address per cache
  lifetime.
- Privacy: a named address leaves the machine once per cache lifetime, as text, to the Census
  geocoder, and nowhere else. The listing sites are sent the circle around it, never the address.

## Open questions

None.
