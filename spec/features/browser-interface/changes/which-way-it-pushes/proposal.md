# Proposal — browser-interface

**Trigger:** One question, asked after reading the overlay for the first time: "So if a petal is
very long on the East side, it means the wind is coming FROM the East or blowing TO the East?"

That is the question the page was written to prevent, asked by somebody who had just read the two
sentences written to prevent it. The sentences are not the problem. The drawing is.

**Summary.** A wind rose points into the wind, the way a weather vane does. The convention is right,
it is older than anybody who will ever work on this, and it is read backwards by everybody who was
never taught it. What makes it worth changing rather than explaining harder is what backwards costs
here: "from the west" and "toward the west" name opposite sides of a house as the side to worry
about. Nothing else on this map fails that way. A misread hazard colour is a house looked at twice;
a misread wind is a house bought.

So the glyph is turned around. Every arm now points the way the wind pushes, the longest one carries
a head so there is a pointed end to read, and the word "from" is gone from the page: what somebody
buying a house wants to know is which way a fire would run, and that is now the way the arrow
points. The two readings can no longer disagree, because only one of them is offered.

The archive is untouched and so is `enrich/wind.py`. A record of facts should hold a direction the
way meteorology records it, and it still does. The half-turn happens once, in the drawing, at
`pushes()`, and every direction that reaches a reader goes through it.

## Blast radius

- **The fire map's wind overlay only.** No stored value changes, no route changes, nothing is
  re-fetched, and the cached roses on disk are still correct.
- **The vocabulary goes with the drawing.** Half of this change is worse than none of it: arms
  pointing downwind under a caption that says "from" is the same wrong answer with a second voice
  agreeing. The control, the legend, every bubble, and the text a screen reader is given all move
  together, and a test pins both halves against each other.
- **The glyph grew**, 64 pixels to 72, to leave room for the head without shortening the arms.

## What this trades away

Somebody who already knows wind roses now meets a familiar shape turned around. That is a real cost
and the arrowheads are what pays it: a rose has no arrowheads, so the glyph says on sight that it is
not one. Between confusing the reader who knows the convention and inverting the answer for the
reader who does not, this product has exactly one audience and it is the second one.
