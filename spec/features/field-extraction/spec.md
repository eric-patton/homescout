## Why

Half the columns in the spreadsheet this tool replaces are facts that no provider returns as data,
because they live in the description: refrigerated air, private well, community septic, metal roof.
Recovering them is what lets a person filter on habitability rather than on square footage. The
constraint that shapes the whole feature is the brief's rule, restated in the decisions log: a
field the text does not support is left empty, never guessed, on every backend. The optional model
pass is exactly that, optional, and the tool must be complete without it. The problem brief is in
`research.md`.

## Vocabulary used in this feature

- An **extracted field** is a structured value recovered from a listing's prose, as opposed to one
  the provider returned as data.
- **Provenance** on an extracted field records how it was determined: `source` when the provider
  supplied it directly, `pattern` when deterministic matching recovered it, `model` when the
  optional pass did.
- The **model pass** is the optional extraction backend. It is one client speaking one request
  shape against a configurable address, which is either a hosted service or a local server.

## User stories

- As the person running searches, I want water source, sewer, heating, gas, and roof recovered from
  descriptions, so that the columns I used to fill in by hand fill themselves.
- As the person running searches, I want to know how each value was determined, so that I can trust
  a provider-supplied value more than a recovered one.
- As the person running searches, I want a field left empty when the text does not say, so that I
  never drive to a property on the strength of a well that was never mentioned.
- As the person running searches, I want to use the entire tool without configuring any model, so
  that this capability is a convenience rather than a dependency.
- As the person running searches, I want to point the model pass at a local server instead of a
  paid service, so that I can choose between cost and setup.
- As the person running searches, I want a description processed at most once, so that re-running a
  search does not re-spend anything.

## Behavior & scenarios

- **Scenario: patterns recover a stated fact**
  - Given a description reading "private well and community septic"
  - When extraction runs with only the deterministic baseline
  - Then water source records a well and sewer records septic, each with provenance `pattern`

- **Scenario: the text does not say**
  - Given a description that never mentions heating
  - When extraction runs
  - Then the heating field is empty with no provenance, and is not populated with a default, a most
    common value, or a guess

- **Scenario: a provider supplied the value directly**
  - Given a provider that returned a structured heating field
  - When extraction runs
  - Then the provider's value is kept with provenance `source`, and extraction does not overwrite
    it

- **Scenario: the model pass is off**
  - Given a search that has not enabled the model pass
  - When it runs
  - Then no model is contacted, no key is read, no local server is required, and only the
    deterministic baseline contributes values

- **Scenario: the model pass is on**
  - Given a search that has enabled the model pass, with a configured address and model
  - When a description the patterns could not resolve is processed
  - Then the model pass is asked, values it returns are recorded with provenance `model`, and
    values it declines to determine remain empty

- **Scenario: one client, two backends**
  - Given the model pass configured against a hosted service, and separately against a local server
  - When each is used
  - Then both go through the same client with only the configured address, model name, and
    credential source differing

- **Scenario: a description is processed once**
  - Given a description already processed by the model pass
  - When any later run encounters the identical description
  - Then the cached result is used and no request is made

- **Scenario: the model is unavailable**
  - Given the model pass enabled and its address unreachable
  - When extraction runs
  - Then the failure is reported, the deterministic values remain, the affected fields stay empty
    rather than being filled by fallback, and the run completes

- **Scenario: the model returns something unusable**
  - Given a model response that does not match the expected shape, or asserts a value the
    description does not contain
  - When it is processed
  - Then the response is rejected, the field remains empty, and the rejection is recorded

## Acceptance criteria

- [ ] AC-1: Deterministic pattern extraction always runs and requires no configuration, no key, and
      no network access.
- [ ] AC-2: Extracted fields cover at minimum heating and cooling, water source, sewer or septic,
      gas, and roof or construction.
- [ ] AC-3: Every populated field carries provenance of `source`, `pattern`, or `model`.
- [ ] AC-4: A provider-supplied value is never overwritten by an extracted one.
- [ ] AC-5: A field the text does not support is left empty. A test over descriptions that mention
      none of the target fields asserts that every extracted field is empty.
- [ ] AC-6: The model pass is off by default and is enabled per saved search.
- [ ] AC-7: With the model pass off, the tool performs no model request, reads no model credential,
      and functions completely. A test asserts the tool works end to end with no model configuration
      present.
- [ ] AC-8: The model pass reads its credential from the environment, never from a saved search, a
      configuration file under version control, or a command-line argument.
- [ ] AC-9: The model pass is one client against a configurable address, so a hosted service and a
      local server differ only in configuration. A test exercises both through the same client.
- [ ] AC-10: Model results are cached against the description content, so identical description text
      is never processed twice regardless of how many properties or runs contain it.
- [ ] AC-11: A model failure or timeout is reported, leaves deterministic values intact, leaves the
      affected fields empty, and does not fail the run.
- [ ] AC-12: A model response that does not match the expected shape is rejected and the field is
      left empty rather than partially populated.
- [ ] AC-13: A model-supplied value that the description does not support is rejected. Extraction
      requires the value to be attributable to the text.
- [ ] AC-14: Extracted values are members of the rule engine's field namespace, and an unpopulated
      one yields an undetermined verdict rather than a false one.

## Edge cases & errors

- A description mentions a feature as absent, such as "no natural gas at the road". This is a known
  negative, which is a different value from empty, and must not be recorded as though gas were
  present.
- A description mentions a neighbouring property's feature, or a feature of a nearby development.
  Attribution to the subject property is required, which is what AC-13 exists to enforce.
- A description mentions two conflicting values, such as both a well and city water, which happens
  on properties that have both. The field records the ambiguity or stays empty; it does not silently
  pick one.
- The description is empty or absent. Extraction produces no values and reports nothing unusual.
- The description is extremely long. It is truncated to a bounded length before any model request,
  and the truncation is recorded.
- The same property is described differently by two providers. Each description is extracted
  independently and the canonical listing carries both, with conflicts visible rather than resolved
  by preference order.
- The model pass is enabled but no credential is configured. This is reported at validation time,
  before the run, rather than as a failure per property.
- A description contains text that reads like an instruction. It is data. Nothing in a description
  can change what the extraction is asked to do or cause any action outside producing field values.

## Non-functional requirements

- Performance: with the model pass off, extraction over 5,000 properties adds no more than a few
  seconds to a run. With it on, the cost is bounded by the number of distinct unprocessed
  descriptions, not by the number of properties or runs.
- Security: the credential comes only from the environment. Listing text is untrusted input and is
  never treated as instruction, never evaluated, and never used to construct a path or a request
  target.
- Reliability: any model failure degrades coverage of extracted fields and nothing else.
- Accessibility: none. No user-facing surface.

## Open questions

None.
