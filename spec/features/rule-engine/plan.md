# Plan — Rule engine (feat-008)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

Four facts read out of the built code and the constitution, because each one settles a decision that
would otherwise be argued twice.

- **M-1: `ast.parse` is `compile`.** CPython implements it as `compile(source, ..., PyCF_ONLY_AST)`.
  AC-16 says no code-compilation facility appears anywhere in the evaluation path and that this is
  verified by inspection. A reviewer inspecting a module that calls `ast.parse` finds a call into
  the compiler, and has to be argued out of what they can see. That is the wrong shape of argument
  to have to win about the one feature the brief names as an injection surface.
- **M-2: the store already migrates forward.** `store/migrations.py` keeps an ordered tuple of
  migrations and refuses a file written by a newer build; its docstring says in as many words that
  eleven further features add tables to this same file. So recording verdicts is a schema version,
  not a new database.
- **M-3: the digest's flagged set is already there and always empty.** `digest.py` emits
  `"flagged": []` and `"flagged": 0` deliberately, so the document's shape would not depend on this
  feature existing (feat-003's AC-12). Filling it is this feature's job and needs no new shape.
- **M-4: a saved search already carries its rules untouched.** feat-004 validates the `rules` key's
  shape (a list) and never reads inside it, which is exactly the seam this feature fills. Round trip
  through the file is already lossless, so AC-24 is a test here rather than new machinery.

## Design decisions

### D-1: layout

A new package, `src/homescout/rules/`, sitting above the store and below the surfaces, which is
where the constitution's layer order puts it.

| file | holds |
|---|---|
| `rules/tokens.py` | the lexer: text in, tokens with positions out. |
| `rules/syntax.py` | the expression node types, and nothing that can execute. |
| `rules/parse.py` | a recursive-descent parser over the tokens, with the size and depth bounds. |
| `rules/namespace.py` | every name an expression may use, its type, and where its value comes from. |
| `rules/check.py` | static checks over a parsed expression: unknown names, type mismatches. |
| `rules/evaluate.py` | three-valued evaluation against one property's values. |
| `rules/definition.py` | a rule (identifier, expression, severity), and reading the file's section. |
| `rules/verdicts.py` | recording a run's verdicts and reading them back. |
| `rules/results.py` | applying verdicts: what is excluded, what is flagged, what order. |

### D-2: the parser is written here, not borrowed from Python

A hand-written lexer and recursive-descent parser producing this feature's own node types. Not
Python's `ast` module with a node whitelist, which is the usual answer.

Three reasons, in order of weight:

1. **Inspection is the requirement.** AC-16 asks for a path with no compilation facility in it, and
   asks that this be verifiable by reading the code. A module with no import of `ast`, `eval`,
   `exec`, `compile`, or `__import__` anywhere in it is verifiable in one grep. That is a claim a
   reviewer can check in ten seconds, which is worth more than an argument about what
   `PyCF_ONLY_AST` does (M-1).
2. **A whitelist has to keep up with a language that keeps growing.** Python has added the walrus,
   f-strings, starred expressions, pattern matching and more to the grammar `ast` parses. Every one
   of them is a node a whitelist author had to already know to exclude. A grammar written here
   accepts what it was written to accept, and a future Python cannot widen it.
3. **The bounds and the positions come free.** AC-15 wants the position of a parse failure and AC-18
   wants size and nesting bounded at parse time. Both are natural in a parser you wrote, and awkward
   bolted onto one you did not.

The cost is roughly two hundred and fifty lines of ordinary code with no dependencies, for a grammar
small enough to state in full in this plan.

### D-3: the grammar, complete

```
expression  := disjunction
disjunction := conjunction ( "or" conjunction )*
conjunction := negation ( "and" negation )*
negation    := "not" negation | comparison
comparison  := sum ( ("=="|"!="|"<"|"<="|">"|">="|"in"|"not in") sum )?
sum         := product ( ("+"|"-") product )*
product     := unary ( ("*"|"/") unary )*
unary       := "-" unary | primary
primary     := NUMBER | STRING | "true" | "false" | "null" | NAME | "(" expression ")" | list
list        := "[" ( expression ( "," expression )* )? "]"
```

That is the whole language. A comparison does not chain (`a < b < c` is a parse error naming the
second operator), because chained comparison in a three-valued logic is a subtlety nobody writing a
property criterion wants to think about, and refusing it is honest.

There is no call syntax, no attribute syntax, no index syntax, no assignment, and no statement
separator, so AC-17's rejections are not a filter over a larger language: the parser has no rule
that could produce them. Each rejection still gets its own message naming the construct, because
"unexpected `(`" is a worse experience than "a rule cannot call a function".

### D-4: the field namespace is a declaration, not a dictionary

`namespace.py` declares every name once, as a table of `(name, type, origin, populated_by)`:

- **listing**: the fields a source reports, read from `records.FIELD_NAMES` rather than restated, so
  the two cannot disagree (the store already uses that trick and it has already paid).
- **derived**: computed locally from history. `dom` (days on market, the tool's own reckoning),
  `price_cut`, `price_raised_after_days`, `is_new`, `presence`.
- **enriched**: `flood_zone`, `upload_mbps`, `download_mbps`, `over_principal_aquifer`,
  `wildfire_hazard`, `elevation_ft`, and the rest, declared here and populated by feat-007.
- **extracted**: `water_source`, `septic`, `hoa_fee`, and the rest, declared here and populated by
  feat-009.

The `populated_by` column is what makes AC-14 answerable in the words the criterion uses. Three
different messages, three different fixes:

| what the rule named | severity | message |
|---|---|---|
| not in the table | problem | that name does not exist; here are the names that do (AC-13) |
| in the table, populated by a feature that is not built or not configured | notice | that name exists, but nothing in this installation fills it, so this rule can only ever be undetermined (AC-14) |
| in the table, populated, missing for this property | a verdict | undetermined for this property, naming the field (AC-11) |

The middle row is a **notice**, not a failure, and that matters more than it looks. The spec's edge
case says a rule naming an unconfigured enrichment value is *reported* as a value that will never be
populated, which is a more useful message than a per-property undetermined verdict. It does not say
refused, and refusing would be actively wrong: the brief's own example search drops on
`upload_mbps < 100`, and that name is populated by feat-007, which is not built. A tool that refused
to run the brief's own example until an unrelated feature shipped would be answering a question
nobody asked.

feat-004 built the severity channel for exactly this, so a notice travels the same path a problem
does and stops nothing.

A test asserts the table is enumerable and that the set of names an expression may use is exactly
the set the table declares (AC-20), by parsing a rule for every declared name and asserting that a
name absent from the table is rejected.

### D-5: three-valued, and unknown remembers why

Evaluation returns one of a value, or `Unknown`, which carries the names that were missing.
Comparison with an unknown operand is unknown; arithmetic with an unknown operand is unknown;
division by zero is unknown rather than an error (the spec's edge case).

Boolean combination is Kleene's, which is the only combination that satisfies AC-12:

| `and` | true | false | unknown |   | `or` | true | false | unknown |
|---|---|---|---|---|---|---|---|---|
| **true** | true | false | unknown |   | **true** | true | true | true |
| **false** | false | false | false |   | **false** | true | false | unknown |
| **unknown** | unknown | false | unknown |   | **unknown** | true | unknown | unknown |

Both operands are always evaluated, rather than short-circuiting, so that the missing names an
unknown carries are the complete set rather than however many were reached before the answer was
settled. Evaluation has no effects (D-11), so evaluating both costs only time, and the expressions
are tiny.

A rule's verdict is then `fired` when its expression is true, `not-fired` when false, and
`undetermined` when unknown (AC-9). An expression whose value is a number or a string rather than a
boolean is a validation failure at check time, not a truthiness rule at evaluation time.

### D-6: types are checked before anything runs

`check.py` walks a parsed expression and gives every node a type from the namespace's declarations
and the literals' own types. A comparison between text and a number, an arithmetic operator over
text, or a boolean operator over a number is a validation failure naming the rule and the position
(the spec's first edge case, which says explicitly that this is a validation failure and not a
silent false).

`null` compares equal or unequal to anything and is otherwise a type error, which is what makes
`water_source == null` a legal way to ask whether something is missing. It is *not* the same as
undetermined: `null` is a value the property carries, undetermined is a value nobody has.

That distinction needs care: for a field this tool has never populated there is no stored `null`
to compare against, so `x == null` on an unpopulated field is undetermined
rather than true. The declaration's `populated_by` is what tells those apart, and the message says
which.

### D-7: bounds, stated as numbers

- 1,000 characters of expression
- 32 levels of nesting
- 200 nodes
- 10^15 in magnitude, for every literal and every arithmetic result

All four are bounds, and the first three are checked while parsing: exceeding one is a parse failure
naming it (AC-18). They are far above any honest criterion (the brief's longest is 45 characters)
and far below anything that could take meaningful time. Nesting is bounded during the descent rather
than after, so a deeply nested expression cannot exhaust the interpreter's own stack before the
check runs.

**The fourth bound is about arithmetic rather than shape.** Python's integers are arbitrary
precision, so bounding how many pieces an expression has says nothing about how large a number it
can build: `(x*x)*(x*x)` squares the digit count at every level.

Measured, the other bounds already contain it. Each level of doubling has to write its subexpression
twice, so a thousand characters buys seven levels: a 768-digit number, computed in well under a
millisecond, and flat multiplication to the node bound reaches about three thousand digits in two
tenths of one. There is no catastrophe here to prevent, and an earlier draft of this plan said there
was; the correction is recorded in the pre-build check rather than quietly dropped.

The bound stays anyway, for two reasons that do not depend on that. It keeps arithmetic meaningful:
a criterion whose result has left the range of real quantities is not a question about a house, and
`unknown` says so where a confident enormous number would not. And it keeps AC-19 local to this
decision, rather than resting on a lexical limit somebody could reasonably raise one day without
realizing what else was leaning on it. A literal above 10^15 is a parse failure and an arithmetic
result above it is `unknown`, which is the answer division by zero already gets.

Two related closures, for the same reason:

- **`+` is arithmetic only, never concatenation.** String concatenation reintroduces the same
  doubling with text instead of digits, and a criterion never needs to build a string. The type
  check refuses `+` over text (D-6).
- **There is no exponent operator**, which is the other way to write the doubling attack in three
  characters. The grammar in D-3 has no rule that could parse one.

### D-8: verdicts are recorded, because a rule can be edited

Schema version 2, one migration, one table:

```sql
CREATE TABLE rule_verdicts (
  run_id      TEXT NOT NULL REFERENCES runs(id),
  listing_id  TEXT NOT NULL REFERENCES listings(id),
  rule_id     TEXT NOT NULL,
  severity    TEXT NOT NULL,
  verdict     TEXT NOT NULL,          -- fired | not-fired | undetermined
  missing     TEXT,                   -- the names that were unknown, sorted, when undetermined
  PRIMARY KEY (run_id, listing_id, rule_id)
);
```

Append-only, with the same update-and-delete triggers every other history table carries, because
AC-23 says an earlier run's verdicts are unchanged by a later edit and the database is where this
project enforces that rather than trusting a convention.

Recomputing verdicts on demand instead was considered and is wrong: re-evaluating today's rules
against an old snapshot would silently rewrite what that run decided, which is the one thing
non-negotiable 1 forbids.

This is a change to the listing store (feat-001): a migration appended, the version bumped, and the
entry recorded in that feature's manifest.

### D-9: the run evaluates, the surfaces read

The run loop already hands every matching property to the store. After it completes, this feature
evaluates the search's rules against each property and records the verdicts for that run. Rules that
need a value only the store can give (days on market, price movement) read it from the store, once
per property, not once per rule.

`results.py` then answers what a surface needs, from the recorded verdicts rather than by
re-evaluating:

- `results(store, search, run_id, *, order=None)` — the properties a run kept, minus the dropped,
  each with its flags, in the default order unless the caller names another. The `order` argument is
  how AC-6's "explicit sort chosen by the user" arrives: no surface offers one yet, and the two that
  will (feat-010, feat-011) pass it through rather than sorting the answer themselves, because a
  surface that re-sorted would be making a decision the constitution keeps out of surfaces.
- `excluded(store, search, run_id)` — what was dropped and by which rule (AC-4).
- `exclusion_counts(store, search, run_id)` — how many properties each rule removed. This is what
  the spec's edge case about a search that drops everything needs: an empty result set with the
  counts beside it is a search that is working and badly written, and an empty result set on its own
  is indistinguishable from a market that emptied. The counts go into the run's report and its
  digest entry alongside the flagged set.
- `newly_fired(store, search, run_id, since)` — what fired that did not fire in the baseline run
  (AC-22), which is what fills the digest's flagged set (M-3).

AC-4's "retrievable on request" is served here by `excluded`, and reaches a person today through the
run's report. The browser interface and the export inherit the obligation to show it, which is
recorded in their features rather than assumed.

### D-10: the order, documented once

Default order is by score, descending, where score is the number of `boost` rules that fired minus
the number of `demote` rules that fired. Undetermined contributes nothing (AC-10). Ties fall back to
the store's own stable order, which is first observation then identifier, so the order is total and
deterministic (AC-7, AC-21). A sort the user asks for replaces this entirely rather than being
combined with it (AC-6).

A `drop` that fires beats everything else on that property (AC-8): the property is excluded whatever
else fired, and its other verdicts are still recorded, because "excluded, and it would also have
been flagged" is a thing worth being able to see.

### D-11: no effects, checked mechanically

The evaluation path (`tokens`, `syntax`, `parse`, `check`, `evaluate`) imports nothing but the
standard library's `dataclasses`, `enum` and `typing`. A test walks those modules' source and fails
if any of them names `eval`, `exec`, `compile`, `__import__`, `getattr`, `globals`, `locals`,
`open`, `os`, `io`, `socket`, `subprocess`, `pathlib`, or `sqlite3` (AC-16, AC-19).

This is the same shape of mechanical check feat-003 uses to hold the command line to "no business
logic in a surface", and it exists for the same reason: a rule that is only a convention is a rule
that is one hurried afternoon from being broken.

### D-12: how the saved search learns to validate its rules

`search/validate.py` calls into `rules.definition.check_section`, which reads the `rules` list and
returns problems with locations, in the shape feat-004 already carries. A direct import rather than
another registry.

This is a deliberate departure from the three ports this codebase already has (the catalog, the
boundary provider, the merge queue). Those are ports because the implementation genuinely varies: a
catalog is files or memory, a boundary provider exists or does not. The rule engine is not optional
and has no second implementation, so a registry would model a state the product never occupies and
would let a saved search with unreadable rules validate cleanly whenever somebody forgot to
register. `rules` does not import `search`, so the dependency is one way.

### D-12a: how the run loop learns which rules to evaluate

`SearchDefinition` gains one member, `rules: tuple[Rule, ...]`, defaulting to empty. The run loop
already holds the definition; asking it for its rules is one member rather than a second path from
the loop back to the file. feat-004's file-backed definition parses its `rules` section once when it
loads and exposes the result; the in-memory definition the tests use exposes nothing, which is the
honest answer for a search that has no rules.

Recorded in feat-003's manifest as a further change to the contract, alongside the three feat-004
already made.

### D-13: what this feature does not own

Producing enriched values (feat-007) or extracted values (feat-009): declared here, populated there,
and this feature's behavior when they are absent is specified rather than incidental. Badges and
pixels (feat-010). The file format (feat-004), which carries the section untouched.

## Verification approach

Test files, all under `tests/` per `spec/.spec-flow.md`:

- `tests/rules_fakes.py` — a property builder, a rules-section builder, and a store with runs in it.
- `tests/test_rules_parse.py` — the grammar, the rejections, the bounds, the positions.
- `tests/test_rules_evaluate.py` — three-valued logic, arithmetic, determinism.
- `tests/test_rules_namespace.py` — the declaration, and the three kinds of unknown name.
- `tests/test_rules_verdicts.py` — recording, reading back, and what an edit does not change.
- `tests/test_rules_results.py` — drop, flag, order, exclusions, newly fired.
- `tests/test_rules_safety.py` — the mechanical inspection, and the constructs that cannot parse.

| criterion | seam the test enters through | trace token |
|---|---|---|
| AC-1 a rule's three parts | `rules.definition.check_section` and `homescout searches validate` | `feat-008/AC-1` |
| AC-2 duplicate identifiers | `check_section` | `feat-008/AC-2` |
| AC-3 drop excludes but keeps | `results.results` and the store | `feat-008/AC-3` |
| AC-4 exclusions are retrievable | `results.excluded` | `feat-008/AC-4` |
| AC-5 flag marks without excluding | `results.results` | `feat-008/AC-5` |
| AC-6 boost and demote order only | `results.results` with and without a requested sort | `feat-008/AC-6` |
| AC-7 several verdicts at once | `results.results` | `feat-008/AC-7` |
| AC-8 drop beats the rest | `results.results` | `feat-008/AC-8` |
| AC-9 unknown is not false | `evaluate.verdict` | `feat-008/AC-9` |
| AC-10 unknown excludes nothing, orders nothing | `results.results` | `feat-008/AC-10` |
| AC-11 undetermined names its field | `evaluate.verdict`, and the same names read back off the recorded verdict | `feat-008/AC-11` |
| AC-12 unknown through and/or | `evaluate.verdict` | `feat-008/AC-12` |
| AC-13 a name outside the namespace | `check_section` | `feat-008/AC-13` |
| AC-14 absent name against unpopulated name | `check_section` | `feat-008/AC-14` |
| AC-15 a parse failure and its position | `check_section` | `feat-008/AC-15` |
| AC-16 no interpreter in the path | source inspection of the evaluation modules | `feat-008/AC-16` |
| AC-17 each rejected construct | `parse.parse`, one test per construct | `feat-008/AC-17` |
| AC-18 size and depth bounds | `parse.parse` | `feat-008/AC-18` |
| AC-19 evaluation has no effects | the same inspection, plus a store handed to nothing | `feat-008/AC-19` |
| AC-20 the namespace is one declaration | `namespace` | `feat-008/AC-20` |
| AC-21 determinism | `evaluate.verdict` over shuffled inputs | `feat-008/AC-21` |
| AC-22 newly fired since a run | `results.newly_fired` | `feat-008/AC-22` |
| AC-23 an edit does not rewrite history | two runs with a changed expression | `feat-008/AC-23` |
| AC-24 rules round-trip | `FileCatalog.load` then save, byte equality | `feat-008/AC-24` |
| the magnitude bound | `parse.parse` for a literal, `evaluate.verdict` for a result, and a nested doubling expression that must answer unknown in milliseconds | `feat-008/AC-19` |
| every property dropped | `results.exclusion_counts` | `feat-008/AC-4` |
| performance NFR | 5,000 properties by 10 rules, marked slow | `feat-008/NFR-performance` |
| security NFR | `tests/test_rules_safety.py` in full | `feat-008/NFR-security` |
