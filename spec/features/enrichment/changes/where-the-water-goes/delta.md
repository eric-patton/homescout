# Delta: enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

### Soils

- **AC-41**: A soils provider exists, is individually enableable, is registered like every other
  provider, and requires no change to the enrichment pass. It supplies five values from the USDA
  NRCS Soil Data Access service, keyless and national, one paced request per location:
  `soil_flooding`, the soil map unit's flooding frequency class; `soil_ponding_percent`, the share
  of the unit that ponds; `water_table_cm`, the shallowest depth to a seasonal water table in
  centimetres; `soil_drainage`, the unit's wettest drainage class; and `hydric_percent`, the share
  that is hydric (wetland) soil. The query sent is built only from the two coordinates, each checked
  to be a number, and from nothing a page or a saved search supplied.

- **AC-42**: The words are the source's own classes, read rather than inferred, in lower case:
  `none`, `very rare`, `rare`, `occasional`, `frequent`, `very frequent` for flooding, and the seven
  drainage classes from `excessively drained` to `very poorly drained`. The flooding class is the
  worst among the unit's major components as the source computes it. The legacy class `Common`,
  which a handful of older surveys still carry, reads `frequent`, because it is the older name for
  occasional-to-frequent and the cost of reading it low falls entirely one way. A class this build
  does not recognise is a failure naming it, never a guess. Reading `Common` as `frequent` is the
  one written exception to that rule, and it is not a guess at an unknown code: `Common` is a
  documented legacy class whose range runs from occasional to frequent, and it is read at the top of
  that range because reading it low costs somebody a damp house.

- **AC-43**: Three readings stay apart. A place with no soil survey reads `soil_flooding` as `not
  surveyed`, a determined value, as the interface provider's `outside coverage` is. A surveyed place
  where the survey records no seasonal water table leaves `water_table_cm` empty, and every surface
  that shows it says the survey records no water table (on the listing page, the command line and to
  the assessment model in those words; in the table and the sheet, `none recorded`) rather than "not
  known". A place nobody asked about has no value at all. Wherever these values are shown, two
  caveats travel with them: a soil value describes a map unit, which can be hundreds of acres,
  rather than the parcel; and soil flooding is overbank river flooding of the soil, which says
  nothing about flash floods arriving down a wash.

### Flash-flood history

- **AC-44**: A flash-flood provider exists, is individually enableable, is registered like every
  other provider, and requires no change to the pass. It supplies five values, named because a
  person types them into a saved search: `flash_flood_warnings`, how many National Weather Service
  flash-flood warnings have covered the point since 2008; `flash_flood_emergencies`, how many of
  those were ever raised to a Flash Flood Emergency; `flash_flood_latest`, the date of the most
  recent warning that covered it; `flash_flood_latest_year`, that date's year, as a number a
  criterion can compare; and `flood_reports_nearby`, how many flood, flash-flood or debris-flow
  storm reports were filed within one mile since 2005. It needs no credential.

- **AC-45**: The values are answered from locally held records, fetched whole a state at a time for
  the states the store's properties are in, through a spatial index, as the data center provider
  answers from its own (AC-29, AC-37). Building them is a side effect of a pass that finds them
  stale, decided once per pass and never per location. A year that has ended is fetched once and
  never again, because a closed year's warnings do not change; the current year and the storm
  reports are held for seven days. A year's file fetched before that year closed (or within a week
  of its end) is fetched once more after it closes, and is then held for good. A pass over a state
  whose records are fresh makes no request.

- **AC-46**: Each warning is counted once, by its identity: the issuing office, the phenomenon, the
  significance, the event number and the year. The polygon counted is the one issued, which is the
  warning's widest extent, since an update can only shrink it. A warning is an emergency if it was
  ever raised to one, including by a follow-up statement, which is how most of New Mexico's were
  declared. The damage threat the Weather Service attached (considerable or catastrophic) is kept
  with it, worst first, for the map to show (`feat-010/AC-99`).

- **AC-47**: A point in a state whose records are not held reads as missing, never as zero, because
  zero means "held, and never warned". A refresh that fails leaves the held records in use and
  labelled stale, as every other stale value is (AC-7). The storm reports are a separate record from
  the warnings, and failing to fetch one does not take the other's values with it.

- **AC-48**: What these values are is said wherever they are read. A warning says where the
  Weather Service warned, not where water went, and its polygon is drawn wide (a median of about
  550 square kilometres in New Mexico); "warned" is the word, never "flooded". An emergency polygon is
  drawn over whole towns. A storm report is positioned to about a kilometre, usually as an offset
  from a named place, which is why reports are counted within a mile rather than at the point.
  Dates are the local standard time of the place, worked out from its longitude, so a warning issued
  on a September evening is dated that evening rather than the next day in Greenwich.

- **AC-49**: Everything these sources say in words is data. A report's remark is shown as text and
  never as markup, and the archive's own ready-made HTML link is not kept at all.

### Streams and arroyos

- **AC-50**: A streams provider exists, is individually enableable, is registered like every other
  provider, and requires no change to the pass. From the USGS National Hydrography Dataset, keyless
  and national, one paced request per location, it supplies `stream_feet`, the distance to the
  nearest mapped natural channel within a mile, and `stream_nearest`, which channel that is: its
  name where it has one, whether it is perennial, intermittent or ephemeral where the dataset says
  (a plain `stream`, or a `river` drawn through a lake, where it does not), and the distance again
  in words. A natural channel is a stream, river or wash, including the line a river is drawn along
  through a lake; a canal, ditch, pipeline or underground conduit is not, because water does not
  leave one of those the way it leaves an arroyo. With no channel within a mile, `stream_feet` is
  empty and `stream_nearest` says `none mapped within a mile`, which is an answer.

- **AC-51**: The distance is measured to the channel's line rather than to any point on it, and is
  reported to the nearest ten feet, which is finer than the map it is measured on and no finer. Its
  cache key rounds to five decimal places, about a metre, so the key is finer than the number it
  keys, which is the promise AC-32 makes for data centers. A mapped channel is a channel somebody
  mapped: an unmapped wash can be closer, and this is said where the value is shown.

### Dams

- **AC-52**: A dams provider exists, is individually enableable, is registered like every other
  provider, and requires no change to the pass. From the USACE National Inventory of Dams, keyless,
  it supplies four values about high-hazard dams, which are the ones whose failure would probably
  cost a life: `dam_miles`, how far to the nearest one among the states held for this property (its
  own and its neighbours, AC-53), to a tenth of a mile, at any distance; `dam_nearest`, what that
  dam is (its name, its inventory id, the year it was built, its condition and when that was
  assessed, whether it has an emergency action plan, and the distance); `dams_nearby`, how many lie
  within ten miles; and `dam_worst_nearby`, the worst condition among those, or `none within 10
  miles`. Each held dam also keeps its primary purpose and owner, which no value carries and the map
  shows when the dam is opened (`feat-010/AC-100`). Where no high-hazard dam is held at all,
  `dam_miles` and `dam_nearest` are empty, `dams_nearby` is 0 and `dam_worst_nearby` is `none within
  10 miles`.

- **AC-53**: The inventory is fetched whole a state at a time, for the states the store's properties
  are in and the states bordering them, because a dam ten miles away can be across a state line. It
  is held for ninety days, refreshed as a side effect of a pass that finds it stale, and a point in a
  state whose inventory or neighbours' inventories are not held reads as missing. The inventory's
  codes are mapped by a table written down here rather than inferred: condition 1 to 6 is
  satisfactory, fair, poor, unsatisfactory, not rated, not available; hazard 4 is high; emergency plan
  1 to 3 is yes, no, not required. `not rated` and `not available` both read `not rated`, which is
  never read as satisfactory. A code this build does not recognise is a failure naming it.

- **AC-54**: "Near" is said, and "downstream" never is. The inventory places each dam as one point
  on a structure that can run more than a mile, and inundation maps for local dams are not public,
  so nothing here knows which way a dam drains. The inventory is credited where its data is shown,
  and the README credits all four of this change's sources: the inventory, the Weather Service and
  Iowa State's archive of it, the Natural Resources Conservation Service, and the U.S. Geological
  Survey.

### All four

- **AC-55**: Enriching a fully cached area of five thousand properties stays inside the performance
  requirement with these providers registered, and the two that hold records answer through a spatial
  index. A test asserts the time for each of the two, in the shape AC-37 already asserts it for data
  centers.

## MODIFIED

- **AC-11, which providers exist**
  - Was: providers for flood zone, broadband service, principal aquifer, wildfire hazard, elevation,
    boundary resolution, wildland-urban interface, county, and data center proximity.
  - Now: the same list, plus soils, flash-flood history, streams and arroyos, and dams.

- **Non-functional requirements, performance: what bounds a cold pass**
  - Was: "A cold pass is bounded by provider pacing rather than by local work, for every provider that
    asks a question per location, which is all of them but one."
  - Now: all of them but three. The flash-flood and dam providers, like the data center provider,
    make no per-location request; their cold pass is bounded by local work, which AC-55 keeps small.

- **Non-functional requirements, security: the count of keyless providers**
  - Was: seven of the eight are keyless public services and the eighth needs no credential either;
    broadband remains the one exception.
  - Now: every provider but broadband is a keyless public service; broadband needs its FCC
    account, as before. Counting them had already drifted once, so the sentence no longer counts. The soils query is
    the first request here with a body, and the body is built from two checked numbers and a fixed
    query text, nothing else.

## REMOVED

Nothing.
