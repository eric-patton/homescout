"""Specific houses a saved search asks for by address, beside its areas or instead of them.

An area admits everything inside it and answers the exact test by geometry. A named address admits
exactly one property and answers by address, which is why it is not a seventh kind of area (plan
D-21): folding it into `SearchArea` would give every area a second way to qualify and every geometry
test a case that is not geometry.

What this module owns is the shape of the list in the file and the questions that need only the
search package to answer: where each address is (through the boundary port, never fetching), which
circles to ask for, and in what statuses. Deciding which returned row *is* the named house needs the
address matcher, and lives in the run loop, which already has it (plan D-24).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..sources.base import Capabilities, SearchQuery
from . import geometry as geo
from .areas import SearchArea
from .boundaries import PlacedAddress, boundaries

#: How far around a placed address each source is asked to look. Measured rather than chosen, on
#: eight Louisiana houses on 2026-09-30: the Census put an address 0.02 to 0.07 miles from where the
#: listing sites put the house on ordinary streets, and up to 0.30 miles on numbered highways, where
#: it interpolates along the road and lots are large. The circle only decides what is asked for; the
#: address comparison decides what is kept, so a generous one costs discarded rows and never a wrong
#: property (plan D-23).
RADIUS_MILES = 0.5

#: Longer than any real address, and the text goes into a URL, a cache key and a parser (AC-17).
LONGEST = 200

#: Above this many, validation says what they will cost per run. A notice, never a refusal: "any
#: number" is allowed, and an unannounced nine-hour nightly run is not (AC-17).
MANY = 50

#: What a named house is looked for as, whatever the search's own listing types are, so a house
#: that goes under contract is still seen (AC-18).
STATUSES: tuple[str, ...] = ("for_sale", "pending", "contingent")

#: The parser's labels that begin the part of a one-line address after the street.
_AFTER_STREET = frozenset({"PlaceName", "StateName", "ZipCode", "CountryName"})

_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\s*$")


class AddressError(ValueError):
    """An entry in `addresses` that cannot be read. Reported at its place in the file."""


@dataclass(frozen=True, slots=True)
class NamedAddress:
    """One house a search asks for by name, exactly as the file says it."""

    text: str
    #: Why this house is here, in the person's own words, under the same rules as an area's.
    reason: str | None = None
    #: Where it is, when the person said so. Places the query only: it is never written onto a
    #: listing as that listing's coordinates (product invariant 10).
    at: tuple[float, float] | None = None

    def street(self) -> str:
        """The street part of the line, which is what the address matcher reads."""
        return split(self.text)[0]

    def postal(self) -> str:
        """The ZIP code the person wrote, or nothing."""
        return split(self.text)[1]


@dataclass(frozen=True, slots=True)
class Circle:
    """One place a source is asked about, and every named address it is asked about for."""

    latitude: float
    longitude: float
    miles: float
    members: tuple[NamedAddress, ...]


@dataclass(frozen=True, slots=True)
class AddressQuery:
    """One coarse query sent for named addresses, and which of them it is looking for."""

    query: SearchQuery
    circle: Circle


@dataclass(frozen=True, slots=True)
class AddressPlan:
    """Every named address of one search, placed or not, and the circles to ask for.

    Built once per run, from the boundary port's cache, so a run looks each address up at most once
    whatever the number of sources.
    """

    placed: tuple[tuple[NamedAddress, PlacedAddress], ...] = ()
    unplaced: tuple[NamedAddress, ...] = ()
    circles: tuple[Circle, ...] = ()

    def where(self, address: NamedAddress) -> PlacedAddress | None:
        for named, placed in self.placed:
            if named == address:
                return placed
        return None

    def queries_for(self, capabilities: Capabilities) -> tuple[AddressQuery, ...]:
        """The queries one source is sent for this search's named addresses.

        No filter is ever sent with them: a named house is wanted whatever the search's filters say
        (AC-20). A source that takes a listing status is asked once per status; one that does not
        is asked once and returns whatever it returns, because a source's capabilities say whether
        it takes a status and never which ones (AC-18, plan D-23).
        """
        statuses: tuple[str | None, ...] = (
            STATUSES if "listing_status" in capabilities.applies else (None,)
        )
        made: list[AddressQuery] = []
        for circle in self.circles:
            area = SearchArea(
                kind="radius", centre=(circle.latitude, circle.longitude), miles=circle.miles
            )
            for coarse in area.coarse_for(capabilities):
                for status in statuses:
                    query = (
                        SearchQuery(area=coarse)
                        if status is None
                        else SearchQuery(area=coarse, listing_status=status)
                    )
                    made.append(AddressQuery(query=query, circle=circle))
        return tuple(made)


def split(text: str) -> tuple[str, str]:
    """A one-line address as its street part and its ZIP code.

    `202 Marguerite St, Folsom, LA 70437` is `202 Marguerite St` and `70437`. The parser finds where
    the town begins, which also handles a line written without commas; a line it refuses is cut at
    its first comma instead, which is how every listing site and the Census write one.
    """
    import usaddress

    line = text.strip()
    try:
        tokens = usaddress.parse(line)
    except Exception:  # noqa: BLE001 - a third-party parser on text a person typed
        tokens = []

    street: list[str] = []
    postal = ""
    reached_town = False
    for token, label in tokens:
        if label in _AFTER_STREET:
            reached_town = True
        if label == "ZipCode":
            postal = re.sub(r"[^0-9]", "", token)[:5]
        if not reached_town:
            street.append(token)

    if not tokens or not street:
        street = [line.split(",", 1)[0]]
    if not postal:
        found = _ZIP.search(line)
        postal = found.group(1) if found else ""
    return " ".join(street).strip().rstrip(","), postal


def read(entries: Any) -> tuple[tuple[NamedAddress, ...], list[tuple[tuple[Any, ...], str, str]]]:
    """The `addresses` list, and everything wrong with it, each at its index (AC-15, AC-17).

    Returns the addresses that could be read and a list of `(where, message, severity)`, where
    `where` is the path inside the list. Nothing is looked up: validation never contacts anything.
    """
    found: list[tuple[tuple[Any, ...], str, str]] = []
    if entries is None:
        return (), found
    if isinstance(entries, str) or not isinstance(entries, Sequence):
        found.append(((), "addresses has to be a list of street addresses", "problem"))
        return (), found

    made: list[NamedAddress] = []
    seen: dict[str, int] = {}
    for index, entry in enumerate(entries):
        try:
            address = _entry(entry)
        except AddressError as exc:
            found.append(((index,), str(exc), "problem"))
            continue
        key = _folded(address.text)
        if key in seen:
            found.append(
                (
                    (index,),
                    f"{address.text!r} is already named at entry {seen[key] + 1}, so it is looked "
                    "for once.",
                    "notice",
                )
            )
            continue
        seen[key] = index
        made.append(address)

    if len(made) > MANY:
        found.append(
            (
                (),
                f"{len(made)} named addresses. Each one is asked for separately from every source, "
                f"once per listing status a source takes, so this adds up to {len(made) * 3} "
                "queries to every source on every run, each one paced. The search is valid; it "
                "will just be slow.",
                "notice",
            )
        )
    return tuple(made), found


def _entry(entry: Any) -> NamedAddress:
    if isinstance(entry, str):
        return NamedAddress(text=_text(entry))
    if not isinstance(entry, Mapping):
        raise AddressError(
            "each named address is a line of text, such as "
            '"202 Marguerite St, Folsom, LA 70437", or an entry with an address'
        )
    unknown = [key for key in entry if key not in ("address", "reason", "at")]
    if unknown:
        raise AddressError(
            f"{unknown[0]!r} is not part of a named address. It takes address, reason and at."
        )
    if "address" not in entry:
        raise AddressError("a named address entry needs an address")
    raw = entry.get("address")
    if not isinstance(raw, str):
        raise AddressError("an address has to be text")
    reason = entry.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise AddressError("a named address's reason has to be text")
    return NamedAddress(
        text=_text(raw),
        reason=(reason.strip() or None) if isinstance(reason, str) else None,
        at=_at(entry.get("at")) if "at" in entry else None,
    )


def _text(raw: str) -> str:
    text = " ".join(raw.split())
    if not text:
        raise AddressError("a named address cannot be empty")
    if len(text) > LONGEST:
        raise AddressError(
            f"a named address is {len(text)} characters and the limit is {LONGEST}. It is sent to "
            "the Census to be placed, so it has to be an address rather than a paragraph."
        )
    return text


def _at(value: Any) -> tuple[float, float]:
    """The same check a radius centre gets, and the same message, because it is the same pair."""
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise AddressError("at is a latitude and longitude pair, such as [30.6013, -90.1371]")
    try:
        if any(isinstance(part, bool) for part in value):
            raise TypeError
        latitude, longitude = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        raise AddressError("at has to be two numbers, latitude first") from None
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise AddressError(
            f"at {latitude:g}, {longitude:g} is not a place on earth. It is latitude first, "
            "unlike GeoJSON."
        )
    return (latitude, longitude)


def _folded(text: str) -> str:
    return " ".join(text.casefold().replace(",", " ").split())


def plan(addresses: Sequence[NamedAddress]) -> AddressPlan:
    """Place every named address from what is already known, and group the circles.

    Asks the boundary port's `place_address`, which answers from its cache and never fetches; the
    fetching happened before the run (plan D-22). An `at` in the file is used as written and nothing
    is asked about it.
    """
    if not addresses:
        return AddressPlan()
    provider = boundaries()
    asking = getattr(provider, "place_address", None) if provider is not None else None

    placed: list[tuple[NamedAddress, PlacedAddress]] = []
    unplaced: list[NamedAddress] = []
    for address in addresses:
        if address.at is not None:
            placed.append((address, PlacedAddress(address.at[0], address.at[1])))
            continue
        found = asking(address.text) if asking is not None else None
        if found is None:
            unplaced.append(address)
        else:
            placed.append((address, found))
    return AddressPlan(
        placed=tuple(placed), unplaced=tuple(unplaced), circles=_circles(placed)
    )


def _circles(placed: Sequence[tuple[NamedAddress, PlacedAddress]]) -> tuple[Circle, ...]:
    """One circle per address, and one covering circle for addresses whose circles overlap.

    Taylor Dr and Ditta Dr in Loranger are 0.14 miles apart: asking for each separately is the same
    houses twice, at twice the pacing. Grouped by overlap, then each group asked for as the smallest
    simple circle that contains every member's own circle, so nothing is asked for less widely than
    it would have been alone.
    """
    points = [(placed_at.latitude, placed_at.longitude) for _, placed_at in placed]
    parent = list(range(len(points)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for one in range(len(points)):
        for other in range(one + 1, len(points)):
            if geo.miles_between(points[one], points[other]) <= 2 * RADIUS_MILES:
                parent[root(one)] = root(other)

    groups: dict[int, list[int]] = {}
    for index in range(len(points)):
        groups.setdefault(root(index), []).append(index)

    made: list[Circle] = []
    for members in groups.values():
        latitude = sum(points[i][0] for i in members) / len(members)
        longitude = sum(points[i][1] for i in members) / len(members)
        reach = max(geo.miles_between((latitude, longitude), points[i]) for i in members)
        made.append(
            Circle(
                latitude=latitude,
                longitude=longitude,
                miles=math.ceil((reach + RADIUS_MILES) * 1000) / 1000,
                members=tuple(placed[i][0] for i in members),
            )
        )
    return tuple(made)


__all__ = [
    "LONGEST",
    "MANY",
    "RADIUS_MILES",
    "STATUSES",
    "AddressError",
    "AddressPlan",
    "AddressQuery",
    "Circle",
    "NamedAddress",
    "plan",
    "read",
    "split",
]
