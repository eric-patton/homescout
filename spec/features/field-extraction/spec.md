## Why

Half the columns in the spreadsheet this tool replaces are facts that no source returns as data,
because they live in the description: refrigerated air, private well, community septic, metal roof.
Recovering them is what lets a person filter on habitability rather than on square footage. The
constraint that shapes the whole feature is the brief's rule, restated in the decisions log: a
field the text does not support is left empty, never guessed, on every backend. The optional model
pass is exactly that, optional, and the tool must be complete without it. The problem brief is in
`research.md`.

## Vocabulary used in this feature

- An **extracted field** is a structured value recovered from a listing's prose, as opposed to one
  the source returned as data.
- **Provenance** on an extracted field records how it was determined: `source` when the source
  supplied it directly, `pattern` when deterministic matching recovered it, `model` when the
  optional pass did.
- The **model pass** is the optional extraction backend. It is one client speaking one request
  shape against a configurable address, which is either a hosted service or a local server.
- A **note for the model** is a short piece of writing by the person running searches, in their own
  words, describing how listings in their market are written. There are two, one for the
  installation and one per saved search, and both are optional and absent by default.

## User stories

- As the person running searches, I want water source, sewer, heating, gas, and roof recovered from
  descriptions, so that the columns I used to fill in by hand fill themselves.
- As the person running searches, I want to know how each value was determined, so that I can trust
  a source-supplied value more than a recovered one.
- As the person running searches, I want a field left empty when the text does not say, so that I
  never drive to a property on the strength of a well that was never mentioned.
- As the person running searches, I want to use the entire tool without configuring any model, so
  that this capability is a convenience rather than a dependency.
- As the person running searches, I want to point the model pass at a local server instead of a
  paid service, so that I can choose between cost and setup.
- As the person running searches, I want a description processed at most once, so that re-running a
  search does not re-spend anything.
- As the person running searches, I want to tell the model in plain language what I know about how
  listings in my market are written, so that it reads "community water" the way everybody here means
  it rather than the way the words look.
- As the person running searches, I want the note I wrote to take effect on the next pass, so that
  editing it is not silently cancelled by an answer cached under the old one.

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

- **Scenario: a source supplied the value directly**
  - Given a source that returned a structured heating field
  - When extraction runs
  - Then the source's value is kept with provenance `source`, and extraction does not overwrite
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

- **Scenario: a note is written for the market**
  - Given a note for the installation and a note on the saved search
  - When a description is processed
  - Then both are in the instruction, the installation's first, marked as written by the operator
    rather than found in the listing, and the description itself is unchanged

- **Scenario: a note asks for something the vocabulary does not have**
  - Given a note instructing the model to report a value outside the closed set, and a model that
    obeys it
  - When the answer is processed
  - Then it is rejected on the same check every other answer meets, and the field stays empty

- **Scenario: a note is edited**
  - Given descriptions already answered under one note
  - When the note is changed and the pass runs again
  - Then those descriptions are asked about again under the new note, the answers given under the
    old one are kept rather than rewritten, and a value already recorded still shows while the new
    pass is pending

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
- [ ] AC-4: A source-supplied value is never overwritten by an extracted one.
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
- [ ] AC-10: Model results are cached against the description content together with the notes in
      force, so identical description text under unchanged notes is never processed twice regardless
      of how many properties or runs contain it.
- [ ] AC-11: A model failure or timeout is reported, leaves deterministic values intact, leaves the
      affected fields empty, and does not fail the run.
- [ ] AC-12: A model response that does not match the expected shape is rejected and the field is
      left empty rather than partially populated.
- [ ] AC-13: A model-supplied value that the description does not support is rejected. Extraction
      requires the value to be attributable to the text.
- [ ] AC-14: Extracted values are members of the rule engine's field namespace, and an unpopulated
      one yields an undetermined verdict rather than a false one.
- [ ] AC-15: A note for the model can be written for the installation and for each saved search,
      both optional, both absent by default, and both in plain language rather than a format.
- [ ] AC-16: When either note is present it is included in the model request, in the instruction
      rather than in the description, and marked as coming from the operator rather than from the
      listing. When both are present both are included, the installation's first.
- [ ] AC-17: A note cannot widen the answer. The field vocabulary, the closed set of values, and the
      requirement that every value be quoted from the description are unchanged by any note, and a
      note asking for a value outside the vocabulary or for a field that does not exist changes
      nothing about what is accepted.
- [ ] AC-18: The cached answer for a description is identified by the notes in force when it was
      produced, so editing either note causes the next pass to ask again rather than reusing an
      answer given under different instructions. Answers cached under a previous note are kept, not
      rewritten.
- [ ] AC-19: Each note is bounded at 2,000 characters. A note longer than that is truncated before
      the request and the truncation is reported to the person who wrote it, rather than being sent
      whole or silently cut.
- [ ] AC-20: With no note written anywhere, the request is identical to what it was before this
      capability existed. A test asserts the request body is byte-for-byte unchanged, so a person
      who does not use this pays nothing for it.
- [ ] AC-21: A note is written by a person and never by the tool. Nothing read from a listing, a
      source, or a run is ever placed in a note by any code path, and both places a note can be
      written say before it is written that its text is sent to the model with every description.

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
- The same property is described differently by two sources. Each description is extracted
  independently and the canonical listing carries both, with conflicts visible rather than resolved
  by preference order.
- The model pass is enabled but no credential is configured. This is reported at validation time,
  before the run, rather than as a failure per property.
- A description contains text that reads like an instruction. It is data. Nothing in a description
  can change what the extraction is asked to do or cause any action outside producing field values.
  The operator's note is the one piece of writing here that is an instruction, because a person
  wrote it deliberately on this machine. It is carried in the instruction rather than in the
  description, and it is subject to the same closed vocabulary and the same quote requirement as
  everything else, so the worst it can do is make the model wrong in the ordinary way.
- A note is written and the whole corpus has already been answered. Every description is asked about
  again, which costs what the first pass cost. That is the price of the note taking effect at all,
  and it is visible in the pass report rather than discovered on a bill.

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
