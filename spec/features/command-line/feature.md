---
schema_version: 2
id: "feat-003"
slug: "command-line"
title: "Command line and run orchestration"
status: done
owner: "eric-patton"
depth: "mvp"
sprint: null
external: null
depends_on: [feat-001, feat-002]
requires_design: null
readiness:
  research: ready
  design:   n/a
  spec:     ready
  plan:     ready
  tasks:    ready
gate:
  analyze: pass
  product_global_hash: "sha256:869c75445341"
  constitution_hash: "sha256:7ed19648690b"
converge:
  last_run: 2026-08-23
  open: 0
  contradicts: 0
human_signoff: []
open_decisions:
  - id: od-1
    description: >-
      When a scheduled run and a manual run of the same saved search overlap, does the second wait
      for the first or decline outright? Both satisfy the spec. Scheduling and digests (feat-012)
      defers to whatever this feature decides, so it must be settled here before either is planned,
      or the two plans will assume opposite answers.
    owner: eric-patton
    resolved: true
    decision: >-
      Decline. The second run stops before fetching anything, names the run already in progress and
      when it started, and exits with the precondition code (AC-3, "valid but cannot proceed yet").
      A scheduled task reads that code and simply runs again on its next tick. Waiting was rejected
      because a manual run interrupted by the machine sleeping would block the nightly task
      indefinitely, and because two runs back to back fetch the same listings twice for almost no
      new information, against non-negotiable 10.
    decided_by: eric-patton
    decided_at: 2026-08-23
overrides: []
extends: []
---

# Feature notes — Command line and run orchestration

## Scope

The run loop that asks each source what it can filter, pushes those filters, applies the rest
locally, writes a snapshot, and records per-source status, plus the command line that exposes it.
Owns the machine contract: every command takes --json, returns a stable exit code, and never
prints prose an automated caller has to parse. Owns the digest shape emitted by run --all.

Brief sections 5, 7. Product invariant 6.

## Sources

Derived from `homescout-brief.md` and `homescout-decisions.md` at the repository root.

## Later changes by other features

- **2026-08-23, saved searches and geography (feat-004).** The contract a saved search satisfies,
  in `homescout/search/`, changed in three places. This feature's own acceptance criteria are all
  unaffected and its suite passed unchanged apart from the fakes that implement the seam.

  **Coarse queries are per source.** `SearchDefinition.queries()` became `areas` (what the search
  covers, source-independent, which is what a surface counts) plus
  `queries_for(capabilities)` (what to send one source, given what that source accepts). One set of
  coarse queries sent to every source cannot be right for a product whose sources take different
  geography: Realtor.com takes named places and a radius, Zillow takes a box, neither takes a drawn
  shape. A source that can express none of a search's areas is now reported `unavailable` naming
  them, rather than being asked for somewhere else or quietly returning nothing, which serves this
  feature's own AC-6: not asked and asked-and-found-nothing must never look alike to the store.

  **The exact local test has three answers.** `keeps(fields) -> bool` became
  `place(fields) -> Placement`, one of inside, outside, or unlocatable, and the run loop keeps the
  first and the last, drops the middle, and counts the last into `SourceReport.not_locatable`,
  which the digest's per-source block carries. A property a source returned without coordinates
  cannot be placed, and both of the two answers a boolean allows are lies: keeping it asserts it
  qualified, dropping it stops recording a property the store would then read as having
  disappeared. Serves feat-004/AC-6.

  **A problem and a notice are told apart.** `SearchProblem` gained a severity, and only a
  `problem` makes a definition invalid or refuses a run. A search whose exclusions cover all of its
  areas is valid, matches nothing, and has to be able to say which of those two it is. `validate`
  reports both and exits successfully when only notices are present.

- **2026-08-23, rule engine (feat-008).** Two further changes to the same contract.

  `SearchDefinition` gained `rules`, defaulting to empty, so the run loop can ask a search for its
  criteria rather than reaching back to the file. After a run completes, the loop evaluates them and
  records the verdicts. Deliberately after, and never during: a criterion decides what a person is
  shown and nothing about what is recorded, because a property a rule drops is still observed, still
  snapshotted and still comparable, and excluding it from the recording would make the store read
  the exclusion as a disappearance.

  The digest's flagged set, which this feature deliberately shipped as always empty so its shape
  would not depend on the rule engine existing, is now filled: the properties that newly tripped a
  criterion since the baseline run, with the criteria they tripped. A per-rule `excluded` count sits
  beside it, so a run that dropped everything says why rather than looking like a market that
  emptied out.

- **2026-08-23, location enrichment (feat-007).** The `enrich` command stopped reporting itself
  unbuilt and grew a body: it runs the enrichment pass, takes `--stale` and `--search`, emits the
  per-provider outcomes as a structured document, and exits degraded rather than failed when a
  provider is down, because one dead service costs one column and the values that were obtained are
  worth what they were always worth.

  This is the first of the three reserved commands to arrive, and it is what that reservation was
  for: an automated caller that could already discover the command did not need to learn a version
  number to find out it now works.
- **2026-08-24, scheduling and digests (feat-012).** Two changes to this feature's surface, both
  additive.

  **`run --deliver`.** A new flag that writes the digest to the configured path and sends the email
  digest when a run found something to say. Explicit rather than inferred from a configured mail
  account, for two reasons: a person running one search at a terminal must never accidentally email
  themselves, and a Task Scheduler entry should say what it does without somebody having to go and
  read a `.env` file. With `--json`, the invocation's own answer gains a `delivery` section; the
  file written to disk is the digest document unchanged, because a file cannot record whether it was
  written.

  **Exit code 1 widened by one word.** It was "at least one source failed or was unavailable" and is
  now "at least one source or delivery failed". A mail server that refuses the message is degraded
  rather than an error: the run's results are complete and stored, and what failed is a report about
  them. A digest file that could not be written stays code 4, matching what `--output` already
  returns for the same failure, and deliberately not 1: an agent that reads the file needs to know
  the file is not there, and 1 would tell it the file is fine and a source was down. This feature's
  own criteria about the codes are unaffected; the meanings of 0, 2, 3 and 4 did not move.

- **2026-08-24, defect found by the first real run over three sources.** A property's address was
  composed in two places, `cli/render.address` and the email's own `address_of`, and both appended
  the unit unconditionally. Both Realtor.com and Zillow write the unit into the address line *and*
  into their own unit field, and both adapters record both faithfully, so a real digest printed
  `1828 Redwine Unit B Unit B` and `1839 S Roosevelt Rd S #7 # 7`.

  Fixed by composing it once, in `digest.address_of`, which both surfaces now call: the digest owns
  the summary's shape, so it is the right place to decide how one is written out. The unit is
  appended only when the address line does not already end with it, compared with the decoration
  (`#`, `Unit`, `Apt`, `Lot`) removed. At the end rather than anywhere, because the digit 2 lives
  inside the house number 425. Regression tests cite `feat-012/AC-4`.

  Recorded here because it is a change to what this feature's surface prints, and because the
  general shape is worth remembering: two implementations of one small rendering decision is how a
  wrong address reaches somebody's inbox.
- **2026-08-24, address matching and merge review (feat-006).** Three changes, all of them things
  this feature's surface was built to accommodate.

  **The merge queue port grew two methods.** `MergeQueue` declared `pending`, `get` and `record`,
  which is what a surface does with a queue; it now also declares `offer` and `clear`, which is what
  fills one. They are on the same protocol rather than a second one because a queue that cannot be
  filled is not a queue. `matches list` and `matches resolve` are unchanged and now have something
  to list.

  **The run loop runs the merge pass**, after the run completes and before the comparison is
  computed. That ordering is deliberate: a comparison computed across a merge would have to reason
  about records changing identity, and computed before it, a run's comparison is about the records
  that run actually observed. The next run's comparison follows the merge, because the store already
  resolves a superseded record to the one that replaced it.

  **The digest gained one count**, `counts.waiting_for_review`: how many pairs of records need a
  person's decision. Always present, zero until there is more than one source, and never a failure:
  it is a number of judgments waiting, which is a thing to do rather than a thing that went wrong.
  The terminal renderer prints a line pointing at `homescout matches list` when it is not zero.
