# Proposal — browser-interface

**Trigger:** From the person the page is drawn for, after a week of using the turned-around rose:
"for the wind, it would be more intuitive for me if it just showed actual arrows... arrows like
that - thin."

**Summary.** The overlay was a wind rose: sixteen arms, each as long as that direction was common.
The last change turned the arms around to point downwind, which fixed the half of the problem that
was about which way. This is the other half, and the reason it was still wrong is worth writing
down rather than treating as taste.

A rose and an arrow answer different questions. A rose answers "what is the distribution of wind
direction at this station", which has sixteen numbers in the answer and is asked by somebody
studying the wind. What she is asking is "which way would a fire here run", which has one direction
in the answer. The drawing of one direction is an arrow. Sixteen arms was the right shape for a
question nobody on this page was asking, and every reading of it had to be done twice: find the
longest arm, then read its direction.

So: one thin arrow per station, pointing the way the wind pushes, longer where the wind more often
does the same thing. The sixteen numbers did not go anywhere; they are in the bubble, which is
where a second question belongs.

A second arrow, in the darker violet, only where hard wind pushes somewhere the everyday wind does
not. That is the one case where a station has two answers rather than one, and it is worth a second
arrow because it is the difference between "the fire goes east" and "the fire goes east, except on
the days that would actually move it". Drawn always, it would be decoration shaped like an answer.

## Blast radius

- **The fire map's wind overlay only.** No stored value changes, no route changes, nothing is
  re-fetched, and the cached roses on disk are still exactly what the archive said.
- **The glyph grew again**, 72 pixels to 112, because an arrow needs length to have a direction in
  a way a wedge does not.

## What this trades away

The distribution. A station where the wind is scattered across eight directions and one where it
sits in one now draw the same shape. The arrow's length is what carries that: it is scaled by how
much of the time the wind actually does this, with a floor so a weak answer is still a readable
one. That is less information than sixteen arms and it is the information somebody buying a house
uses.
