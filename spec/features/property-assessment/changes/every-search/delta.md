# Delta: property-assessment

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-20.

**User story.** As the person running searches, I want a pass with no search named to read every
search I am watching, so that leaving the box empty does what it says rather than whatever sorts
first.

- [ ] AC-20: With no saved search named, a pass covers every saved search a run of everything would:
      a paused or archived search is left out, and is still read when it is named. Each search's
      properties are read against that search's own criteria. A property two searches share is read
      once in a pass, against the first of them by name. A bounded pass is bounded as a whole rather
      than per search, and the outcome counts across every search it covered. A search with nothing
      to read, because it has no completed run or its file cannot be read, is named and passed over
      rather than failing the rest.

      **Once, because a reading belongs to the property.** It is kept per property rather than per
      search and its fingerprint includes the criteria, so reading a shared property against each
      search in turn would pay twice and leave each reading stale to the other, and the next pass
      would pay twice again. The first by name is a stable order, so the same search owns it every
      time.

## MODIFIED

None. AC-1 still describes a pass over one search, which is what each search in an unnamed pass is.

## REMOVED

None.
