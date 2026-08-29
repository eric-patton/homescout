# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-69 and AC-70.

**User story.** As the person running searches, I want everything I have set aside kept somewhere
other than the list of what I am watching, so that opening the tool in the morning shows me the
searches that ran and not the ones I stopped caring about.

**User story.** As the person running searches, I want to be finished with a search for good, so
that a tool I have used for a year is not carrying every experiment I ever made.

- AC-69: A saved search that has been set aside is not on the list of searches. Archived and deleted
  searches are read on a surface of their own, reachable from the list, which says how many are
  there before it is opened and is not offered at all while there are none. Each one is shown as
  what it was rather than as a name on a button: its description, how many areas it had, which
  sources it used, when it last ran, and when it was set aside. An archived search is brought back
  from there; a deleted one is restored from there, with its areas and comments intact, which is
  AC-27's guarantee unchanged and now offered in one place rather than two. The list of searches
  gains no control for showing archived ones among the watched ones, because there is nowhere left
  for them to be shown.

- AC-70: A deleted search can be discarded for good, from that surface and nowhere else. It is the
  only operation in this interface that removes a file, and it is built as the only one: it asks for
  the search's name to be typed before it will act, and it says what survives before it is
  confirmed rather than after. What survives is everything the runs recorded. Every property that
  search ever found, its price history and every judgment written on it stay in the store, because
  snapshot history is append-only under non-negotiable 2 and product invariant 1, and the answer
  reports how much of it there is, so nobody is left believing more was removed than was. A discard
  of a search that is not deleted is refused in words rather than performed: the two steps are
  deliberate, because the reversible one is what makes the irreversible one safe to offer.

  **The file it removes is found the same way every other operation on a saved search finds one:**
  through the strict name rule and the containment check, and never by a pattern built from the
  name. The name reaches this operation as a segment of a URL, and this is the one operation in the
  product where being wrong about which file that names cannot be undone. A pattern is how the
  restore beside it finds a file today, and a pattern built from a name walks out of its own
  directory. That restore is harmless, and not because it is careful: it is harmless because a
  later check, there to decide where the file is going, refuses every name that could have escaped,
  so the move never happens. A function saved by the order its checks fall in has protected itself
  and nothing else. This operation removes what it finds, with nothing downstream to be saved by.
  The rule is stated here rather than left to the implementation because the implementation will be
  written in that file, next to that function, by somebody who will reasonably read the neighbour as
  the pattern to follow.

  **The typed name is a guard against the hand, not against an attacker, and the criterion says so
  rather than leaving somebody to assume otherwise.** This server has no authentication by design,
  the route is reachable directly, and nothing the browser does can prove to it that a person typed
  anything. What stands between a hostile page and this operation is the check on the request that
  already covers every write: the permitted host, the origin, and the header no cross-site form can
  set. The dialog stops the person at the keyboard removing the wrong thing by reflex. The two are
  different jobs and neither substitutes for the other.

  **Whether the search is already deleted is read from the catalogue inside the request that
  performs the removal**, and no claim the client makes about that state is accepted. Every request
  that touches the workspace is already serialised, so this is not a race today; it is written down
  so that it does not become one, and so that the refusal is a fact the server established rather
  than a page's recollection of what it displayed a minute ago.

## MODIFIED

- **The vocabulary's definition of a surface.**
  - Was: a surface is one screen, and there are six: the map and search builder, the saved search
    list, the results table, the listing detail, the run comparison, and the merge review queue.
  - Now: there are nine: the search builder, the saved search list, the results table, the listing
    detail, the run comparison, the merge review queue, the map, the settings surface, and the
    surface holding what has been set aside. Two of the three additions were built and never written
    down here; recording them is a correction rather than a change, and it is made here because this
    delta adds the third and a list that is wrong in three ways is worse than one that is wrong in
    two.

    **The first one is renamed and the reason belongs to the other in-flight change.** It was "the
    map and search builder"; `changes/like-with-like/` gives the word "map" to the surface that has
    earned it, and two surfaces whose names both contain "map" is the exact ambiguity that change
    exists to remove. What the first one has is a map for drawing the areas a search covers, which
    is a tool on a builder rather than a way of reading a run, so it is the search builder. Recorded
    in this delta because this is the delta that rewrites the sentence; if the two are folded in the
    other order, the rename still happens here and the other change's naming sweep finds nothing
    left to do in this line.

- **Everywhere else the specification says "the map" and means the search builder.** Renaming the
  surface in the vocabulary and stopping there would be worse than not renaming it: the word would
  be defined as one surface and still used for the other in six places, which is the ambiguity this
  was meant to end, dressed as a definition. Each is a wording correction and none of them changes
  behaviour or has any code behind it, which is why no task claims them.

  - The settings user story: "a background for the map" becomes "a background for the maps". Both
    surfaces draw the configured background and always have.
  - The scenario "drawing and saving a search": "Given the map surface" becomes "Given the search
    builder".
  - The scenario "a map with nothing behind it": "When the map is opened" becomes "When the search
    builder is opened". The coordinate grid is the search builder's, drawn by `search.js`, and the
    map page says so about itself in as many words: it "draws its own grid and says what is missing,
    and nothing here has an opinion about that."
  - **AC-2**: "Areas can be drawn, named, and edited on the map" becomes "...on the search builder's
    map". This is the sharpest of the six: the renamed surface cannot draw an area at all.
  - **AC-25**: "where the map's tiles come from" becomes "where map tiles come from". This one is
    not a surface reference and never was. The tile configuration is one setting serving both
    surfaces, and the possessive is what made it read as belonging to one.
  - **AC-26**: "the map draws a labelled coordinate grid" becomes "the search builder's map draws a
    labelled coordinate grid".

  Left alone deliberately: AC-56, AC-58 through AC-62, AC-65 and AC-68 already say "the map" and
  already mean the surface this rename is for.

- **AC-1.**
  - Was: seven surfaces exist and are reachable: map and search builder, saved search list, results
    table, listing detail, run comparison, merge review queue, and the fire map.
  - Now: nine surfaces exist and are reachable, adding the settings surface, which has existed since
    the optional parts became configurable from the screen that reports them off, and the set-aside
    surface this delta introduces.

- **AC-23.**
  - Was: a saved search can be created, copied, paused, resumed, archived, and brought back from the
    interface; none of these six deletes anything; a paused or archived search is skipped by a run
    of everything, which reports that it skipped it, and still runs when asked for by name.
  - Now: unchanged in every guarantee, and bringing an archived search back happens on the set-aside
    surface rather than from a control that reveals archived searches among the watched ones. A
    paused search stays on the list, because a pause is a search somebody is still watching and
    means to resume, and a search that vanished when paused would be a pause nobody would use.

- **AC-27.**
  - Was: a saved search can be deleted; its definition is kept rather than unlinked so it can be
    restored with its areas and comments intact, and the interface offers that restoration.
  - Now: the same, and the restoration is offered on the set-aside surface rather than at the foot
    of the list of searches. The list says how many searches are set aside and where to read them;
    it does not carry them. Deleting is still offered from the search's own card, because that is
    where somebody decides it, and the two limits are still stated at that point rather than only in
    a document.

- **The user story about setting a search aside.**
  - Was: ...and so that a search I no longer want stops cluttering the list without taking the
    properties it found with it.
  - Now: ...so that a search I no longer want leaves the list entirely, is still somewhere I can
    find it and bring it back, and can finally be discarded when I am sure, without taking the
    properties it found with it. The story is not new; what it asked for was read too narrowly, and
    a strip of restore buttons at the foot of the list is not a search that has left it.

## REMOVED

Nothing. No guarantee is withdrawn: everything AC-23 and AC-27 promised still holds, and the only
control that disappears (the one that shows archived searches among the watched ones) was never a
criterion in its own right.
