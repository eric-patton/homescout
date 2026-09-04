# Proposal — browser-interface

**Trigger:** The person the map is drawn for, after reading about the Santa Teresa project: "would
be good to have a layer on the map for current data centers, future known, guaranteed data center
sites, and proposed possible future data center sites (like awaiting approval, etc). just read
about a large data center that's going to be built in dona ana county."

**Summary:** A fourth thing to draw on the map, on exactly the terms the first three are drawn on:
off by default, public keyless national data, fetched by this machine and kept, and the person
decides. It reads the same indexes the enrichment pass builds
(`features/enrichment/changes/how-close-the-data-centers/`), at the same configured addresses, so
the layer has nothing of its own to keep current and one fetch serves both a column and a picture.
That is the arrangement AC-55 already describes for the fire layer.

Her three categories are the whole design, and they are one axis: how real is this. A building that
is running, a build that is approved and going up, and a proposal somebody has applied for are three
different facts about a piece of ground, and a person deciding where to live treats them very
differently. So the drawing distinguishes them along that axis and along no other, and it does it
with **fill rather than hue**, because hue is spent. The hazard layer underneath is a green to red
scale and the pins on top are gold, blue and red; a fourth family of colours on that map is a map
nobody can read. A solid shape is a thing that is there, a half-filled one is a thing that is
coming, and an outline is a thing somebody has asked for. That reads correctly without a legend and
survives being read over red.

**Cancelled and suspended projects are not drawn unless asked for.** The tracker holds 78 cancelled
and 69 suspended, and there is a good argument for seeing them: a proposal that was beaten here once
says something about here. There is a better argument against drawing them by default, and this page
has already made it. It once drew fifty-five houses that were no longer for sale, pinned exactly
like the ones that were, and the fix was a box that defaults to hiding them. A cancelled data center
drawn beside a real one is the same mistake with worse consequences, so it takes the same shape of
answer: available, off, and clearly labelled when on.

**How well each location is known has to be visible, or the layer lies.** The tracker rates its own
siting: 1,310 pinned, 303 to the right town, 50 to a county. The last group is not a small error.
The seven-thousand-megawatt New Era proposal is recorded at a city of "Lea County", 4,400 square
miles, so its stored point is a county centroid, and drawing it as a crisp square on a specific
patch of desert would put a data center on somebody's particular horizon on the strength of nothing.
So the drawing carries its own uncertainty: a precisely-known site is drawn at a size that means
where, and a county-level one is drawn as a mark over the county that means somewhere in here. The
column half of this change refuses to give those a distance for the same reason
(`feat-007/AC-32`); this half refuses to give them a location they have not got.

**The mapped buildings are drawn as buildings.** The OpenStreetMap half of the index is polygons,
so it goes on the map as outlines of the actual campuses rather than as pins. That is not decoration.
It is the clearest possible statement of the difference between the two sources: a shape with the
right footprint is a thing somebody surveyed, and a pin is a thing somebody announced. The six
buildings at Los Lunas drawn at their real size say more about what a data center is than any
legend would, which matters when the next question is about a 1,400-acre one.

## Blast radius

- **The map only.** No change to the results table, the listing page, the search builder or any
  other surface. One more layer, off by default, on the same terms as the wind and the county lines.
- **Two new read-only routes**, both thin over the indexes the enrichment change builds, and both
  read-only in the sense the rest of this page's routes are. No stored property value changes here;
  the values are the other change's business.
- **`fire.js` gains a layer and its toggle**, alongside `wind`, `land` and `rule`. The legend gains a
  block. The existing "nothing drawn over the properties takes the pointer off them except where it
  is actually drawn" rule of AC-60 applies to it, and this layer breaks it in a new way, since it is
  the first one with clickable shapes of real size rather than points or uncounted outlines.
- **The page's statement about what it fetches changes.** AC-55 says the page tells the person that
  drawing the hazard asks a federal server for what is on screen. This adds two more hosts, neither
  federal, and both are fetched by this machine rather than by the browser, which is the rule the
  hazard tiles already follow.
- **Attribution appears on the map**, which is new: no layer here has required it before. Both
  sources are free to use and both require credit, one by its terms and one by the Open Database
  License.

## What this trades away

**No count, no density, no colouring of houses.** The map says where they are and what kind. It
does not shade a region by how many, and no property is scored, ranked, hidden or coloured by its
distance from one, which is the rule AC-56 already states for this page and which this change does
not get to bend.

**No filtering of the layer beyond the categories.** The tracker holds megawatts, acreage, operator,
cooling and community opposition, and all of it goes in a bubble when a shape is opened. None of it
becomes a control. The three categories are what was asked for, and a panel of filters over
somebody else's dataset is a second product.

**Both sources drawn, neither de-duplicated.** A site the tracker knows and OpenStreetMap has mapped
appears as a pin inside an outline. That is honest, it is legible, and it is the visible form of the
same decision the column half makes for the same reason: the two sources disagree about what exists,
and papering over the disagreement would hide which one to trust.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
