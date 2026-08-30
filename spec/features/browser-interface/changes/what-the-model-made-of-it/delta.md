# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Two acceptance criteria, taking the next stable ids when folded into `spec.md`: AC-86 and AC-87.
They are numbered after the three `changes/come-back-to-it/` adds.

**User story.** As the person running searches, I want to see at a glance which properties the model
raised something about, so that a table of a hundred and fifty rows tells me where to look.

**User story.** As the person running searches, I want the whole of what it said about one property
without leaving the table, so that reading an assessment is not a decision to navigate away from
what I was doing.

- [ ] AC-86: The results table carries a column saying how many concerns the assessment raised about
      each property. It is marked when any of them is serious, and marked differently when the
      assessment no longer describes the property because what it was assessed from has changed. A
      property with no concerns shows nothing rather than a zero, and a property never assessed shows
      nothing rather than an absence, because those are different facts and neither is a number.

      It is an ordinary column. It hides, comes back from the chooser, sorts and filters exactly as
      every other column does, which is AC-45 and AC-52 applying to it without being restated. It
      joins the chooser under an origin of its own, because what a model made of a property is a
      different kind of claim from a value a source reported, one this tool computed, one read out
      of a description, public data about the place, or something the person wrote.

      **Ordinary means it joins the declaration every column is declared in, and not the default
      spreadsheet.** Those are already two different things: forty-three columns are declared and
      the default sheet uses thirty-two. Joining the declaration is what makes sorting, filtering,
      hiding and the chooser work without a special case, and staying out of the default sheet is
      what leaves feat-011's header untouched and needs no change against it. Somebody who wants the
      count in a sheet adds it to a template, which is what feat-011/AC-7 says a template is for.

- [ ] AC-87: Pressing the count opens the assessment for that property beneath it, in the table,
      without leaving the page. What opens is the whole of it: the account of the property, every
      concern with the evidence it came from, what each picture showed, what to check before
      visiting, and what could not be determined. Pressing again closes it, and it opens from the
      keyboard the same way, because the cell is already reachable that way.

      **The count and not the row.** Pressing a row already means something here and means two
      things: it moves the cell focus, which is what makes a writable column typable, and with shift
      held it extends the range AC-81 acts on. A third meaning on the same press would have taken
      one of those away, and the one it would have taken is the one somebody already reported
      losing. The count is where the information is, so it is where the press belongs; a property
      with nothing assessed has an empty cell and nothing to press.

      **The person's own judgment stays visibly theirs.** What is drawn here is labelled as the
      model's and dated, and nothing in it is written into `rank`, `verdict`, `red_flags`,
      `summary`, `next_step` or the rest, which remain the user's own as feat-013/AC-6 requires.
      Somebody reading a concern must be able to tell instantly that they are reading an opinion
      rather than their own note.

      **An assessment that no longer describes the property says so before its content.** Reading a
      stale assessment as current is the one way this feature misleads rather than merely
      disappoints.

      **The text is fetched when a row is opened rather than sent with the table.** The results
      answer for this workspace is already 2.7MB, and adding every assessment's prose to every page
      load to show what is usually one of them is the wrong trade. The count in AC-86 is three small
      values per row and travels with the table.

## MODIFIED

None. AC-45's rule that an arrangement is remembered per browser and per search, and AC-52's that
any column can be hidden and brought back from the chooser, both apply to the new column as written.
That they need no amendment is the evidence they were written generally enough.

## REMOVED

None.
