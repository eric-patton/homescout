# Delta — enrichment

> The change expressed against the current spec as explicit operations.

## ADDED

New requirements, written as full spec requirements. Each acceptance criterion here takes the next
stable id when folded into `spec.md`: AC-22 through AC-26.

**Vocabulary.** The **wildland-urban interface** is where housing meets or intermingles with
undeveloped wildland vegetation. It has two kinds: **intermix**, where housing and vegetation are
mixed together, and **interface**, where housing sits against a large continuous block of
vegetation. A location the provider covers that is in neither is **not in the interface**, which is
an answer. A location the provider does not cover is **not applicable**, which is not an answer and
must never be shown as one; it is recorded as the value `outside coverage`, which says in a cell
what the category says in the governing rule.

**User story.** As the person running searches, I want to know whether a property stands in the
wildland-urban interface, so that I can tell a house with trees near it from a house standing inside
the fire problem, which is the distinction fire agencies and insurers act on and which a hazard
rating for the surrounding vegetation does not make.

**User story.** As the person running searches, I want a provider that only covers part of the
country to say so where it does not reach, so that a property in another state does not read as a
property with nothing to worry about.

- AC-22: A wildland-urban interface provider exists, is individually enableable, and supplies a
  value naming which kind of interface a location stands in. It is registered like every other
  provider and requires no change to the enrichment pass.
- AC-23: A location inside the provider's coverage that falls in no interface polygon is recorded as
  a known negative, in the same way a point outside a mapped flood zone is, and is distinguishable
  from a value nobody obtained.
- AC-24: A location outside the provider's coverage is recorded as not applicable, which is written
  as the value `outside coverage`. That is a determined value and not a state of the cache: it is
  distinct from the known negative of AC-23, distinct from the missing value of AC-7, and no surface
  may render it as either. A test asserts all three read differently. Deciding it costs no request,
  and it is not re-asked on a later pass, because a value the provider will never answer differently
  is not a value worth asking about again.
- AC-25: The classification is read from the source's own attribute. A code this build does not
  recognize is a failure naming the code, never a guessed classification, on the same principle the
  wildfire hazard provider already follows: a wrong fire rating is worse than no fire rating.
- AC-26: A provider that does not cover the whole country declares what it does cover, and that
  declaration is readable wherever the provider is listed, so nobody has to open the module to learn
  what a column answers for. Providers that cover the country declare nothing, which is the default
  AC-12 states. The coverage test of AC-12 asserts, for a declaring provider, both a successful
  lookup inside its coverage and a not-applicable result outside it.

**Edge cases added.**

- The interface source is reachable but the property is in a state it does not cover. Not a failure
  and not a negative: the value is not applicable, no request needs to be repeated on the next pass,
  and the reason is legible without opening the source.
- A property sits inside the coverage but outside every polygon, which is the normal answer for a
  town centre. A known negative, cached like any other answer.

## MODIFIED

- **AC-11 — which providers exist**
  - Was: Providers for flood zone, broadband service, principal aquifer, wildfire hazard, elevation,
    and boundary resolution exist and are individually enableable.
  - Now: Providers for flood zone, broadband service, principal aquifer, wildfire hazard, elevation,
    boundary resolution, and wildland-urban interface exist and are individually enableable.

- **AC-12 — coverage**
  - Was: Every provider covers the whole country. A test asserts a successful lookup at locations in
    geographically distant states, for every provider this installation can run. A provider that is
    not configured is skipped by name rather than silently passed over. Broadband covers the country
    a state at a time: every state can be indexed and the test asserts that, while a state nobody has
    indexed reads as an unloaded state rather than as a gap in coverage.
  - Now: A provider covers the whole country unless it declares otherwise. A test asserts a
    successful lookup at locations in geographically distant states, for every provider this
    installation can run. A provider that is not configured is skipped by name rather than silently
    passed over. Broadband covers the country a state at a time: every state can be indexed and the
    test asserts that, while a state nobody has indexed reads as an unloaded state rather than as a
    gap in coverage. A provider that declares partial coverage is tested on both sides of its
    boundary: inside it answers, and outside it reports not applicable rather than answering.

- **Vocabulary used in this feature**
  - Was: A value is **fresh** when it is cached and within its time to live, **stale** when it is
    cached and past it, and **missing** when it was never obtained. Stale is usable and labelled;
    missing is not a value.
  - Now: A value is **fresh** when it is cached and within its time to live, **stale** when it is
    cached and past it, and **missing** when it was never obtained. Stale is usable and labelled;
    missing is not a value. Those three describe the cache. A fourth condition describes the answer
    instead: a value is **not applicable** when the provider was asked, answered, and what it
    answered is that this location is outside what it covers. That is a fresh, determined value
    whose content happens to be an absence of jurisdiction, and it is not one of the other three.

- **Edge case — a provider returns a successful response with no data for the point**
  - Was: A provider returns a successful response with no data for the point, which is the normal
    answer for a location outside a mapped hazard area. This is a known negative value, not a
    missing one, and the two must not be conflated.
  - Now: A provider returns a successful response with no data for the point, which is the normal
    answer for a location outside a mapped hazard area. This is a known negative value, not a
    missing one, and the two must not be conflated. Where the provider covers only part of the
    country there is a third reading, and all three must stay separate: the point is in no mapped
    area (a negative), the point is somewhere this provider does not cover (not applicable), or
    nobody has asked (missing).

- **Security (non-functional requirement), first sentences only**
  - Was: No credentials are required, and none is embedded. Five of the six providers are keyless
    public services.
  - Now: No credentials are required, and none is embedded. Six of the seven providers are keyless
    public services, and the seventh needs no credential either; broadband remains the one exception
    below.

- **Why (opening section)**
  - Was: The questions that decide a rural property are not listing fields: flood zone, broadband,
    aquifer, wildfire, elevation.
  - Now: The questions that decide a rural property are not listing fields: flood zone, broadband,
    aquifer, wildfire, whether the house stands in the wildland-urban interface, elevation.

## REMOVED

Nothing. No requirement in this feature stops being true, and the two the change leans hardest on
(AC-7's separation of missing from negative, and AC-1's plugin shape) are the reason it fits without
one.
