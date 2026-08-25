"""What a model has already said, keyed by the words it said it about.

The key is the description and the notes, not the property. The notes travel inside the model
name (`extract/notes.py`, D-16): a model with no note written for it is cached under its own name,
and one with a note is cached under its name plus a short fingerprint of the note. That is what
makes editing a note take effect. Without it the edit would change nothing for every description
already answered, which after the first pass is all of them.

The key is the description, not the property. Two listings carrying identical prose, and the same
listing seen on a hundred consecutive nights, are one question and are paid for once. That is AC-10
in one sentence, and it is why this module exists rather than the pass simply asking every time.

Three states, and only two of them are here. A digest this model has answered is a row, and the row
may carry a value or may carry none, which means it was asked and determined nothing. A digest with
no rows was never asked, which is not an answer and must never read as one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..store import Store
from . import Extracted


def read(
    store: Store, model: str, digests: Sequence[str], *, any_notes: bool = False
) -> dict[str, dict[str, Extracted]]:
    """Everything this model has said about these descriptions, in one query.

    Only fields with a value come back as `Extracted`. A row with no value is an answered nothing:
    it stops the pass asking again, and it is deliberately not returned as a value, because there
    is no value to return.

    `any_notes` is for everything that displays a value: it wants the most recent thing this model
    said, whichever note was in force at the time. The pass leaves it off, because it is asking
    whether this exact question has been answered.
    """
    held = store.extractions(model, list(digests), any_notes=any_notes)
    found: dict[str, dict[str, Extracted]] = {}
    for digest, entries in held.items():
        answers: dict[str, Extracted] = {}
        for name, (value, evidence) in entries.items():
            if value is None:
                continue
            answers[name] = Extracted(
                name, value, "model", (evidence,) if evidence else ()
            )
        found[digest] = answers
    return found


def answered(store: Store, model: str, digests: Sequence[str]) -> dict[str, frozenset[str]]:
    """Which fields this model has already been asked about, per description.

    Distinct from `read`, and the distinction is the point: a field answered with nothing is in here
    and is not in there. Asking again would cost a request to be told the same nothing.
    """
    held = store.extractions(model, list(digests))
    return {digest: frozenset(entries) for digest, entries in held.items()}


def write(
    store: Store,
    model: str,
    digest: str,
    *,
    values: Mapping[str, tuple[str, str]],
    undetermined: Sequence[str],
) -> None:
    """Record one description's answers, including the ones that were nothing.

    The nothings matter as much as the values. Without them a description the model has already
    considered and had no opinion about would be re-asked on every run forever, which is precisely
    the cost AC-10 exists to prevent.
    """
    rows: dict[str, tuple[str | None, str | None]] = {
        name: (value, evidence) for name, (value, evidence) in values.items()
    }
    for name in undetermined:
        rows.setdefault(name, (None, None))
    store.record_extractions(digest, model, rows)
