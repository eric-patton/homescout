# Plan — Saved searches and geography (feat-004)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

Five facts read out of the built code, because each one changes the design rather than confirming
it.

- **M-1: the run loop asks for coarse queries once, without saying which source is asking.**
  `runner.py:226` calls `definition.queries()` and sends the same queries to every source. But
  Realtor accepts named places and a radius and nothing else (`sources/realtor/__init__.py:93`),
  while Zillow (feat-005) will accept a bounding box and no named place at all. One
  source-independent coarse form cannot be correct for both, and the difference is not cosmetic: it
  decides whether an area can be searched at all.
- **M-2: the exact local test is a yes or no.** `search.py:74` declares `keeps(fields) -> bool`. A
  property a test cannot place has no third answer available, so today it can only be kept as if it
  qualified or dropped as if it did not. AC-6 requires neither.
- **M-3: Realtor's radius search already takes a coordinate pair and a distance.**
  `sources/realtor/__init__.py:238` builds `coordinates: [lon, lat]` and `radius: "Nmi"`. The only
  reason an address string is involved is the geocoding step that produces those coordinates. A
  radius around a known point needs no geocoder.
- **M-4: the command line's saved-search commands already exist and already call the catalog seam**
  (`cli/main.py:250`). This feature plugs a file-backed catalog in behind them. It adds no commands,
  and the two-surface rule is satisfied by the facade that is already there.
- **M-5: nothing in the store carries a per-listing flag.** Snapshots carry the fields a source
  reported, and empty latitude and longitude are already recorded honestly. So "marked as not
  locatable" has to be something the run reports, not a new column.

## Design decisions

### D-1: layout, and `search.py` becomes a package

`src/homescout/search.py` becomes `src/homescout/search/`, keeping every existing import path
(`from .search import SearchDefinition` and friends keep working, so feat-003 needs no import
edits).

| file | holds |
|---|---|
| `search/__init__.py` | the contract: the protocols, the problems, the errors, the catalog registry. What is there today, plus D-5 and D-6. |
| `search/geometry.py` | everything that touches shapely: GeoJSON in, prepared geometry out, validity, containment, and the smallest circle and box that cover a shape. |
| `search/areas.py` | the area vocabulary this feature reads from a file, each one able to say its coarse form for a given source and whether a property is inside it. |
| `search/document.py` | the YAML document: load, save, edit one key, and say where in the file any node is. |
| `search/validate.py` | every validation rule, in one pass. |
| `search/definition.py` | `FileSearch` and `FileCatalog`: one saved search and the directory of them. |
| `search/boundaries.py` | the boundary provider port, and the honest no-op default. |

The reason for a package rather than one more module beside `search.py` is that half of what a
saved search is already lives in `search.py` as a contract. Splitting the contract from its
implementation across two differently named top-level modules would leave nobody able to guess
which one to open.

### D-2: two dependencies, `shapely` and `ruamel.yaml`

`shapely` is the constitution's mandated choice for geospatial work, and it brings validity
checking (a self-intersecting ring, AC-10), prepared geometries (the performance budget), and
multipolygons for free.

`ruamel.yaml` in round-trip mode, rather than `PyYAML`. This is not a preference. AC-8 and the
round-trip scenario require comments, key ordering, and number formatting to survive a load and a
save, and `PyYAML` discards all three by construction: it parses to plain dicts and re-emits from
scratch. `ruamel.yaml` also carries line and column information on every node, which is exactly
what AC-9 needs to name where a problem is. One library answers two hard requirements.

### D-3: one file per search, at `<workspace>/searches/<name>.yaml`

The workspace root is the database's directory, which is what `default_catalog` is already handed.
One file per search rather than one file of all searches: a readable difference confined to what
changed (AC-12) is much easier to guarantee when an edit to one search cannot move a line in
another, and a person editing by hand opens the search they mean.

The `name:` inside the file is authoritative. A file whose name does not match its `name:` key is a
validation problem, not a silent rename, because the run command takes the name and the person
reading a directory listing takes the file name, and those two disagreeing is a trap.

### D-4: the file shape is the brief's, with two additions

Section 6 of the brief, exactly: `name`, `description`, `areas`, `exclude_areas`, `filters`,
`sources`, `rules`, `export`. Two additions, each because the brief's shape alone cannot answer a
question this feature has to answer:

1. **`radius.center` may be a coordinate pair as well as a place name.** The brief shows
   `center: "Portales, NM"`, which needs a geocoder before the exact local test can run. Accepting
   `center: [34.18, -103.35]` lets a radius be tested exactly with nothing external, and it is the
   form the map surface will write when someone drops a pin. A named center still works; see D-9
   for what happens before it can be resolved.
2. **`geometry` accepts a GeoJSON geometry object or a GeoJSON Feature.** Leaflet.draw hands out
   either one depending on how it is called, and refusing one of them would make the round trip
   depend on which code path drew the shape.

`rules` and `export` are carried through untouched and validated only for shape (a list, and a
mapping with a string template). Their contents belong to the rule engine (feat-008) and the
spreadsheet export (feat-011).

Filter names map onto the query the source layer already understands: `price`, `beds`, `baths`,
`sqft`, `year_built` to their `_min` and `_max` pairs, `property_type` to `property_types`,
`lot_acres` to `lot_sqft` (one acre is 43,560 square feet, converted on the way in so the file
speaks acres and the source speaks feet), `listing_type` per D-12, and `listed_within_days` per
D-11.

### D-5: the run loop asks each source for its own coarse queries

`SearchDefinition.queries()` is replaced by two members:

```python
areas: tuple[SearchArea, ...]                                 # what the search covers
def queries_for(self, capabilities: Capabilities) -> tuple[SearchQuery, ...]: ...
```

`areas` is the source-independent answer to "what does this search cover", which is what the
display layer counts (`cli/main.py:190` and `cli/render.py:120` change from `len(search.queries())`
to `len(search.areas)`, and nothing else about them changes). `queries_for` is the coarse
resolution itself, and it takes the asking source's capability declaration because that declaration
is already the one place a source says what geography it accepts (M-1).

`SearchArea` is this feature's own type (D-12a), not the source layer's `Area`. The source layer's
polygon is a bare list of points, so exposing that one would drop the name AC-2 requires a named
polygon to keep. A source-layer area is what `queries_for` produces, on the way out.

A source for which an area yields no expressible coarse form contributes no query for that area. If
that leaves the source with no queries at all, the run records it as `unavailable` naming the areas
it cannot express, which is the outcome the source layer already produces for the same situation
one level down. A definition with no areas at all is still invalid input, refused before the run
starts, exactly as today.

Two methods rather than keeping `queries()` alongside a new one: two coarse resolutions that can
disagree is a defect waiting for the first source that behaves differently from the others, which
is every source after the first.

### D-6: the exact test answers three ways, and the run loop reports the third

`keeps(fields) -> bool` is replaced by:

```python
class Placement(StrEnum):
    inside = "inside"
    outside = "outside"
    unlocatable = "unlocatable"

def place(self, fields: ListingFields) -> Placement: ...
```

The run loop keeps `inside` and `unlocatable`, drops `outside`, and counts the `unlocatable` rows
into the per-source report it already builds (`SourceReport` gains `not_locatable: int`, which
flows into the run digest's per-source block unchanged in shape). That count is the "marked" half
of AC-6: the property is recorded like any other, its coordinates are empty because they were never
reported, and the run says out loud how many properties it could not place rather than letting them
vanish into a matched count.

This is the smallest change that satisfies AC-6, because M-2 and M-5 between them leave no other
place for the answer to live. A boolean seam forces a lie in one direction or the other, and the
store has no flag column to write.

### D-7: coarse resolution, area by area

The rule that must hold is AC-4: whatever is sent fully contains the area, so exact filtering only
ever removes properties and never needs to add one.

| area in the file | coarse form sent | contains the area because |
|---|---|---|
| city, county, zip, state | itself | it is the same place |
| radius with a named centre | `AddressRadius(name, miles)` | it is the same circle |
| radius with a coordinate centre | `PointRadius(lat, lon, miles)` (D-8) | it is the same circle |
| polygon, source takes a box | the polygon's bounding box | a box around a shape contains it |
| polygon, source takes a radius | `PointRadius` at the centroid, reaching the farthest vertex plus a margin | a circle through the farthest vertex contains every vertex, and the margin covers the difference between the flat distance used to compute it and the great-circle distance the site measures |
| polygon, boundary provider registered | the named places the provider says the polygon touches, one query each | the union of the places containing it contains it |
| polygon, source takes neither and no provider | nothing, and the source reports it cannot cover this area | saying so beats searching somewhere else |

The circle is the load-bearing choice, because it is what makes a drawn polygon work today with
nothing external registered. It costs requests: a circle around a long thin shape can cover several
times the shape's area, and everything extra comes back and is filtered locally. That is the right
trade for a rate-limited nightly run over a county, and it degrades to the cheaper named-place path
by itself the moment enrichment (feat-007) registers a provider.

The alternative considered and rejected: let the file name the containing place by hand
(`{type: polygon, within: "Roosevelt County, NM"}`). It is cheaper to run and impossible to check.
Nothing available offline can verify that the named place actually contains the polygon, and a
`within` that does not contain it silently loses listings that were never asked for. A containment
claim this tool cannot verify is exactly the class of failure the project treats as unacceptable,
so the file does not get to make one.

### D-8: `PointRadius` is added to the source layer (feat-002)

A new area type, `PointRadius(latitude, longitude, miles)`, added to `sources/base.py` beside the
existing ones, and accepted by the Realtor adapter. The adapter change is small and mechanical
(M-3): a `PointRadius` resolves to a `Place` directly, with no geocoding request, because the
coordinates are the thing the geocoding step exists to produce. Existing behavior for
`AddressRadius` is untouched.

This is an addition to a finished feature, recorded in feat-002's manifest under "Later changes by
other features" with the reason and the tests. It does not contradict anything feat-002 specified:
its area vocabulary is explicitly the set of forms a source can be asked for, and this adds one.

### D-9: containment, area by area, and what an unresolved place means

Every area answers `inside`, `outside`, or `unknown` for one property, and the definition combines
them:

```
if any exclude area says inside            -> outside      (positive evidence wins)
elif any area says inside                  -> inside
elif any area or exclude area says unknown -> unlocatable
else                                       -> outside
```

An exclusion that cannot be evaluated never excludes, for the same reason a filter never drops a
row whose field is absent (feat-003's AC-28): a test that could not be run is not a failed test.

Per area:

- **Polygon**: shapely, against the property's coordinates. `unknown` when the property has no
  coordinates.
- **Radius with a coordinate centre**: great-circle distance. `unknown` when the property has no
  coordinates.
- **Radius with a named centre**: the centre through the boundary provider when one is registered.
  With no provider, it is *delegated*: the circle went to the source verbatim, the source applied it,
  and nothing here can measure from a name, so this area declines to remove anything and validation
  says so as a notice. Answering `unknown` instead was the plan, and it is wrong in the commonest
  case there is: a search whose only area is a radius around a town would report every property in
  it as not locatable, which would drown the count that exists to make a genuinely unplaceable
  property visible. Never guessed from the property's own city.
- **City, county, zip, state**: the provider's boundary when one is registered and the property has
  coordinates. Otherwise the property's own place fields, compared case-insensitively and with the
  state qualifier honored (`city == "Portales"` and `state == "NM"`). Otherwise `unknown`.

The textual fallback is what makes named areas work with no provider registered, and it is honest
about what it is: a source that says a house is in Portales is evidence that it is in Portales. It
is never used to contradict coordinates, only when there are none to test.

### D-10: the boundary provider is a port, with a default that admits it cannot help

`search/boundaries.py` holds the same registry shape this codebase already uses twice (the source
registry, the catalog registry):

```python
class BoundaryProvider(Protocol):
    def boundary(self, area: Area) -> object | None: ...
    def locate(self, place: str) -> tuple[float, float] | None: ...

def register_boundaries(provider): ...
def unregister_boundaries(): ...
def boundaries() -> BoundaryProvider | None: ...
```

Nothing is registered until enrichment (feat-007) arrives, and until then every call returns
`None`, which the containment rules above already read as `unknown` rather than as `outside`. This
is AC-13's delegation: one implementation, one cache, and neither of them here.

Each distinct area is resolved through the provider at most once per loaded definition, memoized on
the definition. Across separate invocations the provider's own cache answers, which is the
enrichment feature's declared job. The test for AC-13 registers a counting provider and asserts two
runs of one search cause one lookup per area.

### D-11: the freshness filter never reaches a source, and never drops a row

`listed_within_days` is carried, validated, and exposed as `definition.freshness_days`, together
with a pure predicate that reads a property's own first observation. It is not mapped onto
`SearchQuery.listed_since`, and it takes no part in the exact local test.

Both halves matter, and both are the same defect one step apart. If it were pushed to a source, the
source would stop returning properties older than the window, and the store, which reads absence
across a whole search as a possible disappearance, would have no way to tell a filtered-out house
from a sold one. If it were applied locally during a run, the row would be dropped before it was
recorded and the store would read the same absence. Either one destroys history to save a person
some scrolling. The tool's own "new" is already computed from first observation (product invariant
7), so freshness is a question asked when results are read, by the browser interface (feat-010) and
the export (feat-011), against history this feature never truncates.

This is the same shape as the defect feat-003 found in its own status filter, one field over, which
is why it is decided here in writing rather than discovered later.

### D-12: several listing types fan out into several coarse queries

`listing_type: [for_sale, pending]` becomes one coarse query per status per area, because
`listing_status` is pushed to the source and is never applied locally (feat-003's AC-32), and the
source's field takes one status. The overlap rule already in the run loop drops a property returned
by two of one search's queries (feat-003's AC-29), so the fan-out costs requests and cannot produce
a duplicate. A single status stays a single query.

### D-12a: this feature's own area type

`search/areas.py` defines `SearchArea`, which is what a definition exposes and what the geometry
works against:

```python
@dataclass(frozen=True, slots=True)
class SearchArea:
    kind: Literal["polygon", "city", "county", "zip", "state", "radius"]
    name: str | None                 # a drawn shape's own name, kept (AC-2)
    value: str | None                # a named place, as written in the file
    geometry: object | None          # prepared shapely geometry, for a polygon
    centre: tuple[float, float] | None
    miles: float | None
    excluded: bool = False

    def coarse_for(self, capabilities) -> tuple[Area, ...]: ...
    def holds(self, fields) -> Verdict: ...      # inside | outside | unknown
```

One type with a `kind` rather than six classes, because every area answers the same two questions
and the file's own `type:` key is the discriminator a person reads. The name survives a load, a
save, and a run, which is what AC-2 asks for and what makes an exclusion legible on a map later.

### D-13: validation is one pass, everything located, nothing fetched

`validate.py` collects problems rather than raising at the first one (AC-9), and each carries a
location built from the document's own line and column information, formatted
`searches/nm.yaml:14:7 areas[0].geometry`. The rules:

- the file parses as YAML, and is a mapping
- `name` present, a string, and matching the file name
- unknown top-level keys reported (a typo in a key is otherwise silent)
- `areas` present and non-empty; every area has a recognized `type` (AC-10)
- every polygon parses as GeoJSON, is a Polygon or MultiPolygon, has at least four positions in
  each ring, and is valid geometry with no self-intersection (AC-10, via shapely)
- coordinates are plausible: latitude within 90, longitude within 180, and in the GeoJSON order
  (longitude first), which catches the single most common hand-editing mistake
- a city or county with no state qualifier is reported as ambiguous (D-17)
- a zip is five digits; a radius has a positive `miles` and a centre
- every filter range has `min <= max` (AC-10)
- `property_type` and `listing_type` values are known, non-empty strings
- `sources` is non-empty and every name is registered (AC-10)
- `rules` is a list; `export.template` is a string
- the document carries no YAML tag asking for an object to be constructed (D-19)

Nothing in validation contacts a source or a provider, which the test asserts with a source whose
every method raises (AC-9).

### D-14: a save rewrites only what changed

`catalog.edit(name, changes)` loads the document in round-trip mode, assigns into the parsed tree,
and dumps it. `ruamel.yaml` preserves comments, key order, quoting style, and scalar formatting for
every node it was not asked to change, which is what makes AC-8 (an untouched load and save is
byte-identical) and AC-12 (a one-filter edit produces a one-line difference) true by construction
rather than by care. The round-trip test asserts byte equality, and the edit test asserts the
unified difference touches only the intended lines.

A definition created by `searches create` is written from a template carrying the brief's shape with
comments, so a person's first encounter with the format is a file that explains itself.

### D-15: prepared geometry, prepared once

Every polygon in a definition is converted to shapely and prepared (`shapely.prepared.prep`) when
the definition is loaded, not per property. Preparation builds the index that makes containment
cheap against a many-vertex ring, and doing it per row would make the many-vertex case quadratic in
the worst way. The performance test (5,000 properties, a polygon with several thousand vertices,
under two seconds) is marked slow and excluded from the default run.

### D-16: the file catalog becomes the default

`default_catalog(root)` returns `FileCatalog(root / "searches")` when nothing is registered, rather
than today's empty in-memory catalog. Tests that want an in-memory catalog register one explicitly,
which they already do. This is what makes `homescout run <name>` work on a fresh machine with a
file in a directory and nothing else.

A missing `searches/` directory is not an error: it means no saved searches, which `searches list`
reports as none and `run` reports as an unknown name with the empty list of known ones.

The catalog holds each definition it has loaded for as long as that file's modification time and
size are unchanged. Reading a file is cheap; what a loaded definition holds is not, being a prepared
geometry and whatever a boundary provider was asked. This is also what makes AC-13 true in the sense
it is written: two runs of one search in one invocation look a place up once, rather than once per
load.

### D-17: what validation can honestly say about a place it cannot resolve

Two of the spec's edge cases turn on resolving names, which this feature deliberately does not do
(D-10).

- **Ambiguous** ("Las Cruces" with no state): reported as a validation problem naming the ambiguity
  and what would settle it. When a provider is registered, the problem lists the candidates it
  returned. Without one, it says a state qualifier is required. Neither picks a place.
- **Unresolvable** (a place no provider and no source recognizes): validation cannot know this
  offline. It surfaces at run time as the source reporting `unavailable` for that area with the
  place named, which degrades the run's exit code and appears in the per-source report. The area is
  never silently omitted, which is the part the spec's edge case actually protects.

### D-19: a definition is data, and a name is not a path

The security requirement in the spec is one sentence ("geometry and place names are data. Nothing in
a definition is executed"), and satisfying it takes two deliberate decisions rather than none.

**The document is parsed, never constructed.** `ruamel.yaml` is used in round-trip mode, which
refuses tags it does not know rather than instantiating anything. A definition containing
`!!python/object/apply:...` is a validation problem naming the tag and its line, not an import and a
call. The plan states this because the difference between a safe loader and an unsafe one in every
YAML library is one keyword, and "we used the obvious default" is not a control anybody can check.
There is a test with a tagged document, and it asserts a problem rather than an effect.

**A search name is not a file path.** The name arrives from the command line and, later, from a
browser form, and the catalog turns it into a file name. Unconstrained, `run ../../something` reads
outside the searches directory and `searches create` writes outside it. So a name must be letters,
digits, dashes and underscores, at most sixty-four characters, and the resolved path must still be
inside the searches directory after resolution, which also closes the symbolic-link route. Anything
else is invalid input, refused before the file system is touched. Tested from the command line with
a traversing name for both reading and creating.

### D-20: a notice is not a problem

`SearchProblem` gains `severity: Literal["problem", "notice"]`, defaulting to `problem`. A
definition is invalid, and is refused, only when it carries at least one `problem`
(`api.run_search` and the `validate` command both change from "any" to "any problem"). Notices are
reported in the same list, with the same location, and stop nothing.

This is what the spec's wholly excluded search needs: an exclusion covering every area is valid, it
matches nothing, and it has to say why it matched nothing rather than looking like a market that
emptied out. It is computed when the shapes can be compared (both sides resolvable to geometry) and
skipped when they cannot, because an unresolved area is not evidence of anything. An area that no configured source can express is
reported by the run instead of by validation, as that source being `unavailable` with the areas
named: validation may not build a source, and what a source accepts is a property of the source
rather than of the file.

Severity, rather than a second list, because the command line already renders problems with their
locations and the browser will read the same structure. One list with a severity is a smaller change
than a second list everywhere.

### D-18: what this feature does not own

Rules (feat-008) and export templates (feat-011) are carried and shape-checked, never interpreted.
Boundary data and its cache (feat-007) sit behind the port. The map (feat-010) is a second writer of
the same file through the same catalog. Fetching (feat-002, feat-005) is asked for coarse queries
and answers with rows.

## Verification approach

Test files, all under `tests/` per `spec/.spec-flow.md`:

- `tests/searches_fakes.py` — a builder for definition files, a counting boundary provider, a source
  that raises if contacted.
- `tests/test_searches_document.py` — the file: load, save, round trip, edit, create.
- `tests/test_searches_validation.py` — every rule, and that nothing is fetched.
- `tests/test_searches_geometry.py` — coarse forms, containment, unions, exclusions, unlocatable.
- `tests/test_searches_run.py` — through the run loop and the command line.
- `tests/test_searches_performance.py` — the two-second budget, marked slow.

| criterion | seam the test enters through | trace token |
|---|---|---|
| AC-1 the file shape | `FileCatalog.load` and `homescout searches show --json` | `feat-004/AC-1` |
| AC-2 area forms, a named polygon keeps its name | `FileCatalog.load` then `definition.areas` | `feat-004/AC-2` |
| AC-3 inside any area, inside no exclusion | `definition.place(fields)` | `feat-004/AC-3` |
| AC-4 coarse contains the area | `definition.queries_for(capabilities)`, asserting every vertex of the area is inside the coarse form for each source capability shape | `feat-004/AC-4` |
| AC-5 exact filtering removes what a source returned | `api.run_search` with a fake source returning rows outside the polygon | `feat-004/AC-5` |
| AC-6 no coordinates is retained and marked | `api.run_search`, asserting the row is recorded and the per-source report counts it | `feat-004/AC-6` |
| AC-7 both surfaces, identical geometry | the command line and `api.run_search` directly, asserting identical coarse queries and identical kept sets for one definition file | `feat-004/AC-7` |
| security NFR, a document is data | `api.validate_search` against a file carrying a constructor tag, and the command line against a traversing name for both reading and creating (D-19) | `feat-004/NFR-security` |
| the wholly excluded search, and an area no source can express | `api.validate_search`, asserting a notice and a valid definition (D-20) | `feat-004/AC-9` |
| AC-8 lossless round trip | `FileCatalog.load` then save, asserting byte equality including comments and geometry precision | `feat-004/AC-8` |
| AC-9 every problem, one pass, nothing fetched | `api.validate_search` with a source that raises when touched | `feat-004/AC-9` |
| AC-10 the four named rejections | `api.validate_search` | `feat-004/AC-10` |
| AC-11 freshness is local | `definition.queries_for` (asserting `listed_since` is never set), `api.run_search` (asserting no row is dropped for it), and the predicate against first observation | `feat-004/AC-11` |
| AC-12 readable differences | `catalog.edit`, asserting the unified difference is confined to the changed lines | `feat-004/AC-12` |
| AC-13 boundaries are delegated and looked up once | `api.run_search` twice with a counting provider registered | `feat-004/AC-13` |
| performance NFR | `definition.place` over 5,000 properties against a many-vertex polygon | `feat-004/NFR-performance` |

Every test names the criterion in its docstring, the way feat-003's do, so the linter reads coverage
from the token.

Two notes on what these tests can and cannot reach:

- **AC-7 names the browser interface, which does not exist yet** (feat-010). Its test uses the
  facade in `api.py` that the browser will call, which is the same seam feat-003's own two-surface
  test uses. That is the strongest available check today, and it is not the whole criterion: feat-010
  inherits the obligation to enter through the same facade, and its own tests re-assert this one with
  a real second surface.
- **`lot_acres` converts to square feet at 43,560 to the acre, rounded to the nearest whole foot**,
  so a minimum of one acre is 43,560 and not 43,559. A test pins the boundary, because a rounding
  slip here silently changes which properties qualify.
- **The polygon that crosses a county line** (a spec edge case) is satisfied without a provider by
  the covering circle, which is a single coarse query containing the whole shape. With a provider
  registered it becomes the several queries the edge case describes. Both are tested against the
  containment rule in AC-4 rather than against the number of queries, because the number is not
  what matters.

The regression surface is feat-003's suite, which must stay green through D-5 and D-6 unchanged
except for the fakes that implement the seam. That is the real check on whether the seam change is
as small as it claims to be.
