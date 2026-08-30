## Why

Two things need a screen: drawing the area a person actually means, and reviewing properties in a
wide table while writing judgment directly onto the row being read. The brief is explicit that the
second is what makes this a replacement for the spreadsheet rather than another producer of one. The
technology constraint is as load-bearing as any requirement here: plain HTML and vanilla JavaScript
on localhost, no framework and no second build toolchain, because a personal tool has to still start
in five years. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **surface** is one screen. There are ten: the search builder, the saved search list, the
  results table, the listing detail, the run comparison, the merge review queue, the map, the
  settings surface, the tools, and the surface holding what has been set aside.

  The first is the search builder rather than "the map and search builder", and the seventh is the
  map. The surface that draws the wildfire hazard model also draws either background, which way the
  wind pushes, county lines, town names, rainfall and a ruler, so it has the word outright: two
  surfaces whose names both contain "map" is the ambiguity that rename exists to remove. The search
  builder still has a map on it, and what that map is for is drawing the areas a search covers.
- An **inline edit** is a change to an annotation made directly in a results table row, without
  navigating away from it.
- A **judgment** is the person's own decision about whether a property is still worth their
  attention: `keep`, `pass`, or nothing at all. Nothing is the starting state and means undecided,
  which is a different thing from `keep`: one is a house nobody has looked at, the other is a house
  somebody looked at and kept. A property whose judgment is `pass` is **passed**, and a passed
  property is hidden from the default results view and from nowhere else.

## User stories

- As the person running searches, I want to draw the area I mean, including the parts to leave out,
  and save it as a search, so that "not the east side of town" becomes geometry rather than
  something I re-apply by eye.
- As the person running searches, I want every field in one wide table that I can sort and filter
  myself, so that I am not paging through properties one at a time.
- As the person reading a thousand rows, I want to narrow one column at a time by typing what its
  value should contain, so that I can ask a question about a particular column instead of about
  every column at once.
- As the person reading a thousand rows, I want the table to open on the columns I decide with, so
  that the address and the price are not four screens apart on a table I have not arranged yet.
- As the person putting columns away, I want the chooser sorted by where a value comes from, so
  that finding the flood zone is looking in one place rather than reading forty-three names.
- As the person reading four screens about the same search, I want each number to say what it is
  counting, so that four different totals read as four questions rather than as a fault.
- As the person who has used this tool before, I want the instructions out of the way once I have
  read them, so that the screen is the work rather than the manual for it.
- As the person setting the optional parts up, I want what I configure separated from what I run,
  so that the button I come back for every week is not seventh on a page of settings.
- As the person clearing a table of a thousand rows, I want to pass on forty of them in one action,
  so that ruling out a town is a decision rather than forty decisions.
- As the person editing a search, I want to be told what I have not saved, so that leaving the page
  is not how I find out.
- As the person choosing where to live, I want to measure how far a house is from something on the
  map, so that "too close to the red" is a number rather than an impression.
- As the person choosing where to live, I want to see which way the wind normally blows here, so
  that I can tell a house upwind of a hazard from a house downwind of the same hazard.
- As the person running searches, I want to write my rank, verdict, red flags, and next step on the
  row I am reading, so that my judgment lands in the tool rather than in a separate spreadsheet.
- As the person running searches, I want one property's full picture on one page, including how its
  record was assembled from sources, so that I can tell a real record from a bad merge.
- As the person running searches, I want to see what changed since any earlier run, so that I can
  catch up after being away.
- As the person running searches, I want to make a new search, copy one, set one aside without
  deleting it, and delete one I am truly finished with, so that the browser is somewhere I can keep
  the set of searches rather than only look at it, and so that a search I no longer want leaves the
  list entirely, is still somewhere I can find it and bring it back, and can finally be discarded
  when I am sure, without taking the properties it found with it.
- As the person running searches, I want everything I have set aside kept somewhere other than the
  list of what I am watching, so that opening the tool in the morning shows me the searches that
  ran and not the ones I stopped caring about.
- As the person running searches, I want to be finished with a search for good, so that a tool I
  have used for a year is not carrying every experiment I ever made.
- As the person running searches, I want a link to say where it goes, so that I do not have to open
  a screen to find out it does more than its name admits.
- As the person running searches, I want to see at a glance which properties the model raised
  something about, so that a table of a hundred and fifty rows tells me where to look.

- As the person running searches, I want the whole of what it said about one property without
  leaving the page, so that reading an assessment is not a decision to navigate away from what I
  was doing.

- As the person running searches, I want to leave a pass running and come back to it, so that a job
  that takes twenty minutes does not require me to sit in front of it.

- As the person running searches, I want any screen to tell me something is still going, so that I
  do not have to go looking for the one page that might know.

- As the person running searches, I want pressing a button on a pass the nightly job is already
  running to say so, so that I do not quietly start the same work twice.

- As the person running searches, I want the controls on a screen sorted by what they do, so that I
  can find the one I want by looking rather than by reading all of them.
- As the person running searches, I want to move between the screens about one search without going
  back to the list each time, so that reading a property, checking what changed and looking at
  where it is are one task rather than three.
- As the person running searches, I want to set up the optional parts (a model to read descriptions,
  a background for the maps) from the screen that tells me they are off, so that turning one on does
  not mean finding a file and knowing its variable names.
- As the person running searches, I want to see both houses on the card, so that the pairs that are
  obviously one house take a glance rather than two tabs.
- As the person running searches, I want to resolve the matches the tool refused to guess at, so
  that its uncertainty becomes my decision rather than a silent error.
- As the person running searches, I want a search edited here to be the same file I can edit by
  hand, so that the two ways of working never fight.

- As the person running searches, I want to say no to a property once and stop seeing it, so that
  the houses I have already ruled out do not cost me the same attention every night as the ones I
  have not seen.
- As the person running searches, I want to see what I passed on when I ask, so that a decision I
  made in a hurry is one I can go back and check rather than one that has vanished.
- As the person running searches, I want saying no to be one click rather than a sentence I have to
  type, so that clearing a table of forty houses is a thing I actually do.

## Behavior & scenarios

- **Scenario: drawing and saving a search**
  - Given the search builder
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
    source's listing, its price and status timeline, and the source rows the record was built
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
  - Then progress is visible, per-source outcomes are shown on completion including any failure,
    and the resulting state is identical to running the same search from a terminal

- **Scenario: reachable only from this machine**
  - Given the server started with its defaults
  - When a connection is attempted from another machine on the network
  - Then it is refused, because the server is bound to the local interface only

- **Scenario: reached through a proxy on the same machine**
  - Given a reverse proxy on this machine forwarding to the interface, and its name configured
  - When a request arrives through it
  - Then it is answered, the server having listened on the local interface throughout, and a request
    naming any other host is still refused

- **Scenario: setting a search aside**
  - Given a saved search that is not being watched at the moment
  - When it is paused, or archived, from the list
  - Then nothing about it is deleted, a run of everything leaves it alone and says so, and running it
    by name still runs it

- **Scenario: deleting a saved search**
  - Given a saved search that is no longer wanted
  - When it is deleted from the list
  - Then it stops being a saved search at once, its definition is kept where it can be brought back
    from, everything its runs recorded stays in the store, and the interface says both of those
    things at the point the deletion is offered

- **Scenario: turning on something that is off**
  - Given the interface reporting that descriptions are not being read by a model
  - When a model's address and name are given on the settings surface
  - Then they are written to the uncommitted file beside the database, they take effect without a
    restart, and a credential is not asked for and cannot be written from here

- **Scenario: a map with nothing behind it**
  - Given no tile server configured, which is the default
  - When the search builder is opened
  - Then it draws a labelled coordinate grid that can be drawn over, says what is missing, and offers
    to turn a background on with what that costs stated beside the offer

## Acceptance criteria

- [ ] AC-1: Nine surfaces exist and are reachable: the search builder, the saved search list,
      the results table, the listing detail, the run comparison, the merge review queue, the map,
      the settings surface, the tools, and the surface holding what has been set aside.

      The settings surface has existed since the optional parts became configurable from the screen
      that reports them off, and was not written down here until the count moved for another
      reason. The tools were seventh on it: what is configured once and what is come back to and
      run are two different visits, and they are two surfaces now (AC-79).
- [ ] AC-2: Areas can be drawn, named, and edited on the search builder's map, including exclusion areas, and are
      saved as geometry in the saved search definition.
- [ ] AC-3: A saved search opened and re-saved here is unchanged apart from the edits made,
      including parts of the definition this interface does not itself edit.
- [ ] AC-4: Annotations are editable directly in a results table row without navigating away, and
      cover rank, verdict, red flags, summary, next step, free notes, and the household's own five
      headings. A cell holding prose opens into a box the size of what somebody writes in it, over
      the row it belongs to and naming the property, rather than into a single line the height of a
      table row; a number keeps the single line. Enter makes a new line in prose, so saving is the
      button, or Ctrl with Enter, or clicking away, and only Escape discards.
- [ ] AC-5: An inline edit persists across a page reload and across any number of subsequent runs. A
      test asserts the value survives a run that also changes the property's price.
- [ ] AC-6: A failed save is surfaced on the affected row, retains the user's typed value, and never
      presents an unsaved edit as saved.
- [ ] AC-7: The results table shows every available column, minus the properties the person has
      passed on, and supports sorting and filtering without a round trip to the server for each
      interaction. Filtering is two things and both work that way: one box that searches every
      column at once, and the per-column filters of AC-57. Passed properties are shown when asked
      for; the control for that sits with the one for properties that disappeared, because they are
      the same pattern.
- [ ] AC-8: Criteria that fired are shown as badges naming the criterion, and the default ordering
      reflects boost and demote criteria until an explicit sort is chosen.
- [ ] AC-9: A property with no address is titled by what is known about it (AC-77) rather than by
      its identifier. The listing detail shows photographs, the full description, enriched values, a link per
      source, the price and status timeline, and the source rows underneath the record with the
      signal that justified each join.
- [ ] AC-10: A value that is missing is displayed as missing and is visually distinguishable from a
      value that is known to be negative.
- [ ] AC-11: A property with no address is listed by what is known about it (AC-77). The run comparison surface produces the same result as the equivalent terminal
      comparison for the same two points in time.
- [ ] AC-12: Ambiguous match pairs are listed with the agreeing and conflicting signals, and with
      the two properties themselves, so a decision can be made from the card rather than from two
      other tabs. A decision made here is durable and honored by later runs.
- [ ] AC-13: Running a search from here shows progress and per-source outcomes, including
      failures, and leaves the store in the same state the equivalent terminal command would.
      Progress is visible whenever the screen is looked at rather than only in the tab that started
      the run: a run under way is reported to a page that has just loaded, including one that has
      never seen this run and one in another browser, and including a run started from a terminal or
      by the scheduled job. What is shown is the run's own progress lines and, on completion, its
      per-source outcomes.
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
- [ ] AC-19: Notes about an area or a town can be written and edited, addressed by the area they
      describe rather than by a property, and are the notes the spreadsheet export's second sheet
      carries. They are writable from the results table too, where the opinion is formed, and the
      cell says whose note it is before it is opened: writing one from a row writes it for every
      property in that town, and those rows take it there and then rather than at the next reload.
- [ ] AC-20: Properties whose presence is `disappeared` are hidden from the results table by
      default and are shown by an explicit filter, which is always available and reports how many
      are hidden. The number is reported where every other reason a row is missing is reported, in
      the bar above the table (AC-57), with its own control to lift it.

      This criterion used to name the mechanism as well: "one of the table's four view toggles,
      alongside the ones for passed properties, photographs and wrapped text". There are not four
      any more, because the two that hid rows became one control with four answers and this one
      became a statement in the bar. A criterion that counts the controls on a screen dates the
      moment the screen is rearranged, and this one had dated twice. What must be true of the
      hiding is that it is explicit, reversible, and counted where the other reasons are counted.
      Photographs (AC-43) and wrapped text (AC-47) hide no rows and belong with the columns.
- [ ] AC-21: The server answers to the loopback names and to no others, unless a name is explicitly
      configured. A configured name is how a reverse proxy running on the same machine reaches it,
      and it changes nothing about where the server listens. A name that was not configured is
      refused, and so is a request from another site's page and one that changes something without
      the header a form cannot set. A test exercises a configured proxy name, an unconfigured one,
      and the default, which is loopback and nothing else.
- [ ] AC-22: Everything the command line can do is reachable from here. A test enumerates the
      command line's commands and asserts each one has a route that reaches the same core operation,
      so a capability added to one surface cannot quietly be missing from the other.
- [ ] AC-23: A saved search can be created, copied, paused, resumed, archived, and brought back from
      the interface. None of these six deletes anything. A paused or archived search is skipped by a
      run of everything, which reports that it skipped it, and still runs when asked for by name.

      Bringing an archived search back happens on the set-aside surface (AC-69) rather than from a
      control that reveals archived searches among the watched ones. A paused search stays on the
      list, because a pause is a search somebody is still watching and means to resume, and a pause
      that made the search vanish is a pause nobody would use.
- [ ] AC-24: The parts of a saved search this interface edits (its description, its sources, its
      filters, whether a model reads its descriptions, and its criteria) are editable here, and
      AC-3's guarantee holds for every edit made through them. A criterion is sent as the conditions
      a person chose, and the expression is composed by the rule engine rather than by the
      interface, so the grammar has one home and the file gets the same line somebody would have
      typed. What each kind of criterion does is said once above the list rather than inside each
      of them (AC-78).
- [ ] AC-25: The optional configuration (which model reads descriptions, where map tiles come
      from, where the digest is written) is editable here and written to the uncommitted file beside
      the database, taking effect without a restart and leaving the rest of that file, comments
      included, exactly as it was. A setting whose name looks like a credential is refused, and no
      credential is ever displayed.
- [ ] AC-26: With no tile server configured, the search builder's map draws a labelled coordinate grid, says what is
      missing, and offers to turn a background on with the privacy cost stated beside the offer
      rather than in a document.
- [ ] AC-27: A saved search can be deleted. It leaves the list at once, is skipped by a run of
      everything, and is not found when asked for by name. Two limits hold and are stated where the
      deletion is offered rather than only in a document. The definition is kept rather than
      unlinked, so it can be restored with its areas and comments intact, and the interface offers
      that restoration on the set-aside surface (AC-69) rather than at the foot of the list of
      searches. Deleting is still offered from the search's own card, because that is where somebody
      decides it. And nothing a run recorded is removed: the properties, their price history
      and any judgment written on them survive, because non-negotiable 2 and product invariant 1
      make snapshot history append-only. The answer reports how many runs were kept, so nobody is
      left believing more was removed than was.
- [ ] AC-28: A criterion is built by choosing, not by typing an expression. Its field, its
      comparison and its value are each chosen from what is possible, conditions can be added and
      removed, and criteria can be added and removed.
- [ ] AC-29: What a value may be follows the field that was chosen. A field with a closed set of
      values offers exactly that set; a number offers a number; a true-or-false offers yes and no.
      A comparison that cannot apply to the chosen field is not offered.
- [ ] AC-30: Nothing on any screen shows a person the name a field has in the code. Every field,
      value, comparison and severity is shown in words chosen for a reader, and those words are
      declared once in the core rather than in a surface.
- [ ] AC-31: A criterion that cannot be shown as conditions is shown as the expression it is,
      marked as such, and is not rewritten. Saving the other criteria leaves it exactly as written.
- [ ] AC-32: The interface offers a set of ready-made criteria that are one click to add and
      ordinary to edit or remove afterwards, so that the first criterion somebody has is not one
      they had to invent.
- [ ] AC-33: A property carries a judgment of `keep`, `pass`, or unset. It is an annotation: written
      only by a person, never by a run, and surviving every subsequent run, merge, unmerge and
      re-export, which is the listing store's AC-15, AC-16 and AC-17 applying to it unchanged.
- [ ] AC-34: The results table sets a property's judgment from a column of controls that is first
      on every row (AC-49), in one action, without
      opening the property and without typing, and the same action applies to a selected range of
      them (AC-81). Setting it again to the same value clears it back to unset, for a batch as for
      one, so the control that passes forty houses is the control that un-passes them.
- [ ] AC-35: A passed property is absent from the results table by default. Which properties are
      shown by judgment is one control with one answer in force at a time: the ones still in play,
      the ones kept, the ones passed on, or all of them. In play means everything not passed on,
      which is the undecided and the kept together, and it is the default because a kept property
      is on the shortlist and AC-49 says it is hidden from nothing. A test covers each answer.

      One control because it is one question about one field. Two controls over it could express a
      state the table could not be in, and had to be applied in a careful order so that "only what
      you kept" and "show passed" could not contradict each other. One answer cannot contradict
      itself.
- [ ] AC-36: When passed properties are hidden, their number is reported, in the same place and the
      same form as every other reason the table is narrowed: as a statement in the bar above it,
      in words, carrying the number it is holding back and its own control to lift it (AC-57). A
      table that is quietly shorter than the run that produced it is not acceptable; the difference
      has to be visible without being asked for, and the defence against it is one place a person
      looks rather than two.

      Two kinds of fact were run together in one line: how many properties there are, which is a
      total nobody can act on, and why some are missing, which is a reason and is something a
      person may want to undo. The totals stay in a line under the controls, which says how many
      are drawn, out of how many the run found, and how many are kept. The reasons are in the bar.
      Nothing is said in both places, and how long the table took to draw is said in neither.
- [ ] AC-37: Passing a property changes what is displayed and nothing else. It is still observed by
      every run, still snapshotted, still compared, still counted in a run's totals, and still
      reported as new, changed, gone or returned in the digest. A test asserts a passed property
      still appears in a run's comparison.
- [ ] AC-38: A criterion cannot name a judgment. The rule engine's declared namespace gains nothing
      from this change, so a person's conclusion can never become an input to the tool's own tests.
- [ ] AC-39: The judgment is settable and readable from the command line as well as the browser, and
      the command line can list what has been passed, satisfying product invariant 5. Whether a
      property is hidden by default is decided in the core and read by both surfaces, so neither
      holds its own copy of that rule.
- [ ] AC-40: Each queued pair shows, for every record in it, its stored photograph, address, price,
      size and the sources it was seen by. A record with no stored photograph is shown as having
      none, in the same shape as one that has, so the records stay aligned and the absence is
      legible. Nothing is fetched to satisfy this: the images and the summary come from what the
      store already holds.
- [ ] AC-41: The summary a review needs is assembled in the core and read by both surfaces. The
      terminal lists the same addresses, prices and sources for the same pairs, and neither surface
      works out for itself what a pair is.
- [ ] AC-42: The results table offers a link to the property on every site it was found on, each
      named by its site, rather than one address for a record assembled from several. The sites are
      not interchangeable: a person keeping a shortlist on one of them can only add that site's own
      page, and a site the property was never seen on contributes no link rather than a broken one.
      Where only one address is held, the cell reads as it did before.
- [ ] AC-43: The results table can show each property's stored photograph beside its address, off by
      default and turned on from the same row of controls as the other view toggles. The picture is
      the one this tool stored, so drawing the table asks nothing of any listing site and a property
      that has disappeared still has its photograph. A property with none holds the same space, so
      the addresses stay in a straight line to run an eye down.
- [ ] AC-44: A column can be moved to another position and set to another width, by pointer and by
      keyboard, and doing either changes nothing about what the column holds or what it is called.
- [ ] AC-45: The arrangement of the columns is remembered per browser and per saved search, and a
      control returns it to the opening view (AC-74). It is a view preference and is never written
      to the workspace, so two people reading one workspace arrange it independently. Where the
      browser cannot store it, the table opens on that view and every other part of the page
      behaves identically. A column that did not exist when an arrangement was saved appears beside
      the column it is declared beside, never on the end: a remembered arrangement names every
      column there was, so on the end means past the right edge of a table forty columns wide, and
      a column nobody can see is a capability nobody has. Nothing somebody placed themselves is
      moved by this.
- [ ] AC-46: Every column is either filled by this tool or written by the person, and its heading
      says which, so that an empty cell is never read as the tool having failed at something it was
      not doing. There is no third kind: a column that is neither filled nor writable is a heading
      with an apology under it.
- [ ] AC-47: Long text can be made to wrap, from the same row of controls as the other view
      toggles, and a wrapped row is as tall as its own text needs. Nothing is cut off and nothing is
      left to a tooltip to make up for: a control that says "wrap long text" and then shows three
      lines of it is a control that does not do what it says.

      So while wrapping is on the table places rows from measured heights rather than from one
      height times a count. A row that has been drawn carries its measurement; a row that has not is
      a guess, and the guess only ever decides where the scrollbar sits, never what is on the
      screen. Two things follow from that and both are required rather than tolerated. The height of
      the whole table changes as somebody scrolls into rows nobody has looked at, which is what a
      scrollbar over unmeasured content is everywhere such a thing exists. And the row under the top
      of the window does not move while that happens, because a correction that shoves the line
      somebody is reading off the screen is worse than the estimate it corrects.

      A row with nothing long in it stays the height it was, and no row is taller than what is in it
      needs. With wrapping off, every row is one height and is placed by arithmetic, which is what a
      thousand rows without measuring any of them requires.
- [ ] AC-52: A column can be hidden from this screen, by right-clicking its heading and by the
      keyboard, and brought back from a chooser that lists every column, grouped by where each
      value comes from (AC-75) rather than as one flat list of them all. Hiding is remembered
      alongside the order and the widths, and a column comes back where it was rather than on the
      end. It changes what this screen draws and nothing else: every column stays in the answer and
      in the spreadsheet. The control column cannot be hidden.
- [ ] AC-53: The table's own box ends within the window, so the horizontal scrollbar on its bottom
      edge is reachable, and the page behind it does not scroll. Its height is measured from where
      the box actually falls rather than assumed, so it stays right as the controls wrap and the
      window changes. Its column headings stay on screen for the whole of the list, however far down
      it is scrolled: a heading that leaves partway is worse than one that never stuck, because it
      works long enough to be trusted and the first anybody knows is a screen of prices, acreages and
      years with nothing above them.
- [ ] AC-48: Passing on a property asks for confirmation first, in a dialog on the page rather than
      the browser's own, which says what passing does, that it is reversible, and how many
      properties it is about when it is about more than one. Dismissing it by any means, including
      the keyboard, leaves every property it named exactly as it was. Keeping a property asks
      nothing, for a batch as for one: it hides nothing, and the same control undoes it.
- [ ] AC-49: Keeping and passing are the first thing on a row, in a column of their own that cannot
      be moved or displaced, so the controls are in one place on every row of every arrangement. A
      kept property is on the shortlist and is hidden from nothing; narrowing to the shortlist alone
      is one of the answers of AC-35's control rather than a box of its own, and the number kept is
      reported in the line of totals, because how many have been kept is a fact about the search
      rather than a reason a row is missing. The shortlist is
      readable from the command line as well, which is product invariant 5 applying to it exactly as
      it applies to the passed list.
- [ ] AC-54: Keeping a property and passing on one both ask why, in their own words, at the moment
      the decision is made, because a reason recorded later is a reconstruction. The reason is
      wanted and never demanded: an empty answer records the decision and nothing else, and clearing
      forty houses must not mean typing forty times. It is kept as the property's verdict, which is
      the field that already means what the person concluded about the house, so it exports and
      prints alongside the kept and passed lists without anything new to read it. Passing asks
      before acting, because it takes the house out of the table; keeping records the keep first and
      asks afterwards, because it hides nothing and the same control undoes it.
- [ ] AC-55: Every property in a run that has a location is drawn on the wildfire hazard model,
      using the same layer at the same configured address the enrichment pass reads, with its own
      legend drawn from this tool rather than fetched. A property with no location is not drawn, and
      is counted and said so. How strongly the hazard layer is drawn can be turned down to read the
      map beneath it. Drawing it asks that server for the part of the country on screen, which the
      page states, because nothing else here does that unless a map background has been turned on.
- [ ] AC-56: A property can be kept or passed on from its pin, with the same question about why and
      the same effect as from the results table, and the map reflects the decision at once. No
      property is scored, ranked, hidden or coloured by its distance from anything, and the only
      reason one is left off the map is a judgment the person made themselves, because anything else
      would be a criterion with no rule behind it and no way to argue with it. The page may measure
      a distance somebody asked it to measure (AC-58); what it may not do is decide something about
      a house from one.

      The bubble carries the photograph this tool stored, which is the one thing about a house that
      neither a pin nor a row of numbers can say. It is the stored copy served from this machine, so
      opening a pin on a screenful of houses still asks no listing site anything; pressing it opens
      every photograph the listing carried, which is the one thing on this page that does ask, and
      it says so while it does. It is never drawn larger than it was stored, because most of what
      the sites hand over is a small picture and a small picture blown up to fill a frame reads as a
      fault in this tool. A property with no stored photograph gets no frame at all, which is the
      opposite of the results table's rule and right for the same reason: there an empty box keeps a
      column of addresses in a straight line, and here there is one bubble on its own.
- [ ] AC-50: The spreadsheet can be downloaded from the results table itself, in either format the
      export writes, without going to another screen and without being told a path to go and find.
      It is the same core operation the terminal calls and still writes its copy into the workspace,
      so a sheet taken from the browser and a sheet taken from the terminal are one file made one
      way. A format the export does not write is refused in words rather than written.
- [ ] AC-51: Every photograph a listing carried can be looked through, one at a time and at the size
      the window allows, from the stored thumbnail on the results table, from the picture in a pin's
      bubble on the map, and from the property's own page. These pictures are the listing site's rather than this tool's, so nothing is asked of
      any listing site until somebody opens the gallery, and the gallery says where they come from:
      it is the one place in this product where looking at a property is not free of the site it was
      found on. A listing that carried none says so rather than opening an empty gallery. What a
      site hands over is a thumbnail address, so the gallery asks for the full-size rendition where
      the site's addressing scheme says how; that is a rule about somebody else's scheme, so a
      rewritten address that fails to load falls back to the stored one rather than showing nothing,
      and an address from a site with no such rule is used exactly as it was given.
- [ ] AC-57: Every column that can be sorted can be filtered, from a control on its own heading that
      opens a box for plain text. A row is kept when the text appears in what that column shows for
      it, matched without regard to case and against the cell as displayed rather than as stored, so
      that a price typed the way it is printed matches it and "not known" finds the properties
      nobody could determine that column for. Filters on several columns all apply, together with
      the whole-table search box, and are applied in the browser without contacting the server.
      Every reason the table is showing fewer rows than the run found is named in words above the
      table with its own control to lift it, and one control lifts all of them. That is the column
      filters, the whole-table search, the judgment being narrowed to anything but all of them, and
      the properties that have come off the market being held back; each says how many rows it is
      holding, which is what satisfies AC-36 and AC-20 for the two that hide by the thousand. The
      bar is drawn on arrival rather than once somebody touches a filter, because the judgment
      narrows the table by default and a bar that waited would be silent for exactly the person who
      has not worked out why the table is short. A filter narrows what is drawn
      and changes nothing else: no property is altered, judged or deleted by one, and none of it is
      remembered past the visit, because a narrowing that came back days later would hide rows for a
      reason nobody remembers setting.
- [ ] AC-58: The map carries a scale that reports the distance across the screen in miles and
      follows the zoom. It also offers a ruler, off by default, laid across the middle of what is on
      screen: either end can be moved to a point on the map, the whole ruler can be carried
      elsewhere without changing its length, and it reads the distance between its ends in miles, or
      in feet below the point where a mile is no longer a useful picture. It is operable by pointer
      and by keyboard, in steps taken from what is on screen rather than in fixed degrees. A scale
      fixed in a corner cannot be held up against two things that are somewhere else on the map,
      which is the whole reason the second one exists.
- [ ] AC-59: The map can draw which way the wind pushes, off by default, per weather station
      over that station's whole recorded history rather than as any forecast. It draws one arrow per
      station, pointing the way the wind most often pushes and longer where the wind more often does
      the same thing, and a second arrow only where hard wind pushes somewhere the everyday wind
      does not, because that is the one case where a station has two answers rather than one. It
      still holds, for each of sixteen directions, how often the wind pushed that way and how often
      it did so at fifteen miles an hour or more, and opens into those numbers with the number of
      readings and the years they span: the question the drawing answers has one direction in it and
      the question the numbers answer has sixteen, and only the first belongs on a map. The whole year and the single month that is both windiest and in fire season are both
      offered. Every direction a reader is shown is the direction the wind pushes, in the drawing and
      in the words together, and never the meteorological direction it came from: the reader is
      somebody buying a house, the question is which way a fire would run, and the two readings name
      opposite sides of that house as the side to worry about. What is fetched and stored keeps the
      archive's own convention; the turn happens once, where the drawing is. Only the stations on
      screen are asked about, each exactly once ever, and what is on its way is visible as such. A
      station or a state that cannot be read is reported and does not stop the others being drawn.
      Nothing is scored, ranked, hidden or coloured by wind: the page reports what was recorded and
      the person decides.

      An arrow is drawn at a fixed size at every zoom, so the box it is drawn in is large and mostly
      empty, and it and the mark for a station still being read are both drawn over the properties.
      Only the arrow's own ink answers to the pointer, under the rule in AC-60: nothing drawn over
      the properties takes the pointer off them except at the pixels where it is actually drawn.
- [ ] AC-60: The map can draw county lines and town names over the hazard layer, off by
      default, from the same public boundary service the rest of this tool uses, fetched once per
      state and kept. They are drawn over the layer and not under it, because underneath is where
      the map's own names already are and a raster opaque enough to read is a raster that hides
      them: the moment this map becomes useful it also becomes anonymous. More town names appear as
      the map is zoomed in, biggest first, and a name that would sit on top of another is not drawn
      at all, because two names in the same place is neither name. A state that cannot be read is
      reported and does not stop the others.

      **Nothing drawn over the properties takes the pointer off them except where it is actually
      drawn.** This is a rule about every layer over the map rather than about names, and it has to
      be stated as one because each layer breaks it in a different way and the symptom is always
      the same: houses that will not open, and a pointer that never says one is there. A name is
      read and never clicked, so it takes no pointer at all. An arrow is opened, so its ink does
      and the empty box around it does not. And a layer of outlines nobody clicks still has to say
      so at the layer, not at the shapes, because these shapes are drawn on a canvas and a canvas
      is one element covering everything beneath it whether anything is painted there or not.
- [ ] AC-61: The map can draw how much rain and snow a county gets in a year, off by default,
      as an average over the last thirty complete years the national record holds, written under
      that county's name with its unit. Rain *and snow*, and the page says so: the national record
      measures frozen precipitation by melting it, so a mountain county's real winter is written
      down as a small number, and reading the wettest county against the driest as a difference in
      rain misses that most of the gap is snow. An average and not a year: a single year here is a story about
      one monsoon, and what somebody buying land is asking is what the place is normally like. It is
      per county because that is the finest grain the record publishes, and the page says so rather
      than interpolating a figure that would look like it was measured at the house. Turning it on
      turns the county names on with it, because the number is written under a name and a number
      floating on an unnamed patch of map is a number about nothing. Nothing is scored, ranked,
      hidden or coloured by rainfall. A county that cannot be read is named and the rest are still
      drawn, with lines and a name and no number.
- [ ] AC-62: The map shows the properties currently on it as a list underneath it, holding
      exactly the pins the map is drawing and hiding whatever the map hides, re-read whenever the
      map moves. A pin is very good at "where" and says nothing until it is opened, so reading a
      screenful of them means opening every one; the list is the same look with the numbers in it.
      It can be sorted by any of its columns and starts cheapest first. Its address opens that
      property's pin where it stands rather than travelling to it, because the pin is already on
      screen and a map that jumps whenever a row is read loses the place somebody was looking at.
      Beyond a few hundred rows it draws what can be read and says plainly how many there are.
- [ ] AC-63: A property's tags are shown and set from the results table, in a column like any other
      and filterable like any other. Setting them offers the words already in use, ticked or not,
      with one line to make a new one, rather than a box to type a list into: a vocabulary somebody
      retypes from memory grows a second spelling of every word in it, and nothing on the page would
      ever say that had happened. What is sent is the whole list, because that is what a set of
      ticked boxes is. The property's own page shows them and does not set them, like every other
      annotation.

      The cell opens on a single press, unlike every other writable column, and the difference
      follows what the cell is: the others are boxes somebody types into, so one press has to mean
      "select this cell" and leave the keyboard free to move on, while this one holds a list and
      pressing it opens the list. A cell carrying no tags says so with a mark rather than being
      blank, because blank is this table's word for "nobody has written anything" and what an
      empty tag cell also has to say is that there is something here to press.
- [ ] AC-67: The map and the results table hide the same properties, by the same rules, with the
      same controls and the same words on them. A property passed on is hidden from both; a property
      that has come off the market is hidden from both; either can be brought back from either page.

      Two surfaces over one library are allowed to show different things about a property. What they
      are not allowed to do is disagree about which properties there are, because somebody who
      counts the same search twice and gets two answers cannot tell which one is wrong, and the more
      alarming reading is always the true one. The map may still show fewer than the table, but only
      for a reason it says out loud: a property with no coordinates cannot be drawn, and the count
      says how many that is.
- [ ] AC-68: The map's background can be the drawn map or the photograph from above, switched from
      the map itself rather than from a settings page. Both are optional, both are off until
      configured, and no switch is offered while there is nothing to switch to.

      Two rather than one because they answer different questions about a rural property, and
      neither replaces the other: a drawn map says where the roads go and what a parcel is called, a
      photograph says whether the trees come up to the house and what the neighbour is doing. Only
      one is drawn at a time, and the credit shown is the credit for the one on screen, because the
      two are not the same people's work.

      A photographic source that runs out of detail before the map runs out of zoom keeps showing
      its deepest picture rather than nothing, so zooming in past the imagery gets blurry instead of
      blank. A background that fails to load leaves a usable map.

      Both are a computer being told which part of the world is being looked at, so the second is
      offered with the same warning as the first, in the same place, and is no more on by default.
- [ ] AC-66: An answer worth compressing is compressed before it leaves. This interface is written
      as though it were read over loopback, and it is not always: the second person in the household
      reads it across a tailnet, and when that has not managed a direct connection every byte goes
      out to a shared relay and back. The server's own work is identical either way, which is why
      the page is slow only sometimes and why nothing on this machine ever shows it.

      Compression is an optimisation and never a requirement, so a client that does not ask for it
      is answered in full rather than refused, and something already compressed is not compressed
      again. The answer a reader ends up with is byte for byte the answer they would have had
      without it.
- [ ] AC-69: A saved search that has been set aside is not on the list of searches. Archived and
      deleted searches are read on a surface of their own, reachable from the list, which says how
      many are there before it is opened and is not offered at all while there are none. Each one is
      shown as what it was rather than as a name on a button: its description, how many areas it
      had, which sources it used, when it last ran, and when it was set aside. An archived search is
      brought back from there; a deleted one is restored from there, with its areas and comments
      intact, which is AC-27's guarantee unchanged and now offered in one place rather than two. The
      list of searches gains no control for showing archived ones among the watched ones, because
      there is nowhere left for them to be shown.
- [ ] AC-70: A deleted search can be discarded for good, from that surface and nowhere else. It is
      the only operation in this interface that removes a file, and it is built as the only one: it
      asks for the search's name to be typed before it will act, and it says what survives before it
      is confirmed rather than after. What survives is everything the runs recorded. Every property
      that search ever found, its price history and every judgment written on it stay in the store,
      because snapshot history is append-only under non-negotiable 2 and product invariant 1, and
      the answer reports how much of it there is, so nobody is left believing more was removed than
      was. A discard of a search that is not deleted is refused in words rather than performed: the
      two steps are deliberate, because the reversible one is what makes the irreversible one safe
      to offer.

      The file it removes is found the same way every other operation on a saved search finds one:
      through the strict name rule and the containment check, and never by a pattern built from the
      name. The name reaches this operation as a segment of a URL, and this is the one operation in
      the product where being wrong about which file that names cannot be undone.

      The typed name is a guard against the hand, not against an attacker. This server has no
      authentication by design, the route is reachable directly, and nothing the browser does can
      prove to it that a person typed anything. What stands between a hostile page and this
      operation is the check on the request that already covers every write: the permitted host, the
      origin, and the header no cross-site form can set. The two are different jobs and neither
      substitutes for the other.

      Whether the search is already deleted is read from the catalogue inside the request that
      performs the removal, and no claim the client makes about that state is accepted.
- [ ] AC-71: A surface is named for everything it does, on every link that reaches it and in its own
      heading. The map is called the map: it draws the wildfire hazard model, either configured
      background, which way the wind pushes, county lines, town names, rainfall by county, a movable
      ruler, and the properties themselves as pins that can be kept or passed on, and a name that
      says "fire" describes one of those.

      Its address is renamed with it, and the old one keeps working: the surface is at `/map/{name}`
      and `/fire/{name}` answers with a permanent redirect rather than a not-found. Every surface
      here is reloadable and bookmarkable by design and this one is reached from a phone, so an
      address that stops answering is a bookmark that breaks with nothing on screen to say where the
      page went.
- [ ] AC-72: The controls on a surface are grouped by the question they answer, each group named in
      words, rather than set out as one row of everything. On the results table the groups are which
      rows are shown, which columns are shown, and where else to go. On the map they are which
      properties are drawn and what is drawn underneath them. A group's name is a word rather than
      an icon, and a group is open rather than a menu: this reorders and labels controls and hides
      none of them.

      Two things go with the regrouping, both about a screen saying one thing once. A surface
      announces a change of state to anything reading the page out through one region rather than
      several: three regions that announce themselves separately are three interruptions for one
      change, and to somebody who cannot see that they landed together they read as three unrelated
      events. And a measurement of how long the page took to draw is not shown to the person reading
      it; that is a number for whoever is writing the table.
- [ ] AC-73: Every surface about one saved search says which search it is about and offers the
      others. From the results table, the run comparison, the map or the search builder, the other
      three and the list of searches are each one press away, from the same place on every one of
      them. A property's own page offers the way back to the table it was read from, carried in the
      address because a property can appear in several saved searches and "back to the search" has
      no single answer; a property page opened without one offers no trail rather than guessing.

      The navigation that names the same three destinations everywhere is not this: a bar that
      reports "the list of searches" while standing on a search's own results is naming somewhere
      the reader is not.
- [ ] AC-74: The results table opens on a named view rather than on every column it has. Three
      exist: the columns a property is decided with, the columns about what a place is next to, and
      all of them. Which one is in force is shown in words with the number of columns it draws,
      counted against what the answer declares rather than a number written down here, and changing
      it is one control. Everything a view leaves out is still in the answer, still in the
      spreadsheet, and still one tick away in the chooser, which is AC-52's guarantee unchanged.

      A remembered arrangement wins over the view, always. A person who has arranged this table
      opens it as they left it, and the view decides only what a table nobody has arranged yet
      looks like. That is what makes this a default rather than a redesign of somebody's screen.

      **What is remembered is the set of columns, and the view's name is a label on it.** A view is
      applied at exactly two moments: when there is nothing remembered at all, and when a person
      picks one. It is never recomputed from its name on a later load. Two things follow and both
      are required. Somebody who deviates from a view keeps every other column exactly as the view
      left it, rather than having the thirty the view was hiding reappear because only the one they
      touched was written down. And a release that changes what a view contains does not silently
      rearrange a table already in use.

      A stored arrangement carrying no view name is somebody's arrangement from before views
      existed, and reads as one rather than as an invitation to impose a default.

      A view is a starting point and not a lock: hiding or showing a single column afterwards
      leaves the view rather than being reasserted by it, and the control says so rather than
      continuing to claim a view the table is no longer showing.

      A view naming a column this answer does not declare draws the columns it does declare: a view
      is a list of names, so a release that renames or retires one narrows the view. The table
      draws the rest, raises nothing, and is never left blank.

      Both this control and the chooser are operable from the keyboard, like everything else on
      this surface (AC-17).
- [ ] AC-75: The chooser groups every column by where its value comes from, under the same five
      names the table already uses to say what an empty cell in that column means: reported by the
      listing, worked out by this tool, read out of the description, public data about the place,
      and yours to write in. The words are the core's, declared once with the columns themselves,
      so the chooser and the heading tooltips cannot come to describe the same column differently.

      The grouping is the answer to "where in this list is the flood zone", which a flat list of
      forty-three names makes somebody read all of them to answer. Each group says how many of its
      columns are shown, and can be shown or put away as a group, from the pointer and from the
      keyboard, because "all the public data" and "everything I write in myself" are the two most
      common of those thirty decisions.
- [ ] AC-76: Every count of properties on every surface says which properties it counts, in the
      words beside it rather than in a tooltip. They are four different questions and the same noun
      on all four is what makes them read as a contradiction: how many this workspace watches
      across every search, how many the latest run of one search found, how many were matched
      against an earlier run, and how many of them can be drawn on a map. No number changes; what
      changes is that each one is named. Where a surface holds properties back, why and how many is
      already said separately (AC-36, AC-57) and stays there.
- [ ] AC-77: A property with no address is named for what is known about it rather than by its
      identifier. The identifier is exact and is kept, on the page and as the way to ask for the
      property again; it is not what a person is asked to read, recognise or say aloud. This
      applies wherever a property is named: its own page, the run comparison, the results table and
      the map, and the rule is written once rather than on each of them, because four copies is how
      one goes on printing the string after the others stopped.
- [ ] AC-78: Explanation that is the same on every visit is behind a disclosure that names what it
      holds, rather than printed above the controls. It is open the first time somebody is on that
      surface and closed afterwards, remembered on the terms AC-45 already sets for every view
      preference here. Nothing is removed: every sentence is one press away, and a disclosure that
      hid something a person needs on a later visit would be worse than the paragraph it replaced.

      Explanation that repeats is said once. A criterion's explanation of what it does belongs
      above the list of criteria rather than inside each of them, where fifteen criteria are
      fifteen copies of it and the rules themselves are what a person came to read.
- [ ] AC-79: What is configured and what is run are two surfaces. Configuring is the model, the
      mail account, the map's backgrounds and the broadband account, each of which is set up once
      and then reports itself. Running is attaching public data, asking a model about descriptions,
      writing the digest and writing a spreadsheet, each of which takes minutes and is come back
      to. The navigation has always named both; it now reaches both.

      The settings surface keeps its address and its subject; the tools are what move. Splitting
      into two new addresses would break a bookmark for no gain, which AC-71 settled for the map,
      and it keeps AC-25 and the scenario about turning on something that is off true exactly as
      written.

      Every section that exists still exists and nothing about what any of them does changes. Where
      a thing to run needs something configured, it says so and says where, rather than repeating
      its setup or pointing at a part of a page it is no longer on.
- [ ] AC-80: A figure in the overview strip that can be zero is drawn at zero, so the strip is the
      same shape every morning. A count appearing is harder to notice than a count changing, which
      is exactly backwards for a strip whose job is telling somebody whether anything needs them
      today.

      A figure that does not apply to this installation at all is still absent, and the rule for
      which those are is product invariant 9 rather than a list kept here: a figure about an
      optional component, absent by default and not configured here, is not drawn. Every other
      figure is drawn whatever its count. "None today" and "this does not happen here" are
      different answers and a zero would give the wrong one.
- [ ] AC-81: A judgment can be set on several properties at once. A range of rows is selected from
      the pointer and from the keyboard, and one action keeps or passes on all of them. Everything
      AC-48 requires of passing one property is required here: it asks first, in a dialog on the
      page that says what it does and how many it does it to, and dismissing it by any means leaves
      every row exactly as it was. The reason it collects is written to each property in the batch,
      because a reason recorded for forty houses at the moment forty were ruled out is as true of
      each of them as a reason typed on one.

      It is one operation in the core rather than a loop in the browser, which is what makes it
      reachable from the command line as AC-22 requires and what stops forty writes ending half
      done with no record of which half. The answer says how many were changed.

      A batch that does not entirely succeed says so on the rows, which is AC-6 applying to forty
      rows rather than one. The rows that were written show what was written; the rows that were
      not are marked as unsaved, keep what was being set, and are never presented as saved. A count
      of what changed that is smaller than the count asked for is reported as what it is, because
      the one thing this must never do is leave somebody believing forty houses were ruled out when
      thirty were.

      One action undoes the batch, and it is the same control that made it, which is AC-34's rule
      about setting a judgment applying to a batch unchanged.
- [ ] AC-82: A panel of the search builder that has unsaved changes says so, and leaving the page
      while any panel does is refused until it is confirmed. The four panels stay four, because
      they write four genuinely different parts of a definition and one button over all of them
      would write parts nobody touched, which AC-3 forbids by requiring that a definition opened
      and re-saved here is unchanged apart from the edits made. What is added is that the interface
      stops being silent about which parts are dirty, and stops apologising for it in its own
      opening line.
- [ ] AC-83: A screen about an operation that takes minutes asks, when it loads, whether that
      operation is running, and shows the same live progress it would have shown had the operation
      been started from that screen. This holds for the tools surface and for the list of searches,
      and it holds across a reload, a fresh visit, a second browser and a different device, because
      none of those is the tab that pressed the button and all of them are asking the same question.

      What is shown is what the operation has said, updating while it runs, and what it produced
      when it ends, which is what AC-13 requires of a search run started here and what nothing
      required once the page had been left. A screen that finds nothing running shows nothing and
      says nothing, because an idle installation is the normal case and a line reporting that
      nothing is happening is noise on every visit.

      **An operation that stopped without finishing is shown as that.** Never as running, which
      would be a panel that never advances and never ends, and never as completed, which would be a
      lie about work that did not happen. This is the browser reading feat-001/AC-31's own answer
      rather than deciding anything: what the store cannot distinguish, the screen must not pretend
      to.
- [ ] AC-84: Every screen says when an operation is under way, in the frame the screens share rather
      than on the one page that started it. It names what is running and reaches the screen showing
      its progress. It is drawn only when something is running, and it goes away on its own when the
      operation ends without the page being reloaded.

      It is one ask on a shared schedule rather than one per surface, because six screens each
      polling for themselves is six answers that can disagree and six requests where one would do.
      The ask is a single cheap read on a stated interval, because it runs on every screen including
      the results table, and every request on that screen queues behind the same one-at-a-time rule
      as the table's own, which is the most expensive read this interface has.

      **What is under way is part of the overview both surfaces already draw.** The overview reports
      running searches and is widened to report every pass, which is what makes this reachable from
      the command line as invariant 5 requires without inventing a command: `overview` already emits
      it structured, with the stable exit code invariant 6 asks for. A marker in the browser and a
      line in a terminal are then two renderings of one answer rather than two answers.
- [ ] AC-85: Starting an operation that takes minutes while another is under way is refused rather
      than started, and the refusal names what is running, what it is running on, and when it began.
      One at a time means on this machine rather than in this process: the browser will not start an
      extraction pass while the scheduled nightly job is running one, which it previously would,
      because each process knew only about its own work.

      Any long operation blocks any other, not merely another of the same kind. Two of them has
      never been faster: they are paced against the same sources and write to the same file, so the
      second only makes the first take longer while doubling what it costs. This is the rule the
      browser already applied to itself, moved somewhere it can see the whole machine.

      It is one core operation, so both surfaces refuse identically and for the same reason, which
      is AC-14's rule that this layer contains no business logic applied to a decision that lived in
      the browser's own process. The store records and does not refuse; the refusal is computed from
      what the store says. A command somebody typed is not refused: they asked for it explicitly,
      and this guards a button rather than a person at a keyboard.
- [ ] AC-86: The results table carries two columns for what the assessment made of each property,
      both drawn as a control rather than as a measurement: an icon carrying a count as a badge, the
      way a count riding on an icon is read everywhere else as "there are this many things here,
      press to see them". A magnifying glass for the concerns it raised, marked when any of them is
      serious; a tick for what counts in the property's favour. Both are marked differently when the
      assessment no longer describes the property because what it was assessed from has changed.

      **The same control, drawn twice.** The two counts are read together in one movement: "two
      things for it, three against" is a single sentence a person assembles as their eye crosses the
      row. Two differently shaped buttons would read as two unrelated facilities rather than as two
      halves of one reading.

      **A tick and not a star.** The first column of this table already uses a star and it means
      *the person kept this house*. One symbol cannot mean both that and a model's opinion, and the
      boundary this feature keeps everywhere else is exactly that the two are never confused.

      **What counts for it comes first.** It is the order the questions get asked in, and a column
      of worries read first colours the row behind it. A table of nothing but concerns is a reading
      of a risk rather than of a house: across the first 292 readings the model raised 235 concerns
      and said nothing whatever in any property's favour, because nothing had asked it to, and every
      one of those concerns was true and carried its evidence, which is why the bias was easy to
      miss.

      Three facts stay apart in each column, and the drawing is what keeps them apart. **Nothing
      has assessed this property**: the cell is empty, because an absence is not a count. **It was
      assessed and there was nothing to say**: the icon, with no badge. That is a real answer and 55
      of the first 155 properties were it for concerns, so it is drawn rather than left blank, and
      "read and clear" can never be mistaken for "not read". It carries no zero, because a badge
      reading `0` is a thing a person has to be taught to read and an unbadged icon is not. **There
      were this many**: the icon with the number on it.

      A property read before the favourable half of the question existed draws an empty cell there,
      the same as one nothing has assessed. Those are two different facts in the store, because only
      one of them is worth spending money on again, and one fact to a reader: nobody has told them
      what is good about this house. The column does not carry a distinction that exists for the
      benefit of a pass. The dialog does, because there a reader is owed it.

      Each is an ordinary column: it hides, comes back from the chooser, sorts and filters exactly as
      every other column does, which is AC-45 and AC-52 applying to it without being restated. Its
      value is still the number, so a sort orders by how much was raised and a filter tests the
      count, whatever the cell happens to draw. It joins the chooser under an origin of its own,
      because what a model made of a property is a different kind of claim from a value a source
      reported, one this tool computed, one read out of a description, public data about the place,
      or something the person wrote.

      **Ordinary means it joins the declaration every column is declared in, and not the default
      spreadsheet.** Those are already two different things: forty-five columns are declared and the
      default sheet uses thirty-two. Joining the declaration is what makes sorting, filtering,
      hiding and the chooser work without a special case; staying out of the default sheet is what
      leaves feat-011/AC-1's header exactly as it was. Anybody who wants the count in a sheet puts
      it in a template, which is what feat-011/AC-7 says a template is for.

      **It is in the view the table opens on.** A count somebody has to go and un-hide is a count
      they will not see, and this one exists only where a person is deciding.

      **Neither mark is a colour.** This feature's own accessibility requirement is that nothing is
      conveyed by colour alone, and a red badge beside a blue one is exactly that. A serious count
      is squared where an ordinary one is round, and an assessment that no longer describes the
      property is drawn dashed. A property can be both, so the two marks are a shape and a texture
      rather than two colours competing for the same pixels. Both are said in words as well, because
      the badge is hidden from a screen reader and the control has to speak the count itself.
      **Why a control and not a number.** A right-aligned integer in a column standing between Tags
      and Town is read as one more measurement of the house, like beds or square feet. It is not a
      measurement; it is a door. Drawing it as a door is the whole of the difference, and it costs
      nothing, because the sortable, filterable value underneath is unchanged.
- [ ] AC-87: Pressing either opens the assessment for that property in a dialog over the page,
      without leaving the page. What opens is the whole of it: the account of the property, every
      concern with the evidence it came from, what counts in the property's favour under a heading
      of its own, what each picture showed, what to check before visiting, and what could not be
      determined. Both controls open the same dialog, because there is one reading of the house and
      these are two sections of it rather than two documents; a person opened it to find out about a
      property, not to choose which list to read.

      **A reading made before the favourable half existed says so, in words.** Null and empty are
      different answers, and drawing the first as the second would put a false negative in front of
      somebody deciding whether to drive four hours. It closes with its own control, with Escape, and by pressing
      outside it, which is how every other dialog in this interface closes. It opens from the
      keyboard the same way, because the cell is already reachable that way, and focus moves into it
      when it opens and back to the control it came from when it closes.

      **Over the page rather than inside the table.** Three reasons, and the first was learned by
      looking at it built the other way. *Prose does not survive this grid*: every cell here is
      deliberately `white-space: nowrap`, because a data row is read across, and every cell takes
      the table's line height, which is a *row* height of 25px rather than a line height. A
      paragraph inheriting it is set a full line apart, and that is not a styling slip to correct in
      place; it is what a table configured for one-line cells does to prose, and the next thing that
      puts prose in a cell would meet it again. *The reading is not the deciding*: the table exists
      to compare a hundred and fifty rows, while reading what a model made of one house is a
      single-subject act, and this interface already opens a dialog for exactly that kind of act,
      for the photographs and for the question asked before a house is passed on. *Nothing behind it
      moves*: an opened row changes the height of the virtual window and pushes every row below it
      down the page, where a dialog leaves the table untouched, so closing it puts the reader back
      on the row they were looking at rather than near it. That also removes the one place where
      AC-53's measurement had to account for a second row belonging to a first.

      **The control and not the row.** Pressing a row already means two things here: it moves the
      cell focus, which is what makes a writable column typable, and with shift held it extends the
      range AC-81 acts on. A third meaning on the same press would have taken one of those away, and
      the one it would have taken is the one somebody already reported losing.

      **The person's own judgment stays visibly theirs.** What is drawn is labelled as the model's
      and dated, and nothing in it is written into `rank`, `verdict`, `red_flags`, `summary`,
      `next_step` or the rest, which remain the user's own as feat-013/AC-6 requires. Somebody
      reading a concern must be able to tell instantly that they are reading an opinion rather than
      their own note.

      **An assessment that no longer describes the property says so before its content.** Reading a
      stale assessment as current is the one way this misleads rather than merely disappoints.

      **The text is fetched when the dialog is opened rather than sent with the table.** The results
      answer for this workspace is already 2.7MB, and adding every assessment's prose to every page
      load to show what is usually one of them is the wrong trade. The count in AC-86 is three small
      values per row and travels with the table.
- [ ] AC-64: Two requests that read the database never run at the same time, because there is one
      connection under all of them. The exceptions are named in one place and are the answers that
      never open the store at all: a hazard tile, a wind rose, and this tool's own files, the first
      two being somebody else's network with a disk cache in front and either of which would
      otherwise stop the interface answering for ten seconds at a time.

      **Waiting for a turn consumes nothing.** Not a thread, in particular: a page opening is a
      burst of dozens of requests, and a queue that parks each waiting request in the same limited
      pool the running one needs is a queue that stops the server dead, with the process up and the
      port open and nothing answered ever again. A burst larger than that pool is therefore
      answered in full, and the server still answers afterwards. A request that fails still lets
      the next one in.
- [ ] AC-65: A property's own page draws that property on the wildfire hazard layer, small, using
      the same layer at the same address through the same cached route the map uses, so
      nothing new talks to the outside world. The map answers which of a hundred properties is
      near the red; this answers the other half of the same question, which is what this one is next
      to, and it is a map rather than a value for the reason the map exists at all: no column
      in this tool says what a house is beside. It can be dragged and zoomed. A property with no
      location says so and draws nothing, because an empty map centred on nowhere reads as a fault
      in the tool rather than as a fact about the listing.

## Edge cases & errors

- A property is passed and then a later run observes a price cut on it. It stays passed and stays
  hidden, and the change is still recorded and still reported in the digest. Hiding is about
  attention, not about the record, and a house somebody said no to does not become one they said
  yes to because it got cheaper. Un-passing it is one action away.
- A passed property is merged with an unpassed one. The merged record is passed if either
  constituent was, on the grounds that a decision to stop looking at a house should not be undone by
  the tool noticing that two records were the same house all along.
- Every property in a search is passed. The table is empty and says so, naming the number hidden and
  how to see them, rather than reading as a search that found nothing.
- An unknown judgment value arrives from a hand-edited database or an older client. Rejected on
  write with the accepted values named, in the same way an unknown severity in a criterion is.

- The list is long enough that the rows drawn are a small fraction of it, which on this table is
  the ordinary case rather than the extreme one. Whatever stands in for the rows that are not drawn
  has to be real height and not a shift applied to the ones that are, because the headings are held
  in place by the table being as tall as the list it stands for.
- A row holds four sentences of description and the row beside it holds none. They are different
  heights, and each of them is exactly as tall as what is in it. The one thing that must not happen
  is the blank space standing in for the rows that are not drawn disagreeing with where those rows
  are said to be, because that is the whole of the scrollbar: off by a pixel a row and the end of a
  long table cannot be reached at all.
- Wrapping was left on and the page is opened again. It is on, and the table is wrapping. A setting
  that is remembered, shown as remembered, and does nothing until it is switched off and on again is
  worse than one that is not remembered at all.
- Every overlay is switched on at once and somebody clicks a house. It opens. That is not one
  check but three: the county lines, the wind arrows, and the mark for a station still being read
  are each drawn in a pane above the properties, and each of them was, at one time or another,
  answering for the whole map.
- A weather station's record is on its way.
- A county's rainfall record will not answer while the rest will. That county keeps its lines and
  its name and has no number, and the failure is named. A county silently missing its number would
  read as a county with no rainfall record at all, which is a different and much more interesting
  fact.
- Somebody looks for a column added since they last arranged the table. It is beside the column
  it belongs with, not at the far right, and the heading text says how tags are opened, because a
  control that is only found by people who already know it is there was found by nobody.
- Somebody looks for a column added since they last arranged the table. It is beside the column
  it belongs with, not at the far right, and the heading text says how tags are opened, because a
  control that is only found by people who already know it is there was found by nobody.
- A property has no coordinates and its own page is opened. It says no source gave it a location
  and that the map counts it as unplaced, rather than drawing an empty map.
- A page opens and fires several dozen requests at once, which is what a page opening is. Every
  one of them is answered and the server is still answering afterwards. This is the case that must
  be tested with a burst: two requests at a time pass happily under an arrangement that stops the
  server dead under forty.
- Two overlays are switched on at once, so two requests that both read the run's properties are
  in flight together. They are served one after the other rather than interleaved on one database
  connection, which is a pair of five hundreds and an overlay that silently never appears.
- The map is moved somewhere none of the run's properties are. The list underneath it is empty and
  says so, because it is a list about what is on screen rather than about the run. It is drawn as what it is, a marker where the rose
  will be, because the first read of a station takes about ten seconds and an empty patch of map
  says nothing about whether anything is happening.
- A state has no automated weather network, or the archive is having a bad afternoon. That state is
  named as unreachable and every other state is still drawn, which is the reliability invariant
  applying here exactly as it applies to a run: no single outside failure decides the answer.
- Somebody opens a rose near the edge of the screen. The map pans to fit the bubble, which moves the
  map, which is what decides which stations to ask about. Whatever is already drawn correctly is
  left alone rather than replaced, because replacing it takes the open bubble with it.
- A column with a filter on it is hidden. The filter keeps holding and keeps its place in the list
  above the table, said to be on a hidden column. Lifting it with the column would throw away work
  somebody did; leaving it in force without saying so would take the reason four hundred rows are
  missing off the screen along with the column.
- A search's own filters and the results table's are different things with the same word. A saved
  search's filters decide which properties are collected and are written to its file; the table's
  decide what is drawn on one screen in one browser and are written nowhere. Each screen says which
  it means.

- A filter is cleared. It is removed from the file rather than left as an empty key, and a field
  left untouched is not written at all. A page that saved on every blur wrote a file nobody had
  edited.

- The results table holds several thousand rows. Sorting and filtering remain responsive, which
  constrains how the table is built but is not satisfied by silently paginating away rows the user
  asked to see.
- A property has no coordinates and cannot be placed on the map. It still appears in the table,
  marked as not locatable.
- A property has no photographs. The detail surface renders without them rather than showing broken
  images.
- A photograph the source has since removed. The stored preview still renders; the full gallery
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
- A record in a queued pair has no stored photograph. Its place on the card keeps the same shape and
  says there is none, so the two records stay side by side and comparable. The core answers whether
  an image exists rather than the page finding out by requesting one and failing.

## Non-functional requirements

- Performance: a results table of 5,000 rows becomes interactive within three seconds, and sorting
  or filtering it responds within 200 milliseconds without contacting the server.
- Security: bound to the local interface, single user, no authentication by design. Every value
  originating from a source or from a user note is rendered as text and never as markup, so no
  listing description can inject content into the page. No authentication by design means whatever
  can reach the interface can use it, so putting a proxy in front of it is a decision about who can
  reach that proxy, and the interface says so where the decision is taken rather than assuming it.
- Reliability: an interface error affects the surface being used and never leaves an annotation
  half-written or a saved search partially overwritten.
- Accessibility: fully keyboard operable, legible at default zoom, and conveying nothing by color
  alone.

## Open questions

None.
