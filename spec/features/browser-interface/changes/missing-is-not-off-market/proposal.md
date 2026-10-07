# Missing search results do not confirm a delisting

The owner requested the fixes and cleanup after a live spot check on 2026-10-07 found
400 duplicate Zillow collection cards among 414 rows described as off the market.
The other 14 were addressed properties absent from the search; absence does not prove
a sale or delisting. The shared product invariant already requires positive evidence
before claiming a property is unavailable.

This change corrects the browser's wording in the table, map, filters and property
detail. It retains the existing disappearance state and default hiding behavior.
It modifies AC-20, AC-57 and AC-67, their display plan, and their regression checks.
The Zillow parsing repair and retraction of invalid collection records are separate
fidelity defects; neither changes the definition of a property or rewrites history.
