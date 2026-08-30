## Why

This tool already knows a great deal about each of the 155 properties still in play, and nothing
reads it together. The flood zone is in one column, the wildfire hazard in another, which rules
fired in a third, the description in a fourth, a photograph on disk, and the household's actual
worries in eight paragraphs of prose inside a saved search that no model has ever been shown. A
person doing this by hand opens each property and cross-references four screens. That is the work
this feature does.

The existing model pass cannot do it, and not by accident. Description field extraction (feat-009)
is handed prose, a vocabulary and the operator's notes, and deliberately not a listing, a snapshot
or a store, on the stated grounds that there is no address in scope there to send. That blindfold
is correct for transcribing six enumerated fields out of a sentence. It is exactly why that pass
can tell you a description says "private well" and cannot tell you the property is a mile downwind
of a feedlot the household has spent a paragraph explaining it wants to avoid.

So: a second pass, with a different boundary, doing a different job. It reads one property and
reports what it makes of it against criteria that were already written down. It writes what it
thinks beside what the person thinks, never into it, and it decides nothing.

## Vocabulary used in this feature

- **Assessment**: what the model made of one property at one moment, given one set of inputs.
  Recorded, attributed, and never mistaken for the person's own judgment.
- **Dossier**: everything about one property that is sent in one request. Assembled here, from what
  other features already collected; nothing in it is fetched for this purpose.
- **Concern**: one thing the model thinks is wrong or worth checking, with the evidence it came
  from. A concern is not a verdict and never removes a property from anything.
- **Criteria**: what the household has said it wants and does not want, gathered from the saved
  search's exclusion reasons, its rules, the installation's notes, and a sample of what has been
  kept and passed on with the reasons given.
- **In play**: found by the latest completed run of a search, not passed on, and not off the market.
  The set this pass runs over.
- **Stale**: an assessment whose inputs have changed since it was made, so it no longer describes
  the property it names.

## User stories

- As the person running searches, I want each property still in play read against what I have
  already said I want, so that a table of 155 rows becomes a shortlist I can act on.

- As the person running searches, I want each concern to cite what it came from, so that I can
  check it rather than take it on faith.

- As the person running searches, I want the model told about the things no column holds, my
  reasons for excluding whole areas, so that it can notice a property that is technically fine and
  sits in the middle of a worry I have already written down.

- As the person running searches, I want to see the photograph's evidence used, so that a
  description claiming a metal roof over a picture of asphalt shingles is caught.

- As the person running searches, I want what the model thinks kept separate from what I think, so
  that I can disagree with it and have my disagreement survive.

- As the person running searches, I want to be told what it could not determine, so that a silent
  gap is never read as an all-clear.

- As the person running searches, I want it to assess only what is new since last time, so that a
  nightly run costs a handful of requests rather than a full pass.

- As an automated caller, I want the assessment and its provenance in the same structured document
  both surfaces read, so that the browser and the command line agree.

## Behavior & scenarios

- **Scenario: the pass runs over what is in play**
  - Given a search whose latest completed run found 951 properties, of which 804 have been passed
    on and 67 are off the market
  - When an assessment pass runs over that search
  - Then it assesses the remaining properties and no others, and reports how many it considered,
    how many it assessed, and how many it skipped as already current

- **Scenario: a concern cites its evidence**
  - Given a property whose description says the septic system was installed in 2025 and whose
    wildfire hazard reads moderate
  - When it is assessed
  - Then each concern names what it came from, a quoted phrase for one read out of the description
    and the field and value for one read out of enrichment, and a reader can check either

- **Scenario: the household's own reasons are applied**
  - Given a saved search whose exclusion areas explain that the concern in one county is dairy odor
    and in another is flaring and truck traffic
  - And a property that is outside every exclusion polygon
  - When it is assessed
  - Then the model may raise a concern naming that worry when the property's own evidence supports
    it, and may not raise one on the basis of the area alone, because the polygons have already
    removed what the household decided to remove

- **Scenario: the photograph disagrees with the description**
  - Given a description claiming a metal roof and a photograph showing asphalt shingles
  - When it is assessed
  - Then the disagreement is reported as a concern citing both, and neither the description's claim
    nor the picture's is written into the property's roof field, which stays as feat-009 left it

- **Scenario: nothing is decided**
  - Given an assessment that ranks a property last and raises four concerns
  - When the results table is drawn
  - Then the property is still there, in its usual place under whatever the person sorted by, with
    its assessment readable beside it and no judgment set

- **Scenario: the person's own judgment is untouched**
  - Given a property carrying a verdict, a rank and free notes written by the person
  - When it is assessed, twice, with different results
  - Then everything the person wrote is exactly as they left it, and a test asserts the annotation
    row is byte-identical before and after

- **Scenario: an assessment goes stale**
  - Given a property assessed yesterday
  - When its description changes, or an enrichment value it was assessed from changes, or the
    household edits the criteria
  - Then the assessment is reported as stale rather than as current, the previous one remains
    readable and attributed to when it was made, and the next pass reassesses that property

- **Scenario: a price change is not staleness**
  - Given a property assessed yesterday whose price has since been cut
  - When the next pass runs
  - Then it is not reassessed, because nothing it was assessed from has changed, and paying a
    request per price cut is how a pass over a live market costs more than it is worth

- **Scenario: the model is not configured**
  - Given an installation with no model configured
  - When anything asks for an assessment
  - Then the pass reports that it is not configured, in the same words feat-009 uses, nothing else
    in the tool behaves differently, and no screen shows a gap where an assessment would be

- **Scenario: one property's request fails**
  - Given a pass over forty properties where the model refuses the eleventh
  - When the pass finishes
  - Then the other thirty-nine are assessed and recorded, the failure is reported with the eleventh
    named, and the credential is not in the message

- **Scenario: what it could not tell**
  - Given a property with no coordinates, and therefore no hazard rating, no elevation and no
    nearest weather station
  - When it is assessed
  - Then the assessment says which of its inputs were absent, and no concern is raised or dismissed
    on the basis of a value nobody has

## Acceptance criteria

- [ ] AC-1: An assessment pass runs over the properties in play for a search: found by the latest
      completed run, not passed on, and not off the market. It reports how many it considered, how
      many it assessed, how many it skipped as current, and how many failed.

- [ ] AC-2: One property is one request. The dossier sent carries the listing's own fields, its
      description, the six recovered fields with their provenance, every enrichment value held for
      it, which rules fired with each severity, and the criteria. Everything in it is read from what
      other features already collected; this feature fetches nothing of its own.

- [ ] AC-3: The dossier carries the address, the coordinates and the photograph. This is the
      boundary feat-009 does not cross and the reason this is a separate feature: that pass is
      handed a description and nothing else, on the stated grounds that there is no address in scope
      there to send. Here there is, deliberately. The spec says so out loud so that a later reader
      finds a decision rather than an inconsistency.

      **Every surface that can turn this on says what it sends, above the control rather than below
      it.** feat-010 already does exactly this for the notes box, which says that the text goes to
      the model with every description and that it cannot add a field. The same sentence is owed
      here and is larger: the address of a house somebody is thinking of buying, its coordinates and
      its photograph leave this machine.

      **And it says where they can go instead.** The model's address is configurable and a local one
      needs no credential and no network, which the settings surface already explains for the
      existing pass. That is the answer to somebody who wants the assessment and does not want the
      address leaving the house, and it is a sentence rather than a feature because the
      configuration for it already exists.

- [ ] AC-4: The criteria sent are the household's own words: the saved search's description, each
      exclusion area's reason, the rules with their severities, the installation's and the search's
      notes for the model, and a sample of properties kept and passed on with the reason recorded at
      the time. No criterion is written for this feature; every one of them is something the person
      already said somewhere else.

- [ ] AC-5: An assessment records a short account of the property, its concerns, how well it matches
      the stated criteria, what to check before visiting, and what could not be determined. Each
      concern carries the evidence it came from: a phrase quoted from the description, or the name
      and value of a field, or a statement that it came from the photograph.

- [ ] AC-6: An assessment is stored separately from the person's annotations and is never written
      into them. `rank`, `verdict`, `red_flags`, `summary`, `next_step`, `notes`, `taxes`, `crime`,
      `fire_egress`, `sewage_exposure` and `outbuildings` remain what the store declares them to be,
      the user's own judgment, never written by a run. A test asserts an annotation row is unchanged
      across two assessments of the same property.

- [ ] AC-7: An assessment decides nothing. It never sets or clears a judgment, never hides a
      property from any view, never reorders a table by itself, and never removes a row from an
      export. Keeping and passing on remain the person's, which is non-negotiable 7.

      **This is also the whole of this feature's answer to a description written to manipulate it.**
      A listing's text is written by somebody with an interest in the sale and arrives here as
      untrusted input; the instruction says a description is data and that nothing written in it
      changes the instructions, exactly as feat-009's already does. But an instruction is a request,
      not a guarantee. What makes that acceptable is that nothing acts on the answer: the worst a
      successful injection achieves is a misleading paragraph that a person reads, in a place that
      is labelled as the model's opinion, next to rules it cannot influence and a judgment it cannot
      set. A design in which an assessment could hide a property would make the same injection worth
      writing.

- [ ] AC-8: An assessment carries what it was made from and when, sufficient to tell whether it
      still describes the property. When any of those inputs changes it is reported as stale, the
      previous assessment stays readable and attributed, and the next pass reassesses it. A price
      change alone is not a change to what it was assessed from.

      **What counts as an input is the household's stated criteria and the property's own data, and
      not the sample of past judgments.** The stated criteria are the search's description, the
      exclusion reasons, the rules and the notes: things somebody wrote deliberately, which change
      rarely and should invalidate everything when they do. The sample of kept and passed properties
      is calibration rather than instruction, and it changes every time anybody passes on a house.
      Folding it in would mean one click on one property reassessing all 155, at a cost, for a
      change nobody made to what they were looking for.

- [ ] AC-9: A pass assesses only what is not already current, so a run that brings in four new
      properties costs four requests. A caller may ask for a bounded first pass, and whatever is
      left over is named in the outcome rather than silently dropped, exactly as feat-009 requires.

- [ ] AC-10: With no model configured the pass reports that, before anything is sent, in the same
      terms feat-009 already uses for the same condition. Nothing else in the product behaves
      differently and no surface shows an empty space where an assessment would be. This is
      invariant 9: an optional component absent by default.

- [ ] AC-11: One property's failure is that property's. The rest of the pass completes, each failure
      is reported with the property named, and no failure message carries a credential.

- [ ] AC-12: The assessment is one core operation, with a command-line surface that takes `--json`
      and returns a stable exit code, which is invariant 6. Invariant 5 requires the browser to
      reach it too, and the browser is another feature's file: starting a pass from a screen is a
      change against feat-010, named as a task here rather than assumed, because a capability that
      exists on one surface only is the thing that invariant forbids. What each surface does with
      the result is separate, and only the drawing of it is deferred.

- [ ] AC-13: Every request is paced by the same politeness the model client already applies, with
      the same delay, timeout, backoff and retry bound. This feature adds no second pacing policy
      and no second client.

- [ ] AC-14: What the model could not determine is recorded as that. An input absent for a property
      is named, and no concern is raised or dismissed on the basis of a value nobody holds, which is
      invariant 10 read at the level of a judgment rather than a field.

- [ ] AC-15: Whether a run assesses what it found is a property of the saved search, off unless
      turned on, in the same shape and the same file as the existing switch for the model pass. On
      demand is always available regardless.

- [ ] AC-16: Wind is reported with its distance. The rose comes from the nearest weather station,
      which can be tens of miles away, so what is sent says which station and how far, and the model
      is told that a rose is regional rather than a fact about the parcel.

- [ ] AC-17: The pass records itself the way every long operation does, so it is visible while it
      runs from either surface and survives the process that started it.

## Edge cases & errors

- **A property with no coordinates.** No hazard rating, no elevation, no aquifer answer, no nearest
  station, and no map picture. Assessed on what remains, with the absences named. Never assessed as
  though the missing values were negatives.

- **A property with no photograph.** 2,650 listings hold exactly one image and some hold none. The
  dossier says the picture is absent rather than omitting the fact, so nothing reads a silent gap as
  a property whose appearance raised no concerns.

- **A property with no description.** The rules and enrichment still say things worth reporting.
  The assessment says what it was working from.

- **A merged property.** Its constituents keep their own history and their own pages. The assessment
  belongs to the canonical record, and a constituent merged into another is not assessed separately,
  because the person is deciding about a house rather than about a listing.

- **The model answers with something unusable.** Nothing is partially applied. The property is
  reported as failed rather than recorded with half an assessment, and the previous one, if any,
  stays exactly as it was.

- **The model contradicts a rule.** The rules are the household's own and are not overridden by
  anything here. The contradiction is reported as a concern about the model's own reading, and the
  rule verdict stands.

- **Criteria change mid-pass.** A pass reads the criteria once, at the start, and records what it
  used. Half a pass under one set of instructions and half under another is worse than either.

- **A model that is asked about a property twice in one pass.** The second is skipped as current
  rather than paid for, which is the same rule AC-9 applies across passes.

## Non-functional requirements

- **Cost is stated before it is incurred.** A pass reports how many properties it will assess before
  it starts asking, because this is the only operation in the product that costs money per property
  and the number is the thing a person needs to see.

- **Politeness.** Non-negotiable 10, through the client and pacing feat-009 already owns.

- **Privacy.** The dossier is the first thing in this product that sends an address to a model. That
  is the deliberate change. It goes only to the configured model, which is one of the four
  destinations the constitution already names, and to nowhere else. Nothing about it is republished.

- **Absent by default.** Invariant 9. No key, no assessment, no difference to anything else.

- **Recoverable.** An assessment is data about a moment, not history. Losing every one of them costs
  a pass and nothing else: no snapshot, no annotation and no run is computed from them.

## Open questions

None outstanding. The four raised during research are resolved above: staleness is defined by what
was assessed from rather than by any change to the property (AC-8), the wind season and its distance
caveat are settled by AC-16, whether a run triggers a pass follows the existing per-search switch
(AC-15), and what could not be determined is recorded rather than hedged over (AC-14).
