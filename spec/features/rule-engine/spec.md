## Why

The criteria that actually decide whether a property is worth a drive combine listing data with
public data no provider has heard of, and they change as a search matures. Keeping them as data in
the saved search makes them tunable and reviewable as a change. The hard part is not evaluating
them; it is evaluating them safely and honestly: no path from a written expression to executable
code, and no property quietly excluded because a value was missing rather than because it failed
the test. The problem brief is in `research.md`.

## Vocabulary used in this feature

- A **rule** has a stable identifier, an expression, and a severity.
- **Severity** is one of `drop`, `flag`, `boost`, `demote`.
- A rule's **verdict** on one property is `fired`, `not-fired`, or `undetermined`. `undetermined`
  means the expression depended on a value that is not known, which is different from evaluating to
  false.
- The **field namespace** is the fixed, declared set of names an expression may refer to. Nothing
  outside it is reachable.

## User stories

- As the person running searches, I want to write my criteria once in the search file and have them
  applied to every property in every run, so that I stop re-checking the same things by hand.
- As the person running searches, I want a property that fails a hard requirement excluded but not
  deleted, so that I can still look at what was excluded and why.
- As the person running searches, I want to be told when a criterion names something that does not
  exist or has not been fetched, so that I find out from a message rather than from a suspiciously
  short result list.
- As the person running searches, I want a property with an unknown value never excluded on the
  strength of that unknown, so that missing data does not read as failure.
- As the person running searches, I want to see which criteria a property tripped, so that a badge
  means something specific.
- As a scheduled agent, I want to know which properties newly tripped a criterion since the last
  run, so that a digest can report it.

## Behavior & scenarios

- **Scenario: a criterion excludes a property**
  - Given a rule with severity `drop` whose expression is true for a property
  - When the search's results are produced
  - Then that property is absent from the results, remains stored with its full history, and is
    recorded as excluded by that rule's identifier

- **Scenario: a criterion marks a property**
  - Given a rule with severity `flag` whose expression is true for a property
  - When the search's results are produced
  - Then the property is present in the results and carries that rule's identifier as a flag

- **Scenario: criteria affect the default order**
  - Given two otherwise equivalent properties, one tripping a `boost` rule and one tripping a
    `demote` rule
  - When the results are produced in their default order
  - Then the boosted property sorts above the demoted one, and an explicit sort chosen by the user
    overrides both

- **Scenario: a value is not known**
  - Given a rule testing that upload speed is below 100, and a property whose upload speed has not
    been enriched
  - When the rule is evaluated
  - Then the verdict is `undetermined`, the rule does not fire, the property is not excluded, and
    the property is reported as having an undetermined verdict for that rule

- **Scenario: a criterion names a field that does not exist**
  - Given a rule referring to a name that is not in the field namespace
  - When the saved search is validated or run
  - Then the problem is reported naming the rule's identifier and the offending name, and listing
    the names that are available, and no results are produced from a search containing it

- **Scenario: a criterion is not valid**
  - Given a rule whose expression cannot be parsed
  - When the saved search is validated or run
  - Then the parse failure is reported with the rule's identifier and the position in the
    expression, and nothing is evaluated

- **Scenario: an expression cannot escape the namespace**
  - Given a rule whose expression attempts to call a function, reach an attribute, index a value,
    or name anything outside the declared namespace
  - When it is parsed
  - Then parsing fails with a message naming the disallowed construct, and no evaluation is
    attempted

- **Scenario: criteria combine listing and enriched data**
  - Given a rule testing that the water source is a well and the property is not over a principal
    aquifer
  - When both values are known for a property and both conditions hold
  - Then the rule fires

- **Scenario: newly tripped criteria**
  - Given a property that did not trip a rule in the previous run
  - When a run evaluates the same rule as fired
  - Then the property appears in that run's newly flagged set, and a property that tripped the same
    rule in both runs does not

- **Scenario: the same criteria produce the same verdicts**
  - Given a fixed set of properties and a fixed set of rules
  - When they are evaluated repeatedly
  - Then every verdict is identical each time, with no dependence on evaluation order or on which
    run is executing

- **Scenario: a criterion is edited**
  - Given a saved search whose rule expression is changed
  - When the search is run again
  - Then the new expression governs from that run forward, previous runs' recorded verdicts are
    unchanged, and the change is visible as an ordinary edit to the saved search file

## Acceptance criteria

- [ ] AC-1: A rule is defined by a stable identifier, an expression, and a severity of `drop`,
      `flag`, `boost`, or `demote`. A rule missing any of the three is a validation failure.
- [ ] AC-2: Two rules sharing an identifier within one saved search is a validation failure naming
      the duplicated identifier.
- [ ] AC-3: A `drop` rule that fires excludes the property from results while leaving it stored with
      its full history, and the exclusion records the rule identifier responsible.
- [ ] AC-4: Excluded properties are retrievable on request, with their exclusion reasons, so a user
      can audit what a rule removed.
- [ ] AC-5: A `flag` rule that fires attaches its identifier to the property and does not affect
      whether the property appears.
- [ ] AC-6: `boost` and `demote` affect only the default ordering. An explicit sort requested by the
      user takes precedence over both.
- [ ] AC-7: A property may carry any number of flags and may be affected by boost and demote rules
      simultaneously; the resulting order is deterministic and documented.
- [ ] AC-8: A `drop` verdict takes precedence over `flag`, `boost`, and `demote` on the same
      property.
- [ ] AC-9: An expression referring to a value that is not known yields `undetermined`, not false.
- [ ] AC-10: An `undetermined` verdict never excludes a property and never contributes to ordering.
- [ ] AC-11: A property with an `undetermined` verdict is reported as such, naming the rule and the
      field whose value was missing, so the user can tell "not checked" from "passed".
- [ ] AC-12: Unknown propagates through combination: a conjunction with a false operand is false
      even when another operand is unknown, and a disjunction with a true operand is true even when
      another operand is unknown. A test covers both.
- [ ] AC-13: A rule naming a field outside the declared namespace is a validation failure that names
      the rule, the offending name, and the available names. The search does not run.
- [ ] AC-14: The distinction between a name that does not exist and a name that exists but has no
      value yet is preserved in the reported message. They are different problems with different
      fixes.
- [ ] AC-15: An expression that cannot be parsed is a validation failure naming the rule identifier
      and the position of the failure.
- [ ] AC-16: Evaluation uses a restricted parser over the declared namespace. No general-purpose
      interpreter, dynamic evaluation facility, or code-compilation facility appears anywhere in the
      evaluation path. This is verified by inspection as well as by test.
- [ ] AC-17: Function calls, attribute access, indexing, assignment, and any reference to a name
      outside the namespace are rejected at parse time with a message naming the construct. A test
      covers each rejected construct individually.
- [ ] AC-18: Expression size and nesting depth are bounded, and an expression exceeding either bound
      is rejected at parse time rather than evaluated.
- [ ] AC-19: Evaluating a rule has no effect other than producing a verdict. It cannot write to the
      store, read a file, open a network connection, or consume unbounded time.
- [ ] AC-20: The field namespace is declared in one place and covers listing fields, locally derived
      fields such as days on market, enriched values, and extracted values. A test asserts the
      namespace is enumerable and that its members are exactly what expressions may name.
- [ ] AC-21: Verdicts are deterministic: the same properties and rules produce identical verdicts on
      repeated evaluation, independent of ordering.
- [ ] AC-22: Each run records its verdicts, so that the set of properties newly firing a given rule
      since any earlier run is computable and reproducible.
- [ ] AC-23: Editing a rule changes verdicts from the next run forward and does not alter verdicts
      recorded by earlier runs.
- [ ] AC-24: Rules round-trip losslessly through the browser interface: a saved search edited in the
      interface and written back is unchanged in its rules section apart from the edit made.

## Edge cases & errors

- A rule compares a text value against a number. This is a validation failure at parse or bind
  time, not a silent false at evaluation time.
- A rule's expression is a bare constant that is always true, so it drops every property. This is
  valid and is honored; the report showing how many properties each rule excluded is what makes it
  obvious.
- A saved search contains no rules. Every property passes, nothing is flagged, and the default
  ordering is unaffected.
- Every property in a search is dropped. The result is an empty result set together with the
  exclusion counts per rule, not an unexplained empty table.
- Two rules contradict each other, one boosting and one demoting the same property. The documented
  combination order under AC-7 settles it deterministically.
- A rule refers to an enriched value in a search where that enrichment provider is not configured.
  Reported under AC-14 as a value that exists in the namespace but will never be populated for this
  search, which is a more useful message than a per-property undetermined verdict.
- Arithmetic that cannot produce a value, such as a division by zero, yields unknown rather than an
  error that aborts the run.
- An expression contains characters intended to break out of a string. There is no interpolation
  and no interpreter, so it is a parse failure or a literal string, never an escape.

## Non-functional requirements

- Performance: evaluating every rule in a saved search against 5,000 properties is a small fraction
  of a run, and evaluation time grows linearly with properties and rules.
- Security: this is the feature the brief names as an injection surface. No expression a user writes
  may reach a general-purpose interpreter, touch the filesystem or network, or run unbounded. Bounds
  on size, depth, and effect are requirements, not defensive extras.
- Reliability: a failure evaluating one rule against one property yields an `undetermined` verdict
  for that pair and does not abort the pass or the run.
- Accessibility: none directly. Badges and ordering are presented by the browser interface.

## Open questions

- Whether the expression language should eventually support a set-membership test against a
  user-defined list stored elsewhere in the saved search is a future extension. This release scopes
  membership to literal lists written in the expression.
