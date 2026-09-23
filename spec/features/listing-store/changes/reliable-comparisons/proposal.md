# Proposal: Reliable comparisons across search edits and merges

**Trigger:** The implementation review found that runs keep only a search name, and historical
comparisons resolve listings through today's merge state. A search edit can therefore look like a
market disappearance, and a later merge can change an earlier comparison.

**Summary:** Record the effective search revision with each run, reset the comparison baseline when
that revision changes, and freeze canonical identity for each completed run. Keep older observations
immutable. A source handoff must not be called a verified price change merely because two sites
reported different values.

## Blast radius

- Requirements affected: AC-5, AC-8, AC-18, AC-20, plus new comparison criteria.
- Design decisions affected: D-5, D-6, D-8, D-10.
- Tasks affected: store migration, run creation, comparison queries, source provenance, digest and
  interface reporting, migration and regression tests.
- Already-built code affected: `store/schema.py`, `store/migrations.py`, `store/core.py`,
  `store/diff.py`, `runner.py`, `search/definition.py`, and the two surfaces reading comparisons.

## Status

- [x] delta reviewed (analyze)
- [x] implemented and verified
- [x] folded into the feature's spec.md
