# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Three acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-78, AC-79 and
AC-80. They are numbered after the two `changes/say-what-you-count/` adds.

**User story.** As the person who has used this tool before, I want the instructions out of the way
once I have read them, so that the screen is the work rather than the manual for it.

**User story.** As the person setting the optional parts up, I want what I configure separated from
what I run, so that the button I come back for every week is not seventh on a page of settings.

- AC-78: Explanation that is the same on every visit is behind a disclosure that names what it
  holds, rather than printed above the controls. It is open the first time somebody is on that
  surface and closed afterwards, remembered per browser like every other view preference and never
  written to the workspace. Nothing is removed: every sentence is one press away, and a disclosure
  that hid something a person needs on a later visit would be worse than the paragraph it replaced.

  Explanation that repeats is said once. A criterion's explanation of what it does belongs above
  the list of criteria rather than inside each of them, where fifteen criteria are fifteen copies
  of it and the rules themselves are what a person came to read.

- AC-79: What is configured and what is run are two surfaces. Configuring is the model, the mail
  account, the map's backgrounds and the broadband account, each of which is set up once and then
  reports itself. Running is attaching public data, asking a model about descriptions, writing the
  digest and writing a spreadsheet, each of which takes minutes and is come back to. The navigation
  has always named both; it now reaches both.

  Every section that exists still exists and nothing about what any of them does changes. Where a
  thing to run needs something configured, it says so and links to it rather than repeating its
  setup.

- AC-80: A figure in the overview strip that can be zero is drawn at zero rather than removed, so
  the strip is the same shape every morning. A count appearing is harder to notice than a count
  changing, which is exactly backwards for a strip whose job is telling somebody whether anything
  needs them today. A figure that is nothing at all on this installation, rather than zero, is still
  absent: there is a difference between "none today" and "this does not apply here".

## MODIFIED

- **AC-1.**
  - Was: nine surfaces exist and are reachable, including the settings surface.
  - Now: ten. The settings surface becomes two, one for what is configured and one for what is run
    (AC-79).

- **AC-24.**
  - Was: the parts of a saved search this interface edits are editable here, and a criterion is sent
    as the conditions a person chose.
  - Now: unchanged in every guarantee, and the explanation of what a criterion does is said once
    above the criteria rather than inside each one (AC-78).

## REMOVED

Nothing. No sentence is deleted, no section is dropped, and no control is taken away.
