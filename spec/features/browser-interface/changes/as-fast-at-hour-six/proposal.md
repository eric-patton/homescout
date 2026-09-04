# Proposal — browser-interface

**Trigger:** Reported on 2026-09-04, in these words: "the site seems to slow down over time. Like
it is loading the results page really slowly now when it was very fast right after a server
restart."

**Summary:** The interface was measured doing exactly the same work at two speeds. A results answer
of 1,251 rows costs 0.7 seconds in a process started by hand and between 3 and 4.8 seconds in the
copy the scheduled task had started three hours earlier, with the same reads, the same bytes and
the same memory in both. The difference was not in the tool. Windows 11 moves a hidden background
process into its efficiency mode some time after it starts, and everything in that process then
runs at a fraction of the speed; the watchdog starts the server hidden, at below-normal priority,
which is the profile Windows throttles. Lifting the throttling on the running process, and nothing
else, took the answer back to 0.7 seconds, and putting it back took it to 4.8.

So the server asks, when it starts, not to be throttled. One call to the operating system, on
Windows only, best effort. It belongs in the server rather than in the scheduled task or the
watchdog script, because those live on one machine and this travels with the tool: a copy started
by hand, by a shortcut, by a task or by anything else gets the same answer. Raising the process
priority on its own was tried and did nothing, so priority is left alone.

The other half of what was reported, the map being slow with the data centers on, was a defect and
is recorded as one: every shape had a drawing surface of its own and none was ever taken away.

## Blast radius
Everything this change touches, so the ripple is explicit.
- Requirements affected: one added, `AC-96`. The performance requirement this feature already
  states, a table interactive within three seconds, was being missed in practice on the target
  platform for a reason no requirement named.
- Design decisions affected: none changed. One added, on where the call lives and why.
- Tasks affected (regenerate these): none. Three added, `T-afh-1` to `T-afh-3`.
- Already-built code affected: `web/serve.py` gains the call, made from `serve()` before the
  server is run. `docs/tailscale.md` says so where it explains how the interface is kept up.

The id `AC-96` had been cited once by a task of the data centers change (`T-dcm-10`) without
existing in the spec; that citation now points at `AC-56`, whose wording is what the task verifies, and
`AC-96` is this criterion.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into product.md and archived
