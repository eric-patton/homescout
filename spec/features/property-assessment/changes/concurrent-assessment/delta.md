## ADDED

- AC-23: Assessments run with a configurable maximum number of concurrent model calls, defaulting
  to eight. `HOMESCOUT_ASSESS_CONCURRENCY` is read from the existing environment or ignored `.env`
  beside the database; allowed values are integers from 1 to 32. Invalid values are reported before
  model requests. Calls share the existing model pacing and retry policy, with a common cooldown
  after a temporary refusal and respect for a valid Retry-After hint. The queued work is bounded by
  the configured concurrency. Pictures, store reads, writes and progress run on the coordinator
  thread; workers perform only model calls. Current readings, per-pass limits, criteria selection,
  narrow-question priority and property-wide failure isolation continue to hold. An interruption
  preserves completed readings, which are skipped when the pass is restarted.

- AC-24: Each completed model job reports the number finished out of the scheduled total,
  successful full assessments, successful top-ups, failures and remaining jobs. Results are saved
  when ready without waiting for an earlier slow request. The final counts agree with the saved
  results and reported failures. Existing CLI and browser progress surfaces show these core lines.

## MODIFIED

None. Existing model, criteria, fingerprint and pacing settings remain in effect.

## REMOVED

None.
