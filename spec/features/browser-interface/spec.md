## Why

Two things need a screen: drawing the area a person actually means, and reviewing properties in a
wide table while writing judgment directly onto the row being read. The brief is explicit that the
second is what makes this a replacement for the spreadsheet rather than another producer of one. The
technology constraint is as load-bearing as any requirement here: plain HTML and vanilla JavaScript
on localhost, no framework and no second build toolchain, because a personal tool has to still start
in five years. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **surface** is one screen. There are six: the map and search builder, the saved search list, the
  results table, the listing detail, the run comparison, and the merge review queue.
- An **inline edit** is a change to an annotation made directly in a results table row, without
  navigating away from it.

## User stories

- As the person running searches, I want to draw the area I mean, including the parts to leave out,
  and save it as a search, so that "not the east side of town" becomes geometry rather than
  something I re-apply by eye.
- As the person running searches, I want every field in one wide table that I can sort and filter
  myself, so that I am not paging through properties one at a time.
- As the person running searches, I want to write my rank, verdict, red flags, and next step on the
  row I am reading, so that my judgment lands in the tool rather than in a separate spreadsheet.
- As the person running searches, I want one property's full picture on one page, including how its
  record was assembled from providers, so that I can tell a real record from a bad merge.
- As the person running searches, I want to see what changed since any earlier run, so that I can
  catch up after being away.
- As the person running searches, I want to resolve the matches the tool refused to guess at, so
  that its uncertainty becomes my decision rather than a silent error.
- As the person running searches, I want a search edited here to be the same file I can edit by
  hand, so that the two ways of working never fight.

## Behavior & scenarios

- **Scenario: drawing and saving a search**
  - Given the map surface
  - When areas are drawn and named, exclusions are drawn, filters and criteria are set, and the
    search is saved
  - Then a saved search definition exists containing that geometry, and running it from a terminal
    produces the same results as running it here

- **Scenario: a hand-written search round-trips**
  - Given a saved search written by hand, containing comments and a polygon
  - When it is opened here, one filter is changed, and it is saved
  - Then every other part of the definition is unchanged and the geometry is not degraded

- **Scenario: editing judgment in place**
  - Given the results table showing a property
  - When a rank, a verdict, a red flag, a summary, or a next step is typed directly into the row
  - Then the change is saved without leaving the table, is visible immediately, and is still there
    after the page is reloaded and after any number of later runs

- **Scenario: an edit that cannot be saved**
  - Given an inline edit and a store that refuses the write
  - When the save fails
  - Then the failure is shown on the row being edited, the typed value is not discarded, and the
    user is not left believing the edit was recorded

- **Scenario: criteria are visible as badges**
  - Given properties that tripped `flag` criteria
  - When the results table is shown
  - Then each carries a badge naming the criterion, and the default order reflects any `boost` and
    `demote` criteria until the user sorts explicitly

- **Scenario: a property's full picture**
  - Given the detail surface for one property
  - When it is opened
  - Then it shows its photographs, its full description, its enriched values, links to each
    provider's listing, its price and status timeline, and the provider rows the record was built
    from with the signal that justified each join

- **Scenario: comparing against an earlier run**
  - Given several completed runs
  - When a comparison against an earlier one is requested
  - Then each affected property is listed once with its difference event, matching what the same
    comparison produces from a terminal

- **Scenario: resolving an ambiguous match**
  - Given pairs awaiting a decision in the merge review queue
  - When a pair is decided as the same property or as different properties
  - Then the decision takes effect immediately, the pair leaves the queue, and it does not return in
    later runs

- **Scenario: running a search from here**
  - Given the saved search list
  - When a search is run
  - Then progress is visible, per-provider outcomes are shown on completion including any failure,
    and the resulting state is identical to running the same search from a terminal

- **Scenario: reachable only from this machine**
  - Given the server started with its defaults
  - When a connection is attempted from another machine on the network
  - Then it is refused, because the server is bound to the local interface only

## Acceptance criteria

- [ ] AC-1: Six surfaces exist and are reachable: map and search builder, saved search list, results
      table, listing detail, run comparison, and merge review queue.
- [ ] AC-2: Areas can be drawn, named, and edited on the map, including exclusion areas, and are
      saved as geometry in the saved search definition.
- [ ] AC-3: A saved search opened and re-saved here is unchanged apart from the edits made,
      including parts of the definition this interface does not itself edit.
- [ ] AC-4: Annotations are editable directly in a results table row without navigating away, and
      cover rank, verdict, red flags, summary, next step, and free notes.
- [ ] AC-5: An inline edit persists across a page reload and across any number of subsequent runs. A
      test asserts the value survives a run that also changes the property's price.
- [ ] AC-6: A failed save is surfaced on the affected row, retains the user's typed value, and never
      presents an unsaved edit as saved.
- [ ] AC-7: The results table shows every available column, and supports sorting and filtering
      without a round trip to the server for each interaction.
- [ ] AC-8: Criteria that fired are shown as badges naming the criterion, and the default ordering
      reflects boost and demote criteria until an explicit sort is chosen.
- [ ] AC-9: The listing detail shows photographs, the full description, enriched values, a link per
      provider, the price and status timeline, and the provider rows underneath the record with the
      signal that justified each join.
- [ ] AC-10: A value that is missing is displayed as missing and is visually distinguishable from a
      value that is known to be negative.
- [ ] AC-11: The run comparison surface produces the same result as the equivalent terminal
      comparison for the same two points in time.
- [ ] AC-12: Ambiguous match pairs are listed with the agreeing and conflicting signals, and a
      decision made here is durable and honored by later runs.
- [ ] AC-13: Running a search from here shows progress and per-provider outcomes, including
      failures, and leaves the store in the same state the equivalent terminal command would.
- [ ] AC-14: This layer contains no business logic. Every action calls a core operation, and a test
      asserts identical resulting state for an action performed here and through the core directly.
- [ ] AC-15: The server binds to the local interface only by default, and a connection from another
      machine is refused.
- [ ] AC-16: The interface is plain HTML and JavaScript served directly, with no
      single-page-application framework and no build step. A test asserts the served assets are the
      files as committed.
- [ ] AC-17: Every surface is fully operable by keyboard, including inline annotation editing and
      the merge review decisions.
- [ ] AC-18: No information is conveyed by color alone. Every badge, status, and difference event
      carries a text label.

## Edge cases & errors

- The results table holds several thousand rows. Sorting and filtering remain responsive, which
  constrains how the table is built but is not satisfied by silently paginating away rows the user
  asked to see.
- A property has no coordinates and cannot be placed on the map. It still appears in the table,
  marked as not locatable.
- A property has no photographs. The detail surface renders without them rather than showing broken
  images.
- A photograph the provider has since removed. The stored preview still renders; the full gallery
  shows the images that still load and does not present a wall of broken frames.
- Two browser tabs edit the same annotation. The last write wins, consistent with the store's
  decision, and the other tab shows the current value on its next read rather than silently holding
  a stale one.
- A run is in progress when the table is opened. The table shows the last completed state and
  indicates that a run is under way, rather than showing a half-written run.
- The store is locked because a terminal command is running. The interface reports it in terms
  naming the likely cause rather than failing opaquely.
- A drawn polygon self-intersects. It is rejected at draw time with an explanation, not saved and
  failed at run time.
- The merge review queue is empty. The surface says so plainly rather than appearing broken.

## Non-functional requirements

- Performance: a results table of 5,000 rows becomes interactive within three seconds, and sorting
  or filtering it responds within 200 milliseconds without contacting the server.
- Security: bound to the local interface, single user, no authentication by design. Every value
  originating from a provider or from a user note is rendered as text and never as markup, so no
  listing description can inject content into the page.
- Reliability: an interface error affects the surface being used and never leaves an annotation
  half-written or a saved search partially overwritten.
- Accessibility: fully keyboard operable, legible at default zoom, and conveying nothing by color
  alone.

## Open questions

None.
