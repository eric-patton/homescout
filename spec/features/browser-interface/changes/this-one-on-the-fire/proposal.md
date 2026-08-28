# Proposal — browser-interface

**Trigger:** "Would be nice if on the individual property pages, it showed a small firemap so you
could quickly see where that one was."

**Summary.** The fire map answers "which of these hundred is near the red". Somebody reading one
listing has the other half of the same question and no way to ask it: what is *this* one next to.
The answer today is to go back to the map and find the pin again, which is far enough away from
what they are doing that they mostly do not.

It is a map rather than a value for exactly the reason the big map exists at all: `wildfire_hazard`
is the ground the house stands on, and no column in this tool says what it is beside. That was the
whole argument for the fire map and it applies unchanged one property at a time.

Small, and interactive. Sixteen rems of height in the column that already holds the photograph and
the enrichment: enough to see a wall of red half a mile off, with dragging and zooming there for
the moment that raises a question.

## Blast radius

- **One section on the property page**, and one shared function. The tile-layer builder moves from
  the fire map into `common.js`, because two pages draw it now and the conversion from Leaflet's
  tile coordinates to the service's rectangle is exactly the sort of thing that gets written twice
  and then diverges by half a tile with no way to tell which page is right.
- **No new route and no new data.** The same layer, at the same address, through the same cached
  route this machine already serves, so opening a property twice costs nothing and nothing new
  talks to the outside world.
- **The property page now loads the map library.** It is committed with the tool and already loaded
  by the fire map.

## What this trades away

A little weight on a page that was text. It is drawn after the page is on screen and only for a
property that has somewhere to be drawn, so a page with no coordinates is a sentence rather than a
grey rectangle over the Atlantic.
