"""Recovering the facts a listing site leaves in prose.

Half the columns in the spreadsheet this tool replaces are things no source returns as data: whether
a house is on a well or on the town supply, whether it has refrigerated air or a swamp cooler,
whether the sewer is a pipe or a tank in the yard. They are in the description, and this package
takes them out of it.

Two backends, one vocabulary, and a rule they both obey: **a field the text does not support is
left empty, never guessed** (product invariant 10). The deterministic patterns are always on and
need no configuration, no credential and no network. The model pass is off until a saved search
turns it on, and the tool is complete without it.

What everything else in the product calls is `values_for`, which answers with a value, how it was
determined, and the sentence it came from.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from . import fields as fx
from . import patterns
from .text import Prose
from .text import read as read_prose

__all__ = ["Extracted", "NAMES", "known_values", "read_prose", "values_for"]

NAMES = fx.NAMES

#: How a value was determined, in the order that decides which one wins. A source that supplies one
#: of these directly is believed over anything recovered from prose (AC-4); the model is only ever
#: asked about fields the patterns left empty, so the last two rarely meet at all.
PRECEDENCE: tuple[str, ...] = ("source", "pattern", "model")


@dataclass(frozen=True, slots=True)
class Extracted:
    """One field, as far as anything could determine it.

    An empty `value` with `conflicted` set is a description that said two different things. It is
    reported as empty, because a criterion asking for a well must not fire on a property whose
    description also mentions the town supply, and it keeps both sentences, because "we could not
    tell, and here is why" is the useful form of not knowing.
    """

    field: str
    value: str | None = None
    provenance: str | None = None
    evidence: tuple[str, ...] = ()
    conflicted: bool = False

    @property
    def determined(self) -> bool:
        """Was anything decided? `none` counts: it is knowledge, not an absence."""
        return self.value is not None


@lru_cache(maxsize=8192)
def _recovered(description: str | None) -> Mapping[str, Extracted]:
    """What the patterns make of one description, remembered for as long as this process runs.

    Keyed by the words rather than by the property, which is the same key `extract/cache.py` uses
    for the model and for the same two reasons: two listings carrying identical prose are one
    question, and the same listing read on a hundred consecutive nights is one question asked a
    hundred times. Unlike the model's, this answer is free to compute and expensive only in bulk:
    thirty-four expressions against every sentence of a thousand descriptions is the largest single
    cost in drawing a results table, paid again on every page load.

    There is nothing to invalidate. The patterns are code, so an edit to them is a new process, and
    the key is the whole of the input. The bound is memory, not staleness.

    The answer is shared between callers and must not be modified. Nothing does: `Extracted` is
    frozen and `values_for` below only reads.
    """
    return _from_patterns(read_prose(description))


def _from_patterns(prose: Prose | None) -> dict[str, Extracted]:
    if prose is None:
        return {}
    answers: dict[str, Extracted] = {}
    for name, found in patterns.read(prose).items():
        values = {entry.value for entry in found}
        evidence = tuple(dict.fromkeys(entry.evidence for entry in found))
        if len(values) > 1:
            answers[name] = Extracted(name, None, None, evidence, conflicted=True)
            continue
        answers[name] = Extracted(name, values.pop(), "pattern", evidence)
    return answers


def values_for(
    fields: Any,
    *,
    model: Mapping[str, Extracted] | None = None,
) -> dict[str, Extracted]:
    """Every recoverable field for one property, with how each was determined.

    `fields` is a normalized listing, and is asked first: a source that supplies one of these
    directly is never overwritten by something recovered from prose. No shipped adapter supplies any
    of them today, which is measured rather than assumed, so this path exists for the day one starts
    and is exercised only by its own test.

    Every one of the six names is always present in the answer, so a caller never branches on shape.
    A field nobody determined comes back with a `value` of `None`, which the rule engine reads as
    unknown and therefore as undetermined rather than false (AC-14).
    """
    recovered = _recovered(getattr(fields, "description", None))
    supplied = model or {}

    answers: dict[str, Extracted] = {}
    for name in NAMES:
        given = getattr(fields, name, None)
        if given:
            answers[name] = Extracted(name, str(given), "source")
            continue
        found = recovered.get(name)
        if found is not None and (found.determined or found.conflicted):
            answers[name] = found
            continue
        from_model = supplied.get(name)
        if from_model is not None and from_model.determined:
            answers[name] = from_model
            continue
        answers[name] = Extracted(name)
    return answers


def known_values(found: Mapping[str, Extracted]) -> dict[str, Any]:
    """Just the fields something determined, for handing to the evaluator.

    An undetermined field is left out rather than passed as `None`, because the evaluator treats
    absent as unknown and unknown is exactly what it is. `none` is passed, because a property with
    no natural gas is a property a criterion can ask about.
    """
    return {name: entry.value for name, entry in found.items() if entry.determined}
