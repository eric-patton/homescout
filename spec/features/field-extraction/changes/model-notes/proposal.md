# Proposal — field-extraction

**Trigger:** The person running searches asked for it, in these words: "is there any way for us to
have an overall search 'prompt' globally and per search that we can feed to the AI for when it is
reviewing things and pulling fields out? That way, in natural language, we could say our preferences
to help it when it is looking at the houses."

**Summary:** The model pass currently reads one description and one generated instruction, and the
instruction is built entirely from the field vocabulary. Nothing a person knows about the market
they are searching can reach it. That is fine for "does this description say septic" and poor for
the cases that actually go wrong here: in eastern New Mexico "community water" is a mutual domestic
water association rather than a city main, and a description that says it is describing a shared
system rather than city water. The person searching knows that. The model does not, and there is no
way to tell it. This change adds a note in plain language, one for the whole installation and one
per saved search, folded into the instruction the model already receives. It is a hint about how to
read a description. It is not a new field, not a new value, and not a way to ask for a different
answer: everything the model returns is still checked against the closed vocabulary and still has to
be quoted from the description, and those two checks are what stop a note from being able to do any
harm.

The change also settles a question the existing design would otherwise get wrong. Answers are cached
against the description text, so a note that changed after an answer was cached would be silently
ignored for every description already seen, which is the whole corpus. The cache identity has to
include the notes or editing one does nothing visible.

## Blast radius

Everything this change touches, so the ripple is explicit.

- **Requirements affected:** AC-10 (a description is processed once) gains a second dimension: the
  cache is per description *and* per note. AC-13 (a value must be attributable to the text) is
  unchanged and is the load-bearing guarantee that makes this safe. The design note in `model.py`
  that reads "Only the description leaves this machine" becomes untrue as written and has to be
  restated: the operator's own note leaves too, deliberately, and nothing else changes.
- **Design decisions affected:** D-13, whose enforcement is structural (`body_for` takes a string
  rather than a property, so there is no address in scope to send). That stays exactly as it is: the
  note is a second string, passed in the same way, and no listing field becomes reachable.
- **Tasks affected (regenerate these):** the model-pass tasks in `tasks.md`. New tasks for the note
  source, the request, the cache identity, the saved-search key, and both interfaces.
- **Already-built code affected:** `extract/model.py` (`instruction`, `body_for`, `ask`),
  `extract/pass_.py` (reads the notes, passes them, keys the cache), `extract/settings.py` (where the
  global note lives), `search/validate.py` and `search/definition.py` (the `extract.notes` key),
  `api.py` (reading and writing both notes), the browser's search and settings pages, and the
  command line's `searches edit`.

## Status

- [x] delta reviewed (analyze)
- [x] implemented & verified
- [x] folded into spec.md
