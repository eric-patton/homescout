# Plan — Location enrichment providers (feat-007)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

The spec says the brief's list of endpoints is a starting point rather than a contract, and that they
must be verified at implementation time. So they were, before anything was designed, because what
they return decides what the code looks like. Measured on 2026-08-23 from a point in Portales, New
Mexico, and a point in New Orleans:

| value | endpoint that answers today | what comes back |
|---|---|---|
| flood zone | `hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query` | `FLD_ZONE` and `ZONE_SUBTY` on the intersecting feature, or no features |
| elevation | `epqs.nationalmap.gov/v1/json` | a number, in the units asked for |
| principal aquifer | `arcgis.water.nv.gov/arcgis/rest/services/BaseLayers/USGS_Aquifers_Principal/MapServer/0/query` | the intersecting aquifer's `AQ_NAME` and `ROCK_TYPE`, or no features |
| wildfire hazard | `imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer/identify` | a pixel value, 1 to 5, plus non-burnable classes |
| boundaries | `tigerweb.geo.census.gov` for shapes, `geocoding.geo.census.gov` for what contains a point | named places, with or without geometry |
| broadband | nothing keyless. See M-4 | — |

Four things came out of that hour, and each one changes the design:

- **M-1: the brief's FEMA address is gone.** `hazards.fema.gov/gis/nfhl/rest/...` is a 404; the
  service now lives under `/arcgis/rest/...`, and the flood zones are layer 28 of a service with
  thirty of them. This is exactly why AC-14 asks for endpoints to be configuration: this one moved
  between the brief being written and this feature being built, and it will move again.
- **M-2: the USFS wildfire server refuses this tool.** Every path under `apps.fs.usda.gov` answers
  403, including its own folder listing, whatever user agent is offered. The same data is published
  on `imagery.geoplatform.gov`, which answers plainly. Found by asking the ArcGIS Online catalogue
  where the layer is, rather than by guessing paths, which is the technique to use again when one of
  these moves.
- **M-3: no federal keyless endpoint for principal aquifers could be found.** The Esri copy needs a
  token. The one that answers is the *national* USGS layer hosted by Nevada's water agency. National
  data, national coverage, state-run mirror, and treated as a configured endpoint like the rest.
- **M-4: the broadband map now requires an API token.** The current FCC National Broadband Map data
  API is keyed; the old keyless one covered mobile only and is gone. That collides with this
  feature's own security requirement, and D-9 is what to do about it.

## Design decisions

### D-1: layout

A new package, `src/homescout/enrich/`, above the store and beside the rules.

| file | holds |
|---|---|
| `enrich/provider.py` | what a provider is: the values it supplies, its precision, its time to live, and how it asks. |
| `enrich/settings.py` | every endpoint, as configuration with a default and an environment override. |
| `enrich/cache.py` | reading and writing cached values, and telling fresh from stale from missing. |
| `enrich/pass_.py` | the pass: which locations, which providers, what happened. |
| `enrich/providers/flood.py`, `elevation.py`, `aquifer.py`, `wildfire.py`, `boundaries.py`, `broadband.py` | one per provider, each a plugin. |
| `enrich/registry.py` | the registered providers, in the same shape the source registry already has. |

### D-2: the cache is a cache, and says so

Schema version 3, one table:

```sql
CREATE TABLE enrichment_values (
    provider   TEXT NOT NULL,
    cache_key  TEXT NOT NULL,      -- the rounded location, at this provider's precision
    name       TEXT NOT NULL,      -- the value's name in the rule engine's namespace
    value      TEXT,               -- JSON, so a number stays a number and absent stays absent
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (provider, cache_key, name)
);
```

**Not append-only, and that is the one deliberate exception in this database.** Every other table
here records what this tool observed, and an observation is never rewritten. This one records a copy
of somebody else's fact about a place, and refreshing a copy is what a cache is for.

Checked rather than assumed: the constitution's first non-negotiable is about what a run observed of
a listing, and product invariant 1 names snapshot and raw-listing history. A cached copy of a federal
map is neither, so neither rule reaches this table. The rule that does is narrower and is in AC-4: a
failure never removes a cached value. A refresh replaces; a failure leaves it alone and it reads as
stale.

One row per value rather than a blob per provider, so a provider that starts supplying one more
value does not invalidate what is already cached, and so "fresh, stale, missing" is answerable per
value (AC-7) rather than per provider.

### D-3: the cache key is the rounded location, and the rounding is the provider's business

`f"{latitude:.{precision}f},{longitude:.{precision}f}"`, with `precision` declared by the provider.
Two properties whose coordinates round to the same key share one lookup (AC-3), which is most of the
saving on a street of houses.

Precision is per provider because the spec's edge case is real: rounding can put a property on the
wrong side of a hazard boundary. Elevation over a quarter mile is the same answer, so four decimal
places is waste; a flood zone boundary can run down the middle of a street, so flood uses four (about
eleven metres) and elevation three (about a hundred).

| provider | decimals | about |
|---|---|---|
| flood | 4 | 11 m |
| aquifer | 2 | 1.1 km |
| wildfire | 3 | 110 m |
| elevation | 3 | 110 m |
| boundaries | 3 | 110 m |

### D-4: a provider is a plugin, and the pass never names one

```python
class Provider(Protocol):
    name: str
    def values(self) -> tuple[str, ...]: ...        # names in the rule engine's namespace
    def precision(self) -> int: ...
    def ttl_days(self) -> int | None: ...           # None means it never goes stale
    def configured(self) -> bool: ...               # False when it needs something nobody supplied
    def fetch(self, session, latitude, longitude) -> Mapping[str, object]: ...
```

`fetch` returns a mapping from value name to value, and a value that is genuinely absent for that
location is `None` in the mapping rather than missing from it. That is the spec's first edge case,
and it is the distinction the whole feature turns on: a point outside every mapped flood zone has a
*known* answer, and a point nobody asked about has none.

`values()` is checked against the rule engine's namespace at import, so a provider cannot supply a
value no criterion could ever name, and the enriched names the rule engine declares cannot silently
have nobody filling them.

### D-5: pacing is the one the sources already use

`sources.politeness.PacedSession`, keyed by provider name rather than source name. It already does
per-key rate limiting, backoff with jitter, an honest user agent and a configurable delay, which is
what AC-13 asks for in the same spirit as listing sources. A second implementation of politeness
would be a second place to get it wrong.

Government endpoints are not listing sites and do not need three seconds between requests, so the
default delay for a provider is shorter than a source's. It is still a delay: a backfill over a
county is thousands of points, and these are public services.

### D-6: the pass

`enrich(store, *, providers, stale_only=False, search=None, images=...)` walks the properties in the
store (or those a named search has seen), turns each into one cache key per provider, and asks each
provider once per distinct key. It returns per-provider outcomes in the same shape a run reports
per-source outcomes, because it is the same question.

- A property with no coordinates is skipped with the reason `no location`, distinct from any
  provider failure (AC-10), and costs no request.
- A provider that fails is recorded `failed` with its detail; every other provider is asked normally
  and the pass completes (AC-5). Cached values stay exactly as they were and read as stale (AC-4).
- `stale_only` asks only for values that are stale or missing (AC-8).
- Nothing here raises into a listing run: enrichment is its own pass, invoked separately (AC-6,
  AC-9), and the command line already has the command reserved.

AC-6 says a provider failure never fails the listing run that requested enrichment, and no listing
run requests it: the run loop asks sources for listings and stops. So the criterion holds
structurally rather than by handling, and its test says exactly that, by asserting a run completes
normally while every provider is broken and that the run made no enrichment call at all. A test that
instead configured a failing provider and watched a run succeed would be testing nothing, because
nothing was connected.

### D-7: reading a value says how old it is

`cache.values_for(store, latitude, longitude)` returns a mapping of name to `Value(value, status)`
where status is `fresh`, `stale`, or `missing`. Missing is not a value: it is the absence of one, and
nothing renders it as a negative answer (AC-7).

Read in bulk, not per property. The performance requirement is five thousand fully cached properties
in under five seconds, and five providers times five thousand properties is twenty-five thousand
lookups: one query each would spend the whole budget on round trips to a local file. A pass reads
every cached value for the keys it is about to need in one query per provider and works from that.

A criterion sees the value and not its age, deliberately. These facts change on the scale of decades,
so a rule about a flood zone does not mean something different because the copy is thirteen months
old, and threading staleness into the three-valued logic would add a fourth state to a system whose
whole argument is that three is already one more than people expect. Staleness is visible where
values are read and where the pass reports.

The rule engine's per-property values gain these names, so a criterion naming `flood_zone` finds one.
A missing value stays absent from that mapping, which the evaluator already reads as unknown, which
is already the answer the rule engine's own criteria demand. A stale value is used: out of date is
better than absent for data that changes on the scale of decades, and the staleness is visible where
values are read.

This is a change to the rule engine (feat-008), recorded in its manifest: the enriched names it
declares are now filled by something.

### D-8: the boundary provider the geography feature has been waiting for

Saved searches (feat-004) declared a port for turning a place name into a shape and left it
unregistered, which is on record as an open gap in that feature's ledger. The Census provider
registers it: `boundary(kind, value)` from TIGERweb, `locate(place)` from the Census geocoder, and
`containing(shape)` from the geographies a point falls in.

That closes feat-004's gap-001 in its next audit, and it turns a radius around a place name from
"applied by the source and not re-checkable here" into an exact local test.

### D-9: broadband ships needing a key, and says so plainly

The FCC's current national broadband API is keyed (M-4). This feature's own non-functional
requirement says no credentials, and AC-11 says a broadband provider exists and is individually
enableable. Both cannot be honoured with the same code.

What is built: the provider exists, declares the values it supplies, and reports itself
**not configured** unless `HOMESCOUT_FCC_TOKEN` is present in the environment or the `.env` file.
With no token it makes no request and its values stay missing, so the tool is fully functional
without it, which is product invariant 9. With a token it works.

That is a deliberate departure from this feature's stated security requirement, and it needs a spec
delta rather than a quiet decision. The alternatives were worse: shipping a provider whose default
endpoint returns 403 would be dishonest, and dropping broadband would remove one of the five
questions the whole feature exists to answer. The constitution already anticipates exactly this
shape (secrets read from the environment, never committed, optional components absent by default),
which is why the delta is small.

### D-10: endpoints are configuration, because they move

`settings.py` holds one entry per provider: the address, the timeout, and the fields it reads. Each
is overridable by an environment variable (`HOMESCOUT_ENRICH_FLOOD_URL` and so on). M-1 is the
argument: the brief's FEMA address died between the brief and this feature, and the next one to move
should be a line in a settings file rather than a release.

### D-11: what this feature does not own

Evaluating criteria over these values (feat-008, which declares the names). Extracting values from
prose (feat-009, a different kind of guess). Presenting them (feat-010, feat-011). Crime and school
data, which the export template mentions and which have no free national source, and which are
therefore left blank rather than filled from a source covering part of the country.

## Verification approach

| criterion | seam the test enters through | trace token |
|---|---|---|
| AC-1 a provider is a plugin | `enrich.registry` with a fake provider, asserting the pass names none of them | `feat-007/AC-1` |
| AC-2 a cache hit makes no request | two passes over one location, counting requests on a fake transport | `feat-007/AC-2` |
| AC-3 nearby properties share a lookup | two properties inside one rounding step | `feat-007/AC-3` |
| AC-4 a failure never removes a value | cache, then fail, then read | `feat-007/AC-4` |
| AC-5 one failure does not stop the others | two providers, one broken | `feat-007/AC-5` |
| AC-6 a failure never fails a run | `api.run_search` with every provider broken, asserting the run completes and made no enrichment call | `feat-007/AC-6` |
| AC-7 fresh, stale and missing | `cache.values_for` across the three states | `feat-007/AC-7` |
| AC-8 stale only, and one search | `api.enrich` | `feat-007/AC-8` |
| AC-9 invocable on its own | `homescout enrich --json` | `feat-007/AC-9` |
| AC-10 no coordinates is not a failure | a property with none | `feat-007/AC-10` |
| AC-11 the six providers exist | `enrich.registry.registered()` | `feat-007/AC-11` |
| AC-12 national coverage | a live lookup at three distant states, for every provider that can run, marked slow | `feat-007/AC-12` |
| AC-13 paced per provider | the shared politeness session, asserting the delay is applied per provider | `feat-007/AC-13` |
| AC-14 endpoints are configuration | an environment override, asserting the request goes elsewhere | `feat-007/AC-14` |
| performance NFR | 5,000 fully cached properties, marked slow | `feat-007/NFR-performance` |

Test files: `tests/enrich_fakes.py`, `tests/test_enrich_cache.py`, `tests/test_enrich_pass.py`,
`tests/test_enrich_providers.py`, `tests/test_enrich_live.py` (slow).
