# Proposal — browser-interface

**Trigger:** "Also, if we could somehow add tags or similar - tags we create, beyond just
kept/passed on/not decided."

**Summary.** Keeping and passing answer the tool's own question, which is whether a house is still
in. They are three fixed states about one decision. Everything else somebody wants to say about a
house in one word is theirs and this tool cannot know it in advance: "septic unknown", "drive by on
Saturday", "her favourite", "too close to the highway". A fixed field per idea would be a schema
change per thought.

The store side of this is specified against the listing store, where the person's own data lives.
What belongs here is the control: a cell that opens the list of words already in use, ticked or
not, and one line to make a new one.

Deliberately not a text box that takes a comma-separated list. That is how a vocabulary of eight
words becomes a vocabulary of fourteen, half of them typos of the other half, and nothing on the
page would ever tell you it had happened. The store folds case for the same reason; this is the
half that stops the second spelling being typed at all.

What is sent is the whole list, because that is exactly what a set of ticked boxes is. Sending "add
this, remove that" is how what is shown and what is stored come apart.

## Blast radius

- **One new column in the results table**, filterable by the filter every other column already has,
  because the column shows a comma-joined list and a tag cannot contain a comma.
- **The property's own page shows them and does not set them**, like every other annotation: this
  page is for reading one property, and the table is where a decision is made about it against the
  others.
- **`send` learned a method.** It was POST-only; a whole list replacing a whole list is a PUT.
