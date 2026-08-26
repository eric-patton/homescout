# Delta — listing-store

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-27.

**User story.** As the person reviewing results, I want a way back to this property on each site it
was found on, so that I can add it to the list I keep on the site I actually use, and so that a site
with no link tells me that site does not have it.

- AC-27: A source link carries the address the source row can be read at, alongside the source's
  name and the source's own identifier. A property assembled from rows on several sites therefore
  reports one address per site, not one address in total, and a site the property was never seen on
  contributes no address rather than a broken one. A test asserts that a record merged from two
  sources reports both addresses and that they differ.

## MODIFIED

Nothing. The record gains a field; no existing statement about it changes.

## REMOVED

Nothing.
