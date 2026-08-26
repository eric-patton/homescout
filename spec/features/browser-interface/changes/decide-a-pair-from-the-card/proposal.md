# Proposal — browser-interface

**Trigger:** The person running searches asked for it, in these words: "Can we update the match
review page so that it shows the thumbnail for both homes in the card list? Most of these are the
same house, and that would make it much easier for me than having to click into each link for the
easy ones."

**Summary:** The review queue listed each pair as two truncated identifiers and the signals that
pointed both ways. That is complete evidence about the *match* and no evidence at all about the two
houses, which are what somebody is actually ruling on. Deciding a pair meant opening two tabs,
looking at two photographs, and coming back. Over a queue of a hundred and sixty-six, that is the
difference between a review somebody does and a review somebody abandons.

The card now carries both properties: the photograph first, then the address, the price, the size,
and which sites each record was seen by.

**The photograph is doing most of the work, and the sources are doing the rest.** A record seen by
Realtor and one seen by Zillow, at one address, is the shape of a house observed twice. The first
pair in the real queue is the other shape: `16 Mimbres Rd SW` at $650,000 seen by two sites, against
`16 Mimbres Ct` at $710,000 seen by one. Different street, different price, and no tab needed.

**Nothing new is fetched.** The stored preview images already exist, the endpoint that serves one
already exists, and the summary comes from snapshots the store already holds. This is a change to
what is shown, not to what is collected.

## Blast radius

- **Requirements affected here:** AC-12, which says pairs are listed with the agreeing and
  conflicting signals. It gains the two properties themselves.

- **The core assembles the summary, not the page.** `api.review_queue` is the new operation and
  both surfaces read it, which is non-negotiable 8. The web's `wire.matches` becomes a pass-through,
  which is the correct amount of work for a layer whose whole job is rearranging.

- **The command line shows the same facts.** `matches list` printed a table of identifiers and
  signals; it now prints each pair's addresses, prices and sources. It shows no photographs, because
  a terminal has none, and that is a limit of the medium rather than a capability living on one
  surface only.

- **Code touched:** `api.py` (the new operation), `web/wire.py`, `web/static/matches.js`,
  `web/static/app.css`, `cli/main.py` and `cli/render.py`.

- **A property with no stored photograph** keeps the same shape on the card, so the two sides stay
  aligned and the absence reads as "no photograph" rather than as a broken image. The core says
  whether one exists rather than letting the page find out by requesting it and failing.
