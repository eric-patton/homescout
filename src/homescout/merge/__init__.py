"""Deciding when two rows describe one property, and asking when it is not obvious.

The brief calls this the messiest part of the project and the reason is an asymmetry worth keeping
in mind while reading any of it: failing to merge two rows costs a duplicate line in a table, while
wrongly merging them fuses two properties into one record whose price history is fiction. Everything
here follows from taking that seriously. Merge where the evidence is strong, ask where it is not,
keep the source rows underneath so any decision can be inspected and undone, and never overrule a
person.

Nothing in this package destroys anything. Merging is the store's `supersede`, which writes a new
record over the old ones and leaves them exactly where they were, which is why undoing a merge
recovers rather than reconstructs, and why a person's annotations survive both.
"""

from .address import Address, of, parse
from .compare import Outcome, decide, outcome_for
from .signals import (
    DEFAULT_TOLERANCE_METRES,
    Candidate,
    Signals,
    metres_between,
    normalize_parcel,
    tolerance,
    usable,
)

__all__ = [
    "DEFAULT_TOLERANCE_METRES",
    "Address",
    "Candidate",
    "Outcome",
    "Signals",
    "decide",
    "metres_between",
    "normalize_parcel",
    "of",
    "outcome_for",
    "parse",
    "tolerance",
    "usable",
]
