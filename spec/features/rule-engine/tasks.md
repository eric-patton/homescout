# Tasks — Rule engine (feat-008)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## The language

- [x] T1: `rules/tokens.py`: the lexer. Numbers, strings, names, operators, punctuation, each with
      its position. Unterminated string and unknown character are located failures (D-3).
- [x] T2 [P]: `rules/syntax.py`: the node types, as frozen dataclasses carrying positions (D-3).
- [x] T3: `rules/parse.py`: recursive descent over the grammar in D-3, with the bounds from D-7
      checked while parsing (length, depth, nodes, and the magnitude of a literal), and a named
      message for each construct the language does not have (call, attribute, index, assignment,
      chained comparison) (AC-15, AC-17, AC-18, AC-19).
- [x] T4 [P]: `tests/test_rules_parse.py`: every production, every rejection one at a time, both
      bounds, and the position of a failure.

## The namespace and the checks

- [x] T5: `rules/namespace.py`: the declaration table, listing fields read from
      `records.FIELD_NAMES`, plus derived, enriched and extracted names with their types and what
      populates each (D-4).
- [x] T6: `rules/check.py`: unknown name, name that nothing populates, type mismatch, and an
      expression whose result is not a boolean. Each a located problem (AC-13, AC-14, AC-15,
      and the spec's text-against-number edge case).
- [x] T7 [P]: `tests/test_rules_namespace.py`: the table is enumerable, an expression may name
      exactly its members, and the three kinds of unknown name read differently (AC-13, AC-14,
      AC-20).

## Evaluation

- [x] T8: `rules/evaluate.py`: three-valued evaluation, Kleene combination, unknown carrying the
      names that were missing in a stable order, division by zero as unknown, an arithmetic result
      past the magnitude bound as unknown, no short-circuit (D-5, D-7).
- [x] T9 [P]: `tests/test_rules_evaluate.py`: the truth tables, arithmetic, comparisons,
      membership, and determinism over shuffled inputs (AC-9, AC-10, AC-12, AC-21).
- [x] T10 [P]: `tests/test_rules_safety.py`: the mechanical inspection of the evaluation path, every
      construct that cannot parse, and the magnitude bound against a nested doubling expression,
      which must answer unknown in milliseconds rather than allocating (AC-16, AC-17, AC-19,
      security NFR).

## The rules section of a saved search

- [x] T11: `rules/definition.py`: a rule's three parts, the severities, duplicate identifiers, and
      `check_section` returning located problems in the shape feat-004 carries (AC-1, AC-2).
- [x] T12: `search/validate.py` calls `check_section` (D-12). Record the change in feat-004's
      manifest.
- [x] T13 [P]: `tests/test_rules_definition.py`: a rule missing a part, a duplicate identifier, an
      unparseable expression, all reported at once with locations, and the whole thing through
      `homescout searches validate` (AC-1, AC-2, AC-15).

## Recording verdicts

- [x] T14: Schema version 2: the `rule_verdicts` table and its append-only triggers, appended to
      the store's migration list (D-8). Record the change in feat-001's manifest.
- [x] T15: `rules/verdicts.py`: record a run's verdicts, read them back for a run, and read what
      fired for a rule across two runs (AC-22, AC-23).
- [x] T15a: `SearchDefinition` gains `rules`, feat-004's file definition parses its section once on
      load, and the in-memory one has none (D-12a). Record the change in feat-003's manifest.
- [x] T16: The run loop evaluates the search's rules after the run completes and records the
      verdicts, reading each property's derived values from the store once (D-9). Record the change
      in feat-003's manifest.
- [x] T17 [P]: `tests/test_rules_verdicts.py`: recorded verdicts survive an edited expression, an
      older run's verdicts are unchanged, and the newly fired set is computable (AC-22, AC-23).

## Results

- [x] T18: `rules/results.py`: the kept set minus the dropped, flags per property, the documented
      order and an order the caller asks for instead, the excluded set with reasons, the per-rule
      exclusion counts, and the newly fired set (AC-3 to AC-8, AC-10, AC-22).
- [x] T19: The digest's flagged set and count come from the newly fired set rather than being always
      empty, and the per-rule exclusion counts appear beside them, so a run that dropped everything
      says why (M-3, the spec's edge case). Record the change in feat-003's manifest.
- [x] T20 [P]: `tests/test_rules_results.py`: drop excludes but keeps, flag marks without excluding,
      boost and demote order, an explicit sort overriding both, drop beating everything, several
      verdicts at once, and every property dropped reported with counts rather than an empty table.
- [x] T21 [P]: `tests/rules_fakes.py`: a property builder, a rules-section builder, and a store with
      two runs in it.

## Finishing

- [x] T22 [P]: `tests/test_rules_results.py` also covers AC-24, the rules section round-tripping
      through the file unchanged.
- [x] T23 [P]: `tests/test_rules_performance.py`: 5,000 properties by 10 rules, marked slow.
- [x] T24: Document rules in the README: the four severities, the grammar, the namespace, and what
      undetermined means.
- [x] T25: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T26: `/spec-flow:converge`, then the manifest stamp.
