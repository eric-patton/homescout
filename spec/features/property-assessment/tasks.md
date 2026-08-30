# Tasks — Property assessment (feat-013)

Build order follows the dependencies: the dossier can be assembled and tested before anything is
sent, the storage before the pass writes to it, and the surfaces last.

## The dossier

- [x] T1: `assess/dossier.py`: assemble everything about one property that goes in one request
      (`feat-013/AC-2`, `feat-013/AC-3`). The listing's fields, its description, the six recovered
      fields with provenance, every enrichment value held for it, and the rule verdicts with their
      severities. Read from what feat-001, feat-007, feat-008 and feat-009 already collected;
      nothing is fetched here. The address and coordinates are in it, deliberately, and the module
      docstring says why this boundary differs from `extract/model.py`'s.

- [x] T2: `assess/dossier.py`: name what is absent (`feat-013/AC-14`). A property with no
      coordinates has no hazard rating, no elevation, no aquifer answer and no station; one with no
      photograph has no picture. Each absence is stated in the dossier rather than omitted, because
      a silent gap reads as a thing that raised no concern.

- [x] T3: `assess/criteria.py`: gather what the household has already said (`feat-013/AC-4`). The
      search's description, each exclusion area's reason in the person's own words, the rules with
      severities, the installation's and the search's notes, and a sample of kept and passed
      properties with the reason recorded at the time. Nothing here authors a criterion.

- [x] T4: `assess/criteria.py`: the exclusion reasons are context and not tests (`feat-013/AC-4`).
      The polygons already removed what they remove, so a property being assessed survived them.
      Said in the instruction, because the failure mode is a model that reads "dairy odor" and flags
      the eastern half of the state.

- [x] T5: `assess/pictures.py`: the two images (`feat-013/AC-3`). The stored listing photograph from
      disk, and a hazard map tile centred on the coordinates through the fetcher feat-007 already
      owns. The second is the substitute for a distance this product cannot compute, because the
      layer is a raster; the docstring says so.

- [x] T6: `assess/wind.py`: the nearest station and its distance (`feat-013/AC-16`). Arithmetic over
      the station list already on disk. What is sent carries the station, how far away it is, and a
      plain statement that a rose is regional, so nothing writes a confident sentence about the
      prevailing wind at a parcel.

- [x] T7: `tests/test_assessment_dossier.py`: the dossier, the absences, the criteria and the
      nearest station (`feat-013/AC-2`, `feat-013/AC-3`, `feat-013/AC-4`, `feat-013/AC-14`,
      `feat-013/AC-16`). Including that a property with no coordinates is assessed on what remains
      and that no value nobody holds is treated as a negative.

## Asking, and what comes back

- [x] T8: `assess/model.py`: the request, through feat-009's client, account and pacing
      (`feat-013/AC-13`). No second client, no second credential, no second politeness policy. What
      is new here is the body and the instruction, not the transport.

- [x] T9: `assess/model.py`: the instruction (`feat-013/AC-5`). It asks for a short account, the
      concerns with the evidence for each, how well the property matches the stated criteria, what
      to check before visiting, and what could not be determined. Evidence is a quoted phrase, or a
      field name and value, or a statement that it came from the photograph.

- [x] T10: `assess/model.py`: nothing is partially applied (`feat-013/AC-11`, `feat-013/AC-5`). An
      answer that is unusable makes the property a reported failure rather than a half-recorded
      assessment, and leaves any previous one exactly as it was. The same rule feat-009 applies to a
      field, applied to a property.

- [x] T11: `assess/model.py`: a failure names the property and never the credential
      (`feat-013/AC-11`). Through the stripper that already exists, and now also through the store's
      own scrubbing on the way in.

- [x] T12: `tests/test_assessment_pass.py`: the request and the answer, against a fake client
      (`feat-013/AC-5`, `feat-013/AC-11`, `feat-013/AC-13`). Including an unusable answer leaving a
      previous assessment untouched.

## Storage

- [x] T13: `store/schema.py`: the table an assessment lives in, and its migration (`feat-013/AC-6`,
      `feat-013/AC-8`). Its own table, never the annotation columns: the store declares those the
      user's own judgment, never written by a run, and that stands. It carries the account of the
      property, the concerns with their evidence, what could not be determined, when it was made,
      which model made it, and the fingerprint of what it was assessed from.

- [x] T14: `store/core.py`: writing and reading one, and reading whether one is current
      (`feat-013/AC-8`). Staleness is the fingerprint no longer matching, computed on read.
      A previous assessment stays readable and attributed when a newer one supersedes it.

- [x] T15: `tests/test_assessment_store.py`: the annotation row is byte-identical across two
      assessments of one property (`feat-013/AC-6`). The one that would be catastrophic to get
      wrong, and the reason this table exists at all.

- [x] T16: `tests/test_assessment_store.py`: a price change does not make an assessment stale, and a
      changed description, enrichment value, rule verdict or stated criterion does (`feat-013/AC-8`).
      Asserted in both directions, because a fingerprint that is too broad costs money on every
      price cut and one that is too narrow describes a property that no longer exists.

- [x] T16a: `tests/test_assessment_store.py`: passing on one property does not make any assessment
      stale (`feat-013/AC-8`). The expensive mistake, asserted directly. The kept-and-passed sample
      is calibration and changes constantly; folding it into the fingerprint would mean one click
      reassessing all 155 at cost, over a change nobody made to what they were looking for.

## The pass

- [x] T17: `api.py`: `assess`, over what is in play (`feat-013/AC-1`, `feat-013/AC-9`). Found by the
      latest completed run, not passed on, not off the market. Only what is not already current, so
      a run bringing in four properties costs four requests. A bounded first pass is available and
      whatever is left over is named in the outcome rather than dropped.

- [x] T18: `api.py`: the count is reported before anything is asked (`feat-013/AC-1`). This is the
      only operation in this product that costs money per property, and the number of requests it is
      about to make is the thing a person needs in order to say yes.

- [x] T19: `api.py`: absent by default (`feat-013/AC-10`). With no model configured the pass reports
      that before anything is sent, in the same terms feat-009 already uses. Nothing else behaves
      differently and no surface shows a space where an assessment would be.

- [x] T20: `api.py`: an assessment decides nothing (`feat-013/AC-7`). It sets no judgment, hides no
      property, reorders nothing and removes nothing from an export. Asserted rather than merely
      intended, because a model that could pass on a house is one that can lose a person's decision.

- [x] T21: `api.py`: the pass records itself through the core's recorder (`feat-013/AC-17`). Visible
      from either surface while it runs, surviving the process that started it, and refused while
      another long pass is under way. Already built by feat-001/AC-31; this uses it.

- [x] T22: `tests/test_assessment_pass.py`: in play and nothing else, the bounded pass, the skipping
      of what is current, the count reported first, and that nothing is decided (`feat-013/AC-1`,
      `feat-013/AC-7`, `feat-013/AC-9`, `feat-013/AC-10`).

## Both surfaces

- [x] T23: `search/definition.py`: `assess.model` on a saved search, off unless turned on
      (`feat-013/AC-15`). Beside the existing switch for the model pass, in the same shape and the
      same file, because one shape for one kind of choice is what stops a hand-edited file becoming
      a quiz.

- [x] T24: `cli/main.py`, `cli/render.py`: `homescout assess`, with `--search`, `--limit` and
      `--json` (`feat-013/AC-12`). A stable exit code, which is invariant 6.

- [x] T25: `api.py`: reading one property's assessment, in the shape both surfaces read
      (`feat-013/AC-12`). The seam the browser will draw from when feat-010 gains the screen for it.

- [x] T26: `tests/test_assessment_pass.py`, `tests/test_cli_operations.py`: the same pass through
      the core and through the command leaves one state, and the switch is honoured
      (`feat-013/AC-12`, `feat-013/AC-15`).

## Once it has run

- [x] T27: A change against feat-010 so the browser can start a pass (`feat-013/AC-12`,
      `feat-013/AC-3`). The endpoint and a control on the tools surface, beside the existing model
      pass. Required rather than deferred: a capability reachable from one surface only is what
      invariant 5 forbids, and the browser is where this will actually be used. The control says
      what the dossier sends before it is pressed, which is AC-3's second half, and names the local
      model as the alternative.

- [ ] T28: A change against feat-010 for drawing an assessment beside the person's own notes, never
      inside them. Deliberately deferred, and deliberately not specified until this has run over a
      real set, because what is worth showing is a question somebody answers after reading twenty of
      these rather than before reading any.
