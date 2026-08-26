# Delta — enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-27.

**User story.** As the person reviewing results, I want the county filled in for every property that
has a location, so that an empty county cell means the property has no location rather than meaning
one listing site did not mention it.

- AC-27: A shipped provider answers which county contains a location, supplying `county_name`. A
  location the service places in no county returns an answer of nothing, which is a different thing
  from a location nobody asked about, and is cached like any other answer. The provider needs no
  credential, adds no new service address, and is added to the pass without changing the pass, which
  is AC-1 applying to it unchanged.

## MODIFIED

- **The count of shipped providers.** Was: six shipped providers plus the wildland-urban interface.
  Now: those seven plus the county. The statement of what each supplies gains one row.

## REMOVED

Nothing.
