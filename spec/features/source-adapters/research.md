# Research — source-adapters

## Discovery input

From `homescout-brief.md` sections 5.1 and 12:

- Every viable free source is reachable only through an unofficial library or a download endpoint.
  None offers a supported API, a contract, or a deprecation notice.
- The three sources differ in almost every dimension that matters: what geography they accept,
  which filters they will apply on their side, how many results they will return, and what they do
  when they dislike a caller.
- Sources break. A source changing its markup or its response shape is the expected case, not the
  exception, and the brief's mitigation is adapter isolation with per-source status in every run.
- Being blocked is the failure that ends the project rather than degrading it, so politeness is
  written into the brief as a requirement and into the constitution as a non-negotiable.

## Problem brief

### Problem statement

Someone assembling one view of a regional market struggles to gather comparable listings from
several unrelated sources because each accepts a different query shape, applies a different
subset of filters on its own side, and enforces a different undocumented ceiling on results, which
results in either source-specific special cases smeared through the whole tool or a
lowest-common-denominator query that drags back far more data than anyone wanted. A solution should
let each source be described once, in one place, in terms of what it can and cannot do, and let
the rest of the tool work against that description, without ever making enough requests to get the
user blocked.

### Target users

- **The person running searches** (primary): wants listings, and wants a source outage to cost
  them that source's rows rather than the run.
- **Whoever adds the fourth source later** (secondary, and realistically the same person): needs
  adding a source to mean writing one adapter, not editing the core.

### Jobs to be done

- Fetch every listing matching a query from one source, respecting whatever ceiling it enforces.
- Declare honestly which parts of a query this source will apply itself, so the rest can be
  applied locally rather than assumed.
- Stay under every source's tolerance without being told to, by default.
- Fail in a way that costs one source's contribution and nothing else.

### Success signals

- Adding a source touches one new file and no existing behavior.
- A run against a source that is down produces that source's rows missing and everything else
  intact, with the failure named in the run record.
- Sustained scheduled use does not result in being blocked.

### Constraints

- Politeness is not tunable downward below a floor: per-source rate limiting, backoff, jitter on
  refusal and throttle responses, an honest user agent, and a configurable delay that defaults
  slow.
- Source result ceilings are facts to be worked around, not ignored: Realtor.com caps at 10,000
  per query.
- Nothing may require MLS or IDX credentials, or a paid data API.

### Explicitly out of scope

- Zillow and Redfin, which are feat-005 and exist precisely to prove this interface holds.
- Deciding whether two sources' rows describe the same house (feat-006).
- Turning a saved search's areas into source-shaped queries (feat-004), and orchestrating a run
  across sources (feat-003). This feature answers one query against one source.

### Open questions

None blocking. Whether proxy support is needed is a risk-mitigation option the brief mentions and
the plan can leave as an unused seam.
