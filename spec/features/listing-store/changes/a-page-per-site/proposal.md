# Proposal — listing-store

**Trigger:** The person reviewing results asked for it, in these words: "it would be helpful to have
a redfin link for these, to be able to add them to a list, or see if they're already on a list. if
that's not possible, a realtor.com listing would be helpful."

**Summary:** A merged property is one record here and up to three pages out there, and the store
keeps only enough to say *which* sites it was seen on, not *where* on each. `SourceLink` carries the
source's name and the source's own identifier; the page address is on the raw row underneath and
nothing surfaces it. So a person is offered the one `listing_url` the canonical record settled on,
which is whichever site happened to win, and if they keep a list on a different site they cannot get
to the page they need.

That matters more than it sounds. These sites are not interchangeable views of the same data. A
house on Realtor is not necessarily on Redfin at all: in the last statewide run, Realtor returned
1,099 rows, Zillow 866, and Redfin 58, because Redfin's download excludes what its local MLS does
not permit. Somebody keeping a shortlist on one site has to be able to tell "this house is not on
that site" apart from "this tool only gave me one link".

This adds the address to the link record. It is already in the store, on `raw_listings.listing_url`,
already joined by the query that builds a `SourceLink`, and one more column in the SELECT.

## Blast radius

- **Requirements affected here:** the source-link record only. No table changes, no migration: the
  column being read already exists and is already populated by every adapter.
- **The browser (feat-010) and the command line (feat-003)** both show how a record was assembled
  and both gain the address there. Product invariant 5 means neither may have it alone.
- **The spreadsheet export (feat-011) is out of scope.** Its `Listing URL` column is one cell, one
  address, and a sheet with three link columns is a different question from this one.
- **Merging (feat-002) is untouched.** Which rows belong to one property is decided exactly as
  before; this only reports where each of those rows can be read.
- **Code touched:** the `SourceLink` model, the query in `source_links`, the listing answer's source
  list, and the two surfaces that print it.

## What this is not

Not a second canonical URL, and not a change to which address the record's own `listing_url` holds.
The property still has one address of its own; this is the provenance list saying where each of the
rows underneath it lives.
