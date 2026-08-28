# Proposal — browser-interface

**Trigger:** "Also, if when looking at the map view - it could show the list below it?"

**Summary.** A pin is very good at "where" and says nothing at all until it is opened. Reading a
screenful of them means clicking every one, which is the whole of the request: what am I actually
looking at, with the numbers, in one read.

The rule that makes the list worth having rather than confusing is that it is not a second table
with its own idea of what is going on. It holds exactly the pins the map is drawing, hides what the
map hides, and re-reads itself whenever the map moves. Its address is a button that opens that
property's pin where it stands, rather than flying to it: the pin is already on screen, and a map
that jumps every time somebody reads a row is a map that loses the place they were looking at.

Six columns, not the whole table. The results table has every column this tool knows and a way to
choose between them, and it is one click away at the top of this page; putting it here as well
would be two tables that disagree about what is filtered.

## Blast radius

- **The fire map only.** No route changes and no stored value changes.
- **A cap of four hundred rows**, with the count said plainly above it. At full zoom-out a run is
  the whole state, and a thousand rows under a map is neither readable nor quick; the fix is to
  zoom in, which is what somebody is about to do anyway.
