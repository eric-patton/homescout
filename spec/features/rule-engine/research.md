# Research — rule-engine

## Discovery input

From `homescout-brief.md` sections 5.5 and 12:

- The user's real criteria are compound and idiosyncratic: a well with no principal aquifer under
  it, a listing that sat for six months and then raised its price, an address with no fibre. None
  of these is a filter any source offers, and all of them combine source data with enriched
  data.
- These criteria change as the search matures, which is why the brief insists they are data stored
  in the saved search rather than code: tunable per search and diffable in git.
- Four severities are named: `drop` excludes from results, `flag` shows a badge, and `boost` and
  `demote` affect the default sort.
- The brief lists rule expressions as a named risk, with the mitigation stated twice: a sandboxed
  restricted parser over a fixed namespace, and no `eval`. This is also a constitution
  non-negotiable.
- The brief requires a clear error when a rule names a field that is unknown, or that exists but
  has not been enriched yet.

## Problem brief

### Problem statement

Someone with specific, compound property criteria struggles to express them because no source
filters on the things that actually decide the question, and the ones that matter combine listing
data with public data the source has never heard of, which results in either judging every
property by hand against a mental checklist or hard-coding personal preferences into a tool that
then fits nobody else's search. A solution should let criteria be written as data alongside the
search they belong to, evaluated the same way every run, without any path by which a written
criterion becomes executable code.

### Target users

- **The person running searches** (primary): wants to encode a judgment once and have it applied
  to every property in every future run.
- **The same person tuning a search** (primary, differently): edits a criterion, re-runs, and
  compares. Needs criteria to be readable, diffable, and to fail loudly when they are wrong.

### Jobs to be done

- Exclude properties that fail a hard requirement, without deleting them.
- Mark properties that deserve a second look, without excluding them.
- Push the interesting ones up the default order and the dull ones down.
- Be told plainly when a criterion refers to something that does not exist or has not been fetched
  yet, rather than having it quietly evaluate to false.
- Keep criteria in a file that can be reviewed as a change.

### Success signals

- A criterion written once applies to every subsequent run with no further action.
- A criterion referring to a missing field produces a message naming the field, not a silently
  empty result.
- A property is never excluded because a value was unknown rather than because it failed the test.
- No expression a user writes can reach a general-purpose interpreter.

### Constraints

- No `eval`, and no general-purpose interpreter anywhere in the evaluation path. Constitution
  non-negotiable.
- The field namespace is fixed and declared. A rule cannot reach outside it.
- Rules live in the saved search file and must round-trip losslessly through the browser interface.

### Explicitly out of scope

- The saved search file format itself (feat-004), which this feature occupies a section of.
- Producing the enriched values rules refer to (feat-007) and the extracted values (feat-009).
  This feature consumes them and must behave correctly when they are absent.
- Presenting badges and sort order (feat-010). This feature owns the verdict; the interface owns
  the pixels.

### Open questions

None blocking. Whether the expression language eventually needs arithmetic beyond comparison is a
scope question the acceptance criteria settle for this release.
