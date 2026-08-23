# Research — browser-interface

## Discovery input

From `homescout-brief.md` sections 4, 5.2 and 8:

- The interface exists for two things the terminal cannot do: drawing an area on a map, and
  reviewing properties in a wide table while editing judgment in place.
- The brief is explicit about which capability makes this a replacement rather than an accessory:
  "Annotations being editable in the results table is what lets this replace the spreadsheet rather
  than merely produce one."
- Five screens are named: the map and search builder, the saved search list, the results table, the
  listing detail, and the run history comparison. The merge section adds a sixth requirement, that
  ambiguous matches are resolved by a person in the interface rather than guessed.
- The technology choice is deliberate and constraining: served on localhost, plain HTML and vanilla
  JavaScript with Leaflet for the map, no single-page-application framework and no second build
  toolchain. This is a personal tool that must still start in five years.
- Neither surface may hold business logic. The interface is a view over the same core the command
  line calls.

## Problem brief

### Problem statement

Someone reviewing dozens of properties struggles to form and keep a judgment about each one,
because the reviewing happens in one tool and the judgment gets written in another, which results
in a spreadsheet that is immediately out of date and a set of searches that cannot express where
they actually want to live. A solution should put the map, the table, the property, and the
person's own notes in one place where the notes are edited exactly where the property is read,
without becoming an application that needs maintaining as much as the tool it serves.

### Target users

- **The person running searches** (primary, and the only user): draws areas, reviews rows, records
  judgment, and resolves the cases the tool refused to guess at.

### Jobs to be done

- Draw the area I mean, including the parts to leave out, and save it as a search.
- See every property in one wide table and sort and filter it myself.
- Write my rank, verdict, red flags, and next step directly on the row I am looking at.
- Open one property and see everything known about it, including how the record was assembled.
- See what changed since any earlier run.
- Decide the ambiguous matches the tool refused to guess at.

### Success signals

- The spreadsheet stops being edited by hand, because the judgment is captured here instead.
- A search area drawn here produces the same results as the same definition run from a terminal.
- The interface still runs years later without a build step nobody remembers.

### Constraints

- Localhost only, single user, no authentication, no hosting.
- Plain HTML and vanilla JavaScript. No single-page-application framework, no second build
  toolchain.
- No business logic in this layer.
- Saved searches must round-trip losslessly, so editing here never destroys something written by
  hand.

### Explicitly out of scope

- Multi-user, authentication, and anything reachable from another machine.
- A mobile application. The phone surface is the email digest.
- Any capability not also reachable from the command line.

### Open questions

None blocking.
