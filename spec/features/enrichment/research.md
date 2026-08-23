# Research — enrichment

## Discovery input

From `homescout-brief.md` section 5.4:

- The questions that actually decide a property are not on the listing. Is it in a flood zone. Can
  it get real internet. Is there water under it. Will it burn. The current workaround is
  hand-researching each of these per property, which is most of the hours the tool exists to save.
- All of it is available free from public services, and the brief names six: FEMA's flood hazard
  layer, the FCC's broadband map, the USGS principal aquifers service, the Forest Service's
  wildfire risk data, USGS elevation, and Census boundary data.
- These values attach to a location, not to a listing, so they are worth caching hard and are
  effectively permanent. A flood zone does not change between Tuesday and Wednesday.
- Public endpoints move, throttle, and go down. The brief requires that one dead endpoint marks
  that one field stale and the run continues, and that endpoints be verified at implementation time
  rather than trusted from the brief.

## Problem brief

### Problem statement

Someone evaluating rural and small-town property struggles to answer the questions that actually
decide it because flood, water, internet, and fire risk are not listing fields and have to be
looked up per property in separate government tools, which results in hours of manual research per
batch and, in practice, in only the shortlist ever being checked. A solution should attach these
values to every property automatically, cache them permanently because they do not change, and
treat any one service being down as one missing field rather than a failed run.

### Target users

- **The person running searches** (primary): wants flood, water, internet, and fire answered for
  every property, not just the ones that survived a first pass.
- **The rule engine** (secondary, as a consumer): needs these values present and needs missing to
  be distinguishable from false.

### Jobs to be done

- Answer the location questions for every property, unattended.
- Never ask a service the same question twice.
- Keep working when a service is down.
- Say plainly when a value is missing or stale rather than implying it is known.

### Success signals

- A second run over the same area makes no enrichment requests at all.
- A service outage costs one column, and the run still completes.
- No property silently shows a comfortable value that was actually never fetched.

### Constraints

- National coverage is required. The product scope is general-purpose, so a provider that only
  covers one state does not qualify.
- Each provider is a plugin declaring its own cache key and time to live.
- Endpoints must be verified at implementation time; the brief's list is a starting point, not a
  contract.
- Enrichment is a separate pass, separately schedulable from a run.

### Explicitly out of scope

- Extracting values from listing prose (feat-009), which is a different kind of guess about a
  different kind of data.
- Evaluating rules over these values (feat-008).
- Crime and school data, which the export template mentions but the brief does not source
  nationally. Left blank rather than sourced badly.

### Open questions

- Whether elevation and boundary lookups are worth a cache time to live at all, given they are
  permanent, or should simply never expire. A plan decision.
