"""What two rows agree about, what they contradict each other on, and what could not be checked.

Three lists rather than a score, because the person who has to settle an ambiguous pair needs to
know *which* things lined up. "Same street number, different town" and "same everything, coordinates
a kilometre apart" are not the same question, and a confidence number tells them apart not at all.

The distinction that does most of the work here is between **disagreed** and **unknown**. Two rows
that both have no unit have not agreed about the unit; they have failed to disagree, which is a
different thing and must not be counted as evidence. Every check below returns one of three answers
for that reason.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Literal

from .address import Address

Verdict = Literal["agreed", "disagreed", "unknown"]

#: How far apart two sources' coordinates for one property may be. The brief's figure, and the
#: corpus supports it: true pairs in it are seven to thirty-eight metres apart, and the one pair
#: that turned out to be two different houses is a hundred and two.
DEFAULT_TOLERANCE_METRES = 50.0
TOLERANCE_VARIABLE = "HOMESCOUT_MERGE_TOLERANCE_METRES"

#: Coordinates that are really a way of saying "we do not know". Null island, and the whole-degree
#: pairs that come out of a truncated value. Treated as absent rather than as a contradiction: one
#: bad coordinate would otherwise make every pair involving that row ambiguous.
_EARTH_RADIUS_METRES = 6_371_000.0


def tolerance() -> float:
    """The coordinate tolerance, configurable, defaulting to the brief's fifty metres."""
    raw = (os.environ.get(TOLERANCE_VARIABLE) or "").strip()
    if not raw:
        return DEFAULT_TOLERANCE_METRES
    try:
        given = float(raw)
    except ValueError:
        return DEFAULT_TOLERANCE_METRES
    return given if given > 0 else DEFAULT_TOLERANCE_METRES


def usable(latitude: float | None, longitude: float | None) -> bool:
    """Is this a coordinate, or is it a way of writing that nobody knows?

    Null island is the classic, and a pair of whole degrees is the other one: a value truncated
    somewhere upstream lands in the middle of a state and looks perfectly plausible.
    """
    if latitude is None or longitude is None:
        return False
    if abs(latitude) < 0.01 and abs(longitude) < 0.01:
        return False
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return False
    return not (float(latitude).is_integer() and float(longitude).is_integer())


def metres_between(
    one: tuple[float, float], other: tuple[float, float]
) -> float:
    """Great-circle distance, which at these scales is the same as any other kind."""
    lat1, lon1, lat2, lon2 = (radians(value) for value in (*one, *other))
    half = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * _EARTH_RADIUS_METRES * asin(sqrt(half))


def normalize_parcel(value: str | None) -> str:
    """A parcel number with its punctuation removed.

    Two counties, and two sources reading one county, write the same parcel with and without
    separators. The spec asks for them to be normalized or treated as unavailable rather than as a
    disagreement, and normalizing is the cheaper of the two.
    """
    if not value:
        return ""
    reduced = re.sub(r"[^0-9a-z]", "", str(value).lower())
    return reduced if len(reduced) >= 4 else ""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One row as the comparison sees it: an address, a place, and whatever else it carried."""

    listing_id: str
    address: Address
    latitude: float | None = None
    longitude: float | None = None
    parcel: str = ""

    @property
    def point(self) -> tuple[float, float] | None:
        if usable(self.latitude, self.longitude):
            return (float(self.latitude), float(self.longitude))  # type: ignore[arg-type]
        return None


@dataclass(frozen=True, slots=True)
class Signals:
    """Everything one comparison found, in the words a person will read.

    `agreed` and `conflicted` are what the review queue shows. They are sentences rather than field
    names on purpose: the queue is read by somebody deciding, not by a program.
    """

    agreed: tuple[str, ...] = ()
    conflicted: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    #: Set when the two carry parcel numbers, which settles everything on its own.
    parcel: Verdict = "unknown"
    #: Whether the strong parts of the address agree: number, street, unit, postal code.
    address: Verdict = "unknown"
    #: Whether the coordinates are within the tolerance.
    place: Verdict = "unknown"
    metres: float | None = None


@dataclass
class _Found:
    agreed: list[str] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)


def _parcels(one: Candidate, other: Candidate, found: _Found) -> Verdict:
    mine, theirs = normalize_parcel(one.parcel), normalize_parcel(other.parcel)
    if not mine or not theirs:
        # Exactly one, or neither. Neither confirms nor rules out, which is the spec's own wording.
        if mine or theirs:
            found.unknown.append("only one of them carries a parcel number")
        return "unknown"
    if mine == theirs:
        found.agreed.append(f"the same parcel number, {one.parcel}")
        return "agreed"
    found.conflicted.append(f"different parcel numbers, {one.parcel} against {other.parcel}")
    return "disagreed"


def _addresses(one: Address, other: Address, found: _Found) -> Verdict:
    """The strong parts, and then the weak ones as corroboration.

    A unit present on both sides and different is the one weak-looking field that is decisive: unit
    four and unit five are two properties whatever else agrees. A unit on one side only is not a
    disagreement, because one source breaking it out and another folding it into the line is the
    ordinary case.
    """
    if one.unit and other.unit and one.unit != other.unit:
        found.conflicted.append(
            f"different unit designations, {one.unit!r} against {other.unit!r}"
        )
        return "disagreed"

    mine, theirs = one.key(), other.key()
    if mine is None or theirs is None:
        found.unknown.append("at least one of them has no street address to compare")
        return "unknown"

    if mine != theirs:
        found.conflicted.append(
            f"different addresses, {one.raw!r} against {other.raw!r}"
        )
        return "disagreed"

    found.agreed.append(f"the same address, {one.raw!r}")
    if one.unit or other.unit:
        found.agreed.append("and the same unit" if one.unit and other.unit else "and one unit")

    # Corroborating, never deciding. Three sources in the corpus disagree about the street type of
    # one house, so a difference here is one fewer agreement rather than a contradiction.
    if one.street_type and other.street_type:
        if one.street_type == other.street_type:
            found.agreed.append(f"the same street type, {one.street_type}")
        else:
            found.unknown.append(
                f"the sources disagree about the street type, "
                f"{one.street_type} against {other.street_type}"
            )
    return "agreed"


def _places(
    one: Candidate, other: Candidate, found: _Found, limit: float
) -> tuple[Verdict, float | None]:
    mine, theirs = one.point, other.point
    if mine is None or theirs is None:
        found.unknown.append("at least one of them has no usable coordinates")
        return "unknown", None
    apart = metres_between(mine, theirs)
    if apart <= limit:
        found.agreed.append(f"coordinates {apart:.0f} m apart, within {limit:.0f} m")
        return "agreed", apart
    found.conflicted.append(
        f"coordinates {apart:.0f} m apart, further than the {limit:.0f} m tolerance"
    )
    return "disagreed", apart


def compare(one: Candidate, other: Candidate, *, limit: float | None = None) -> Signals:
    """Everything two rows say about each other, and nothing about what to do with it."""
    within = tolerance() if limit is None else limit
    found = _Found()
    parcel = _parcels(one, other, found)
    address = _addresses(one.address, other.address, found)
    place, metres = _places(one, other, found, within)
    return Signals(
        agreed=tuple(found.agreed),
        conflicted=tuple(found.conflicted),
        unknown=tuple(found.unknown),
        parcel=parcel,
        address=address,
        place=place,
        metres=metres,
    )
