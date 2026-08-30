# Proposal — property-assessment

**Trigger:** After a full pass over every property still in play, the person running searches said:
"We have the Concerns column, but there isn't a column talking about the good stuff for a property.
Can we add that to the assessment and re-run just for that field first but make sure any new ones
get both concerns and good stuff."

**Summary:** This feature only ever asked what was wrong. That was the right first question and it
is half a question, and the half that is missing is the one that makes the other half usable.

The numbers say it plainly. Across 292 readings the model has raised 235 concerns and said nothing
whatever in any property's favour, because it was never asked to. Somebody looking at that table
sees a hundred and fifty houses each with a list of worries and nothing at all saying why any of
them is worth the drive. That is not a reading of a house. It is a reading of a risk, and it is
biased in a way that is easy to miss precisely because every individual concern is true and carries
its evidence.

**Held to the same standard, or it is worse than nothing.** A favourable point carries the evidence
it came from exactly as a concern does, and one that cannot be pointed at is not written. This
matters more here than it does for concerns, not less: flattering sentences are easier to generate
and harder to doubt, and a list of pleasant adjectives about a house somebody is deciding whether to
drive four hours to see is actively harmful. It is also measured against what this household said
they want, so a feature they never asked for is not a point in a property's favour merely for being
nice.

**No severity.** Concerns carry one because "serious" changes what a person does. Nothing equivalent
follows from one good thing being better than another, so grading them would be a number nobody
acts on.

**Two hundred and sixty-eight readings already exist and must not be thrown away.** Asking the whole
question again to gain one section would pay a second time for every part already answered, and
would replace concerns somebody may have read and acted on with freshly generated ones. So a reading
that is still current but predates the question gets one narrow request for the missing section, and
what comes back is added beside what is there. Which request a property gets is decided from what it
is missing, per property, rather than by a flag somebody has to remember to pass.

**Three states, not two, and the column has to hold all three.** Nobody asked. Asked, and nothing
was said for it. This many. The first and the second look the same to a reader and are completely
different to a pass: only the first is worth spending money on again. The store keeps them apart;
the table does not have to.

**Blast radius.** One nullable column on `assessments` and a schema version. The request gains a
section and a second, narrower form. The pass gains a third answer beside "ask" and "skip". Both
surfaces gain a way to read it, which is invariant 5 rather than a choice. The browser's own change
is `browser-interface/changes/what-counts-for-it/`, because a column is that feature's business.
