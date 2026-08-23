# Research — command-line

## Discovery input

From `homescout-brief.md` sections 5, 7 and 10:

- The tool has two surfaces over one core, and neither may hold business logic. Anything one
  surface can do, the other must be able to do.
- The command line is not a convenience. It is the interface a scheduled Windows task and an
  automated agent drive, and it is what makes unattended operation possible at all.
- A scheduled run must report what changed in about a hundred lines, not five megabytes. The full
  dataset is already in the store; what an agent needs is the delta.
- Sources fail routinely, so a run has to be able to say "this worked, this did not" and have the
  caller act on the difference. An exit code that only distinguishes crashed from did-not-crash
  cannot express that.

## Problem brief

### Problem statement

A person who wants a property search re-run on a schedule struggles to automate it because the
useful output is a comparison rather than a dataset, and because a run that half-worked is the
common case rather than the exception, which results in either babysitting every run by hand or
writing fragile glue that scrapes meaning out of human-readable output. A solution should let a
scheduled job or an automated agent start a run, learn precisely what changed and what failed, and
act on it without parsing prose, without that machine contract ever becoming a second
implementation of the tool's behavior.

### Target users

- **A scheduled task and the automated agent reading its output** (primary): needs stable
  structure, stable exit codes, and a delta small enough to read in full.
- **The person running searches** (primary, in the other mode): drives the same commands by hand
  and wants readable output when they have not asked for machine output.

### Jobs to be done

- Run one saved search, or all of them, unattended.
- Learn what is new, what changed, what vanished, and what newly tripped a rule, without being
  handed the whole result set.
- Distinguish a clean run from a degraded one from a failed one, programmatically.
- Ask what changed between now and any earlier point, not just since the previous run.
- Do everything the browser interface can do, from a terminal.

### Success signals

- A scheduled task can decide whether to alert a human purely from the exit code.
- A digest for an unchanged run is short regardless of how many properties matched.
- No behavior exists that is reachable from one surface and not the other.

### Constraints

- Every command accepts a machine-output flag and returns a stable exit code. Both are part of the
  contract and cannot change casually.
- The command line holds no business logic. It parses arguments, calls the core, and formats.
- Windows is the primary platform, and the scheduler invokes the command with an output path.

### Explicitly out of scope

- The saved search format and geography resolution (feat-004), which this feature consumes.
- Fetching from providers (feat-002, feat-005) and the store itself (feat-001).
- Writing the digest to email, and the Task Scheduler setup (feat-012). This feature owns the
  digest's shape and the exit codes; feat-012 owns delivering and scheduling them.
- The browser server's own behavior (feat-010). This feature owns only the command that starts it.

### Open questions

None blocking.
