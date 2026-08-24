"""One geographic component of a saved search, in this tool's vocabulary rather than any site's.

An area answers exactly two questions, and the whole feature is built on keeping them apart.

**What can this source be asked for that contains me?** Coarse, always containing, never narrower.
A city asks for that city. A drawn shape asks for a box, or for the places a boundary provider says
it touches, or for a circle around it: whichever of those the source will actually accept.

**Is this property inside me?** Three answers, not two. `unknown` is what a property with no
coordinates gets from a drawn shape, and it travels all the way up to the run's report rather than
being rounded to yes or no.

One area type with a `kind`, rather than six classes, because every area answers the same two
questions and the file's own `type:` key is the discriminator a person reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from ..records import ListingFields
from ..sources.base import AddressRadius as SourceAddressRadius
from ..sources.base import (
    Area,
    BoundingBox,
    Capabilities,
    City,
    County,
    PointRadius,
    PostalCode,
    State,
)
from . import geometry as geo
from .boundaries import boundaries

Verdict = Literal["inside", "outside", "unknown"]
Kind = Literal["polygon", "city", "county", "zip", "state", "radius"]

KINDS: tuple[str, ...] = ("polygon", "city", "county", "zip", "state", "radius")

#: Enough to compare a state written either way. A file saying "New Mexico" and a source saying
#: "NM" are the same state, and treating them as different would quietly place houses nowhere.
_STATE_CODES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


class AreaError(ValueError):
    """An area that cannot be read. Reported against its place in the file, never guessed at."""


def state_code(value: str | None) -> str | None:
    """A two-letter code from either spelling, or None."""
    if not value:
        return None
    text = value.strip()
    if len(text) == 2:
        return text.upper()
    return _STATE_CODES.get(text.casefold())


def _split(value: str) -> tuple[str, str | None]:
    """`"Las Cruces, NM"` becomes the place and its state."""
    place, _, state = value.partition(",")
    return place.strip(), (state.strip() or None)


def _accepts(capabilities: Capabilities, kind: type) -> bool:
    """Does this source take areas of this shape?

    A source that declares no accepted areas takes anything, which is what the source layer's own
    `accepts` already means and what the test fakes rely on.
    """
    return not capabilities.accepts_areas or kind in capabilities.accepts_areas


@dataclass(eq=False)
class SearchArea:
    """One area, or one exclusion, as read from a definition."""

    kind: Kind
    #: A drawn shape's own name, kept through a load, a save and a run (AC-2).
    name: str | None = None
    #: A named place, or the name of a radius's centre, exactly as written in the file.
    value: str | None = None
    shape: Any = None
    prepared: Any = None
    centre: tuple[float, float] | None = None
    miles: float | None = None
    excluded: bool = False
    _boundary: Any = field(default=None, repr=False)
    _boundary_prepared: Any = field(default=None, repr=False)
    _asked: bool = field(default=False, repr=False)
    _lookups: int = field(default=0, repr=False)

    # -- what a person calls it ---------------------------------------------

    def label(self) -> str:
        if self.name:
            return self.name
        if self.kind == "radius":
            return f"{self.miles:g} miles around {self.value or self.centre}"
        return self.value or self.kind

    @property
    def delegated(self) -> bool:
        """Applied by the source and not re-checkable here.

        True only for a radius around a place name with no boundary provider registered to turn
        that name into a point. The circle is sent to the source verbatim and the source applies
        it; this tool has nothing to measure from, so it declines to remove anything on the
        strength of it, and says so as a notice at validation. With a provider registered it
        becomes exact like anything else.
        """
        return self.kind == "radius" and self.centre is None and self._locate() is None

    # -- coarse: what a source can be asked for ------------------------------

    def coarse_for(self, capabilities: Capabilities) -> tuple[Area, ...]:
        """Forms of this area the given source accepts, every one of them containing it."""
        if self.kind == "city":
            place, state = _split(self.value or "")
            return self._named(capabilities, City(place, state))
        if self.kind == "county":
            place, state = _split(self.value or "")
            return self._named(capabilities, County(place.removesuffix(" County"), state))
        if self.kind == "zip":
            return self._named(capabilities, PostalCode(self.value or ""))
        if self.kind == "state":
            return self._named(capabilities, State(self.value or ""))
        if self.kind == "radius":
            return self._radius(capabilities)
        return self._polygon(capabilities)

    def _named(self, capabilities: Capabilities, area: Area) -> tuple[Area, ...]:
        if _accepts(capabilities, type(area)):
            return (area,)
        # A source that takes only a box can still be asked for a named place, if something can say
        # where that place is. Otherwise it is not asked at all, which the run reports.
        boundary = self._shape_of_boundary()
        if boundary is not None and _accepts(capabilities, BoundingBox):
            return (BoundingBox(*geo.box_of(boundary)),)
        return ()

    def _radius(self, capabilities: Capabilities) -> tuple[Area, ...]:
        miles = self.miles or 0.0
        centre = self.centre or self._locate()
        if centre is not None and _accepts(capabilities, PointRadius):
            return (PointRadius(centre[0], centre[1], miles),)
        if self.value and _accepts(capabilities, SourceAddressRadius):
            return (SourceAddressRadius(self.value, miles),)
        if centre is not None and _accepts(capabilities, BoundingBox):
            return (BoundingBox(*_box_around(centre, miles)),)
        return ()

    def _polygon(self, capabilities: Capabilities) -> tuple[Area, ...]:
        """A drawn shape, as something a listing site will take.

        In order of how much of the extra market each one drags in: a box, the named places a
        boundary provider says the shape touches, then a circle around the whole thing. Every one of
        them contains the shape, which is what makes the local test able to remove and never add.
        """
        if self.shape is None:
            return ()
        if _accepts(capabilities, BoundingBox):
            return (BoundingBox(*geo.box_of(self.shape)),)

        places = self._containing()
        if places:
            usable = tuple(area for area in places if _accepts(capabilities, type(area)))
            if usable:
                return usable

        if _accepts(capabilities, PointRadius):
            latitude, longitude, miles = geo.covering_circle(self.shape)
            return (PointRadius(latitude, longitude, miles),)
        return ()

    # -- exact: is this property inside ---------------------------------------

    def holds(self, fields: ListingFields) -> Verdict:
        """Is this property inside this area, as far as anything here can tell?"""
        if self.kind == "polygon":
            return self._inside_shape(self.prepared, fields)
        if self.kind == "radius":
            return self._inside_circle(fields)
        return self._inside_place(fields)

    def _inside_shape(self, prepared: Any, fields: ListingFields) -> Verdict:
        if prepared is None:
            return "unknown"
        if fields.latitude is None or fields.longitude is None:
            return "unknown"
        return "inside" if geo.contains(prepared, fields.latitude, fields.longitude) else "outside"

    def _inside_circle(self, fields: ListingFields) -> Verdict:
        centre = self.centre or self._locate()
        if centre is None:
            # Delegated to the source, which applied it. Nothing here can measure from a name.
            return "inside"
        if fields.latitude is None or fields.longitude is None:
            return "unknown"
        away = geo.miles_between(centre, (fields.latitude, fields.longitude))
        return "inside" if away <= (self.miles or 0.0) else "outside"

    def _inside_place(self, fields: ListingFields) -> Verdict:
        """A named place: its boundary when one can be had, its name when it cannot.

        The textual answer is not a guess. A source that reports a house is in Portales is
        evidence that it is in Portales, and it is the only evidence available until boundary
        lookups exist. It never contradicts coordinates: a boundary is tried first when there is
        one.
        """
        boundary = self._prepared_boundary()
        if boundary is not None and fields.latitude is not None and fields.longitude is not None:
            return self._inside_shape(boundary, fields)

        place, state = _split(self.value or "")
        wanted_state = state_code(state)
        row_state = state_code(fields.state)

        if self.kind == "zip":
            code = (fields.postal_code or "").strip()[:5]
            if not code:
                return "unknown"
            return "inside" if code == place[:5] else "outside"

        if self.kind == "state":
            wanted = state_code(place)
            if row_state is None:
                return "unknown"
            return "inside" if row_state == wanted else "outside"

        found = fields.city if self.kind == "city" else fields.county
        if self.kind == "county":
            place = place.removesuffix(" County")
            found = (found or "").removesuffix(" County") or None
        if not found:
            return "unknown"
        if found.strip().casefold() != place.casefold():
            return "outside"
        if wanted_state and row_state and wanted_state != row_state:
            return "outside"
        return "inside"

    # -- the boundary provider, asked at most once ---------------------------

    def _ask_provider(self) -> None:
        """One lookup per area per loaded definition, whatever happens after.

        A run tests thousands of properties against the same few areas, so asking per property
        would turn one lookup into one per row. Across invocations the provider's own cache
        answers, which is enrichment's job and not this feature's (AC-13).
        """
        if self._asked:
            return
        provider = boundaries()
        if provider is None:
            # Deliberately not remembered. "Nobody can answer this yet" is a fact about the process,
            # not about the area, and caching it would mean an area loaded before enrichment
            # registers a provider stays unresolvable for the life of the definition.
            return
        self._asked = True
        self._lookups += 1
        if self.kind == "radius":
            if self.value:
                self._boundary = provider.locate(self.value)
            return
        found = provider.boundary(self.kind, self.value or "")
        if found is None:
            return
        try:
            self._boundary = geo.to_geometry(found)
        except geo.GeometryError:
            self._boundary = None

    def _locate(self) -> tuple[float, float] | None:
        self._ask_provider()
        return self._boundary if self.kind == "radius" else None

    def _shape_of_boundary(self) -> Any:
        self._ask_provider()
        return None if self.kind == "radius" else self._boundary

    def _prepared_boundary(self) -> Any:
        shape = self._shape_of_boundary()
        if shape is None:
            return None
        if self._boundary_prepared is None:
            self._boundary_prepared = geo.prepare(shape)
        return self._boundary_prepared

    def _containing(self) -> tuple[Area, ...]:
        """The named places a provider says this shape touches, if it can say."""
        provider = boundaries()
        if provider is None or self.shape is None:
            return ()
        containing = getattr(provider, "containing", None)
        if containing is None:
            return ()
        self._lookups += 1
        found = containing(self.shape.__geo_interface__)
        made: list[Area] = []
        for kind, value in found or ():
            place, state = _split(value)
            if kind == "county":
                made.append(County(place.removesuffix(" County"), state))
            elif kind == "city":
                made.append(City(place, state))
            elif kind == "zip":
                made.append(PostalCode(place))
            elif kind == "state":
                made.append(State(place))
        return tuple(made)


def _box_around(centre: tuple[float, float], miles: float) -> tuple[float, float, float, float]:
    """A box containing a circle. Generous on purpose: containing is the requirement."""
    import math

    latitude, longitude = centre
    north_south = miles / 69.0
    scale = max(math.cos(math.radians(latitude)), 0.01)
    east_west = miles / (69.0 * scale)
    return (
        latitude - north_south,
        longitude - east_west,
        latitude + north_south,
        longitude + east_west,
    )


def build(entry: Mapping[str, Any], *, excluded: bool = False) -> SearchArea:
    """One area from one entry in a definition file, or a refusal naming what is wrong."""
    if not isinstance(entry, Mapping):
        raise AreaError("expected an area object with a type")
    kind = entry.get("type")
    if kind not in KINDS:
        known = ", ".join(KINDS)
        raise AreaError(f"unknown area type {kind!r}. Known types: {known}.")

    if kind == "polygon":
        return _polygon_area(entry, excluded=excluded)
    if kind == "radius":
        return _radius_area(entry, excluded=excluded)

    value = entry.get("value")
    if not isinstance(value, str) or not value.strip():
        raise AreaError(f"a {kind} area needs a value, such as {_example(str(kind))}")
    if kind in ("city", "county"):
        _place, state = _split(value)
        if state is None:
            raise AreaError(
                f"{value!r} could be in more than one state, so it is ambiguous. "
                f"Write it with a state, such as {_example(str(kind))}."
            )
        if state_code(state) is None:
            raise AreaError(f"{state!r} is not a state. Use its name or its two-letter code.")
    if kind == "state" and state_code(value) is None:
        raise AreaError(f"{value!r} is not a state. Use its name or its two-letter code.")
    if kind == "zip":
        digits = value.strip()
        if not (digits.isdigit() and len(digits) == 5):
            raise AreaError(f"{value!r} is not a five-digit ZIP code.")
    return SearchArea(kind=kind, value=value.strip(), excluded=excluded)


def _polygon_area(entry: Mapping[str, Any], *, excluded: bool) -> SearchArea:
    name = entry.get("name")
    if name is not None and not isinstance(name, str):
        raise AreaError("a polygon's name has to be text")
    if "geometry" not in entry:
        raise AreaError("a polygon area needs a geometry, as GeoJSON")
    try:
        shape = geo.to_geometry(entry.get("geometry"))
    except geo.GeometryError as exc:
        raise AreaError(str(exc)) from None
    out_of_range = geo.out_of_range(shape)
    if out_of_range:
        raise AreaError(out_of_range)
    invalid = geo.invalidity(shape)
    if invalid:
        raise AreaError(
            f"the shape is not a valid area: {invalid}. "
            "A shape that crosses itself has no inside, so nothing can be tested against it."
        )
    return SearchArea(
        kind="polygon",
        name=name,
        shape=shape,
        prepared=geo.prepare(shape),
        excluded=excluded,
    )


def _radius_area(entry: Mapping[str, Any], *, excluded: bool) -> SearchArea:
    miles = entry.get("miles")
    if not isinstance(miles, int | float) or isinstance(miles, bool) or miles <= 0:
        raise AreaError("a radius area needs a positive number of miles")
    centre = entry.get("center", entry.get("centre"))
    if isinstance(centre, str) and centre.strip():
        return SearchArea(
            kind="radius", value=centre.strip(), miles=float(miles), excluded=excluded
        )
    if isinstance(centre, list | tuple) and len(centre) == 2:
        try:
            latitude, longitude = float(centre[0]), float(centre[1])
        except (TypeError, ValueError):
            raise AreaError("a radius centre given as a pair has to be two numbers") from None
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise AreaError(
                f"a centre of {latitude:g}, {longitude:g} is not a place on earth. "
                "A pair centre is latitude first, unlike GeoJSON."
            )
        return SearchArea(
            kind="radius", centre=(latitude, longitude), miles=float(miles), excluded=excluded
        )
    raise AreaError(
        "a radius area needs a centre: a place name, or a latitude and longitude pair"
    )


def _example(kind: str) -> str:
    return {
        "city": '"Las Cruces, NM"',
        "county": '"Roosevelt County, NM"',
        "zip": '"88130"',
        "state": '"NM"',
    }.get(kind, '"a place"')
