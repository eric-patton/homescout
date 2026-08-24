"""What to do about two rows, given everything they say about each other.

One table, and it is the most consequential twenty lines in the feature, so the reasoning is here
rather than inferable.

The spec opens by naming an asymmetry: failing to merge two rows costs a duplicate line in a table,
while wrongly merging them fuses two properties into one record whose price history is fiction. One
of those is a nuisance a person can see; the other is a quiet corruption of the only thing this
whole product is for. So `matched` is narrow, `distinct` is narrow, and everything else that shares
any signal at all falls to `ambiguous` and goes to a person.

A large queue on the first run over a new area is this working, not failing.
"""

from __future__ import annotations

from typing import Literal

from .signals import Candidate, Signals
from .signals import compare as read_signals

Outcome = Literal["matched", "ambiguous", "distinct", "unrelated"]


def decide(signals: Signals) -> Outcome:
    """The outcome, from the signals alone.

    Read the branches in order; the order is the argument.
    """
    # A parcel number is the strongest thing either row carries, and it settles the question in
    # both directions regardless of what the addresses say. Two rows for the same parcel are the
    # same property however differently they are written; two rows for different parcels are not
    # the same property however identically they are written.
    if signals.parcel == "agreed":
        return "matched"
    if signals.parcel == "disagreed":
        return "distinct"

    # Different units of one building are different properties whatever else agrees. This is the
    # only address disagreement that is decisive rather than merely absent evidence.
    if signals.address == "disagreed":
        return "distinct" if _units_differ(signals) else "unrelated"

    if signals.address == "agreed":
        # The strong parts of the address line up. Coordinates then confirm it or contradict it, and
        # a contradiction is a question rather than an answer: an address match with the coordinates
        # a hundred metres apart is exactly what two houses on the same numbered street look like,
        # and exactly what one house geocoded twice looks like too.
        if signals.place == "disagreed":
            return "ambiguous"
        return "matched"

    # No address to compare. Coordinates alone are never enough, because a large parcel's centroid
    # and its neighbour's are metres apart and a subdivision is a hundred identical descriptions.
    if signals.place == "agreed":
        return "ambiguous"
    return "unrelated"


def _units_differ(signals: Signals) -> bool:
    return any("unit designation" in note for note in signals.conflicted)


def outcome_for(
    one: Candidate, other: Candidate, *, limit: float | None = None
) -> tuple[Outcome, Signals]:
    """Compare two rows and say what to do, along with why."""
    signals = read_signals(one, other, limit=limit)
    return decide(signals), signals
