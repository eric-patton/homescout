# Delta: property-assessment

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-18 and AC-19.

**User story.** As the person running searches, I want to see what counts for a property as well as
what counts against it, so that a table of assessments tells me which houses are worth the drive
rather than only which ones carry risk.

- [ ] AC-18: An assessment records what counts FOR the property as well as what counts against it.
      Each point carries the evidence it came from, on exactly the same terms as a concern: the
      words from the description, the field and its value, or what was visible in a picture. A point
      that cannot be pointed at is not recorded.

      **The same standard, for a stronger reason.** A flattering sentence is easier to generate than
      a critical one and harder to doubt when read, so an unciteable point is more dangerous here
      than an unciteable concern, not less. A list of pleasant adjectives about a house somebody is
      deciding whether to drive four hours to see is worse than no list.

      **Measured against what this household said they want.** A feature nobody asked for is not a
      point in a property's favour merely for being pleasant, and a point whose whole content is
      that one of their own `boost` criteria fired tells them nothing they could not already see.

      **No severity.** A concern carries one because "serious" changes what somebody does about it.
      Nothing follows from one good thing being better than another, so grading them would be a
      number nobody acts on.

      **Three states, and the store keeps all three apart.** Nobody asked; asked, and nothing was
      said for it; this many. The first two are indistinguishable to a reader and completely
      different to a pass, because only the first is worth spending on again. An assessment recorded
      before this question existed holds the first, not the second, and an answer that omits the
      section entirely is read as the first rather than silently recorded as the second.
- [ ] AC-19: A pass asks each property only what it is still missing. A property whose recorded
      assessment still describes it and is complete is not asked anything. One whose assessment
      still describes it but predates a section of the question is asked for that section alone, and
      what comes back is added beside what is already recorded, with every other part carried across
      untouched. Anything else is asked the whole question.

      **Which of the three a property gets is decided from what it is missing**, per property, and
      never from a flag somebody has to remember to pass. The pass that fills in a gap for two
      hundred properties and the pass that reads ten new ones are the same command.

      **Nothing already recorded is replaced by a narrow request.** The account, the concerns, their
      evidence, what the pictures showed and what could not be told are carried across exactly as
      they were, because that request asked about none of them. Somebody may have already read and
      acted on a concern, and a pass adding a section has no business regenerating it.

      **A topped-up reading keeps the date it was made.** The property was read then, from material
      that has not moved since; stamping it with today would say it had been read again. The row
      recorded before it stays readable, which is how the addition is visible at all.

      **The narrow request still gets the pictures.** They are the reason this feature is worth
      having, and a sound-looking metal roof in a photograph is exactly the kind of point this is
      for. Answering from the earlier reading's description of a picture instead would make a
      topped-up property's points quietly weaker than a freshly read one's, and nobody would
      remember later which was which.

## MODIFIED

Nothing. Every existing criterion holds as written; AC-18 adds a section to what an assessment
records and AC-19 adds a third answer beside the two AC-9 already distinguishes.

## REMOVED

Nothing.
