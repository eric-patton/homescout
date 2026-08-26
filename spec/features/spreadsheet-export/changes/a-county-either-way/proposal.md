# Proposal — spreadsheet-export

**Trigger:** The blank `County/Region` cells the person reviewing results asked about, and the
county lookup added to enrichment (feat-007's change `which-county`) that can now fill them.

**Summary:** `County/Region` reads the listing's own county and nothing else. Two of the three sites
never send one, so on a statewide table a quarter of the column is empty, and the empty cell is the
site's silence rather than a fact about the house. Now that the public record can answer the same
question from the property's coordinates, the column should use it when the listing did not.

The one real decision here is what the cell says. Marking the borrowed answers, `Roosevelt (looked
up)`, would sort and group apart from `Roosevelt` and break the only thing this column is for. So
the cell holds the plain name either way, and provenance is kept in a second column beside it,
`County (looked up)`, which always holds what the public record said and nothing else. Anyone who
wants to know which cells were borrowed compares the two; anyone filtering by county gets one value
per county.

That second column is outside the default sheet, in the same place as `Wildfire Hazard` and
`Elevation (ft)`: real data, deliberately not in the promised document.

## Blast radius

- **Requirements affected here:** the `County/Region` column's source, which moves from the listing
  to derived, and the set of columns beyond the default sheet, which gains one.
- **The default sheet does not change.** Same columns, same order, same names. That promise is about
  a document the household already has.
- **Depends on enrichment (feat-007)** supplying `county_name`. With no enrichment run, the column
  behaves exactly as it does today: the listing's county or nothing.
- **The browser (feat-010) reads the same columns**, so the table fills in without a change there.
- **Code touched:** the column table and one new value function.

## What this is not

Not a guess and not a geocode of an address. It answers only for properties that already carry
coordinates, from the point they carry, and the listing's own word always wins where there is one.
