## Why

A search is the thing a person actually tunes: an area, some filters, some criteria, some
providers, refined over weeks and re-run unchanged. The interesting part is the area, because no
provider accepts the shape anyone actually means. This feature owns the definition file and the
two-stage geography that turns "north of this road, but not the east side of town" into a coarse
provider query plus an exact local test. The problem brief is in `research.md`.

## Vocabulary used in this feature

- An **area** is one geographic component of a search: a polygon, a city, a county, a ZIP code, or
  a radius around a point. An **exclude area** is one that subtracts.
- **Coarse resolution** is turning the search's areas into whatever form a provider will accept.
  **Exact filtering** is testing each returned property against the search's real geometry
  afterwards.
- A **definition** is the complete saved search: name, description, areas, exclude areas, filters,
  providers, rules, and export settings.

## User stories

- As the person running searches, I want to draw the area I care about and have properties outside
  it never reach my table, so that a coarse provider query does not become my problem.
- As the person running searches, I want to exclude a part of town as geometry, so that I stop
  re-applying the same exclusion by eye on every pass.
- As the person running searches, I want to edit the definition in a text file and review the
  change like any other change, so that I can see what I altered last week.
- As the person running searches, I want a definition validated before a run starts, so that a typo
  does not cost me an hour of throttled requests.
- As the person running searches, I want the map and the file to be two views of one definition, so
  that using one never destroys what I did in the other.

## Behavior & scenarios

- **Scenario: a coarse query, then an exact test**
  - Given a search whose area is a drawn polygon inside one county
  - When it is run
  - Then providers are queried using a form they accept that fully contains the polygon, and every
    returned property outside the polygon is removed before results are produced

- **Scenario: an exclusion**
  - Given a search with an area covering a town and an exclude area covering its east side
  - When it is run
  - Then properties inside the town and outside the exclusion appear, and properties inside the
    exclusion do not, regardless of which provider returned them

- **Scenario: several areas**
  - Given a search with a city, a ZIP code, and a radius around a point
  - When it is run
  - Then a property inside any one of them qualifies, subject to the exclusions

- **Scenario: a property with no coordinates**
  - Given a search whose areas include a drawn polygon, and a property a provider returned without
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
  - Given a definition with an unknown provider name and a malformed polygon
  - When it is validated or run
  - Then both problems are reported with enough location detail to fix them by hand, and no
    provider is contacted

- **Scenario: the two surfaces agree**
  - Given the same definition
  - When it is run from the command line and from the browser interface
  - Then the identical geometry reaches the identical code path and the results are the same

## Acceptance criteria

- [ ] AC-1: A definition is a hand-editable text file supporting a name, a description, areas,
      exclude areas, filters, a provider list, rules, and export settings, matching the shape given
      in the brief.
- [ ] AC-2: Areas support polygon, city, county, ZIP code, and radius forms, and a named polygon
      keeps its name.
- [ ] AC-3: A property qualifies if it falls inside any area and inside no exclude area. A test
      covers a property inside two overlapping areas and one inside both an area and an exclusion.
- [ ] AC-4: Coarse resolution produces a provider query that fully contains every area in the
      search, so exact filtering can only remove properties, never need to add them.
- [ ] AC-5: Exact filtering removes every returned property whose location falls outside the
      search's geometry, regardless of which provider returned it or what that provider filtered.
- [ ] AC-6: A property without usable coordinates is retained and marked as not locatable rather
      than being dropped or assumed to qualify.
- [ ] AC-7: The command line and the browser interface pass identical geometry into the same
      resolution and filtering code. A test asserts identical results from both entry points for one
      definition.
- [ ] AC-8: A definition loaded and re-saved without modification is unchanged, including geometry
      precision and any parts the interface does not itself edit.
- [ ] AC-9: Validation reports every problem it can find in one pass, each naming its location in
      the file, and a definition that fails validation is never run.
- [ ] AC-10: Validation rejects an unknown provider name, a malformed or self-intersecting polygon,
      a filter range whose minimum exceeds its maximum, and an area type it does not recognize.
- [ ] AC-11: A local freshness filter expressed in days is evaluated against the tool's own first
      observation, never against a provider's freshness field.
- [ ] AC-12: Definitions are plain text files that produce a readable difference when changed, and a
      change made through the interface produces a difference confined to what was changed.
- [ ] AC-13: Resolving a named city, county, or ZIP code to a boundary uses a national source and
      caches the result, so repeat runs of the same search do not re-resolve it.

## Edge cases & errors

- A polygon crosses a county or state line, so no single coarse provider query contains it. It is
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
- Two areas overlap heavily, so providers return the same property from both coarse queries. It
  appears once.

## Non-functional requirements

- Performance: exact filtering of 5,000 properties against a search's geometry completes in under
  two seconds, including polygons with many vertices.
- Security: geometry and place names are data. Nothing in a definition is executed, and the rules
  section is evaluated only through the restricted parser owned by the rule engine.
- Reliability: a boundary lookup that fails leaves the affected area unresolved and reported, and
  does not corrupt the definition or the run record.
- Accessibility: none directly. The map surface belongs to the browser interface.

## Open questions

None.
