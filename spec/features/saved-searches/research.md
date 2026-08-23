# Research — saved-searches

## Discovery input

From `homescout-brief.md` section 6:

- The unit a person tunes is not a query, it is a search: an area, a set of filters, a set of
  criteria, and a set of sources, kept together and refined over weeks.
- Geography is the part no source gets right. Sources accept coarse forms (a city, a county, a
  ZIP code, a bounding box) and none of them accepts "north of this road but not the east side of
  town", which is how a person actually thinks about where they want to live.
- The brief's answer is two-stage: query the coarse form a source accepts, then test each result
  against the drawn shapes locally. Exclusion shapes let "not the east side" be geometry rather
  than a mental note the user re-applies by eye every time.
- The definition must be hand-editable, git-trackable, and round-trip losslessly through the
  browser interface, so that drawing a polygon and editing a file are two ways at one thing.

## Problem brief

### Problem statement

Someone searching a region struggles to express where they will actually live because source
search boxes accept only coarse areas, which results in either a search too wide to review or a
mental exclusion list re-applied by eye on every pass. A solution should let an area be drawn or
written as precise geometry, combined with ordinary filters, saved under a name, and re-run
unchanged for months, without requiring the person to choose between editing a file and using a
map.

### Target users

- **The person running searches** (primary): tunes one search repeatedly and needs last week's
  definition to still be there, and still mean the same thing.

### Jobs to be done

- Describe an area precisely, including places to leave out.
- Combine that with ordinary filters and with the sources to ask.
- Save it under a name and re-run it later without redefining it.
- Edit it by hand, in a file, and see the change reviewed like any other change.
- Be told when a definition is wrong before a run wastes requests on it.

### Success signals

- A definition edited by hand and a definition edited on the map are the same file, and neither
  loses information written by the other.
- A property outside a drawn shape never appears in results, however coarse the source query was.
- An invalid definition is caught before any source is contacted.

### Constraints

- Hand-editable YAML, git-trackable, lossless round trip through the browser interface.
- Geography is two-stage. The coarse query and the local shape test feed from the same definition,
  and the command line and the browser feed identical geometry into the same code path.
- The rules section belongs to the rule engine (feat-008); this feature owns the file that carries
  it.

### Explicitly out of scope

- Evaluating rules (feat-008), fetching (feat-002, feat-005), the map drawing surface (feat-010).
- Export column templates beyond naming which template a search uses (feat-011).

### Open questions

None blocking.
