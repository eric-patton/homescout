# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

- **AC-97**: What is drawn under the properties is a choice among the wildfire hazard model, FEMA's
  flood zones, and neither, and the opacity control applies to whichever is chosen. FEMA's zones are
  drawn from the same configured address the flood provider reads, fetched by this machine rather
  than the browser and kept, on the same terms as the wildfire tiles. FEMA's service draws its zones
  only at about zoom 14 and closer, so no tile is asked for further out, and the page says "zoom in
  to see FEMA's zones" while it is. The legend follows the choice and uses FEMA's own colours: the 1
  percent flood hazard area, the floodway, the 0.2 percent area, and the unstudied Zone D. Plain
  Zone `X` is not drawn, and the legend says that an undrawn place is either plain Zone X or a place
  FEMA has not mapped at all, and that the property's own values say which, and that FEMA maps
  rivers rather than most arroyos and assumes its dams and levees hold.

- **AC-98**: The map can draw flash floods, off by default: the National Weather Service's
  flash-flood warnings issued within a window of dates, and the flood, flash-flood and debris-flow
  reports filed within it, from the records the flash-flood provider holds. The window opens on the
  fourteen days ending with the most recent Flash Flood Emergency in the held record, so the page
  opens on the latest serious storm without a date written into the code, and either end can be
  changed. A window longer than a year is refused with a sentence, because three thousand polygons
  at once is not a map anybody can read. A warning raised to an emergency is drawn heavier and
  labelled as an emergency.

- **AC-99**: Opening a warning gives the issuing office and its number, the date and time it was
  issued in the place's local standard time, whether it became an emergency, and the damage threat
  the Weather Service attached, with a link to the warning's own text in the archive, which is where
  a cause such as a dam failure is stated; the link is one the person presses and the page says it
  leaves this tool. The link is built by the core from the warning's identity (its office, year and
  number, each checked), never taken from the archive (`feat-007/AC-49`), and goes through the
  page's one link helper, which yields nothing unless the address is http or https (AC-92). Pressing
  it is the person's own request to a third party; the routes behind the layer ask nobody (AC-103).
  Opening a report gives what kind of report it was, where it was filed from, when, who filed it,
  and the remark, rendered as text. The layer's own words say "warned", never "flooded", and the
  page says that a warning marks where flooding was expected rather than where water went, and that
  reports are positioned to about a kilometre.

- **AC-100**: The map can draw dams, off by default: the high-hazard dams in the inventory held for
  the states the run's properties are in and their neighbours, those within the view, drawn as a
  triangle shaded by condition (unsatisfactory, poor, fair, satisfactory, and an empty triangle for
  not rated). Opening one gives its name and inventory id, the year it was built, its condition and
  when that was assessed, its emergency action plan, its primary purpose, and its owner. How many of
  the dams drawn are rated poor or unsatisfactory is counted by the core and said beside the map,
  and the triangle, not the box it is drawn in, is what answers the pointer. The page says "near"
  and never "downstream": the inventory places a dam as one point and does not say which way it
  drains.

- **AC-101**: The flash-flood and dam layers obey AC-60. A warning's polygon answers the pointer on
  its outline and never on its fill, so a property inside a warning still opens, and a test asserts
  it. The warnings and the reports share one renderer made once, not one per shape; the dams are
  markers whose look is class names and nothing else. Both layers draw only what falls within the
  current view, and draw it again when the map moves.

- **AC-102**: The sources are credited on the map, and the page states what turning each layer on
  asks for: the zones ask FEMA's map service for the part of the map on screen, by this machine; the
  flash-flood and dam layers ask nothing at all, because they read records the enrichment pass
  already holds, and say so. When those records have not been fetched yet, the layer says that the
  enrichment pass fetches them rather than drawing an empty map that reads as "no floods".

- **AC-103**: The routes behind these layers read only records already held on this machine. The
  window's dates arrive from the page and are checked in the core as dates before anything is done
  with them, and nothing the page sends reaches a third-party address.

- **AC-104**: The results table's Hazards view includes the flood values the enrichment change adds
  (`feat-007/AC-39` to `feat-007/AC-54`): whether FEMA puts the property in its hazard area, the
  flash-flood emergencies and warnings, the nearest stream or arroyo, the soil flooding class, the
  water table, and the worst dam within ten miles, and the search builder's flood suggestion asks
  `flood_hazard_area == true`, so a floodway is caught by it. A pin's bubble on the map carries the
  same values in one line: the FEMA zone, how many Flash Flood Emergencies have covered the spot,
  the nearest stream or arroyo, and a recorded water table.

## MODIFIED

- **AC-55, what the properties are drawn on**
  - Was: every property is drawn on the wildfire hazard model.
  - Now: on whichever of the wildfire model or FEMA's zones is chosen, or on neither (AC-97).

- **AC-56, nothing is scored or coloured by distance**
  - Was: names a data center as one of the things no property is scored by its distance from.
  - Now: names flash-flood warnings and dams as well.

- **AC-71, what the map is named for**
  - Was: the list of what the map draws, without data centers.
  - Now: the list with FEMA's zones, data centers, flash floods and dams in it.

- **AC-55, what this page tells the person it fetches**
  - Was: drawing the hazard asks a federal server for the part of the country on screen, and the
    data center layer adds two further hosts.
  - Now: the same, and drawing FEMA's flood zones asks FEMA's map service the same way; the
    flash-flood and dam layers ask no host at all.

- **The surface vocabulary: what the map surface draws**
  - Was: "The surface that draws the wildfire hazard model also draws either background, which way
    the wind pushes, county lines, town names, rainfall, data centers and a ruler."
  - Now: the same list, with FEMA's flood zones, flash floods and dams in it.

## REMOVED

Nothing.
