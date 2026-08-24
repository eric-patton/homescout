"""Everything wrong with a definition, in one pass, each thing located.

Two rules shape this module.

**One pass.** A person fixing a file by hand should learn about all of its problems at once, not one
per attempt. So nothing here raises on the first failure: every rule runs, every complaint is
collected, and a definition that cannot produce a query at all still tells you about its typo in
`sources` on the way past.

**Nothing is contacted.** Validation is what stands between a typo and an hour of throttled
requests, so it may not itself make a request. It reads the file, checks it against the shapes and
the registry, and stops.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import Severity
from . import geometry as geo
from .areas import AreaError, SearchArea
from .areas import build as build_area
from .document import Document

#: What may appear at the top of a definition. A typo in a key is otherwise perfectly silent: the
#: file parses, the filter is never applied, and the results look like the market.
TOP_LEVEL = (
    "name",
    "description",
    "areas",
    "exclude_areas",
    "filters",
    "sources",
    "rules",
    "export",
)

#: Filter names, and the query field each becomes. `lot_acres` is the one that changes units: a file
#: speaks acres because that is how land is sold, and a source speaks square feet.
RANGES: dict[str, tuple[str, str]] = {
    "price": ("price_min", "price_max"),
    "beds": ("beds_min", "beds_max"),
    "baths": ("baths_min", "baths_max"),
    "sqft": ("sqft_min", "sqft_max"),
    "lot_acres": ("lot_sqft_min", "lot_sqft_max"),
    "year_built": ("year_built_min", "year_built_max"),
}

WHOLE_NUMBER = ("price_min", "price_max", "sqft_min", "sqft_max", "year_built_min",
                "year_built_max", "lot_sqft_min", "lot_sqft_max")

FILTERS = (*RANGES, "property_type", "listing_type", "listed_within_days")

#: One acre, in square feet. Exact, and rounded to the nearest whole foot on the way through, so a
#: minimum of one acre is 43,560 and not 43,559.
SQUARE_FEET_PER_ACRE = 43_560

#: What a listing site will say about where a property is in its sale. Sent to the source as
#: written; never applied locally, because a status that just changed is the most interesting thing
#: a run can find.
LISTING_TYPES = ("for_sale", "pending", "contingent", "sold", "off_market")


@dataclass
class Reading:
    """A definition as far as it could be read, and everything wrong with it."""

    name: str = ""
    description: str | None = None
    areas: tuple[SearchArea, ...] = ()
    sources: tuple[str, ...] = ()
    filters: dict[str, Any] = field(default_factory=dict)
    statuses: tuple[str, ...] = ("for_sale",)
    freshness_days: int | None = None
    export_template: str | None = None
    found: list[tuple[str, str, str]] = field(default_factory=list)

    def say(self, location: str, message: str, severity: Severity = "problem") -> None:
        self.found.append((location, message, severity))


def examine(document: Document, *, known_sources: Sequence[str]) -> Reading:
    """Read one definition and say everything that is wrong with it."""
    reading = Reading()
    data = document.data

    for tag, line, column in document.foreign:
        reading.say(
            f"{document.path.name}:{line + 1}:{column + 1}",
            f"the tag {tag.rsplit(':', 1)[-1]!r} asks for an object to be built. A saved search is "
            "data: nothing in it is executed, so this is refused rather than obeyed.",
        )

    unknown = [key for key in data if key not in TOP_LEVEL]
    for key in unknown:
        reading.say(
            document.at(key),
            f"{key!r} is not part of a saved search. Known keys: {', '.join(TOP_LEVEL)}.",
        )

    _name(document, reading)
    _description(document, reading)
    _areas(document, reading)
    _filters(document, reading)
    _sources(document, reading, known_sources)
    _rules_and_export(document, reading)
    _notices(document, reading)
    return reading


def _name(document: Document, reading: Reading) -> None:
    value = document.data.get("name")
    expected = document.path.stem
    if not isinstance(value, str) or not value.strip():
        reading.say(document.at("name"), "a saved search needs a name")
        reading.name = expected
        return
    reading.name = value.strip()
    if reading.name != expected:
        reading.say(
            document.at("name"),
            f"the name {reading.name!r} does not match the file name {document.path.name!r}. "
            "A run is asked for by name and a directory is read by file name, so the two "
            "disagreeing hides one of them.",
        )


def _description(document: Document, reading: Reading) -> None:
    value = document.data.get("description")
    if value is None:
        return
    if not isinstance(value, str):
        reading.say(document.at("description"), "a description has to be text")
        return
    reading.description = value


def _areas(document: Document, reading: Reading) -> None:
    made: list[SearchArea] = []
    for key, excluded in (("areas", False), ("exclude_areas", True)):
        entries = document.data.get(key)
        if entries is None:
            if key == "areas":
                reading.say(document.at(key), "a saved search needs at least one area to search")
            continue
        if isinstance(entries, str) or not isinstance(entries, Sequence):
            reading.say(document.at(key), f"{key} has to be a list of areas")
            continue
        if key == "areas" and not entries:
            reading.say(document.at(key), "a saved search needs at least one area to search")
        for index, entry in enumerate(entries):
            try:
                made.append(build_area(entry, excluded=excluded))
            except AreaError as exc:
                reading.say(document.at(key, index), str(exc))

    reading.areas = tuple(made)


def _filters(document: Document, reading: Reading) -> None:
    filters = document.data.get("filters")
    if filters is None:
        return
    if not isinstance(filters, Mapping):
        reading.say(document.at("filters"), "filters has to be an object")
        return

    for key in filters:
        if key not in FILTERS:
            reading.say(
                document.at("filters", key),
                f"{key!r} is not a filter. Known filters: {', '.join(FILTERS)}.",
            )

    for name, (low, high) in RANGES.items():
        bounds = filters.get(name)
        if bounds is None:
            continue
        if not isinstance(bounds, Mapping):
            reading.say(
                document.at("filters", name), f"{name} has to be written as a min, a max, or both"
            )
            continue
        extra = [k for k in bounds if k not in ("min", "max")]
        for key in extra:
            reading.say(document.at("filters", name, key), f"{name} takes only min and max")
        values: dict[str, float] = {}
        for bound, target in (("min", low), ("max", high)):
            raw = bounds.get(bound)
            if raw is None:
                continue
            if not isinstance(raw, int | float) or isinstance(raw, bool):
                reading.say(
                    document.at("filters", name, bound), f"{name} {bound} has to be a number"
                )
                continue
            values[bound] = float(raw)
            reading.filters[target] = _as_query_value(name, target, float(raw))
        if "min" in values and "max" in values and values["min"] > values["max"]:
            reading.say(
                document.at("filters", name, "min"),
                f"{name} min of {values['min']:g} is above its max of {values['max']:g}, "
                "so nothing can match it",
            )

    _list_filter(document, reading, filters, "property_type", None)
    _list_filter(document, reading, filters, "listing_type", LISTING_TYPES)
    _freshness(document, reading, filters)


def _as_query_value(name: str, target: str, raw: float) -> Any:
    if name == "lot_acres":
        return int(round(raw * SQUARE_FEET_PER_ACRE))
    return int(round(raw)) if target in WHOLE_NUMBER else raw


def _list_filter(
    document: Document,
    reading: Reading,
    filters: Mapping[str, Any],
    key: str,
    known: Sequence[str] | None,
) -> None:
    values = filters.get(key)
    if values is None:
        return
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Sequence):
        reading.say(document.at("filters", key), f"{key} has to be a list")
        return
    kept: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            reading.say(document.at("filters", key, index), f"every {key} has to be text")
            continue
        if known is not None and value not in known:
            reading.say(
                document.at("filters", key, index),
                f"{value!r} is not a listing type. Known types: {', '.join(known)}.",
            )
            continue
        kept.append(value.strip())
    if key == "property_type":
        if kept:
            reading.filters["property_types"] = tuple(kept)
    elif kept:
        reading.statuses = tuple(kept)


def _freshness(document: Document, reading: Reading, filters: Mapping[str, Any]) -> None:
    """The one filter that is never sent anywhere and never removes a row from a run.

    Freshness in this tool is the tool's own first observation (product invariant 7). Pushing this
    to a source would stop it returning older properties, and the store would read the gap as
    houses that may have sold; applying it during a run would drop the row before it was recorded
    and do exactly the same damage. So it is carried here, and asked when results are read.
    """
    value = filters.get("listed_within_days")
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        reading.say(
            document.at("filters", "listed_within_days"),
            "listed_within_days has to be a whole number of days above zero",
        )
        return
    reading.freshness_days = value


def _sources(document: Document, reading: Reading, known: Sequence[str]) -> None:
    values = document.data.get("sources")
    if values is None or (isinstance(values, Sequence) and not isinstance(values, str)
                          and len(values) == 0):
        reading.say(document.at("sources"), "a saved search needs at least one source")
        return
    if isinstance(values, str) or not isinstance(values, Sequence):
        reading.say(document.at("sources"), "sources has to be a list of source names")
        return
    kept: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            reading.say(document.at("sources", index), "every source has to be named as text")
            continue
        name = value.strip()
        if known and name not in known:
            reading.say(
                document.at("sources", index),
                f"there is no source named {name!r}. Known sources: {', '.join(known)}.",
            )
            continue
        kept.append(name)
    reading.sources = tuple(kept)


def _rules_and_export(document: Document, reading: Reading) -> None:
    """Two sections this feature carries and does not read.

    Rules belong to the rule engine and export templates to the spreadsheet export. Checking their
    shape here keeps a list from being written as a string; checking their contents would put two
    features' knowledge in one place.
    """
    rules = document.data.get("rules")
    if rules is not None and (isinstance(rules, str) or not isinstance(rules, Sequence)):
        reading.say(document.at("rules"), "rules has to be a list")

    export = document.data.get("export")
    if export is None:
        return
    if not isinstance(export, Mapping):
        reading.say(document.at("export"), "export has to be an object")
        return
    template = export.get("template")
    if template is not None and not isinstance(template, str):
        reading.say(document.at("export", "template"), "an export template is named with text")
        return
    reading.export_template = template


def _notices(document: Document, reading: Reading) -> None:
    """Things worth saying that do not make a definition invalid."""
    for index, area in enumerate(reading.areas):
        if area.delegated:
            reading.say(
                document.at("exclude_areas" if area.excluded else "areas", index),
                f"the radius around {area.value!r} is applied by each source and cannot be "
                "re-checked here, because nothing is registered that can turn a place name into a "
                "point. Properties that came back from it are kept as the source sent them.",
                severity="notice",
            )

    wanted = [a.shape for a in reading.areas if not a.excluded and a.shape is not None]
    excluded = [a.shape for a in reading.areas if a.excluded and a.shape is not None]
    every_area_drawn = wanted and len(wanted) == len([a for a in reading.areas if not a.excluded])
    if every_area_drawn and excluded and geo.covers(geo.union(excluded), geo.union(wanted)):
        reading.say(
            document.at("exclude_areas"),
            "the exclusions cover every area this search looks in, so it matches nothing. "
            "The search is valid; it just cannot return a property.",
            severity="notice",
        )
