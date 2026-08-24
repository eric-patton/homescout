"""Which pairs are worth comparing at all.

The performance requirement says a run of five thousand rows must not be compared against every
other row, and it is right to say so: five thousand rows is twelve and a half million pairs, and
almost all of them are a house in one part of town against a house in another.

So rows go into buckets and only rows sharing a bucket are compared. Two kinds of bucket, because
one is not enough:

- **the address key**, which catches everything with a street address, including the pairs whose
  street type or directional the sources disagree about, because the key deliberately leaves those
  out;
- **a rounded coordinate cell**, which catches what an address key cannot: land with no address at
  all, and the pairs where one source spelled the street differently enough that the keys part.

A row goes in both when it has both. The work is then bounded by how many rows share a bucket, which
in a real town is two or three.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

from .signals import Candidate

#: Three decimal places, about a hundred and ten metres of latitude. Comfortably wider than the
#: fifty-metre tolerance, so a true pair is never split across cells by rounding alone, and narrow
#: enough that a cell holds a street rather than a town.
CELL_DECIMALS = 3


def cells(candidate: Candidate) -> tuple[str, ...]:
    """Which coordinate cells this row belongs to.

    Four of them, not one: the cell it rounds into and its three neighbours towards the rounding
    boundary. A pair thirty metres apart can round into different cells when the boundary runs
    between them, and a bucket that loses a true pair is worse than one that costs a comparison.
    """
    point = candidate.point
    if point is None:
        return ()
    latitude, longitude = point
    step = 10.0**-CELL_DECIMALS
    found = set()
    for down in (0.0, -step / 2):
        for left in (0.0, -step / 2):
            found.add(
                f"{round(latitude + down, CELL_DECIMALS):.{CELL_DECIMALS}f}"
                f",{round(longitude + left, CELL_DECIMALS):.{CELL_DECIMALS}f}"
            )
    return tuple(sorted(found))


def buckets(candidates: Iterable[Candidate]) -> dict[str, list[Candidate]]:
    """Every row filed under every key it shares with anything else."""
    found: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        keys = []
        address = candidate.address.key()
        if address is not None:
            keys.append(f"a:{address}")
        keys.extend(f"c:{cell}" for cell in cells(candidate))
        for key in keys:
            found.setdefault(key, []).append(candidate)
    return found


def pairs(candidates: Iterable[Candidate]) -> list[tuple[Candidate, Candidate]]:
    """Every pair worth comparing, each one once, in a stable order.

    Stable because the merge has to be order-independent, and the cheapest way to get that is to
    stop the order varying in the first place. Sorted by listing id, which is the only identifier
    that does not depend on what a source happened to return first.
    """
    held = {candidate.listing_id: candidate for candidate in candidates}
    seen: set[tuple[str, str]] = set()
    for bucket in buckets(held.values()).values():
        if len(bucket) < 2:
            continue
        identifiers = sorted({candidate.listing_id for candidate in bucket})
        seen.update(combinations(identifiers, 2))
    return [(held[one], held[other]) for one, other in sorted(seen)]
