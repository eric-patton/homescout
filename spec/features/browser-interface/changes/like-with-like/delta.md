# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Three acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-71, AC-72 and
AC-73. They are numbered after the two this feature's other in-flight change adds (AC-69, AC-70).

**User story.** As the person running searches, I want a link to say where it goes, so that I do not
have to open a screen to find out it does more than its name admits.

**User story.** As the person running searches, I want the controls on a screen sorted by what they
do, so that I can find the one I want by looking rather than by reading all of them.

**User story.** As the person running searches, I want to move between the screens about one search
without going back to the list each time, so that reading a property, checking what changed and
looking at where it is are one task rather than three.

- AC-71: A surface is named for everything it does, on every link that reaches it and in its own
  heading. The map is called the map: it draws the wildfire hazard model, either configured
  background, which way the wind pushes, county lines, town names, rainfall by county, a movable
  ruler, and the properties themselves as pins that can be kept or passed on, and a name that says
  "fire" describes one of those. Where this specification says "the fire map" it means that surface,
  and the words are brought into line with the two criteria that already call it the map.

  **Its address is renamed with it, and the old one keeps working** (od-1). The surface is at
  `/map/{name}`, and `/fire/{name}` answers with a permanent redirect to it rather than a
  not-found. Every other surface here is reloadable and bookmarkable by design, and this one is
  reached from a phone, so an address that stops answering is a bookmark that breaks with nothing
  on screen to say why or where the page went. A renamed surface that abandons its old address has
  moved the cost of the rename onto the person who was using it.

- AC-72: The controls on a surface are grouped by the question they answer, each group named in
  words, rather than set out as one row of everything. On the results table the groups are which
  rows are shown, which columns are shown, and where else to go. On the map they are which
  properties are drawn and what is drawn underneath them. A group's name is a word rather than an
  icon, and a group is open rather than a menu: this reorders and labels controls and hides none of
  them. Nothing about what any control does changes, and no control is removed, apart from the two
  AC-49 and AC-35 make into one.

  Two things go with the regrouping, both of them about a screen saying one thing once. A surface
  announces a change of state to anything reading the page out through one region rather than
  several: the map has three, which is three interruptions for one change and reads as three
  unrelated events to somebody who cannot see that they landed together. And a measurement of how
  long the page took to draw is not shown to the person reading it. That is a number for whoever is
  writing this table, it sits in the middle of the sentence that says how many properties there are,
  and it is the one thing on that line nobody reading a search can act on.

- AC-73: Every surface about one saved search says which search it is about and offers the others.
  From the results table, the run comparison, the map or the search builder, the other three and the
  list of searches are each one press away, from the same place on every one of them. A property's
  own page offers the way back to the table it was read from. The navigation that names the same
  three destinations everywhere is not that: a bar that reports "the list of searches" while
  standing on a search's own results is naming somewhere the reader is not.

## MODIFIED

- **The vocabulary's name for the map.**
  - Was: the fire map, wherever it is named.
  - Now: the map. AC-51, AC-58, AC-59, AC-60, AC-61 and AC-62 are reworded on that one word and are
    otherwise untouched; AC-67 and AC-68 already say it.

- **AC-1.**
  - Was: ...merge review queue, and the fire map.
  - Now: ...merge review queue, and the map.

    **How this one folds, because it can go wrong quietly.** This feature's other in-flight change
    also modifies AC-1, taking it from seven surfaces to nine, and it is expected to fold first.
    By the time this one folds, the sentence quoted above as "Was" no longer exists. So this
    modification is applied as a replacement of the phrase "the fire map" wherever it stands, not by
    matching the whole sentence: matching the sentence fails silently and takes the settings and
    set-aside surfaces back out with it. The same is true of every other criterion in this delta's
    naming sweep, none of which the other change touches.

- **AC-35.**
  - Was: a passed property is absent from the results table by default, and present when "show
    passed" is asked for.
  - Now: a passed property is absent from the results table by default. Which properties are shown
    by judgment is one control with one answer in force at a time: the ones still to decide, the
    ones kept, the ones passed on, or all of them. The default answer shows the ones still to
    decide, which is exactly what the two unticked boxes it replaces showed, so nobody's table
    changes under them. Two controls over one field is a state a person cannot read off the
    controls, and it forced the two to be applied in a careful order so they could not contradict
    each other.

- **AC-36.**
  - Was: when passed properties are hidden, their number is reported, in the same place and the same
    form as the count of disappeared listings already hidden.
  - Now: the two things the old line ran together are separated, because they answer different
    questions and only one of them is actionable. How many properties there are is a total, and
    totals stay in a line under the controls: how many are drawn, out of how many the run found, and
    how many are kept. Why any of them are missing is a reason, and every reason lives in the bar
    above the table as a statement in words carrying its own number, with its own control to lift
    it: "737 passed on" beside "Ruidoso in Town/Area", because they are the same kind of fact about
    the same table. Passed properties still report their number, which is what this criterion has
    always required; what changes is that the number is attached to the reason rather than printed
    beside an unrelated total. Nothing is said in two places. A table quietly shorter than the run
    that produced it remains the worst thing this screen can do, and the defence against it is now
    one bar that holds every reason rather than a bar that holds two of them and a line that
    mentions the rest.

- **AC-49.**
  - Was: ...the table can be narrowed to the shortlist alone, and the number kept is reported
    alongside the number hidden.
  - Now: narrowing to the shortlist is one of the answers of AC-35's judgment control rather than a
    box of its own. The number kept is still reported, in the line of totals under the controls,
    because how many have been kept is a fact about the search rather than a reason a row is
    missing: a kept property is hidden from nothing. Everything else in AC-49 stands: keeping and
    passing are still first on the row, still in a column that cannot be moved or displaced, and the
    shortlist is still readable from the command line.

- **AC-20.**
  - Was: properties whose presence is `disappeared` are hidden from the results table by default and
    are shown by an explicit filter, which is always available and reports how many are hidden. It
    is one of the table's four view toggles, alongside the ones for passed properties (AC-35),
    photographs (AC-43) and wrapped text (AC-47); only the toggles that hide something report a
    count.
  - Now: the requirement is unchanged and the sentence naming the mechanism goes. Properties that
    have disappeared are still hidden by default, still shown when asked for, and still report how
    many are held back. What they are no longer is one of four view toggles: there are not four any
    more, because the two that hide rows are now one control with four answers and this one is a
    statement in the bar. A criterion that counts the controls on a screen dates the moment the
    screen is rearranged, and this one has now dated twice; it states what must be true of the
    hiding instead, which is that it is explicit, reversible, and counted where the other reasons
    are counted. Which properties are drawn and how the table is drawn stay separate ideas:
    photographs (AC-43) and wrapped text (AC-47) hide no rows and belong with the columns, not here.

- **AC-57.**
  - Was: every filter in force is named in words above the table with its own control to lift it,
    and one control lifts all of them, the whole-table search included.
  - Now: every reason the table is showing fewer rows than the run found is named in words above the
    table with its own control to lift it, and one control lifts all of them. That is the column
    filters, the whole-table search, the judgment being narrowed to anything but all of them, and
    the properties that have come off the market being held back. Each says how many rows it is
    holding back, which is what satisfies AC-36 and AC-20 for the two that hide by the thousand. The
    bar was built because a table silently missing four hundred rows is the worst thing this screen
    can do, and it was built from the two narrowings that hide the fewest rows.

## REMOVED

Nothing. Two controls become one control with the same reach; no capability is withdrawn and no
guarantee is dropped.
