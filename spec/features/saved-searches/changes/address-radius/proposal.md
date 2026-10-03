# Address-centered radius areas

Trigger: the user approved adding an area within a chosen number of straight-line miles of an address.

This is a behavior change: radius areas already accept coordinates and place names, but cannot
explicitly name a street address. Add an address form, reuse the cached Census geocoder, and retain
resolved coordinates so normal runs need no repeated lookup. Existing include/exclude semantics stay.

Scope: saved-search parsing, radius resolution, shared facade, and a terminal preview command.
Browser controls and serialization are owned by the browser interface's corresponding change.
The new requirements are AC-23 and AC-24; existing AC-2, AC-4, AC-5, AC-6 and AC-14 also apply.
