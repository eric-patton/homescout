# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-81 and AC-82.
They are numbered after the two `changes/say-what-you-count/` adds and the three
`changes/the-page-is-not-the-manual/` adds.

**User story.** As the person clearing a table of a thousand rows, I want to pass on forty of them in
one action, so that ruling out a town is a decision rather than forty decisions.

**User story.** As the person editing a search, I want to be told what I have not saved, so that
leaving the page is not how I find out.

- AC-81: A judgment can be set on several properties at once. A range of rows is selected from the
  pointer and from the keyboard, and one action keeps or passes on all of them. Everything AC-48
  requires of passing one property is required here: it asks first, in a dialog on the page that
  says what it does and how many it does it to, and dismissing it by any means leaves every row
  exactly as it was. The reason it collects is written to each property in the batch, because a
  reason recorded for forty houses at the moment forty were ruled out is as true of each of them as
  a reason typed on one.

  It is one operation in the core rather than a loop in the browser, which is what makes it
  reachable from the command line as AC-22 requires and what stops forty writes ending half done
  with no record of which half. The answer says how many were changed.

  **A batch that does not entirely succeed says so on the rows, which is AC-6 applying to forty
  rows rather than one.** The rows that were written show what was written; the rows that were not
  are marked as unsaved, keep what was being set, and are never presented as saved. A count of what
  changed that is smaller than the count asked for is reported as what it is, because the one thing
  this must never do is leave somebody believing forty houses were ruled out when thirty were.

  One action undoes the batch, and it is the same control that made it, which is AC-34's rule about
  setting a judgment applying to a batch unchanged.

- AC-82: A panel of the search builder that has unsaved changes says so, and leaving the page while
  any panel does is refused until it is confirmed. The four panels stay four, because they write
  four genuinely different parts of a definition and one button over all of them would write parts
  nobody touched, which AC-3 forbids by requiring that a definition opened and re-saved here is
  unchanged apart from the edits made. What is added is that the interface stops being silent about
  which parts are dirty.

## MODIFIED

- **AC-34.**
  - Was: the results table sets a property's judgment from a column of controls that is first on
    every row, in one action, without opening the property and without typing.
  - Now: the same for one property, and the same action applies to a selected range of them
    (AC-81). Setting it again to the same value still clears it back to unset, for a batch as for
    one, so the control that passes forty houses is the control that un-passes them.

- **AC-48.**
  - Was: passing on a property asks for confirmation first, in a dialog on the page rather than the
    browser's own, which says what passing does and that it is reversible.
  - Now: the same, and the dialog says how many properties it is about when it is about more than
    one. Keeping still asks nothing, for a batch as for one: it hides nothing and the same control
    undoes it.

## REMOVED

Nothing.
