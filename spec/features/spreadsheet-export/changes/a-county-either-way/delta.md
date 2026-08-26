# Delta — spreadsheet-export

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-14 and AC-15.

**User story.** As the person filtering a thousand properties, I want every property that has a
location to show a county, so that sorting or filtering by county does not silently drop a quarter
of the table.

- AC-14: `County/Region` holds the county the listing named. Where the listing named none and the
  public record can say which county contains the property's location, it holds that county instead,
  as the plain name with no marker appended, so that the two spellings of one county sort and group
  together. Where neither can say, it is empty. A test covers all three.
- AC-15: A column outside the default sheet, `County (looked up)`, holds only what the public record
  said, so that which cells in `County/Region` were borrowed is answerable by comparing the two.

## MODIFIED

- **`County/Region`'s origin.** Was: `listing`. Now: `derived`, because it reads the listing first
  and the public record second.

## REMOVED

Nothing. The default sheet keeps the same columns in the same order under the same names.
