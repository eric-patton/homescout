# Research — listing-store

## Discovery input

Discovery for this product was done before the workspace existed and is recorded in
`homescout-brief.md` and `homescout-decisions.md` at the repository root. The findings that bear
on this feature:

- The current workaround is manual: run searches on a listing site, open each property, copy
  fields into a spreadsheet, then hand-research flood, internet, water, and crime per property.
  It takes hours per batch and is stale the moment it is finished.
- Almost everything worth knowing is a difference over time rather than a field in any response:
  how new a listing is, price cuts and price increases, back-on-market after a failed contract,
  sold twice in a short window, disappeared from results.
- No free source exposes reliable price history, and the freshness filters sources do offer
  (`past_days` and similar) answer "recently listed according to us", which is not the same
  question and cannot be audited.
- Sources fail. A provider being down, rate-limited, or newly incompatible is a normal Tuesday,
  and the failure mode that would destroy the tool's value is one where a bad run quietly
  rewrites or deletes good history.

## Problem brief

### Problem statement

Someone tracking every property in a region struggles to tell what actually moved since they last
looked, because no free source exposes trustworthy history and each run of a search returns only a
snapshot of now, which results in re-reading the same listings by hand and still missing the price
cut, the relisting, and the quiet disappearance. A solution should make change over time a
recorded, queryable fact derived from what this tool itself observed, without ever rewriting or
discarding an earlier observation.

### Target users

- **The person running searches** (primary): needs to open the tool and be told what is different,
  not be handed the same table again.
- **A scheduled automated agent** (secondary): consumes differences programmatically and needs
  them to be reproducible rather than recomputed differently on each call.

### Jobs to be done

- Tell me which properties are new since a point in time I choose, on evidence this tool gathered.
- Tell me which properties changed, in what field, and in which direction.
- Tell me which properties stopped appearing, without claiming they sold.
- Tell me when one that stopped appearing has come back.
- Keep my own judgment about a property attached to it forever, through every future run.
- Show me why the tool believes something changed, down to the rows it saw.

### Success signals

- The difference between any two past points in time can be recomputed at any later date and
  produces the same answer.
- A user's notes and ranking on a property are still there after arbitrarily many runs, after a
  merge, and after that merge is undone.
- No run ever produces a database state where an earlier observation reads differently than it did
  when it was made.
- A run in which a source failed is visibly a partial run, and nothing in it is mistaken for
  evidence that a property is gone.

### Constraints

- One SQLite file. Windows is the primary platform, so no POSIX-only assumption about paths,
  locking, or file semantics.
- History is append-only. Corrections are new rows. This is a constitution non-negotiable, not a
  preference.
- Eleven further features add tables and columns to this same file, so the schema has to be
  versioned and extendable from the first release.
- Freshness and days-on-market are always computed from local observation, never read from a
  source field.

### Explicitly out of scope

- Fetching anything. Sources belong to the source-adapter feature (feat-002).
- Deciding that rows from different providers describe the same house. Cross-source matching
  belongs to address matching and merge review (feat-006). This feature owns only the trivial case
  where a canonical listing is backed by exactly one source's row.
- Editing annotations through an interface. This feature owns the data and the durability
  guarantee; the browser interface (feat-010) owns the editing surface.
- Location enrichment values (feat-007) and rule evaluation results (feat-008), which attach to
  listings but are owned and cached elsewhere.

### Open questions

None blocking. Storage growth under a year of daily runs is a sizing question the plan resolves,
not a requirement question.
