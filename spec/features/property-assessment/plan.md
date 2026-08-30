# Plan — Property assessment (feat-013)

The design decisions behind `spec.md`, and what was measured before making them.

## What was measured first

Against the live workspace on 2026-08-29, because the feasibility of this feature is entirely a
question of how much is already on hand and how many properties it has to run over.

- **155 properties in play**, out of 951 in the latest run and 1,328 in the store. That number is
  what makes a per-property model request affordable at all. Assessing every description in the
  store would be 1,083 requests; assessing what is in play is 155, once, and then a handful a night.
- **8 kept and 804 passed on**, most of the latter carrying a reason. That is a labelled set of this
  household's taste, sitting unused.
- **Enrichment coverage**: flood zone, interface rating and broadband on 1,821 properties; wildfire
  hazard, elevation and county on 1,436; aquifer on 943.
- **2,650 listings hold exactly one photograph each.** One primary exterior shot, no gallery, no
  interior.
- **Wind roses are per weather station**, fetched once and kept, each station carrying coordinates.
  Nearest-station is arithmetic on data already on disk.
- **The wildfire and interface layers are served as tiles, not as geometry.** The property's own
  rating is known; what is next to it is not, except as a picture.
- **Eighteen real requests through the configured model** to establish it works and how it behaves:
  it quotes verbatim when asked to, and it correctly refuses to record water a property "would" get
  if annexed. Two live passes asked about eleven descriptions and recovered values from two, which
  is the measurement that motivated this feature rather than a fault in the old one.

## Design decisions

### D-1: a second pass, not a wider first one

feat-009's blindfold is load-bearing and its code says so: it is handed prose, a vocabulary and the
operator's notes, and not a listing, a snapshot or a store, because there is no address in scope
there to send. That is enforcement by structure rather than by care, and widening it would delete
the enforcement for both jobs at once.

So this is a separate module with a separate boundary, sharing feat-009's client, account settings
and pacing and nothing else. The one that must not see an address still cannot. AC-3 states the new
boundary out loud in the spec so a later reader finds a decision rather than an inconsistency.

### D-2: the assessment is stored where an annotation is not

Every property row already carries `rank`, `red_flags`, `summary`, `next_step`, `fire_egress`,
`sewage_exposure`, `outbuildings`, `taxes` and `crime`, and all of them are empty across all 813
annotated properties. They look like the obvious home and they are the wrong one: the store declares
them *the user's own judgment, never written by a run*, and *nothing writes them but a person*.

Filling them from a model would delete the boundary the whole product is built on, and would make it
impossible to tell what the person concluded from what a model guessed. Its own table, side by side
on screen. The question somebody actually asks, standing in a kitchen with a phone, is not "what
does the summary say" but "it flagged the egress, do I agree" — and that question cannot be asked if
both live in one cell.

### D-3: what makes an assessment stale is what it was assessed from

The obvious rule, "reassess when the property changes", is wrong in the direction that costs money:
a live market changes a price every week and a price has no bearing on whether the roof is metal or
the arroyo runs behind the house.

So an assessment records a fingerprint of its own inputs and is stale when that fingerprint no
longer matches. What goes into it: the description's digest, the enrichment values used, the rule
verdicts, and the household's *stated* criteria.

What deliberately does not: the sample of kept and passed properties. The pre-build check caught
this and it would have been expensive. That sample changes every time anybody passes on a house, so
folding it into the fingerprint means one click invalidating all 155 assessments and a full pass
being paid for again, over a change nobody made to what they were looking for. The sample is
calibration; the stated criteria are instruction. Only instruction invalidates.

feat-009 already established the shape of this by folding the operator's notes into its cache key,
with the same reasoning: an answer given under different instructions is a different answer. A price
cut changes nothing in the fingerprint and costs nothing.

### D-4: the criteria are gathered, never authored

Nothing in this feature invents a criterion. The four sources are all things the person already
wrote somewhere else, and the best of them is the one nothing currently reads: eight exclusion areas
each carrying a paragraph explaining the actual worry, in the household's own words, about dairy
odor, flaring, uranium groundwater and sonic booms.

The kept-and-passed sample is the second. 812 judgments with reasons is a better statement of taste
than any instruction, and showing a handful of each costs a few hundred tokens.

**The exclusion reasons are context, not tests.** The polygons have already removed what the
household decided to remove; a property that survived them is outside every one. So the reasons are
sent to explain what this household is worried about, and a concern may be raised only when the
property's own evidence supports it. AC-4's scenario pins that distinction, because the failure mode
is a model that reads "dairy odor" and flags every property in the eastern half of the state.

### D-5: two pictures, and the second one is the interesting one

The listing photograph is the obvious one and answers what the description is least honest about:
roof material, vegetation against the house, terrain, outbuildings, visible condition.

The second is a hazard map tile centred on the coordinates. Nothing can compute a distance to the
nearest high-hazard block, because that layer is a raster; a model looking at the picture can see
that the property sits at the edge of one. This is why the map matters and it is worth being
explicit that it is a substitute for a computation this product cannot do.

Both go through the machinery that already fetches them, which is `hazard_tile` for the layer and
the stored image on disk for the photograph. Nothing new reaches the outside world.

### D-6: wind is regional and says so

The rose is the nearest station's, and the nearest station can be forty miles away. Sending it
without that distance invites a confident sentence about prevailing smoke direction at a parcel the
data has nothing to say about. So the dossier carries the station, its distance, and a plain
statement that a rose describes a region. AC-16.

April by default, because it is what matters for smoke and dust in eastern New Mexico and what the
map already defaults to.

### D-7: it advises, and the person decides

An assessment never sets a judgment, never hides a row, never reorders a table and never drops
anything from an export. Non-negotiable 7 says losing a person's judgment is the one failure this
tool cannot have, and a model that could pass on a house is a model that can lose one.

This is also what makes the feature safe to be wrong. A concern that is mistaken costs a moment's
reading; a hidden property costs a house.

### D-8: nothing is partially applied

A model answer that is unusable makes the property a reported failure, not a half-recorded
assessment, and leaves any previous assessment exactly as it was. The same rule feat-009 applies at
the level of a field, applied here at the level of a property, because half an account of a house
reads as a whole one.

### D-9: opt-in per saved search, in the file that already has the switch

Whether a run assesses what it found is `assess.model` on the saved search, off unless turned on,
beside the `extract.model` switch that already works this way. On demand is always available.

One shape rather than two for the same kind of choice, in a file the person edits by hand, and it
keeps invariant 9 true: with nothing configured, nothing changes anywhere.

### D-10: the pass records itself like every other long operation

feat-001/AC-31 exists now, so this needs no machinery of its own: it wraps its work in the core's
recorder, and it is therefore visible while it runs from either surface, survives the process that
started it, and is refused while another long pass is under way. AC-17 is a sentence rather than a
subsystem because that work is already done.

### D-11: the cost is said out loud first

This is the only operation in this product that costs money per property. A pass reports how many it
is about to assess before it starts asking. That is the number a person needs, and the difference
between an informed instruction and a surprise.

### D-12a: where `assess/` sits in the layer order

The constitution names the core's layers as sources, merge, store, enrich, rules, then the surfaces,
and binds them to depend downward only. That list is the data path rather than a module census —
`extract`, `search`, `export` and `deliver` are all real and none of them is in it — so a new module
has to say where it stands rather than assume the list covers it.

`assess` sits above `rules` and below the surfaces. It reads down into `store`, `enrich`, `rules`,
`extract` and `search`, and nothing below it may import it. That is the highest position in the core
and it is the honest one: this is the only thing here that needs a rule verdict, an enrichment value,
a recovered field, a saved search's prose and a photograph in the same breath.

Stated because it decays quietly. The moment something in `rules` or `enrich` wants "the assessment
for this property", the direction has inverted and the reason this module could exist at all is
gone.

### D-12: what this feature does not own

- **The screens.** Drawing an assessment beside a person's own notes is the browser interface's job,
  the way editing annotations already is. Two halves and they are not the same: *starting* a pass
  from a screen is required for invariant 5 and is tasked here as a change against feat-010, and
  *drawing* the result is deferred until this has run over a real set, because what is worth showing
  is a question somebody answers after reading twenty of these.
- **The model client, the account, the pacing, the credential.** feat-009 owns all four.
- **The enrichment values, the hazard tiles and the wind roses.** feat-007 owns them; this reads
  them.
- **Which rules fired.** feat-008 owns that; this reads the verdicts.
- **The digest.** Whether an assessment reaches the nightly email is feat-012's question, and worth
  asking only once this has run over a real set.

## Verification approach

- **Unit, against recorded answers.** The dossier assembly, the fingerprint, the staleness rule and
  the answer parsing are all pure given inputs, and none of them needs a model to test.
- **A fake model client**, the way feat-009's tests already work, for the pass over a set: the
  bounded first pass, the skipping of what is current, one property's failure not taking the others,
  and the credential never reaching a message.
- **An annotation asserted byte-identical** across two assessments, which is AC-6 and the one that
  would be catastrophic to get wrong.
- **A real request, once, by hand**, against a copy of the store, to confirm the dossier is accepted
  and the answer parses. Not in the suite: it costs money and needs a key, exactly as feat-009's
  model path is tested with a fake and exercised for real by a person.

Test commands name explicit paths, never a bare directory:

```
uv run pytest tests/test_assessment_dossier.py tests/test_assessment_pass.py
```

## Deviations from the constitution

One, stated rather than smuggled. The constitution's privacy line names the four destinations
outbound traffic may have, and the configured model is one of them; what changes is *what* is sent
to it. feat-009 sends a description and nothing else, by design. This sends the address, the
coordinates and a photograph.

That is the feature. It was put to the person running searches as one of three scopes, with the
boundary named, and this is the one they chose. Recorded here so that the difference between the two
passes is legible as a decision rather than discovered later as an inconsistency.
