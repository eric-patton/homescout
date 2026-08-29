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
  the set of searches rather than only look at it, and so that a search I no longer want stops
  cluttering the list without taking the properties it found with it.
- As the person running searches, I want to set up the optional parts (a model to read descriptions,
  a background for the map) from the screen that tells me they are off, so that turning one on does
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
  - When the map is opened
  - Then it draws a labelled coordinate grid that can be drawn over, says what is missing, and offers
    to turn a background on with what that costs stated beside the offer

## Acceptance criteria

- [ ] AC-1: Seven surfaces exist and are reachable: map and search builder, saved search list,
      results table, listing detail, run comparison, merge review queue, and the fire map.
- [ ] AC-2: Areas can be drawn, named, and edited on the map, including exclusion areas, and are
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
- [ ] AC-9: The listing detail shows photographs, the full description, enriched values, a link per
      source, the price and status timeline, and the source rows underneath the record with the
      signal that justified each join.
- [ ] AC-10: A value that is missing is displayed as missing and is visually distinguishable from a
      value that is known to be negative.
- [ ] AC-11: The run comparison surface produces the same result as the equivalent terminal
      comparison for the same two points in time.
- [ ] AC-12: Ambiguous match pairs are listed with the agreeing and conflicting signals, and with
      the two properties themselves, so a decision can be made from the card rather than from two
      other tabs. A decision made here is durable and honored by later runs.
- [ ] AC-13: Running a search from here shows progress and per-source outcomes, including
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
- [ ] AC-19: Notes about an area or a town can be written and edited, addressed by the area they
      describe rather than by a property, and are the notes the spreadsheet export's second sheet
      carries. They are writable from the results table too, where the opinion is formed, and the
      cell says whose note it is before it is opened: writing one from a row writes it for every
      property in that town, and those rows take it there and then rather than at the next reload.
- [ ] AC-20: Properties whose presence is `disappeared` are hidden from the results table by
      default and are shown by an explicit filter, which is always available and reports how many
      are hidden. It is one of the table's four view toggles, alongside the ones for passed
      properties (AC-35), photographs (AC-43) and wrapped text (AC-47); only the toggles that hide
      something report a count.
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
- [ ] AC-24: The parts of a saved search this interface edits (its description, its sources, its
      filters, whether a model reads its descriptions, and its criteria) are editable here, and
      AC-3's guarantee holds for every edit made through them. A criterion is sent as the conditions
      a person chose, and the expression is composed by the rule engine rather than by the
      interface, so the grammar has one home and the file gets the same line somebody would have
      typed.
- [ ] AC-25: The optional configuration (which model reads descriptions, where the map's tiles come
      from, where the digest is written) is editable here and written to the uncommitted file beside
      the database, taking effect without a restart and leaving the rest of that file, comments
      included, exactly as it was. A setting whose name looks like a credential is refused, and no
      credential is ever displayed.
- [ ] AC-26: With no tile server configured, the map draws a labelled coordinate grid, says what is
      missing, and offers to turn a background on with the privacy cost stated beside the offer
      rather than in a document.
- [ ] AC-27: A saved search can be deleted. It leaves the list at once, is skipped by a run of
      everything, and is not found when asked for by name. Two limits hold and are stated where the
      deletion is offered rather than only in a document. The definition is kept rather than
      unlinked, so it can be restored with its areas and comments intact, and the interface offers
      that restoration. And nothing a run recorded is removed: the properties, their price history
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
      opening the property and without typing. Setting it again to the same value clears it back to
      unset, so the control that passes a house is the control that un-passes it.
- [ ] AC-35: A passed property is absent from the results table by default, and present when "show
      passed" is asked for. A test covers both.
- [ ] AC-36: When passed properties are hidden, their number is reported, in the same place and the
      same form as the count of disappeared listings already hidden. A table that is quietly shorter
      than the run that produced it is not acceptable; the difference has to be visible without
      being asked for.
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
      control returns it to the declared arrangement. It is a view preference and is never written
      to the workspace, so two people reading one workspace arrange it independently. Where the
      browser cannot store it, the table opens in the declared arrangement and every other part of
      the page behaves identically. A column that did not exist when an arrangement was saved
      appears beside the column it is declared beside, never on the end: a remembered arrangement
      names every column there was, so on the end means past the right edge of a table forty
      columns wide, and a column nobody can see is a capability nobody has. Nothing somebody placed
      themselves is moved by this. A column that did not exist when an arrangement was saved
      appears beside the column it is declared beside, never on the end: a remembered arrangement
      names every column there was, so on the end means past the right edge of a table forty
      columns wide, and a column nobody can see is a capability nobody has. Nothing somebody placed
      themselves is moved by this.
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
      keyboard, and brought back from a chooser that lists every column. Hiding is remembered
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
      the browser's own, which says what passing does and that it is reversible. Dismissing it by
      any means, including the keyboard, leaves the property exactly as it was. Keeping a property
      asks nothing: it hides nothing, and the same control undoes it.
- [ ] AC-49: Keeping and passing are the first thing on a row, in a column of their own that cannot
      be moved or displaced, so the controls are in one place on every row of every arrangement. A
      kept property is on the shortlist and is hidden from nothing; the table can be narrowed to the
      shortlist alone, and the number kept is reported alongside the number hidden. The shortlist is
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
      bubble on the fire map, and from the property's own page. These pictures are the listing site's rather than this tool's, so nothing is asked of
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
      Every filter in force is named in words above the table with its own control to lift it, and
      one control lifts all of them, the whole-table search included. A filter narrows what is drawn
      and changes nothing else: no property is altered, judged or deleted by one, and none of it is
      remembered past the visit, because a narrowing that came back days later would hide rows for a
      reason nobody remembers setting.
- [ ] AC-58: The fire map carries a scale that reports the distance across the screen in miles and
      follows the zoom. It also offers a ruler, off by default, laid across the middle of what is on
      screen: either end can be moved to a point on the map, the whole ruler can be carried
      elsewhere without changing its length, and it reads the distance between its ends in miles, or
      in feet below the point where a mile is no longer a useful picture. It is operable by pointer
      and by keyboard, in steps taken from what is on screen rather than in fixed degrees. A scale
      fixed in a corner cannot be held up against two things that are somewhere else on the map,
      which is the whole reason the second one exists.
- [ ] AC-59: The fire map can draw which way the wind pushes, off by default, per weather station
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
- [ ] AC-60: The fire map can draw county lines and town names over the hazard layer, off by
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
- [ ] AC-61: The fire map can draw how much rain and snow a county gets in a year, off by default,
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
- [ ] AC-62: The fire map shows the properties currently on it as a list underneath it, holding
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
      the same layer at the same address through the same cached route the fire map uses, so
      nothing new talks to the outside world. The fire map answers which of a hundred properties is
      near the red; this answers the other half of the same question, which is what this one is next
      to, and it is a map rather than a value for the reason the fire map exists at all: no column
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
  and that the fire map counts it as unplaced, rather than drawing an empty map.
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
