# Proposal — enrichment

**Trigger:** The person reviewing results asked, of the blank cells in the county column: "for the
ones that say not known for county - is that not listed in the data? if so, that is incredibly
helpful knowledge."

**Summary:** The county column is blank for a quarter of a statewide table, and the blank means
nothing at all. Measured on the run of 2026-08-26: Realtor sent a county on 1,097 of its 1,099 rows;
Zillow sent one on none of its 866, and Redfin on none of its 58. So the blank is one site's silence
and not a fact about the property, and it is impossible to tell those apart from the table.

County is not a decoration in this search. It decides the assessor and the tax bill, the fire
district, the well and septic rules, and which of the household's own exclusion areas a property
falls near. A person filtering a thousand houses by county was being shown an empty cell on a
quarter of them.

Every one of those properties has coordinates, and the Census answers what county contains a point.
This feature already asks that exact service, at that exact address, for what contains a shape
(`boundaries.containing`). This adds a provider that asks it for one point and one layer.

## Blast radius

- **Requirements affected here:** the set of shipped providers and the values they supply. The pass
  itself is untouched, which is AC-1 working as intended: a new provider is a new class and a line
  in the registry.
- **The rule engine (feat-008) gains a name.** `county_name` becomes an enriched field a criterion
  may test, which is required by the registry's own two-way check: a provider supplying a value no
  criterion can name is work nobody can use.
- **The spreadsheet export (feat-011) is where this becomes visible**, and is its own change: the
  `County/Region` column decides what to do when the listing site said nothing.
- **No new service, no new credential, no new address.** The Census geocoder is already configured,
  already paced, already cached, and its answers are cached under the same rules as every other
  provider's, with no lifetime, because county lines do not move.
- **Cost:** one request per distinct rounded location that has no cached answer yet, at the shared
  one-second floor.

## What this is not

Not a replacement for what the listing said. Where a site names the county, that is the county; this
answers only for the properties where nobody did.
