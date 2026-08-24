<!-- DRIFT LEDGER — written only by /spec-flow:converge. Append-only: never rewrite or delete a
     prior run block, never renumber runs or gap ids. This is history, not a projection. -->

# Drift ledger — scheduling and digests

Each run compares the built code against this feature's spec, plan and tasks, and against the
project-wide rules. Gaps are opened with evidence, confirmed while they persist, and closed with a
citation when they are fixed.

## run 1 — 2026-08-24

baseline: spec sha256:077d649bd4d0 · plan sha256:b11c8f434e40 · tasks sha256:18ad128fc250

implemented: AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14

- opened gap-001 [partial] spec:"AC-2 The digest is written to the configured path on every completed
  run, including runs in which nothing changed and runs that were degraded"

  Evidence: `src/homescout/cli/main.py`, `_dispatch` and `_delivered`. The digest is written on every
  completed run **that was asked to deliver**, which is `run --deliver`. A run without the flag
  writes nothing to the configured path.

  Both halves the criterion actually cares about are built and tested: a run that changed nothing
  writes the file, and so does a degraded run (`tests/test_deliver_pass.py`). What is narrower than
  the wording is which runs deliver at all.

  Why it is built this way: the alternative is that `homescout run north`, typed at a terminal to
  look at one search, silently overwrites the file a scheduled agent is watching, and emails the
  operator a digest they did not ask for. Every scenario in the spec that mentions the digest is
  about a scheduled run; the criterion's own sentence is the only place the broader reading appears.

  Why it is not a contradiction: nothing the criterion requires is absent from a scheduled run,
  which is the run the whole feature is about. The code does something narrower than the sentence
  and exactly what the sentence's own scenarios describe.

  Routed: a `/spec-flow:change` proposal against AC-2, to say that delivery is asked for and that
  the digest is written on every completed run that delivers. Recorded rather than applied:
  rewriting a criterion to match code that was already written is the move this ledger exists to
  prevent. Raised in the pre-build check as C-1 before any of this was built, so the wording was a
  known choice rather than a discovery.

verdict: open 1 (missing 0, partial 1, contradicts 0, unrequested 0)

## What was checked and found clean

- **The silence rule holds in both directions, and the file does not depend on it.** An unchanged
  run sends nothing and still writes the digest; a run with one price change sends. A run that is
  both degraded and silent sends nothing and still reports its failing source in the file and in the
  exit code, which is the spec's own edge case and the one place the two rules could have collided.
- **A delivery cannot reach the run.** Asserted structurally rather than observed: the delivery
  module is handed a document that is already built and a store it only appends a delivery record
  to, and a test reads its source for any call that could write a snapshot. A test that merely
  watched the store stay unchanged would prove nothing about the next code path somebody adds.
- **Every value a listing site wrote is escaped, and a link is a link only when its scheme is one.**
  The pre-build check raised this as a Blocking finding against the first draft of the plan, and it
  was closed before any of the message builder existed. The two escaping functions were then
  collapsed to one behavior under two names, because a value moved from element text into an
  attribute during an ordinary edit would otherwise have stopped being safe.
- **Nothing in the message is a credential or a local path.** Searched for both in the rendered
  message, and the credential is scrubbed twice on the failure path: once where the transport turns
  an exception into a failure, and again where a failure becomes a delivery row that outlives the
  process. The second one was added because a test found the first was not enough: a substituted
  transport's failure text reached the durable record unscrubbed.
- **The new table is history and the database enforces it.** `deliveries` carries the same
  append-only triggers as every other history table, and a migration from a real version 3 file was
  run to check that the run rows already in it survive.
- **Two criteria are verified by proxy, and the proxies are written down.** AC-5 (legible on a phone)
  is checked as a single-column table, nothing wider than 600 pixels, no fixed width larger than a
  narrow phone, and no text below 14 pixels. AC-12 (documentation good enough to follow without
  guessing) is checked as: the documented invocation parses under the real argument parser, and the
  document names the task it creates and the command that removes it. Whether either is *legible* or
  *followable* is a human judgment nobody has made yet. Raised in the pre-build check as C-2 and
  repeated here so a later reader does not mistake the proxy for the criterion.
- **Two things were corrected during this audit rather than recorded as debt.** AC-4 asks for each
  new property's notable flags on its own row, and the first build kept them only in a separate
  section; the criteria now appear on the row where a property is first seen. Rendering a sample
  email to look at then showed the same property listed twice in a four-line message, once as new
  and once as newly flagged, so each property is now shown once. Both were caught by reading the
  output rather than by any assertion, which is the argument for rendering one and looking at it.
