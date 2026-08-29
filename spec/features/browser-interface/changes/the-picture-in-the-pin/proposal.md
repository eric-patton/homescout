# Proposal — browser-interface

**Trigger:** "She wants the pins on the map when you click them to show the thumbnail for the house
in that little info popup."

**Summary.** A pin is very good at where. The bubble it opens is good at what: price, beds, acres,
the hazard under it. Neither of them says what the house looks like, which is the first thing
anybody wants from a listing and the reason the results table already carries a picture beside every
address.

The picture is the copy this tool stored, served from this machine, so opening a pin on a screenful
of houses still tells three listing sites nothing about which houses somebody is looking at. That is
the rule the whole product is built on and this change does not bend it. Pressing the picture opens
every photograph the listing carried, which is the one thing here that does ask the site, and it
says so while it does it, exactly as the table's thumbnail does.

**It is never scaled up.** Two thirds of the stored photographs are a hundred and twenty pixels
across, because that is what the site handed over. A frame of a fixed height with the picture inside
it at its own size or smaller: a small photograph blown up to fill a wider box reads as a fault in
this tool rather than as a small photograph.

## Blast radius

- **The fire map's bubble only.** No route changes, no stored value changes, and no new request of
  anybody: the picture is the same address the results table already asks this machine for.
- **A property with no stored picture gets no frame at all**, which is the opposite of the table's
  rule and right for the same reason. There, an empty box of the same size is what keeps a column of
  addresses in a straight line to run an eye down. Here there is one bubble on its own and nothing
  to line it up with.
