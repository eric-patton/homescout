# Research — property-assessment

## Discovery input

From the reading of the interface on 2026-08-29 and the conversation that followed it. The person
running searches, after being shown that the model pass now streams its progress properly:

> couldn't we make this more useful then by having the AI do a real full assessment on properties
> that we haven't hidden or rejected? Still do what it is doing now, but giving us an overview of
> any findings it has or how it measures against what we have in our prompt to it of things we are
> looking for or not looking for? Maybe even showing it some images or the fire map plus wind
> directions?

Everything below was measured against the live workspace rather than assumed, because the whole
question is whether there is enough on hand to make a judgment worth reading.

### What the existing model pass actually does, measured

- Eighteen real requests through the configured model over a copy of the store. It works: it
  returned `water_source: well` from "a private well producing delicious, fresh water" and
  `mini-split` for both heating and cooling from one phrase, each with the verbatim quote the
  instruction asks for, and it correctly declined a listing whose text said the property "could be
  annexed into the city which would give the buyer city water", which is water it might get rather
  than water it has.
- Two passes on the live store asked about eleven descriptions between them and recovered values
  from two. That is not a fault. The deterministic patterns settle the easy cases first, so the
  model is only ever handed the leftovers, and a leftover is usually a description that does not
  mention the roof at all.
- It is blindfolded on purpose and its own code says so: it is handed prose, a vocabulary and the
  operator's notes, and *not a listing, not a snapshot, not a store*, on the grounds that there is
  no address in scope there to send. That is right for transcription and is exactly why that pass
  cannot answer the question being asked here.

### What is on hand per property

Counted in the live store on 2026-08-29:

| | |
|---|---|
| Properties in play (latest run, not passed on, not off-market) | 155 |
| In the latest run | 951 |
| Canonical listings in the store | 1,328 |
| Marked keep / passed on | 8 / 804 |
| Listings with a stored photograph | 2,650, exactly one each |
| Flood zone, interface rating, broadband | 1,821 each |
| Wildfire hazard, elevation, county | 1,436 each |
| Over a principal aquifer | 943 |

The working set is the number that decides feasibility. A pass over 155 properties is one pass of
twenty to thirty minutes and then only what a nightly run brings in; a pass over 951 would be a
different proposition and a pass over every description in the store is not one worth having.

### The criteria are already written down, in three places, and none of them reaches a model

- **Eight exclusion areas, each with a paragraph of reasoning** in the saved search. Not
  coordinates with a label: the dairy and feedlot concentration behind the odor, the flaring and
  truck traffic and the waste repository, mining-affected groundwater that reaches Gallup, booms
  that carry across the whole Tularosa basin rather than one part of it. This is the best statement
  of this household's taste anywhere in the workspace.
- **Twenty rules**: the hard cuts (flat and foam roofs, manufactured construction, insurable flood
  zones, fire that could reach the house), the things worth seeing but never worth hiding (moderate
  hazard, standing against vegetation, indoor wood smoke, on a well), and the preferences that only
  reorder (metal roof, under 800k, not on town sewer).
- **Standing screening reasons** left in annotations by an earlier pass: off-grid and
  solar-reliant, production-builder plan homes, listings with no bedrooms that read as land, lot
  sizes the source cannot mean.

### What the store cannot answer, checked rather than assumed

- **Wind is per weather station, not per property.** Roses are fetched once and kept, each station
  carries coordinates, and seasons are available. Nearest-station is arithmetic over data already
  on disk; the distance to that station is real and can be forty miles.
- **There is no distance to the nearest hazard.** The wildfire and interface layers are served as
  map tiles, not as queryable geometry. The property's own rating is known; what is next to it is
  not, except as a picture.
- **One photograph per property.** 2,650 listings hold exactly one image, the primary exterior
  shot. There is no interior and no gallery.
- **Aquifer coverage is partial**, 943 of 1,821, and the enrichment contract already requires
  outside-coverage to read as not applicable rather than as an answer.

## Problem brief

### Problem statement

Someone deciding which rural properties are worth driving to struggles to use what this tool has
already collected, because the criteria that matter are spread across a saved search's prose, a
rule engine's verdicts, six enrichment fields and a photograph, and nothing reads them together.
The result is that 155 properties sit in a table with no summary of what is wrong with any of them,
and the one model pass that exists is deliberately forbidden the address, the picture and the
hazard rating, so it can transcribe a description and cannot judge a property. A solution should
read each property still in play against the criteria this household has already written down,
report what it finds and what it cannot know, and record that beside the person's own judgment
rather than inside it, without ever removing a property from view or deciding anything.

### Target users

- **The person running searches** (primary): wants to know which of the 155 are worth a drive and
  what to check before going, without opening each one and cross-referencing four columns.
- **The nightly job** (secondary): should assess what a run brings in, so the digest can lead with
  what is worth looking at rather than with a count.

### Jobs to be done

- When a run brings in new properties, assess only those, so a full pass is paid for once.
- When reading the table, see a short account of each property and its concerns, with the evidence
  for each, so a row can be dismissed or promoted without opening it.
- When something the household already ruled out appears again in different words, have it named,
  because the exclusion areas and screening reasons describe worries rather than fields.
- When the model is wrong, disagree with it in a way that persists and is visibly the person's.

### Success signals

- Every property in play carries an assessment, refreshed when what it was assessed from changes.
- A concern the model raises cites the words or the value it came from, so it can be checked.
- Nothing the person wrote is ever overwritten, and nothing is hidden by an assessment.
- The first pass costs a stated amount and the steady state costs a handful of requests a night.

### Constraints

- Non-negotiable 7 and the store's own declaration: annotations are the user's own judgment, never
  written by a run. The assessment goes beside them.
- Non-negotiable 8 and invariant 5: one core operation, both surfaces.
- Non-negotiable 10: paced like every other outbound request.
- Invariant 9: absent-by-default. With no model configured the tool is fully functional and this
  feature is simply not there, exactly as feat-009 already is.
- Invariant 10: a field that could not be determined is empty and never a guess. Applied here to a
  judgment: an assessment says what it could not tell.
- The constitution's privacy line: the only outbound traffic is listing sources, public enrichment
  endpoints, the extraction model and SMTP. This feature sends more to the model than feat-009
  does, and that is the deliberate change, not an oversight.

### Explicitly out of scope

- Deciding. No assessment keeps, passes on, hides, reorders or filters anything by itself.
- Writing into the person's annotation columns.
- Interior condition, valuation, or anything resembling investment advice.
- A second model client, a second set of settings, or a second pacing policy. It uses feat-009's.
- Fetching new data to assess with. It reads what enrichment and the sources already collected.

### Open questions

1. **What invalidates an assessment?** A price change probably should not; a new description, a
   changed hazard rating, or an edit to the household's criteria probably should. feat-009 already
   solves the shape of this by fingerprinting the operator's notes into its cache key.
2. **Which season's wind rose?** April is what matters for smoke and dust in eastern New Mexico and
   is what the map already defaults to, but the rose is available per season and per year.
3. **Does it run inside a nightly run, or only when asked?** Inside means the digest can lead with
   what the model thought. On demand means never paying for a property that would have been passed
   on in two seconds.
4. **How much of the model's uncertainty is worth recording?** A concern it is unsure of is still
   worth seeing; a page full of hedges is not.
