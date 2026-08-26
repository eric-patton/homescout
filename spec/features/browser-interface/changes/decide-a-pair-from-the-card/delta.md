# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

Each acceptance criterion here takes the next stable id when folded into `spec.md`: AC-40 and AC-41.

**User story.** As the person running searches, I want to see both houses on the card, so that the
pairs that are obviously one house take a glance rather than two tabs.

- AC-40: Each queued pair shows, for every record in it, its stored photograph, address, price, size
  and the sources it was seen by. A record with no stored photograph is shown as having none, in the
  same shape as one that has, so the records stay aligned and the absence is legible. Nothing is
  fetched to satisfy this: the images and the summary come from what the store already holds.
- AC-41: The summary a review needs is assembled in the core and read by both surfaces. The terminal
  lists the same addresses, prices and sources for the same pairs, and neither surface works out for
  itself what a pair is.

## MODIFIED

- **AC-12 — what the review queue lists**
  - Was: Ambiguous match pairs are listed with the agreeing and conflicting signals, and a decision
    made here is durable and honored by later runs.
  - Now: the same, and each pair also carries the two properties themselves, so a decision can be
    made from the card. The signals say why the tool could not tell; the properties are what the
    person rules on.

## REMOVED

Nothing.
