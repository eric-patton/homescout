# Proposal: state-areas

**Trigger:** gap-004 of this feature's drift ledger, opened 2026-08-23 and confirmed 2026-09-30: a
state is an area type the code accepts (`search/areas.py` `KINDS`) and AC-2 does not list. Routed
then to a human decision, legitimize or remove. The person asked on 2026-09-30 for every
recommendation to be carried out, and the recommendation was to legitimize.

**Summary:** AC-2 lists the area forms a definition may use: polygon, city, county, ZIP code and
radius. A state works too, and has since the first build, because the source layer already accepts
one (feat-002) and the state lookup this feature needs for the qualifier in "Portales, NM" makes it
nearly free. It is no longer a curiosity: the person's main search, `nm-statewide`, is one
`type: state` area, and it is what runs every night. Removing it would break that search; leaving it
unwritten leaves the spec describing a smaller feature than the one in use. So the spec says it.

## Blast radius

- **Requirements affected:** AC-2 (modified to list a state) and the vocabulary's definition of an
  area. Nothing added, nothing removed.
- **Design decisions affected:** none. D-7 and D-12a already resolve a state.
- **Tasks affected:** one task, tracing the existing state tests to AC-2.
- **Already-built code affected:** none.

Not changed, and noted for whoever next edits the shared rules: `product-global.md`'s glossary also
lists the area forms without a state. Editing that file resets every feature's pre-build check, so
it is left for a deliberate pass over the shared rules rather than done here.

## Status
- [x] delta reviewed (analyze, 2026-09-30, run 3 of this feature's report)
- [x] implemented & verified (no code change; tests traced)
- [x] folded into the feature's spec.md (product.md regenerates; never edit it by hand)
