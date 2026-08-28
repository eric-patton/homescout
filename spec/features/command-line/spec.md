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

- **Scenario: one bad definition among many**
  - Given several saved searches, one of which fails validation
  - When all of them are run
  - Then the failing one is reported and skipped, the others run and record their observations, and
    the command exits with the invalid-input code

- **Scenario: a property leaves the market**
  - Given a saved search for what is for sale, and a source that does not filter on status
  - When a property it returned last time comes back marked as pending
  - Then the property is recorded with its new status and reported as changed, rather than being
    filtered away and reported as having disappeared

- **Scenario: an image already stored is not fetched again**
  - Given a property whose preview image was stored by an earlier run
  - When the search is run again
  - Then no request is made for that property's image, and the stored copy is left as it is

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
      the same request repeated later returns the same result. Later runs of the same search do not
      change a past answer. Only the time the answer was produced differs between two identical
      requests.
- [ ] AC-14: A comparison with no baseline reports that fact and exits with the precondition code.
      It never reports every property as new.
- [ ] AC-15: An unknown saved search name is reported as unknown, the existing names are listed, and
      the exit code is invalid input.
- [ ] AC-16: A saved search that fails validation is reported with the specific failures and enough
      location detail to correct the file by hand, and it is not run. When every saved search is run
      at once, each definition is validated on its own: the ones that fail are reported and skipped,
      the ones that pass still run, and the exit code is invalid input. A missed observation can
      never be made up later, so one unreadable file does not cost a night of history for the
      searches that were fine.
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
      resolved as the same property or as different properties, from the command line. Both surfaces
      resolve through one core operation, so a resolution made from the command line is
      indistinguishable in the store from one made in the browser: resolving as the same property
      writes a merge that every later run follows, and resolving as different records that verdict
      against the queue rather than in either surface. Where the queue keeps its records, and
      therefore how a "different" verdict survives a restart, belongs to the feature that fills the
      queue.
- [ ] AC-25: Both of the above accept machine output and return the same exit codes as every other
      command, so an unattended caller can drain the ambiguous queue without a browser.
- [ ] AC-26: A run of a saved search that is already running declines before making any request,
      reports which run is in progress and when it started, and exits with the precondition code.
      It never waits, and the run already in progress is unaffected. A stale claim left behind by a
      killed process does not block the next run forever.
- [ ] AC-27: A preview image is retrieved once for a property and is not retrieved again while a copy
      is stored, so a nightly run does not re-download pictures it already has. Retrieving images can
      be skipped for a run, and skipping them changes nothing else about what that run records.
- [ ] AC-28: A filter the tool applies locally never removes a property whose value for that field
      is absent. The tool does not report that a property failed a test it could not run.
- [ ] AC-29: A property returned by two of one search's areas is recorded once, because the overlap
      is the tool's own doing. A property returned twice inside one source response is recorded
      twice, because that is the source contradicting itself and both halves are evidence.
- [ ] AC-30: The delay between requests to one source can be set when a run is started, within the
      permitted range, and a value outside that range is reported as invalid input before anything
      is fetched. Unset, the shipped default applies.
- [ ] AC-31: No command-line option accepts a credential, because arguments are visible to other
      processes and are stored in scheduler configuration. A test asserts that the parser defines no
      such option.
- [ ] AC-32: Two filters are pushed to a source that will apply them and are never applied by the
      tool afterwards, and neither is reported as applied locally. The freshness filter, because
      freshness is computed from local history and a local test would have nothing honest to read.
      The listing status, because a property whose status just changed is the most interesting thing
      a run can find, and removing its row would replace the source's own evidence with an absence
      the tool could then only report as an unexplained disappearance.
- [ ] AC-33: The household's own vocabulary is reachable from the terminal: listing every tag with
      how many properties carry it, adding one, renaming one, deleting one, reading what one
      property carries, and setting the whole list a property carries. Naming no tags at all when
      setting means none of them, because a command line has no other way to say an empty list.
      Non-negotiable 8 requires this, and so does the shape of the job: tagging fifty properties
      with one word is what somebody wants the first time they decide a word was worth having, and
      fifty clicks is not how anybody does that.

## Edge cases & errors

- Two runs of the same saved search are started concurrently, which a scheduled task and a manual
  run can easily do on Windows. The second declines before fetching anything, naming the run
  already in progress and when it started, and exits with the precondition code. It does not wait,
  and it does not interleave observations into one run.
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
- The output path's directory does not exist. The command reports it as invalid input before any
  work is done, rather than creating an arbitrary directory tree or discovering the problem after an
  hour of throttled requests.
- The output path exists but cannot be written when the moment comes, because the disk is full or
  the file is held open. The failure is reported and reflected in the exit code. Nothing is written
  to the primary stream that would not have been written anyway, so a command asked for readable
  output does not suddenly emit a structured document.
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

None. Whether concurrent runs of one saved search wait or decline (od-1) was settled on 2026-08-23:
they decline, with the precondition code, so a scheduled task retries on its next tick instead of
queueing behind a manual run. Scheduling and digests (feat-012) inherits that answer.
