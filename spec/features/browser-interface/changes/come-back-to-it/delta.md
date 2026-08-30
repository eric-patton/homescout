# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Three acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-83, AC-84 and
AC-85. They are numbered after the two `changes/work-the-table/` adds.

**User story.** As the person running searches, I want to leave a pass running and come back to it,
so that a job that takes twenty minutes does not require me to sit in front of it.

**User story.** As the person running searches, I want any screen to tell me something is still
going, so that I do not have to go looking for the one page that might know.

**User story.** As the person running searches, I want pressing a button on a pass the nightly job
is already running to say so, so that I do not quietly start the same work twice.

- AC-83: A screen about an operation that takes minutes asks, when it loads, whether that operation
  is running, and shows the same live progress it would have shown had the operation been started
  from that screen. This holds for the tools surface and for the list of searches, and it holds
  across a reload, a fresh visit, a second browser and a different device, because none of those is
  the tab that pressed the button and all of them are asking the same question.

  What is shown is what the operation has said, updating while it runs, and what it produced when
  it ends, which is what AC-13 already requires of a search run started here and what nothing
  requires once the page has been left. A screen that finds nothing running shows nothing and says
  nothing, because an idle installation is the normal case and a line reporting that nothing is
  happening is noise on every visit.

  **An operation that stopped without finishing is shown as that.** Never as running, which would
  be a panel that never advances and never ends, and never as completed, which would be a lie about
  work that did not happen. This is the browser reading feat-001/AC-31's own answer rather than
  deciding anything: what the store cannot distinguish, the screen must not pretend to.

- AC-84: Every screen says when an operation is under way, in the frame the screens share rather
  than on the one page that started it. It names what is running and reaches the screen showing its
  progress. It is drawn only when something is running, and it goes away on its own when the
  operation ends without the page being reloaded.

  It is one ask on a shared schedule rather than one per surface, because six screens each polling
  for themselves is six answers that can disagree and six requests where one would do. The ask is
  a single cheap read on a stated interval, because it runs on every screen including the results
  table, and every request on that screen queues behind the same one-at-a-time rule as the table's
  own, which is the most expensive read this interface has.

  **What is under way is part of the overview both surfaces already draw.** The overview reports
  running searches today and is widened to report every pass, which is what makes this reachable
  from the command line as invariant 5 requires without inventing a command: `overview` already
  emits it structured, with the stable exit code invariant 6 asks for. A marker in the browser and
  a line in a terminal are then two renderings of one answer rather than two answers.

- AC-85: Starting an operation that takes minutes while another is under way is refused rather than
  started, and the refusal names what is running, what it is running on, and when it began. One at
  a time means on this machine rather than in this process: the browser will not start an extraction
  pass while the scheduled nightly job is running one, which today it happily would, because each
  process knew only about its own work.

  Any long operation blocks any other, not merely another of the same kind. Two of them has never
  been faster: they are paced against the same sources and write to the same file, so the second
  only makes the first take longer while doubling what it costs. This is the rule the browser
  already applied to itself, moved somewhere it can see the whole machine.

  It is one core operation, so both surfaces refuse identically and for the same reason, which is
  AC-14's rule that this layer contains no business logic applied to a decision that currently
  lives in the browser's own process. The store records and does not refuse; the refusal is
  computed from what the store says, in the core, where both surfaces reach it.

## MODIFIED

**AC-13**

Was:

> Running a search from here shows progress and per-source outcomes, including failures, and leaves
> the store in the same state the equivalent terminal command would.

Now:

> Running a search from here shows progress and per-source outcomes, including failures, and leaves
> the store in the same state the equivalent terminal command would. Progress is visible whenever
> the screen is looked at rather than only in the tab that started the run: a run under way is
> reported to a page that has just loaded, including one that has never seen this run and one in
> another browser, and including a run started from a terminal or by the scheduled job. What is
> shown is the run's own progress lines and, on completion, its per-source outcomes.

Why: the original is true and stops one clause short of the guarantee it reads as making. It was
satisfied by a panel that only ever existed inside the page session that pressed the button, which
is not what "shows progress" means to somebody who reloaded the page. The addition says when, and
says the same thing about a run this browser did not start, which the sentence about the terminal
command already implies and never quite states.

## REMOVED

None.
