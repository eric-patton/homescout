# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-58 and AC-59.

**User story.** As the person choosing where to live, I want to measure how far a house is from
something on the map, so that "too close to the red" is a number rather than an impression.

**User story.** As the person choosing where to live, I want to see which way the wind normally
blows here, so that I can tell a house upwind of a hazard from a house downwind of it.

- AC-58: The fire map carries a scale that reports the distance across the screen in miles and
  follows the zoom. It also offers a ruler, off by default, laid across the middle of what is on
  screen: either end can be moved to a point on the map, the whole ruler can be carried elsewhere
  without changing its length, and it reads the distance between its ends in miles, or in feet below
  the point where a mile is no longer a useful picture. It is operable by pointer and by keyboard,
  in steps taken from what is on screen rather than in fixed degrees.
- AC-59: The fire map can draw where the wind comes from, off by default, as a wind rose per weather
  station over that station's whole recorded history rather than as any forecast. A rose reports,
  for each of sixteen directions, how often the wind came from it and how often it did so at fifteen
  miles an hour or more, and opens into those numbers with the number of readings and the years they
  span. The whole year and the single month that is both windiest and in fire season are both
  offered. Every claim states that a direction is where the wind comes *from* and what that means
  for a fire, because the opposite reading inverts every conclusion drawn from the page. Only the
  stations on screen are asked about, each exactly once ever, and what is on its way is visible as
  such. A station or a state that cannot be read is reported and does not stop the others being
  drawn. Nothing on the page is scored, ranked, hidden or coloured by wind or by distance from
  anything: the ruler measures what a person put it across, and the rose reports what was recorded.

## MODIFIED

- **AC-56.** Was: the page works nothing out and decides nothing, asserted by the page containing no
  proximity arithmetic at all. Now: no *property* is scored, ranked, hidden or coloured by its
  distance from anything, asserted against the function that turns a property into a pin. The page
  may measure a distance a person asked it to measure; what it may not do is decide something about
  a house from one.

## REMOVED

Nothing.
