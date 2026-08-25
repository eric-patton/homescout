# Tasks — Description field extraction (feat-009)

`[x]` done · `[ ]` not started · `[~]` in progress · `[-]` n/a · `[H]` needs a human · `[P]` can run
alongside its peers.

## The vocabulary and the prose

- [x] T1: `extract/fields.py`: the six fields, the closed value vocabulary for each, and the import
      check that every one is an `extracted` field in the rule engine's namespace (D-11, AC-2).
- [x] T2: `extract/text.py`: bounding a description to four thousand characters and recording that
      it was cut, splitting it into sentences, and the whitespace-folded comparison the attribution
      check needs (D-7, the long-description edge case).
- [x] T3 [P]: The corpus fixture: real descriptions carrying the target vocabulary, kept verbatim,
      with everything that makes a row a real property replaced, and a README saying which half is
      which (verification approach).

## The deterministic baseline

- [x] T4: `extract/patterns.py`: claims per field, the window, and the three outcomes: a value, the
      known negative `none`, or nothing at all (D-3, AC-1, AC-5, M-5, M-6).
- [x] T5: The `well` discriminator: hyphen, participle, `as well as`, and the noun test (D-4, M-3).
- [x] T6: Conflicts leave the field empty and keep both sentences as evidence (D-5, the conflicting
      values edge case).
- [x] T7 [P]: `tests/test_extract_patterns.py`: every field's vocabulary against real sentences, and
      the trap cases asserted to yield nothing (AC-1, AC-2, AC-5).
- [x] T8 [P]: `tests/test_extract_corpus.py`: the whole corpus through the patterns, asserting the
      measured coverage and that no trap phrase in it produces a value.
- [x] T8b [P]: AC-5's own test, named as such: descriptions that mention none of the six fields,
      asserting every extracted field comes back empty with no provenance (AC-5).

## Provenance and the seam

- [x] T9: `extract/__init__.py`: `values_for`, returning each field with its value, its provenance
      and its evidence, with precedence `source`, `pattern`, `model` (AC-3, AC-4).
- [x] T10: The rule engine's per-property values gain the extracted names, and the namespace's six
      `populated` flags flip to true (D-10, AC-14). Record the change in feat-008's manifest.
- [x] T11 [P]: `tests/test_extract_values.py`: a source-supplied value is not overwritten, an
      unpopulated field is undetermined rather than false, and provenance is on every populated one
      (AC-3, AC-4, AC-14).

## The model pass

- [x] T12: Schema version 6: `extracted_values`, keyed by the description's digest, the model and
      the field name, a cache and not history, with the reason in the schema (D-2). Record the
      change in feat-001's manifest.
- [x] T13: `extract/settings.py`: base address, model name and credential, from the environment or
      the same uncommitted `.env` the digest reads; the loopback rule that decides whether a
      credential is required; and a base URL whose scheme is not http or https refused before a run
      starts (D-6, D-13, AC-8).
- [x] T14: `extract/cache.py`: read and write by digest and model, and an answered-but-empty row
      meaning the model was asked and determined nothing (D-2, AC-10).
- [x] T15: `extract/model.py`: one client over the shared paced session, one request shape, the
      closed-vocabulary validation and the verbatim-quote attribution check (D-6, D-7, D-8, D-13,
      AC-9, AC-12, AC-13).
- [x] T16: `extract/pass_.py`: distinct digests, skip what is cached, ask only about fields the
      patterns left empty, per-description failure that does not end the pass, and the credential
      scrubbed from every recorded detail (D-10, D-13, AC-11).
- [x] T17: The saved search gains `extract: {model: bool}`, absent by default, with a typo in it a
      complaint (D-9, AC-6). Record the change in feat-004's manifest.
- [x] T18: The run loop runs the model pass after the run completes and before the criteria are
      evaluated, when the search enables it, degrading the run rather than failing it (D-10, AC-11).
      Record the change in feat-002's manifest.
- [x] T19: `api.extract` and a `homescout extract` command, with `--search`, `--json` and the usual
      exit codes (AC-6). Record the change in feat-003's manifest.
- [x] T20 [P]: `tests/extract_fakes.py`: a fake OpenAI-compatible server that can be told to answer
      well, badly, unattributably, or not at all.
- [x] T21 [P]: `tests/test_extract_model.py`: both backends through one client, a malformed answer,
      an unattributable answer, a timeout, and the injection case (AC-9, AC-11, AC-12, AC-13).
- [x] T22 [P]: `tests/test_extract_pass.py`: caching by description rather than by property, the
      per-description failure, and the pass report (AC-10, AC-11).
- [x] T23 [P]: `tests/test_extract_privacy.py`: the request body built for a property with a known
      address, price and identifier contains none of them, and a base URL with a refused scheme is
      refused (D-13).
- [x] T24 [P]: `tests/test_extract_absent.py`: every extraction variable stripped, the tool run end
      to end, no request made and no credential read (AC-7).

## Finishing

- [x] T25 [P]: The deterministic pass over 5,000 descriptions, marked slow (performance NFR).
- [x] T26 [P]: `tests/test_extract_live.py`: one description against whatever OpenAI-compatible
      server the environment names, marked slow and skipped without one.
- [x] T27: Document extraction in the README: what the six fields are, that only one source supplies
      prose (M-1), what the measured coverage is, and how to point the model pass at a local server.
- [x] T28: `uv run ruff check .` and the full suite, default and slow, green.
- [x] T29: `/spec-flow:converge`, then the manifest stamp.

## Added while building

- [x] T30: `homescout extract --listing ID`: what was read out of one property, how each value was
      determined, and the sentence it came from. The spec's third user story ("I want to know how
      each value was determined") had no surface without it.

## Change: notes for the model (`changes/model-notes/`)

- [x] T31: `extract/notes.py`: the two notes as one value. Read the installation's `model-notes.md`
      beside the database and a saved search's `extract.notes`, bound each at the length limit,
      report what was truncated, and fingerprint the text that will actually be sent (D-15, D-16,
      AC-15, AC-19).
- [x] T32: `extract/model.py`: `instruction` takes the notes and places them in their own marked
      section after the rules, said to come from the operator rather than the listing, with the
      vocabulary and the quote requirement restated as unchanged by anything in them. With no notes
      the string is what it was (D-13, AC-16, AC-17, AC-20).
- [x] T33: `extract/cache.py` and `extract/pass_.py`: the cache identity becomes the model name plus
      the notes fingerprint, and the pass reads the notes once and carries them (D-16, AC-18).
- [x] T34: The saved search gains `extract: {notes: str}`, absent by default, with a length
      complaint and a typo in the key still a complaint (AC-15). Record the change in feat-004's
      manifest.
- [x] T35: `api.py`: read and write both notes, the installation's through the settings surface and
      the search's through `searches edit`, refusing neither and warning on truncation (AC-15,
      AC-19).
- [x] T36: The browser gains a note box on the settings page and one on the search page, each saying
      plainly that what is written there is sent to the model with every description. Record the
      change in feat-012's manifest.
- [x] T37: The command line reaches both notes: a search's through the `--set extract.notes=...`
      that `searches edit` already has, shown by `searches show`, and the installation's through a
      `homescout notes` command that shows it, writes it and clears it (AC-15). Record the change in
      feat-003's manifest.
- [x] T38 [P]: `tests/test_extract_notes.py`: both notes reach the request, both absent leaves the
      body byte-for-byte unchanged, a note asking for a value outside the vocabulary changes
      nothing, an over-long note is truncated and reported, and a changed note re-asks while an
      unchanged one does not (AC-15, AC-16, AC-17, AC-18, AC-19, AC-20).
- [x] T39 [P]: `tests/test_extract_privacy.py` gains the other direction: no code path writes a
      note, and the name the store records for a cached answer is still the model's name rather
      than the composite key (AC-21).
- [x] T40: `uv run ruff check .` and the full suite green, then `/spec-flow:converge` and the
      manifest stamp.
