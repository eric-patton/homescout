# Delta: listing-store

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-31.

**User story.** As the person running searches, I want an operation that takes minutes to record
what it is doing where anything can read it, so that the answer to "how far along is it" does not
depend on which window I am standing in front of.

- AC-31: An operation that takes minutes records that it is under way, what it has said, and how it
  ended. What is recorded is the operation's kind, when it started, every line its own progress
  callback produced, and a terminal state of completed or failed with the outcome or the failure.
  Every long operation this product has records itself this way: a search run, a run of every
  search, an enrichment pass, an extraction pass, a digest, and a broadband load.

  **Whoever asks gets the same answer.** A pass started from a terminal is readable from a browser
  and a pass started from a browser is readable from a terminal, which is AC-1's rule about a run
  applied to the operations that were left out of it and non-negotiable 8 applied to a question
  rather than to an action. Reading it requires nothing of the process that started it and works
  after that process is gone.

  **A pass touches its own row while it works, and one not touched recently enough is reported as
  having stopped without finishing.** This is not optional decoration. Only the pass itself can
  move its row to completed or failed, so a process that is killed leaves a row that would
  otherwise say "running" for ever, and a screen that believes it would show a pass in progress
  that has not existed for a week. A row is touched on a schedule of its own rather than only when
  the operation happens to say something, because the operations here are silent for minutes at a
  time by design; the threshold for reading a row as stopped is a stated multiple of that interval,
  defined once beside it, so the two cannot drift apart. A pass reported as stopped is reported as
  exactly that, and never as completed and never as failed, because nothing knows which it was.

  **Nothing written here may carry a credential.** This is the criterion's one hard requirement and
  it exists because of what this change actually does to a failure message. Today a progress line
  and a failing exception live in the memory of one process and are gone when it exits. Recorded,
  they are bytes in the database file, which this workspace keeps backup copies of beside. The
  extraction layer already strips credentials out of its own per-description failures, for the
  stated reason that an address with a query string can carry a key, and that stripping is applied
  at exactly one call site and not to the exception that ends a pass. So every line and every
  failure is scrubbed on the way in, in the one function that writes a pass row, rather than by
  each caller remembering to. A caller that forgets is the failure mode this is written to remove.

  **A recorded line is bounded and is text.** The same callback the terminal prints and the same
  bound on how many lines are kept, plus a bound on the length of one, because a progress line can
  carry a snippet of a remote server's refusal and that snippet is now durable rather than
  momentary. It is stored and returned as text and is never interpreted as anything else.

  **These rows are operational rather than historical, and this is the one table here that is.**
  Nothing computes a difference over time from them, no annotation refers to them, and what a run
  found is recorded where it always was, so losing one loses nothing that non-negotiable 1 or
  invariant 1 protects. Said out loud because every other table in this store is append-only
  history and a reader is entitled to assume this one is too. Removing them by age is permitted and
  is not built here; nothing in this product depends on their being kept.

  **The store records and never refuses.** There is no constraint here that stops a second pass
  being written while one is running. Whether two passes may run at once is a question about
  operations rather than about rows, it already has an answer elsewhere, and a table that answered
  it too would be a second answer that can disagree with the first.

  **A search run is one operation, not two.** It has a row here and a row in `runs`, and the row
  here carries the run's id. `runs` stays the answer to what a run found; this is the answer to
  what is happening now. A reader that wants both gets one thing rather than two accounts of it.

## MODIFIED

None. AC-1's guarantee about a run being recoverable, AC-2's refusal to update an observation, and
AC-17's rule that a run never touches an annotation are all untouched, and none of them is in
tension with a row that has a lifecycle: `runs` already is one.

## REMOVED

None.
