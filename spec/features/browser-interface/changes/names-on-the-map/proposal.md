# Proposal — browser-interface

**Trigger:** Two sentences, a day apart. "If it could show a number over each county for the annual
precipitation on the map." And then: "also if we could get the counties and major city names on the
map."

**Summary.** One problem underneath both. The hazard layer is a wall of red and green with no words
on it, and the basemap's own names are underneath it, so the moment this map becomes useful it also
becomes anonymous: a person looks at a patch of red half an hour north of somewhere and cannot say
where. County lines and town names, drawn on top by this tool rather than borrowed from a tile,
put the names back.

Rainfall is the same question asked about the ground rather than about the map. Wildfire hazard is
modelled from fuel and terrain and says nothing at all about how dry a place is year on year, and
in this state that is most of what somebody buying land is deciding on: nine inches a year and
twenty inches a year are different countries, and no column in this tool says which one a property
is in. It is per county because that is the finest grain the national record publishes, and saying
so is better than interpolating a number that would look like it was measured at the house.

Thirty years, averaged, not a year. Any single year here is a story about one monsoon.

## Blast radius

- **The fire map only.** Two more layers, both off by default, on the same terms as the wind: only
  public keyless national data, fetched by this machine, kept on disk, and the person decides.
- **Two new read-only routes and one new module**, `enrich/ground.py`. Nothing else reads them and
  no stored property value changes.
- **Turning the rain on turns the names on**, because the number is written under a county's name.
  The box ticks itself when that happens, so the page never holds a state it is not showing.

## What this trades away

Urban areas rather than incorporated places, which means the labels are "where people are" rather
than "every incorporated village". The Census population figures would rank them better and now
need an API key, and a tool that made somebody register for an account before it would label Santa
Fe would be a worse tool. Land area across urban areas ranks them closely enough to put the right
dozen names on a state-sized map.
