## Why

This is the surface an unattended machine drives. It owns two things that have to be stable enough
to build a scheduled job on: the run loop that asks each source what it can filter, applies the
rest locally, and records the outcome, and the machine contract of structured output plus exit
codes that lets a caller act on the result without reading English. The compact digest exists
because the full dataset is already in the store, and what a scheduled agent needs is the part that
moved. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **degraded run** completed and wrote its observations, but at least one configured source
  reported `failed` or `unavailable`. It is neither a success nor a failure and the exit code says
  so.
- A **digest** is the compact summary of what one or more runs changed. It carries counts and the
  changed subset, never the full result set.
- **Machine output** is what a command emits when asked for structured output. **Human output** is
  the default. They are two renderings of one result, never two computations.

## User stories

- As a scheduled task, I want an exit code that distinguishes a clean run, a degraded run, and a
  failure, so that I can decide whether to wake a human without parsing anything.
- As an automated agent, I want a run's structured output to be the delta rather than the dataset,
  so that I can read the whole thing and reason about it.
- As the person running searches, I want to ask what changed since any earlier point, not only
  since the last run, so that I can catch up after being away.
- As the person running searches, I want the same operations available from a terminal that are
  available in the browser, so that the scheduled path and the interactive path never diverge.
- As the person running searches, I want readable output when I have not asked for machine output,
  so that the terminal is usable by hand.
- As whoever debugs a surprising result, I want to see which filters the source applied and which
  the tool applied locally, so that I can tell a source's opinion from mine.

## Behavior & scenarios

- **Scenario: a clean run**
  - Given a saved search whose configured sources all succeed
  - When it is run
  - Then observations are recorded, a comparison against the previous completed run is produced,
    and the command exits with the success code

- **Scenario: a degraded run**
  - Given a saved search where one of three configured sources reports `failed`
  - When it is run
  - Then the run still completes and records its observations, the failing source is named with
    its outcome in the result, and the command exits with the degraded code rather than the success
    code

- **Scenario: every source fails**
  - Given a saved search where every configured source reports `failed`
  - When it is run
  - Then no property is marked as disappeared on the strength of that run, the run is recorded with
    every source's failure, and the command exits with the degraded code

- **Scenario: filters split between the source and the tool**
  - Given a saved search with a filter one source applies and another does not
  - When it is run
  - Then each source is sent only the filters it declared it applies, the remainder are applied
    locally to that source's rows, and the result reports which filters were applied where

- **Scenario: running every saved search**
  - Given several saved searches
  - When all of them are run with machine output requested
  - Then one digest is emitted covering every search, each entry naming its search, its per-source
    outcomes, its counts, and its changed subset

- **Scenario: a digest stays small when nothing changed**
  - Given a saved search matching several thousand properties, none of which changed
  - When it is run with machine output requested
  - Then the digest reports the matched count and empty sets for new, changed, gone, and newly
    flagged, and its size does not grow with the number of properties matched

- **Scenario: comparing against an earlier point**
  - Given a saved search with several completed runs
  - When a comparison is requested against a named date or against the previous run
  - Then the result reports each affected property once with its difference event, and requesting
    the same comparison again later produces the same answer

- **Scenario: comparing when no baseline exists**
  - Given a saved search that has never completed a run
  - When a comparison is requested
  - Then the command reports that no baseline exists and exits with the precondition code, rather
    than reporting every property as new

- **Scenario: a saved search that does not exist**
  - Given a name matching no saved search
  - When any command is given that name
  - Then the command reports the name as unknown, lists the names that do exist, and exits with the
    invalid-input code

- **Scenario: an invalid saved search**
  - Given a saved search file that fails validation
  - When it is validated or run
  - Then the specific problems are reported with enough location detail to fix them by hand, and
    the command exits with the invalid-input code without running anything

- **Scenario: machine output is separable from everything else**
  - Given any command run with machine output requested
  - When its output streams are captured separately
  - Then the structured output is the entire content of the primary stream and parses without
    preprocessing, and all progress and diagnostic text is on the secondary stream

- **Scenario: writing output to a file**
  - Given a command run with machine output requested and an output path
  - When it completes
  - Then the structured output is written to that path, and a failure to write it is itself
    reported and reflected in the exit code

- **Scenario: the surfaces agree**
  - Given any operation available in the browser interface
  - When the equivalent command is run
  - Then the resulting state of the store is identical, because both called the same core operation

## Acceptance criteria

- [ ] AC-1: Every command accepts a flag requesting machine output, and with it set emits a single
      structured document that parses without preprocessing.
- [ ] AC-2: With machine output requested, the structured document is the entire content of the
      primary output stream. Progress, warnings, and diagnostics appear only on the secondary
      stream.
- [ ] AC-3: Exit codes are stable and documented, with exactly these meanings: success; degraded,
      meaning completed with at least one source failed or unavailable; precondition not met,
      meaning the operation is valid but cannot proceed yet; invalid input, meaning usage, an
      unknown name, or a saved search that fails validation; and internal error for anything
      unexpected.
- [ ] AC-4: A run in which every source succeeds exits with the success code. A run in which any
      source reports `failed` or `unavailable` exits with the degraded code. A test asserts both.
- [ ] AC-5: A degraded run still records its observations and its comparison. Degraded never means
      discarded.
- [ ] AC-6: A run where every source failed marks no property as disappeared, satisfying the
      store's rule that absence is not evidence.
- [ ] AC-7: For each configured source, the run sends only the filters that source declared it
      applies, and applies every remaining filter locally to that source's rows.
- [ ] AC-8: The result of a run reports, per source, which filters it applied and which the tool
      applied afterwards.
- [ ] AC-9: A run records one run entry containing its identifier, the search, start and finish
      times, and each source's outcome and row count.
- [ ] AC-10: Running all saved searches emits one digest containing an entry per search, each with
      the search name, per-source outcomes, counts for matched, new, changed and gone, and the
      changed subset.
- [ ] AC-11: A digest never contains the full result set. For a run over N properties of which K
      changed, the digest's size is a function of K and not of N. A test with N large and K zero
      asserts a bounded size.
- [ ] AC-12: A digest reports price changes with a previous value, a new value, and a direction, and
      reports listing-status changes, disappearances, returns, and newly flagged properties as
      separate sets. The newly flagged set is always present and is empty for a search with no
      criteria configured, so the digest's shape does not depend on the rule engine existing.
- [ ] AC-13: A comparison can be requested against the previous completed run or against a date, and
      the same request repeated later returns the same result.
- [ ] AC-14: A comparison with no baseline reports that fact and exits with the precondition code.
      It never reports every property as new.
- [ ] AC-15: An unknown saved search name is reported as unknown, the existing names are listed, and
      the exit code is invalid input.
- [ ] AC-16: A saved search that fails validation is reported with the specific failures and enough
      location detail to correct the file by hand, and nothing is run.
- [ ] AC-17: With an output path given, the structured output is written there, and a failure to
      write it is reported and reflected in the exit code rather than silently swallowed.
- [ ] AC-18: Every operation the command line performs is a call into the core library. A test
      asserts that performing an operation through the core directly, and through the command,
      leaves the store in an identical state.
- [ ] AC-19: No decision about filtering, comparison, merging, or rule evaluation is made in the
      command-line layer. A review criterion: the command layer contains no conditional on listing
      data.
- [ ] AC-20: The commands named in the brief exist and are reachable: listing, creating, editing and
      validating saved searches; running one search and running all of them; comparing since a point
      in time; enriching, optionally limited to stale values or one search; exporting; and starting
      the local server. Alongside them, the two commands the two-surface rule requires: annotating a
      property, and reviewing and resolving queued ambiguous matches.
- [ ] AC-21: Human output is the default. With machine output not requested, the primary stream is
      readable prose and no structured document is emitted.
- [ ] AC-22: An unexpected internal failure exits with the internal-error code and leaves the store
      in a state where the previous completed run is still a usable comparison baseline.
- [ ] AC-23: A property's annotation fields can be set from the command line, individually or
      together, and the resulting stored annotation is identical to the one the browser interface
      would have written for the same values.
- [ ] AC-24: Queued ambiguous matches can be listed with the signals that agreed and conflicted, and
      resolved as the same property or as different properties, from the command line. A resolution
      made this way is indistinguishable in the store from one made in the browser interface, and is
      honored by later runs identically.
- [ ] AC-25: Both of the above accept machine output and return the same exit codes as every other
      command, so an unattended caller can drain the ambiguous queue without a browser.

## Edge cases & errors

- Two runs of the same saved search are started concurrently, which a scheduled task and a manual
  run can easily do on Windows. The second either waits or refuses with a clear message. It does
  not interleave observations into one run.
- A run is interrupted by the machine sleeping or the task being killed. The partial run is not
  usable as a comparison baseline, per the store's rules, and the next run compares against the
  last completed one.
- A saved search names a source that is not registered. This is a validation failure, reported
  before anything is fetched.
- A saved search names zero sources. This is a validation failure, not a run that matches
  nothing.
- Machine output is requested and the result contains characters outside the ASCII range, which
  property descriptions routinely do. Output is UTF-8 encoded and parses correctly on Windows,
  where the console's default encoding is not UTF-8.
- The output path's directory does not exist. The command reports it rather than creating an
  arbitrary directory tree.
- A comparison is requested for a date in the future. It is reported as invalid input.
- The store is locked by the browser interface. The command reports the lock in terms the user can
  act on, naming the likely cause.

## Non-functional requirements

- Performance: command startup overhead is small enough that a scheduled task running several
  searches spends its time on network pacing rather than on process startup.
- Security: no credential is accepted as a command-line argument, because arguments are visible to
  other processes and land in scheduler configuration. Credentials come from the environment.
- Reliability: any command that fails partway leaves the store usable, with the last completed run
  intact as a baseline.
- Accessibility: human output is readable in a plain terminal without color, and conveys nothing by
  color alone.

## Open questions

- Whether concurrent runs of one saved search wait or refuse is a plan decision. Both satisfy the
  edge case above; they differ in how a scheduled task behaves when a manual run is already going.
