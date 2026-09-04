# Proposal — enrichment

**Trigger:** The person the map is drawn for, after reading about the Santa Teresa project in the
paper: "would be good to have a layer on the map for current data centers, future known, guaranteed
data center sites, and proposed possible future data center sites (like awaiting approval, etc).
just read about a large data center that's going to be built in dona ana county."

**Summary:** She asked for a map layer, and the map layer is a separate change against the browser
interface. This one is the half that belongs here, and it exists because the question she is really
asking is the question this feature answers rather than the one a map answers. A layer says where
they are. What a person searching for a house in southern New Mexico wants to know is whether *this
house* is near one, and near which kind, over two hundred rows at a time. That is a value attached
to a location, cached, and readable by a criterion, which is what this feature is.

There is a second reason it belongs here and not only on the map, and it is the reason the fire map
exists at all. That page was built because the wildfire layer is served as tiles, so nothing in this
tool can measure the distance from a house to the nearest red, and the eye had to do what no column
could. Data centers are not tiles. They are points and building polygons, so the distance is
genuinely computable, and the thing the fire map had to hand to a person's eye can here be handed to
a column and to a rule. Refusing to compute it, when it is computable, would leave the tool weaker
than the data.

**Where the data comes from, and what each source is good for.** Two sources, because neither is
enough on its own and the gap between them runs exactly along the line she drew.

The FracTracker Alliance publishes a US data centers tracker as a public, keyless, query-enabled
ArcGIS service, in the same request shape half the providers here already speak. It holds 1,665
sites, it carries the status of each one, and its statuses map onto her three categories almost
word for word: 530 operating and 68 expanding, 172 approved, permitted or under construction, 738
proposed and 10 pre-proposal, plus 69 suspended and 78 cancelled. Every record carries an operator,
a megawatt figure, an acreage, a county, and the sources the entry was built from. It is actively
kept: the newest edit when this was written was four days old. The project she read about is in it,
as "Project Jupiter" at Santa Teresa in Doña Ana County, approved and under construction, Open
AI/Oracle, 700 MW on 1,400 acres. No other free national source carries a *status*, and the status
is the whole of what she asked for.

It has one flaw and it is not a small one. FracTracker's interest is contested projects, so what it
records well is what somebody objected to. Virginia has 463 records and New Mexico has 9. Meta's
campus at Los Lunas, operating since 2018 and one of the largest buildings in the state, is not in
it at all. A tool that answered "the nearest operating data center is 190 miles away" to a house in
Valencia County would be confidently wrong, and would be wrong in the direction that costs
somebody something.

OpenStreetMap closes that gap and closes it well. Its `telecom=data_center` tag and the two older
tags beside it hold 1,778 US features, including all six Meta buildings at Los Lunas, Sandia's
high-performance computing centre, the university's, and CenturyLink's. They are mapped buildings
and campuses rather than announcements, so they are polygons with real edges: the distance is to
the edge of the thing rather than to a guess at its middle, which is better than what the tracker
can give even where the tracker has the site. What OpenStreetMap has no concept of is a building
that does not exist yet, so it answers the first of her three categories and none of the second or
third.

So the two divide cleanly: OpenStreetMap knows what is built, the tracker knows what is coming.
Together they answer all three. Neither needs a credential.

**What was rejected.** The Pacific Northwest National Laboratory publishes an Open Source Data
Center Atlas, which is a processed, footprint-bearing, county-tagged extract of exactly the
OpenStreetMap data above. It was rejected because it is a February 2026 snapshot of a source we can
read live: taking it would mean the same features, seven months staler, behind a manual download.
The commercial trackers (Data Center Map, Baxtel) are paid data APIs and are out by the
constitution.

**The sharp edge, and how it is settled.** The tracker rates how well it knows each site's
location: 1,310 high, 303 medium, 50 low. Low is not a small imprecision. The 7,000 MW New Era
proposal is recorded at a city of "Lea County", which is 4,400 square miles, so the stored point is
a county centroid and the distance to it is a number about nothing. Medium is the Project Jupiter
case: the right town, not the right parcel.

Turning any of that into a distance is the failure this product already refuses by name. The
rainfall value will not interpolate a county figure down to a house, because it would "look like it
was measured at the house"; the broadband values say on every surface that they are for the block
rather than for the property. A distance carries no such label, because a number looks measured by
construction.

So the precision of the number is made to carry the caveat, which needs no second column and cannot
be skipped by a reader the way a footnote can. A site the tracker locates precisely gives a
distance to a tenth of a mile. A site it locates to a town gives a whole number of miles: five
miles rather than 5.3, which is a claim the source can support. A site it locates only to a county
gives no distance at all, because there is no honest number to give; instead it is named as
standing somewhere in this property's county, which is the grain the source actually knows, and is
an answer rather than a gap. OpenStreetMap footprints are surveyed geometry and take the finest
precision.

That last part is load-bearing for a reason that has nothing to do with taste. Without it, a house
in Lea County with a 7,000 MW proposal beside it would read as an empty cell, and an empty cell
here means nobody asked. That is the exact confusion AC-7 exists to prevent, and it would be
manufactured by this change rather than inherited.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected:** AC-11 (which providers exist) gains one. AC-1 (a provider is a plugin
  the pass never names) is not changed and is what makes this a new module rather than an edit.
  AC-16's shape is followed but not its letter: like broadband, the values come from a locally held
  index rather than a per-property request, and unlike broadband the index is not an explicit
  action, because the whole country is 1,665 rows in two requests and 1,778 features in one, rather
  than the FCC's gigabytes. AC-12 (coverage) is satisfied without amendment, since both sources are
  national, but the tracker's under-counting is a different thing from a coverage gap and has to be
  said somewhere a reader meets it. AC-7 (missing is not false) is what the county-grain value
  exists to protect. The security requirement's count of keyless providers changes again.
- **Design decisions affected:** the cache is used at a grain it has not been used at before. Every
  existing provider caches an answer per rounded location; this one caches an *index* per source
  and computes per location from it, with no outbound request in the per-location path at all. That
  is closest to broadband and needs recording as a decision, along with the two time-to-lives,
  which are not alike: a mapped building is effectively permanent, and a project's status is the
  most perishable value this feature holds. A status that changed from proposed to approved six
  months ago and still reads proposed is worse than no value.
- **Tasks affected (regenerate these):** none of the existing ones. New tasks for the two index
  readers, the provider, the two endpoint entries, the namespace fields, the export columns, the
  tests, and the README.
- **Already-built code affected:** `enrich/providers.py` (a new provider), `enrich/settings.py`
  (two new endpoint entries), `enrich/registry.py` (the registration, whose import-time check
  against the rule namespace runs both ways and will fail until the fields exist),
  `rules/namespace.py` (five new enriched fields), `export/columns.py` and the export templates
  (columns outside the default set, as wildfire hazard already is), and whatever the command line
  and the browser use to render an enriched value. One new module for the indexes themselves.

## What this trades away

**A distance to the nearest, and not a count of what is around.** Three houses each four miles from
one data center read identically to a house four miles from a cluster of nine. The tracker holds
enough to count them, and counting is deliberately not done here: the map is where "how much of
this is there" is read, and a second family of columns to answer it would be five more columns for
a question the eye answers better.

**A number that is honest rather than tidy.** Mixing tenths and whole miles in one column looks
untidy, and that is the point: the untidiness is the source's, and hiding it would mean choosing
between claiming precision the tracker has not got and throwing away precision OpenStreetMap has.

**Both sources are drawn on, and neither is de-duplicated.** A site in both is measured twice and
the nearer wins, which is harmless for a nearest-distance and would not be harmless for a count.
That is a second reason there is no count.

**Nothing is scored, ranked or hidden by any of this.** No rule ships that acts on these values.
What a person does with "two miles from a 1,400-acre approved build" is theirs to decide, and this
feature has never decided anything.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
