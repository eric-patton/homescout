# Proposal: browser-interface

**Trigger:** Reading the interface back after a while away: "The UI is kind of not great, especially
the various filters and links. Feels like the deleted stuff should be its own page not cluttering up
the searches too."

**Summary:** A saved search can be in four states and the list page shows all four of them. Active
searches are cards. Paused and archived searches are cards too, greyed, with a sentence underneath
explaining which of the two they are. Deleted searches come back at the bottom of the same page as a
row of "Bring back X" buttons that carry no description, no date and no way to be rid of them, and
that row only ever grows. The page whose job is "what happened overnight" is mostly lifecycle
administration for searches nobody is watching. Everything set aside moves to a surface of its own,
and the list holds what is being watched and nothing else.

The uncomfortable part is that the story this feature already carries asked for exactly this:
a search no longer wanted should stop "cluttering the list without taking the properties it found
with it". What was built satisfies its letter, because the deleted panel is technically below the
list rather than in it, and misses its point entirely. This is not a new idea, it is the old one
finished.

**And it closes a hole nobody had noticed.** There is currently no way to be finished with a search.
Deleting one keeps its file forever so it can be restored, which is right, and nothing anywhere
removes that file, which means the "Deleted" strip on the landing page is permanent. A tool that can
only accumulate is a tool that gets worse the longer it is used. So the set-aside surface is also
where a search is discarded for good, and that operation is built the way the only file-removing
operation in this interface should be: it asks for the name to be typed, and it says what survives
before it does anything.

## Blast radius

- **Requirements affected here:** AC-1 (which surfaces exist), AC-23 (setting a search aside),
  AC-27 (deleting one). The vocabulary section, which still says there are six surfaces and there
  are eight.
- **A new requirement with no precedent in this feature:** discarding a definition for good. Every
  other operation in this interface is reversible or additive. This one is not, which is why it gets
  its own criterion, its own confirmation shape, and its own test.
- **The core (`api.py`) gains two things:** `deleted_searches` must answer with what a card needs
  rather than a list of bare names, and a `discard_search` operation must exist at all. Both are
  core operations rather than browser ones, because the command line has to be able to do everything
  this surface can (AC-22), and a discard that only the browser could do would break that
  enumeration test.
- **Already-built code affected:** `web/static/searches.js` loses `deletedPanel()` and the archived
  toggle; `web/app.py` and `web/wire.py` gain a page route and two API routes; a new
  `web/static/archive.{html,js}`.
- **Tests affected:** `test_web_parity.py` has a test named for the archived toggle's behaviour
  (`test_the_archived_toggle_survives_the_last_one_being_brought_back`) that is about a control this
  change removes. It goes, and what replaces it is the surface that made the control unnecessary.
- **Nothing about a run changes.** No property is touched, no snapshot is removed, and discarding a
  definition leaves every property that search ever found exactly where it is. That is not a
  courtesy, it is non-negotiable 2 and product invariant 1, and the criterion states it because the
  operation is the one place somebody would reasonably fear otherwise.

## What this is not

Not a rename of "archived" to "deleted" or a collapse of the two into one state. They still mean
different things: an archived search is one nobody is watching that still runs when asked for by
name, a deleted one has stopped being a saved search. What changes is where they are read, not what
they are.

Not a way to delete history. Discarding removes one definition file. Every property, price and
judgment that search's runs recorded stays in the store, and the answer says how much of it there
is, for the same reason deleting already reports how many runs were kept: nobody should be left
believing more was removed than was.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
