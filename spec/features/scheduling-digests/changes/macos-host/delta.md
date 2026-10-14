## ADDED

- AC-15: macOS setup generates a boot-supervised interface job and a separate 03:00 nightly job
  that runs all saved searches with delivery, then enrichment, using the existing command line.
  Both processes run as the workspace owner, use an absolute database path, and carry no secrets
  in their launchd property lists or command arguments. Setup documents installation, verification,
  and removal. The nightly job exits between runs; interface supervision is independent.

## MODIFIED

- AC-12:
  - Was: Setup for the Windows scheduler is documented well enough to follow without guessing,
    and states exactly what it creates so it can be undone.
  - Now: Setup for Windows Task Scheduler and macOS launchd is documented well enough to follow
    without guessing, and states exactly what each setup creates so it can be undone.
- AC-13:
  - Was: A scheduled run requires no always-running process. Between runs the tool is not executing.
  - Now: A scheduled run requires no always-running scheduler process within HomeScout. The nightly
    job exits between runs; an independently supervised browser interface may remain running.

## REMOVED

None.
