# Proposal — browser-interface

**Trigger:** The person running searches, asked directly: "Does the UI say when it is running and
show the progress on the screen so you can come back to it to see how far along it is in realtime?"

**Summary:** Only if you never leave. The progress panel is real, updates every second and a half,
and prints the same words the terminal does. It is also started in exactly one place: the button
handler. Nothing asks whether anything is running when a page loads.

What that costs, on the three screens where it matters:

- **The tools surface shows nothing at all.** On load it fetches the configuration and the notes
  and never asks about a pass. Extraction can be twenty minutes into a run and the page looks
  idle, with the button sitting there inviting a second press. The server knows perfectly well;
  the page has never asked.
- **The list of searches shows a snapshot and calls it a state.** A card says "a run is under way"
  and the overview strip counts what is running, both read once when the page drew and never
  again, with no progress behind either. You learn that something is happening and nothing else,
  frozen at whatever was true when you arrived.
- **Every other screen says nothing.** The navigation is four fixed links. Standing at the results
  table or the map, there is no way to know a pass is running except to go and look, and going and
  looking does not tell you either.

There is an accidental workaround, which is the clearest evidence this is a gap rather than a
decision: press the same button again. The server answers "already running" and starts nothing, the
page ignores that answer and attaches its watcher anyway, and the progress comes back. It works,
and nothing on any screen would ever suggest it.

**Three things, in the order they depend on each other.**

**Rejoin what is already running.** A screen about a pass asks, when it loads, whether that pass is
running, and attaches the same live panel it would have attached had you pressed the button
yourself. Reloading, coming back tomorrow, or opening the page on a phone all show the same thing
the tab that started it shows.

**Say it everywhere, not only where it started.** One indicator on every screen, because the
question "is something still going" is asked from wherever you happen to be, and the answer today
requires navigating to the one page that might know.

**Make it survive the process.** The first two work from what the server already answers, and both
stop being true the moment the server restarts, because a pass's progress lives in the memory of
the process running it. `changes/what-a-pass-is-doing/` against feat-001 puts it in the store
instead. That is what makes a pass started by the scheduled nightly job, or from a terminal,
visible here at all, which is the same rule AC-13 already asserts for a search run and the reason
that one works after a reload when nothing else does.

## Blast radius

- **Requirements affected here:** AC-13 by modification, which today says running a search from
  here shows progress and stops short of saying when. Two added, for rejoining a pass and for
  saying so on every screen.
- **Design decisions affected:** none reversed. The decision that these are separate pages rather
  than one application is what makes rejoining necessary rather than free, and it stands: a page
  that can be reloaded is the point, so a page that loses its state on reload is the bug.
- **Already-built code affected:** `web/static/settings.js` and `web/static/searches.js` (asking on
  load), `web/static/common.js` (the shared watcher, and the indicator in the shell every page
  draws), `web/app.py` and `web/wire.py` (one endpoint answering what is running, rather than four
  separate asks per page load), and `web/runs.py`, which currently is the memory that the store
  change replaces.
- **Depends on a change to another feature.** The third part needs
  `listing-store/changes/what-a-pass-is-doing/`. The first two do not, and are worth having either
  way; the ordering is store first, because writing the screens against the process's memory and
  then moving them to the store is two versions of the same work.
- **No change to what a pass does.** Nothing about extraction, enrichment, the digest or a run
  changes. This is about whether the interface can answer a question it currently cannot.

## What this is not

Not a notification. Nothing pops up, nothing steals focus, nothing follows you. A marker says
something is running and a panel says what; both are read when you look at them.

Not a second progress format. It is the same panel, the same lines and the same words the terminal
prints, shown in more places and at more moments.

Not a lock on the button. Pressing a running pass's button is already answered by the core with
"already running" and stays that way. The screen just stops pretending it does not know.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
