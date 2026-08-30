# Proposal — listing-store

**Trigger:** The person running searches, on being shown that the interface now streams a pass's
progress live: "Does the UI say when it is running and show the progress on the screen so you can
come back to it to see how far along it is in realtime?"

The answer was no, and the reason is here rather than on the screens. A pass over the store keeps
what it is doing in the memory of the process running it and nowhere else.

**Summary:** This store already records that a search run is under way. `runs` carries
`started_at`, `finished_at` and a status of running, completed or failed, and the core reads
"is a run happening" from those rows on purpose, in its own words: *read from the store rather than
from anything this process happens to be holding, so the answer is the same whoever asks: a run
started from a terminal is visible to a browser, and a run started from a browser is visible to a
terminal.*

Everything else that takes minutes gets none of that. An enrichment pass, an extraction pass, a
digest and a broadband load all report themselves through a callback and into a dictionary held by
whichever process started them. Three consequences follow, and the third is the one that made this
worth doing.

- **Restart the process and the pass becomes invisible.** Not stopped, invisible. The work carries
  on in its thread and every trace of it is gone. This was observed rather than reasoned about:
  after the server was restarted mid-session, the interface reported that extraction had never
  been started at all.
- **A pass started from a terminal is invisible to a browser, and the reverse.** Which is exactly
  the asymmetry non-negotiable 8 exists to forbid, and which `runs` already fixes for searches.
- **Nothing can say how far along it is except the one tab that pressed the button.** That is the
  screens' problem to solve and they cannot solve it, because there is nothing to ask.

So: a long operation records what it is doing, in the store, the way a run already does. Not the
progress that a screen happens to want, but the fact of the operation, the words it has said, and
how it ended, kept where anything can read it.

**A pass that stops without saying so has to be readable as stopped.** The store cannot tell the
difference between a pass thinking for a minute and a process that was killed, and today's `runs`
table has this problem already: kill a search run and its row says "running" for ever, because only
the run itself can move it. A recorded pass touches itself while it works, and one not touched for
long enough is reported as having stopped without finishing. That is a fact about the row rather
than a guess about the process, and it is why the fact is worth recording separately from the run.

## Blast radius

- **Requirements affected here:** none modified. One added, for what a long operation records. The
  immutability rules are untouched and are not in tension with this: a pass row is not an
  observation, it is a lifecycle, which is exactly what `runs` already is and what its own comment
  says (*a run row is not history: it has a lifecycle*).
- **Design decisions affected:** none reversed. This extends the decision `runs` embodies to the
  operations that were left out of it.
- **Already-built code affected:** `store/schema.py` (one new table and its lines), `store/core.py`
  and `store/models.py` (reading and writing them), and a migration, because this store is opened
  by a build that expects to bring an older file forward.
- **Not a change to what a run is.** `runs` stays the answer to "was there a run and what did it
  find". This answers "is something happening now and what has it said". A search run gets a row in
  both, and the new one carries the run's id so the two are one thing rather than two.
- **Not a second history.** These rows are operational and may be pruned. Nothing computed from
  them is ever a difference over time, which is what non-negotiable 1 protects.

## What this is not

Not a job queue. Nothing here schedules, retries or resumes anything. It records what is already
happening, and the thing happening is still one thread in one process.

Not a lock. Nothing here refuses a row, and the store has no constraint saying two passes may not
both exist. Whether two may run at once is a question about operations rather than about rows: the
pre-build check found this proposal and the browser's plan disagreeing about who answers it, and the
answer is now feat-010/AC-85, in the core, computed from what these rows say.

Not a log. It keeps the same lines a terminal prints and the same number of them, because the
progress callback is the same callback. A pass over a county does not become a megabyte of text.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
