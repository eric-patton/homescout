# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-76 and AC-77.

**User story.** As the person reading four screens about the same search, I want each number to say
what it is counting, so that four different totals read as four questions rather than as a fault.

- AC-76: Every count of properties on every surface says which properties it counts, in the words
  beside it rather than in a tooltip. They are four different questions and the same noun on all
  four is what makes them read as a contradiction: how many this workspace watches across every
  search, how many the latest run of one search found, how many were matched against an earlier run,
  and how many of them can be drawn on a map. No number changes; what changes is that each one is
  named. Where a surface holds properties back, why and how many is already said separately
  (AC-36, AC-57) and stays there.

- AC-77: A property with no address is named for what is known about it rather than by its
  identifier. The identifier is exact and is kept, on the page and as the way to ask for the
  property again; it is not what a person is asked to read, recognise or say aloud. This applies
  wherever a property is named: its own page, the run comparison, the results table and the map.

## MODIFIED

- **AC-9.**
  - Was: the listing detail shows photographs, the full description, enriched values, a link per
    source, its price and status timeline, and the source rows the record was built from.
  - Now: the same, and a property with no address is titled by what is known about it (AC-77) rather
    than by a thirty-two character identifier.

- **AC-11.**
  - Was: the run comparison lists each affected property once with its difference event, matching
    what the same comparison produces from a terminal.
  - Now: the same, and a property with no address is listed by what is known about it (AC-77). The
    comparison itself is unchanged: this is what the browser draws, and the terminal's own rendering
    of the same document is its own business.

## REMOVED

Nothing.
