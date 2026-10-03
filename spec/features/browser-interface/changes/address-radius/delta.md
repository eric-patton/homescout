# Address-centered radius controls delta

## ADDED

- AC-106: The search builder offers an address and positive mileage form, a Preview circle action
  showing the matched address and circle, and an Add radius area action. Lookup and input failures
  retain typed values and change no saved search. The preview must match current inputs before it
  can be added; changing them invalidates it and a stale asynchronous lookup cannot restore it.
  The user can choose inclusion or exclusion, change mileage and remove a radius in the area list.
  Adding is a draft until Save the areas. The form states that distance is straight-line and that
  the address lookup goes to the Census. Included areas continue combining rather than intersecting.
- AC-107: Saving and reopening radius areas preserves address, numeric or named center, mileage,
  name, reason and inclusion/exclusion. Circles with coordinate centers appear on the map with
  their current mileage and sense, alongside existing polygons, and never become GeoJSON points
  or lose their radius. Changing another panel leaves draft areas untouched. A failed save keeps
  the draft and displays failure. Radius control names are keyboard accessible.

## MODIFIED

None.

## REMOVED

None.
