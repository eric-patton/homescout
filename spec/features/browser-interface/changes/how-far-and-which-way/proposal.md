# Proposal — browser-interface

**Trigger:** Two asks, both about the fire map, both from the same afternoon of using it. In her
words: "I want the maps to have a measurement scale to let me have an idea of distances at different
zoom levels. It would be great if I could move it around even." And: "Can this also have an overlay
of wind direction?"

**Summary:** The fire map answers "what is this house next to" by eye. Both of these are the next
question after that one, and neither is answerable by looking harder.

**How far.** A scale bar in a corner tells somebody how big the screen is. It cannot tell them how
far this house is from that red, because the two things being compared are somewhere else on the
map and a bar fixed in a corner cannot be held up against them. So there are two things here: the
bar, which answers the glance, and a ruler, which is the bar taken off the corner and made
draggable. Once a thing is movable and has two ends it may as well say what is between them, so it
reads its own length in miles, and in feet below the point where a mile stops being a picture
anybody has.

**Which way.** "Half a mile from the red" means different things depending on whether the wind
normally comes over that red or normally carries away from it, and no value in this tool says which.
That is a real gap and not a nicety: a house upwind of a hazard and a house downwind of the same
hazard at the same distance are in different positions, and the criteria cannot tell them apart.

The overlay is deliberately **not** a forecast. Thursday's wind is a fact about Thursday and a house
is a longer question than that. It is a wind rose: how often, across every hourly reading a weather
station has on record, the wind came from each of sixteen directions, and how often it did so hard
enough to move a fire. Iowa State's environmental mesonet holds the national archive of those
readings and will compute a station's rose on request, so thirty years of hourly observations for
Taos is one request rather than a dataset to keep.

Two months are offered and only two, because the archive answers about one named month or about all
of them and nothing in between. April is the default: in New Mexico it is both the windiest month
and the middle of fire season, which is not a coincidence.

## Blast radius

- **The fire map only**, plus one new source of public data and the two routes that reach it.
- **A new outside address**, which the privacy statement already covers: a public endpoint, read by
  the machine that already reads public endpoints, never by the browser. Nothing about what talks
  to the outside world changes.
- **Expensive, and asked exactly once.** A rose is a query across tens of thousands of hourly rows
  and takes about ten seconds. Its answer summarises decades, so it is kept on disk for good, and
  only the stations on screen are ever asked about: somebody looking at Taos waits ten seconds for
  Taos rather than four minutes for New Mexico.
- **The rule engine is untouched.** No criterion gains a wind test. This is a way of looking, like
  the map it is drawn on.
- **One existing test had to be re-aimed.** The map's "scores nothing" guarantee was asserted by
  banning the word "distance" anywhere in the page, and that stopped being the same claim once the
  page grew a ruler somebody drags. The ban moved to the function that turns a property into a pin,
  which is where the claim actually lives.

## What this is not

Not a forecast, and not a scoring pass. No property is ranked, hidden or coloured by where it sits
relative to any wind or any hazard, and no number here is computed on anybody's behalf: the ruler
measures what a person put it across, and the rose reports what an anemometer recorded.

## What it cannot say, which the page says

These are airport anemometers, ten metres up, in the open, tens of miles apart. A canyon has its own
wind and this knows nothing about it. What it says well is which way weather moves through a region.
