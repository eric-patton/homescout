# Delta — browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

New requirements, written as full spec requirements. Each acceptance criterion here takes the next
stable id when folded into `spec.md`: AC-28 through AC-32.

**Vocabulary.** A **condition** is one row of a criterion: a field, a comparison, and a value. A
criterion is one or more conditions joined by *and also* or *or else*, plus a name and what firing
does.

**User story.** As the person running searches, who does not write software, I want to build a
criterion by choosing from lists, so that I can say what matters to me without learning a syntax and
without discovering a month later that a criterion I wrote was never true.

- AC-28: A criterion is built by choosing, not by typing an expression. Its field, its comparison and
  its value are each chosen from what is possible, conditions can be added and removed, and criteria
  can be added and removed.
- AC-29: What a value may be follows the field that was chosen. A field with a closed set of values
  offers exactly that set; a number offers a number; a true-or-false offers yes and no. A comparison
  that cannot apply to the chosen field is not offered.
- AC-30: Nothing on any screen shows a person the name a field has in the code. Every field, value,
  comparison and severity is shown in words chosen for a reader, and those words are declared once in
  the core rather than in a surface.
- AC-31: A criterion that cannot be shown as conditions is shown as the expression it is, marked as
  such, and is not rewritten. Saving the other criteria leaves it exactly as written.
- AC-32: The interface offers a set of ready-made criteria that are one click to add and ordinary to
  edit or remove afterwards, so that the first criterion somebody has is not one they had to invent.

## MODIFIED

- **AC-24 — the parts of a saved search this interface edits**
  - Was: The parts of a saved search this interface edits (its description, its sources, its
    filters, whether a model reads its descriptions, and its criteria) are editable here, and AC-3's
    guarantee holds for every edit made through them.
  - Now: The parts of a saved search this interface edits (its description, its sources, its
    filters, whether a model reads its descriptions, and its criteria) are editable here, and AC-3's
    guarantee holds for every edit made through them. A criterion is sent as the conditions a person
    chose, and the expression is composed by the rule engine rather than by the interface, so the
    grammar has one home and the file gets the same line somebody would have typed.

- **Edge case — a filter is cleared**
  - Was: not stated.
  - Now: Clearing a filter removes it from the file rather than leaving an empty key behind, and a
    field left untouched is not written at all. A page that saved on every blur wrote a file nobody
    had edited.

## REMOVED

- The criteria textarea, in which a criterion was a line of `id | severity | expression` — replaced
  by AC-28. Editing a saved search's criteria by hand in the file is unchanged and remains
  supported, which is what AC-31 protects.
