# Delta — field-extraction

> The change expressed against the current spec as explicit operations.

## ADDED

New requirements, written as full spec requirements. Each acceptance criterion here takes the next
stable id when folded into `spec.md`: AC-15 through AC-20.

**Vocabulary.** A **note for the model** is a short piece of writing by the person running searches,
in their own words, describing how descriptions in their market should be read. There are two: one
for the installation and one per saved search. Both are optional and both are absent by default.

**User story.** As the person running searches, I want to tell the model in plain language what I
know about how listings in my market are written, so that it reads "community water" the way
everybody here means it rather than the way the words look.

**User story.** As the person running searches, I want the note I wrote to take effect on the next
pass, so that editing it is not silently cancelled by an answer cached under the old one.

- AC-15: A note for the model can be written for the installation and for each saved search, both
  optional, both absent by default, and both in plain language rather than a format.
- AC-16: When either note is present it is included in the model request, in the instruction rather
  than in the description, and marked as coming from the operator rather than from the listing.
  When both are present both are included, the installation's first.
- AC-17: A note cannot widen the answer. The field vocabulary, the closed set of values, and the
  requirement that every value be quoted from the description are unchanged by any note, and a note
  asking for a value outside the vocabulary or for a field that does not exist changes nothing about
  what is accepted.
- AC-18: The cached answer for a description is identified by the notes in force when it was
  produced, so editing either note causes the next pass to ask again rather than reusing an answer
  given under different instructions. Answers cached under a previous note are kept, not rewritten.
- AC-19: Each note is bounded at 2,000 characters. A note longer than that is truncated before the
  request and the truncation is reported to the person who wrote it, rather than being sent whole or
  silently cut.
- AC-20: With no note written anywhere, the request is identical to what it was before this
  capability existed. A test asserts the request body is byte-for-byte unchanged, so a person who
  does not use this pays nothing for it.
- AC-21: A note is written by a person and never by the tool. Nothing read from a listing, a source,
  or a run is ever placed in a note by any code path, and both places a note can be written say
  before it is written that its text is sent to the model with every description, so a person never
  discovers after the fact where their words went.

## MODIFIED

- **AC-10 — a description is processed at most once**
  - Was: Model results are cached against the description content, so identical description text is
    never processed twice regardless of how many properties or runs contain it.
  - Now: Model results are cached against the description content together with the notes in force,
    so identical description text under unchanged notes is never processed twice regardless of how
    many properties or runs contain it.

- **Edge case — a description contains text that reads like an instruction**
  - Was: It is data. Nothing in a description can change what the extraction is asked to do or cause
    any action outside producing field values.
  - Now: It is data. Nothing in a description can change what the extraction is asked to do or cause
    any action outside producing field values. The operator's note is the one piece of writing that
    is an instruction, because a person wrote it deliberately on this machine; it is carried in the
    instruction rather than in the description, and it is subject to the same closed vocabulary and
    the same quote requirement as everything else, so the worst it can do is make the model wrong in
    the ordinary way.

- **What leaves this machine (design note D-13, stated in `model.py`)**
  - Was: Only the description leaves this machine. The request body carries the instruction, the
    field vocabulary and the prose, and carries no address, no coordinates, no price, no listing
    identifier, no search name and no path.
  - Now: The description and the operator's own notes leave this machine, and nothing else. The
    request body still carries no address, no coordinates, no price, no listing identifier, no
    search name and no path, and the enforcement is unchanged and structural: the function that
    builds a request takes strings rather than a property, so there is nothing for the private parts
    of a listing to leak through even by accident. What is new is that one of those strings was
    written by the person running the searches, who is told plainly where it goes.

## REMOVED

Nothing. This change adds an optional input and tightens a cache identity; it removes no
requirement.
