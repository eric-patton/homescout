# Research — field-extraction

## Discovery input

From `homescout-brief.md` sections 9 and 14, and decision D1 in `homescout-decisions.md`:

- The user's consolidated spreadsheet has columns for heating and cooling, water source, sewer or
  septic, gas, roof and construction, and garage and outbuildings. No provider returns any of these
  as data. They are buried in prose: "newer refrigerated air, private well, community septic".
- The brief asks explicitly whether an AI pass is worth supporting, and the answer recorded in D1
  is that it is optional and off by default, with two interchangeable backends: OpenAI using the
  `OPENAI_API_KEY` environment variable, and a local model served by LM Studio. Both speak the same
  request shape, so this is one client with a configurable address, not two code paths.
- The brief's rule for these columns is stated twice and is binding here: extract where possible,
  leave blank rather than guess where not.
- With extraction disabled the tool must be completely functional, needing no key, no network call
  to a model provider, and no local model runner.

## Problem brief

### Problem statement

Someone comparing rural properties struggles to filter on the things that decide habitability,
because water source, sewer, heating, and gas are written in prose rather than returned as data,
which results in reading every description by hand to fill in a spreadsheet, or filtering on the
subset of criteria that happen to be structured. A solution should recover these fields from the
description where the text supports it, mark clearly how each value was obtained, and leave a field
empty rather than assert something the text does not say, without making a paid service or a local
model a requirement for using the tool at all.

### Target users

- **The person running searches** (primary): wants to filter and sort on well versus city water,
  and wants the spreadsheet columns filled in.
- **The rule engine** (secondary, as a consumer): needs these values, and needs an unfilled value to
  read as unknown rather than as a negative.

### Jobs to be done

- Recover structured fields from listing prose without reading every listing.
- Know whether a value came from a pattern, from a model, or from the provider itself.
- Never be told a property has a well when the description merely mentioned a neighbour's.
- Run the whole tool with no model configured at all.

### Success signals

- The spreadsheet columns that were previously hand-filled are populated for a meaningful share of
  properties.
- Every populated value is traceable to how it was determined.
- Turning the model pass off changes coverage and nothing else.

### Constraints

- Off by default, opt-in per search. No key required to use the tool.
- One client, configurable address, so a hosted key and a local server are one code path.
- Cached per description, so a description is never processed twice.
- Blank rather than guessed, on both backends.

### Explicitly out of scope

- Location data, which is enrichment (feat-007) and a different kind of thing entirely.
- Summarizing a listing, ranking it, or forming any judgment about it. This feature extracts stated
  facts and nothing else.
- Any use of a model anywhere else in the product.

### Open questions

None blocking.
