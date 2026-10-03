# Proposal: browser-interface

**Trigger:** Three reports from using the flood layers on the live map, the day they shipped:
"it is hard to click the edges of the flood warning and emergency zones to see the info for them",
"the popups sometimes go away quickly", and "if you zoom out with the dams enabled, it gets REAL
laggy REAL quick".

**Summary:** All three are the same layers being built for the wrong case.

A warning answered the pointer on its outline only (AC-101), and the outline of an ordinary warning
is a dashed line a pixel and a half wide. That rule exists so that a house inside a warning still
opens, and it can keep doing that without making the warning itself so hard to open: the warning
takes no pointer at all, and a press on the map that lands on nothing else opens a bubble listing
every drawn warning that covers that spot or passes within a few pixels of it, emergencies first.
That is also the better answer to the question being asked. The statewide view is warnings over
warnings, and "what was this spot warned for" is a list, which an outline can never give.

The bubbles closed because of how the layers redraw. Opening a bubble near the edge of the map pans
the map to fit it, a pan is a move, and every move emptied the flood, dam and data centre layers and
drew them again, which took away the shape that owned the bubble, and a shape taken off the map
closes its bubble. So a bubble opened in the lower half of the map, or near a side, opened and
vanished. The data centre layer had written this down as an accepted trade ("a bubble open when the
map moves is closed by this"), without the pan that opening a bubble causes in mind.

The lag is the dams. Measured on the live map with the statewide run: 3,274 high-hazard dams held
for New Mexico and its neighbours, every one of them on screen once the map is zoomed out to the
region, each a separate marker element carrying two drop-shadow filters and two clip paths, all of
them thrown away and built again at the end of every move, and each repositioned separately through
every frame of a zoom. Frames of 300 to 650 milliseconds with dams on; under 35 with them off, on the
same moves. A dam becomes a triangle on one SVG renderer in its own pane, cased by its own stroke
instead of a filter, and both water layers keep what is still in view when the map moves, adding
only what came into view and taking away only what left.

## Blast radius
- Requirements affected: AC-99 (how a warning is opened), AC-100 (how a dam is drawn and reached
  from the keyboard), AC-101 (the pointer rule for warnings, dams as markers, redraw on move); one
  added (AC-105, a bubble stays open while the map moves).
- Design decisions affected: plan.md "Flash floods and dams: two routes over held records", the
  paragraph on how warnings, reports and dams are drawn.
- Tasks affected: new tasks T-eo-1 to T-eo-6 in tasks.md; T-fm-5 and T-fm-9 described the old
  drawing and stay as history.
- Already-built code affected: `web/static/flood.js` (drawing, the warning bubble, the dams),
  `web/static/fire.js` (the data centre redraw keeps an open bubble's shape), `web/static/app.css`
  (the dam marker rules go, the legend's swatches stay), `tests/test_web_browser.py` (the warning
  and dam pointer tests change with the rule they test).

## Status
- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into the feature's spec.md (product.md regenerates; never edit it by hand)
