# Proposal — browser-interface

**Trigger:** The person running searches asked for it, in these words: "Why not instead have a thing
where we can add and remove criteria rows that have dropdowns for the various known things like a
real expression builder. Please make this as easy to use as possible for the entire site. My wife
will be using this, and she is not a developer."

**Summary:** The criteria box was a textarea, one criterion per line, `id | severity | expression`.
Everything about that asks somebody to be a programmer: that a field is spelled with an underscore,
that `=` is not `==`, that text takes quotes and numbers do not, that the six words `cooling` may
hold are a closed set and `"swamp cooler"` is not one of them. Nothing on the page said any of it,
and a wrong value produced a criterion that parsed, saved, ran, and was never true.

This replaces it with a builder. Each criterion is a card: a name, what firing does, and one or more
conditions, each of which is a field, a comparison and a value, all chosen from lists. The value
control follows the field, so picking Water source offers the six words it can hold and picking
Price offers a number box. Eight suggestions are one click each, because a blank builder is still a
blank page.

**The stored form does not change.** A saved search still carries `when: water_source == "well"`,
still readable and editable by hand, and the grammar stays in the rule engine where non-negotiable 8
requires it: the browser sends the rows a person picked and the core composes the expression. The
translation is exact in both directions, and the honest half of that is what it refuses. Not every
criterion is rows: `(a or b) and c` is a perfectly good one and is not a flat chain. The core answers
`parts: null` for those, and the page shows the expression as written rather than rows that would
quietly mean something else and be saved over it.

The rest of the request, "as easy to use as possible for the entire site", is a smaller pass with the
same aim: nowhere shows a person the name a value has in the code. A property's page said "over
principal aquifer" and "elevation ft"; it now says what the core says those fields are called. Three
page introductions that described the file format now describe what the page is for.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected:** AC-24 (the parts of a saved search this interface edits) gains the
  builder as the way criteria are edited. The rule engine's AC-24 (rules round-trip losslessly
  through the browser) is the requirement this whole change has to satisfy and is why the
  translation checks itself rather than trusting itself.
- **Design decisions affected:** none reversed. The interface still holds no business logic: the
  grammar, the composition and the reading are all in `rules/`, and the browser sends and receives
  data.
- **Tasks affected (regenerate these):** the criteria surface. New tasks for the translation, the
  vocabulary's human names, the builder, and the plain-language pass.
- **Already-built code affected:** `rules/namespace.py` (labels), the new `rules/phrase.py`,
  `api.py` (rules in and out), `web/static/search.js`, `web/static/listing.js`,
  `web/static/results.js`, `web/static/searches.js`, `web/static/app.css`.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
