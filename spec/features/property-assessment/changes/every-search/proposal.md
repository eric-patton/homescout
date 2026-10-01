# Proposal: property-assessment

**Trigger:** On 2026-10-01 the person running searches pressed "Read each property against what you
want" for the paused Louisiana search and asked why it seemed to do nothing. Tracing it found two
things. The pass had worked and said only "done" (a defect against AC-1, fixed separately and
recorded in `tasks.md`). And the box beside the control, "Only this saved search (optional)", says
"all of them" when it is empty, while the core reads only the first saved search by name. Before
`la-one-offs` existed that happened to be `nm-statewide`; now an empty box reads the eight Louisiana
houses and silently skips New Mexico. The command line without `--search` does the same.

**Summary:** The spec says a pass runs over the properties in play "for a search" and never says
what a pass with no search named covers. The code answered with whichever file sorts first, which is
not an answer anybody chose and changes when somebody adds a search. This settles it the way the
rest of the product already does: an unnamed pass covers what a run of everything covers.

**Paused and archived are left out, exactly as a run of everything leaves them out.** A paused
search is one nobody is watching this month, and the command-line spec already says such a search is
skipped by a run of everything and still run when asked for by name. The same holds here: name it and
it is read.

**Each search against its own criteria.** The criteria are a search's description, its rules and its
notes, so there is no single set to read every property against.

**A property two searches share is read once per pass.** A reading is kept per property, not per
search, and its fingerprint includes the criteria. Reading a shared property against each search in
turn would pay for it twice, and each reading would make the other look stale, so the next pass would
pay twice again, forever. Read against the first search by name, which is a stable order, so the same
search owns it on every pass.

**A bounded pass is bounded as a whole.** "Just five, to try it" means five requests, not five per
search.

**A search with nothing in play does not fail the others.** One with no completed run, or a file that
cannot be read, is named and passed over rather than ending the pass.

**Blast radius.** `api.assess` gains the loop; `assess/pass_.assess_search` gains a way to be told
what an earlier search in the same pass already covered; the outcome is totalled across searches.
AC-1 is untouched and a new criterion, AC-20, says what an unnamed pass covers. The browser control
needs no change: what it already says becomes true. The command line's help for `--search` says what
leaving it out does.
