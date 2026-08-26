# Proposal — browser-interface

**Trigger:** The person running searches asked for it, in these words: "Do we have a way of saying
'yes' or 'no' in the UI to a property so it is 'hidden' from us (and a way of 'unhiding'
something)?"

**Summary:** There is no way to be done with a house. The table shows every property a run kept, and
a place you have already looked at and ruled out sits there costing you the same attention as one
you have never seen. Over a statewide search that is the difference between a table you read and a
table you scroll past.

Everything needed is already here and none of it is joined up. A property carries an annotation
(rank, verdict, red flags, summary, next step, notes), it is written by a person and never by a run,
and it survives every future run, merge and re-export. `Verdict` is an editable column in the results
table today. What it does not do is change what you see: nothing filters the table by your own
judgment, and criteria deliberately cannot name an annotation, because a criterion is the tool's
test and an annotation is your conclusion.

This adds one three-state field, `judgment`: `keep`, `pass`, or unset. A property you have passed on
drops out of the results table until you ask for it back, in exactly the way a disappeared listing
already does behind the interface's existing "show gone" checkbox.

**`Verdict` stays free prose, and that separation is the point.** "No, but watch it if the price
moves" is a sentence worth keeping, and it should not be ambiguous about whether it hides anything.
The state hides; the prose says why.

**Nothing is deleted or stopped.** A passed property is still observed by every run, still
snapshotted, still compared, and still counted. It is hidden from a default view and from nothing
else, which is the same shape the export already uses for a property a criterion dropped
(`--include-dropped`) and the same shape the store already uses for a disappeared listing: absence
from a view is never absence from the record.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected here:** the results table's default contents and its filter controls. The
  interface already owns a "show gone" toggle and the "N disappeared and hidden" count line, and
  this is the second instance of that pattern rather than a new one.

- **The listing store (feat-001) gains a field.** `Annotation` is defined there, along with the
  three criteria that make it trustworthy: an annotation survives any merge and unmerge (AC-15,
  AC-16) and is never created, modified or deleted by a run (AC-17). `judgment` is an annotation
  field and inherits all three, which is the reason to put it there rather than invent a second kind
  of user state with its own rules. It needs a migration on the annotations table. That feature
  records this under "later changes by other features" when it is built, as the criteria builder did
  to the rule engine.

- **The command line (feat-003) must reach it.** Product invariant 5: every capability is reachable
  from both surfaces. `annotate` names its options one at a time rather than deriving them, so this
  is a `--judgment` flag and a value check, plus something equivalent to the table's toggle wherever
  the command line shows results.

- **The rule engine (feat-008) is deliberately untouched.** A criterion still cannot name an
  annotation. This was considered and rejected: letting a rule read your own verdict would make your
  conclusions an input to the tool's tests, and the two are kept apart on purpose.

- **The spreadsheet export (feat-011) is out of scope for this change, and the omission is
  deliberate rather than forgotten.** A sheet is a thing you take away and read elsewhere, where a
  passed house is context rather than clutter, and the export already has its own answer for
  "removed but retrievable". Whether a passed property should be absent from a sheet by default is a
  separate question and a separate change if the answer turns out to be yes.

- **Code touched:** the annotations table and its migration, the annotation model and its field
  list, the annotation API, the results payload, the results table's filter state and its count
  line, and the `annotate` command.

## What this is not

Not a delete, not an archive, and not a criterion. There is no path here that removes a property
from the store, and a passed house that comes back on the market is still observed, still recorded
and still reported as changed. It simply is not in front of you unless you ask.
