# Proposal: browser-interface

**Trigger:** The same reading of the interface that produced `changes/the-list-is-what-you-watch/`:
"you didn't assess the filters and buttons and links being confusing. Like we have a fire map link
but it's more than that now, so it feels like a Map link would be better. Organizing the filters and
stuff would be nice too. Everything is just kind of all clumped together."

**Summary:** Three complaints, and they are one complaint. A control is hard to find when its name
is wrong, when it is in a row of eleven other controls, or when the surface it leads to is not
reachable from where you are. All three are true here at once.

**The name is wrong because the surface outgrew it.** "On the fire map" was accurate when the
wildfire hazard layer was the only thing that page drew. It now draws either background, the hazard
layer at any opacity, a ruler, which way the wind pushes by season, county lines, town names,
rainfall per county, and a sortable list of everything pinned, and keeping or passing a house can be
done from a pin. Calling that "the fire map" tells somebody it is one overlay when it is the second
way of reading a whole search. The two newest criteria in this feature already call it "the map";
the link never caught up.

**The controls are clumped because nothing groups them.** The results table's toolbar is a search
box, five checkboxes, two buttons, then a second line carrying counts and four links, all at one
weight and in one flow. Three different questions are mixed together and read as one: which rows am
I looking at, which columns am I looking at, and where else can I go. The map's row is worse: ten
controls, three separate live count regions and a link, with labels running into each other so that
"satellite view fire layer" reads as a phrase before the slider beside it is noticed.

**And the reasons rows go missing are split across two places.** The bar above the table exists for
a stated reason: a table quietly missing four hundred rows is the worst thing this screen can do, so
every filter in force is named in words with its own control to lift it. But it is built from the
column filters and the search box only. The three controls that hide by far the most rows are not in
it. In the workspace this was read against, 737 of 951 rows were hidden because they had been passed
on, and the only sign of it was a grey line that also reported a render time in milliseconds. The
bar is right about what it is for and wrong about what it contains.

Two of those three controls are also two controls over one field. "Show properties you passed on"
and "only what you kept" both narrow by judgment, the code has to order them carefully so they
cannot contradict each other, and nobody reading the toolbar can work out what ticking both does.
One field gets one control.

**Navigation is the same problem at the level of pages.** A saved search has five screens joined by
hand-placed one-way links. The search builder reaches none of the other four. A property's own page
reaches nothing at all, so the way back to a thousand-row table is the browser's back button, which
loses the place in it. And the navigation bar names the same three destinations on every screen, so
on any per-search page it reports "Searches", which is where you are not.

## Blast radius

- **Requirements affected here:** the vocabulary (what the map is called), AC-1, AC-35, AC-36,
  AC-49 and AC-57 by modification; AC-51 and AC-58 through AC-62 by the naming sweep only, where
  "the fire map" becomes "the map" and nothing else about them moves.
- **Design decisions affected:** none reversed. The reason the filter bar exists is the reason this
  change puts more into it.
- **Already-built code affected:** `web/static/results.js` (the toolbar, the filter bar, the
  judgment control), `web/static/fire.js` (the toolbar, the heading), `web/static/searches.js` and
  `web/static/changes.js` (the links that name the map), `web/static/common.js` (one shared builder
  for the per-search navigation, so eight pages do not each grow their own), `app.css`.
- **No server change and no core change.** Every part of this is what a surface draws and what it
  calls things. If any of it needs an API change, that is a sign it has been designed wrong.
- **One thing this deliberately does not touch:** which rows are hidden by default. The judgment
  control's default answer produces exactly what the two unticked checkboxes produce today, so a
  person who opens the table after this change sees the same rows they saw before it.

## Open decision

Whether the map's address changes with its name. It is `/fire/{name}` now; `/map/{name}` matches
what the surface is called, and any bookmark or note pointing at the old one stops working. Recorded
as an open decision rather than guessed, because it is the only part of this change that can break
something outside the tool.

## What this is not

Not a redesign of the results table. The table itself, its virtual window, its column arrangement
and its inline editing are untouched. This is the strip above it.

Not fewer controls. Every control that exists still exists and still does what it did, apart from
the two that become one. Grouping is not hiding: a group is named and open, not a menu.

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
