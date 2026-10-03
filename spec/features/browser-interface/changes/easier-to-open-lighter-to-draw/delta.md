# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-105**: A bubble opened on a layer that is drawn again as the map moves (the flash floods, the
  dams, the data centres) stays open when the map moves, and in particular through the pan the map
  makes to fit a newly opened bubble on screen: a redraw never takes away the shape whose bubble is
  open, and it goes when the bubble closes and the map next moves. A browser test opens a report's
  bubble where the map has to pan to show it and finds it still open after the pan.

## MODIFIED

- **AC-99, how a warning is opened**
  - Was: "Opening a warning gives the issuing office and its number, ..." with a warning opened by
    pressing its outline (AC-101).
  - Now: A press on the map that lands on no property, report or dam, with the flash floods on,
    opens one bubble listing every drawn warning that covers the spot or passes within a few pixels
    of it, emergencies first and then newest first, and says how many there were. Enter on the map
    itself asks the same about the middle of what is on screen, so the keyboard reaches it (AC-17).
    Each entry gives
    what opening a warning gave before: the issuing office and its number, the date and time it was
    issued in the place's local standard time, whether it became an emergency, the damage threat,
    and the link to the warning's own text in the archive, on the same terms as before. A press
    that lands inside no warning opens nothing. The rest of AC-99 (the link's construction and
    helper, the report's bubble, "warned" not "flooded") is unchanged.

- **AC-100, how a dam is drawn**
  - Was: "... drawn as a triangle shaded by condition ... and the triangle, not the box it is drawn
    in, is what answers the pointer."
  - Now: Drawn as a triangle shaded by condition (unsatisfactory, poor, fair, satisfactory, and a
    white triangle with a dark edge for not rated), cased in white by its own outline so it reads
    over red or cyan. The triangle is what answers the pointer, and each drawn dam can be reached
    from the keyboard and opened with Enter, naming the dam and its condition to a screen reader.
    The rest of AC-100 is unchanged.

- **AC-101, the pointer rule and the drawing**
  - Was: "A warning's polygon answers the pointer on its outline and never on its fill, so a
    property inside a warning still opens, and a test asserts it. The warnings and the reports share
    one renderer made once, not one per shape; the dams are markers whose look is class names and
    nothing else. Both layers draw only what falls within the current view, and draw it again when
    the map moves."
  - Now: The flash-flood and dam layers obey AC-60. A warning's polygon takes no pointer at all, so
    a property inside a warning still opens, and a test asserts it; the warning is opened by a press
    on the map as AC-99 says. The warnings and the reports share one renderer made once, and the
    dams have one of their own, made once, in their own pane; no shape gets a renderer or an element
    of its own beyond its path, and nothing on either layer carries text from a source in its
    drawing. Both layers draw only what falls within the current view. When the map moves they add
    what came into view and take away what left it, and leave what is still in view alone, so a
    move costs what changed rather than everything on screen; with the dams on and the map zoomed
    out to the region, moving it stays as smooth as with them off, and a browser test asserts the
    dams' shapes are kept rather than built again across a pan.

## REMOVED

- None.
