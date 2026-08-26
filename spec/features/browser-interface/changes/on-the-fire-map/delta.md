# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-55 and AC-56.

**User story.** As the person choosing where to live, I want to see every house on the fire map, so
that I can judge what a house is next to rather than only what it stands on.

**User story.** As the person choosing where to live, I want to say no to a house from the map, so
that the decision is made where the reason for it is visible.

- AC-55: Every property in a run that has a location is drawn on the wildfire hazard model, using the
  same layer at the same configured address the enrichment pass reads, with its own legend drawn from
  this tool rather than fetched. A property with no location is not drawn, and is counted and said
  so. How strongly the hazard layer is drawn can be turned down to read the map beneath it. Drawing
  it asks that server for the part of the country on screen, which the page states.
- AC-56: A property can be kept or passed on from its pin, with the same question about why and the
  same effect as from the results table, and the map reflects the decision at once. The page works
  nothing out and decides nothing: no property is scored, ranked, hidden or coloured by its distance
  from anything, because that would be a criterion with no rule behind it and no way to argue with.

## MODIFIED

- **AC-1.** Was: six surfaces exist and are reachable: map and search builder, saved search list,
  results table, listing detail, run comparison, and merge review queue. Now: seven, the seventh
  being the fire map.

## REMOVED

Nothing.
