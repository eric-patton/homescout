# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-88**: The map can draw data centers, off by default, from the same indexes and the same
  configured addresses the enrichment pass reads, fetched by this machine rather than by the
  browser and kept, on the same terms as every other layer over the fire. It draws three kinds and
  tells them apart by how filled the shape is rather than by its colour: a data center that is
  operating, one approved or under construction, and one proposed. Hue is not available on this
  page. The layer beneath it is a green-to-red scale and the pins above it are already three
  colours, so a fourth family would be unreadable over half the map; fill also happens to be the
  right encoding, because the three categories are one axis, which is how real the thing is.

  Which of the three a site is arrives already decided. The source publishes seven statuses and the
  core collapses them (`feat-007/AC-31`); the routes serve sites already carrying one of the three,
  and the page draws what it is given. A `switch` over status strings in the browser would be
  business logic on this side of the line, which AC-14 and the constitution both forbid.

- **AC-89**: Cancelled and suspended projects are not drawn unless they are asked for, and say
  which they are when they are. This page has made this mistake once already, drawing fifty-five
  properties that were no longer for sale pinned exactly like the ones that were, and a project that
  was dropped drawn exactly like one that is being built is the same error about a larger thing. A
  proposal that was defeated here is worth being able to see, so it is offered rather than removed.

- **AC-90**: A site is drawn no more precisely than its source locates it. A site the tracker pins
  is drawn as a mark at a place. A site it locates only to a town is drawn so that it reads as
  approximate. A site it locates only to a county is not given a point on the ground at all, and is
  instead marked over that county, because its stored position is a county centroid and a county
  here can be four thousand square miles: drawing it crisply would put a data center on a particular
  horizon on the strength of nothing. Opening any of them says how well its position is known, in
  words. Marking a county needs that county's outline, which arrives with the county-lines layer
  that is off by default, so turning this on turns those on with it and the box ticks itself, in
  the same way and for the same reason rainfall already turns the county names on: a mark over an
  unnamed patch of map is a mark over nothing. This is the same refusal the column half makes when it declines to give such a site a
  distance (`feat-007/AC-32`, `feat-007/AC-33`).

- **AC-91**: Data centers that exist as mapped buildings are drawn as their outlines at their real
  size rather than as points, because that is what the source holds and because the difference
  between a surveyed footprint and an announced pin is the most useful thing this layer can show. A
  site carried by both sources is drawn by both and is not de-duplicated, which reads as a pin
  inside an outline and is an honest picture of two sources that disagree about what exists. A
  footprint too small to see at the zoom being drawn becomes a mark rather than nothing, because a
  layer that shows least when the map is widest would be at its emptiest exactly when somebody
  turns it on to ask where these things are.

- **AC-92**: Opening a data center gives what is known about it: its name, which of the three it
  is, who operates it, its size in megawatts and acres where the source has them, when it is
  expected, how well its location is known, and where the entry came from. Nothing is fetched from
  a listing site or any third party to fill that bubble. Any link out is a link the person presses
  deliberately and the page says it leaves, which is the rule this page already follows for the one
  other thing on it that reaches outward.

  **Every address in that bubble was written by somebody else, and is treated as such.** This is
  the first layer on any surface here that renders addresses this tool did not construct: the
  tracker is crowd-sourced and carries a petition link, two community-group sites and up to eight
  source links per record. So they go through the page's one link helper, which parses an address
  and yields nothing unless its scheme is `http` or `https`, and anything else is shown as text or
  not at all rather than as something pressable. A test asserts it, in the same shape as the scan
  that already asserts no data anywhere becomes markup: the defence that holds is the one nobody
  has to remember.

- **AC-93**: The layer obeys the rule of AC-60 that nothing drawn over the properties takes the
  pointer off them except where it is actually drawn, and it breaks that rule in a way none of the
  earlier layers did: it is the first with clickable shapes of real extent, so an outline the size
  of a campus is a hole in the map for every house inside it unless the layer is explicit about
  where its ink is. A test asserts a property under a drawn data center still opens.

- **AC-94**: Both sources are credited on the map, which no layer here has required before. The
  tracker is free for non-commercial use with attribution, and the mapped buildings are under the
  Open Database License with attribution to OpenStreetMap contributors. The page also states, as
  AC-55 already makes it state for the hazard layer, that turning this on causes this machine to
  ask two more hosts, neither of them federal.

- **AC-95**: What the layer is short of is said where it is read. Both sources cover the whole
  country, so nothing on this map is outside coverage, but the tracker's interest is contested
  projects and a quietly-running facility nobody objected to can be missing from it. The page says
  that an absence of shapes is not evidence of an absence of data centers, which is the same
  distinction between a determined negative and an unasked question that the values themselves are
  held to (`feat-007/AC-35`).

## MODIFIED

- **AC-55, what this page tells the person it fetches**
  - Was: drawing the hazard asks a federal server for the part of the country on screen, which the
    page states, because nothing else here does that unless a map background has been turned on.
  - Now: the same statement, extended to name the two further hosts this layer asks for, and to say
    that both are asked by this machine rather than by the browser, as the hazard tiles already are.

- **AC-56, nothing is scored or ranked by distance from anything**
  - Was: no property is scored, ranked, hidden or coloured by its distance from anything, and the
    only reason one is left off the map is a judgment the person made themselves.
  - Now: unchanged in force, and extended to name a data center as one of the things no property is
    scored, ranked, hidden or coloured by its distance from. It is named rather than left to
    "anything" because this is the first thing drawn on this page that a person arrives with an
    opinion about, and an unnamed rule is one somebody talks themselves out of. Stated here as a
    modification rather than as a new criterion, so there is one rule to keep in step instead of
    two that agree.

- **The surface vocabulary: what the map surface draws**
  - Was: "The surface that draws the wildfire hazard model also draws either background, which way
    the wind pushes, county lines, town names, rainfall and a ruler."
  - Now: the same list, with data centers in it.

## REMOVED

Nothing.
