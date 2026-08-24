"""Every column a template may name, and where each one gets its value.

One table, and the writer walks it. Nothing downstream of this module knows a column name, which is
what makes adding or reordering columns a configuration change rather than a code change, and what
lets a template naming `Wells` be refused before a single row is built.

Each column also declares its **origin**, which is not decoration. Eleven of the thirty-two default
columns come out blank on a fresh store, for three completely different reasons. Telling somebody
which one applies, "run `homescout enrich`" or "write some notes" or "no free national source
supplies this", is the difference between a useful sheet and an afternoon spent looking for a bug
in this tool.

Five of the defaults are `unfilled` and always will be. They stay in the set because the sheet has
to stay recognizable as the one somebody has been keeping by hand, and because they are columns that
person writes their own notes in. Nothing here writes a machine's opinion into one of those.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import Literal as Only

from .rows import Row

Kind = Only["text", "number"]

#: Where a column's value comes from, and therefore what an empty one means.
#:
#: `listing` a source reported it · `derived` this tool computed it · `extracted` recovered from
#: prose · `enriched` public data about the location · `annotation` the person wrote it ·
#: `unfilled` nothing in this product ever fills it.
Origin = Only["listing", "derived", "extracted", "enriched", "annotation", "unfilled"]

#: What an empty column of each kind means, in words a person can act on.
WHY_EMPTY: dict[str, str] = {
    "extracted": "no listing description said so",
    "enriched": "the enrichment pass has not been run for these properties",
    "annotation": "nothing has been written about these properties yet",
    "unfilled": "nothing in this tool fills them; they are yours to write in",
}


@dataclass(frozen=True, slots=True)
class Column:
    """One column: what it is called, what kind of thing it holds, and how a row answers it."""

    name: str
    kind: Kind
    origin: Origin
    read: Callable[[Row], Any]
    #: Set on the one column whose cell is a link rather than only text.
    links: bool = False

    def value(self, row: Row) -> Any:
        """This column's value for this row, or `None` when nothing determined it.

        `None` and only `None` becomes an empty cell. A column never substitutes a default, a zero
        or a placeholder, which is product invariant 10 arriving at the last surface that could
        break it.
        """
        return self.read(row)


# ---------------------------------------------------------------------------
# The readers
# ---------------------------------------------------------------------------


def _listing(name: str) -> Callable[[Row], Any]:
    return lambda row: getattr(row.fields, name, None)


def _annotated(name: str) -> Callable[[Row], Any]:
    return lambda row: getattr(row.annotation, name, None) if row.annotation else None


def _extracted(name: str) -> Callable[[Row], Any]:
    def read(row: Row) -> Any:
        found = row.extracted.get(name)
        return found.value if found is not None else None

    return read


def _enriched(name: str) -> Callable[[Row], Any]:
    return lambda row: row.enriched.get(name)


def _nothing(row: Row) -> None:
    """A column no part of this product fills. Always empty, deliberately, and reported as such."""
    return None


def _status(row: Row) -> str | None:
    """What the listing says, and what this tool observed, told apart.

    A property nobody has seen for a while is `disappeared` here rather than `sold`, because absence
    is not evidence and this sheet is not the place to start guessing.
    """
    said = row.fields.listing_status
    if row.presence == "disappeared":
        return f"{said} (disappeared)" if said else "disappeared"
    return said


def _address(row: Row) -> str | None:
    from ..digest import address_of

    line = address_of(
        {
            "address_line": row.fields.address_line,
            "unit": row.fields.unit,
            "city": row.fields.city,
            "state": row.fields.state,
            "postal_code": row.fields.postal_code,
        }
    )
    return line or None


def _price_per_sqft(row: Row) -> float | None:
    """Empty when either input is, rather than zero.

    The spec's own edge case: a property whose price is unknown has an empty price cell and an empty
    price-per-square-foot cell. Zero is a number somebody can sort by, and sorting a market by a
    price nobody knows puts the unknowns at the top.
    """
    price, sqft = row.fields.price, row.fields.sqft
    if not price or not sqft:
        return None
    return round(price / sqft, 2)


def _acres(row: Row) -> float | None:
    """Square feet as the sources report them, acres as land is actually sold."""
    from ..search.validate import SQUARE_FEET_PER_ACRE

    lot = row.fields.lot_sqft
    return round(lot / SQUARE_FEET_PER_ACRE, 2) if lot else None


def _price_history(row: Row) -> str | None:
    """The price movements this tool observed, and its own days on market.

    Its own, never the site's. A source's claim about time on market is recorded and never believed
    (product invariant 7), so this column is counted from this tool's own first sighting.
    """
    prices = [entry.price for entry in row.history.prices if entry.price is not None]
    days = row.history.days_on_market
    parts: list[str] = []
    if len(prices) > 1 and prices[0] != prices[-1]:
        direction = "down" if prices[-1] < prices[0] else "up"
        parts.append(f"{prices[0]:,} to {prices[-1]:,} ({direction})")
    elif prices:
        parts.append("no change")
    if days is not None:
        parts.append(f"{days} days")
    return ", ".join(parts) or None


def _hvac(row: Row) -> str | None:
    """Heating and cooling in one cell, because the hand-built sheet has one column for both."""
    heating = _extracted("heating")(row)
    cooling = _extracted("cooling")(row)
    parts = [f"heat: {heating}" if heating else "", f"cool: {cooling}" if cooling else ""]
    return ", ".join(part for part in parts if part) or None


def _internet(row: Row) -> str | None:
    down = row.enriched.get("download_mbps")
    up = row.enriched.get("upload_mbps")
    who = row.enriched.get("broadband_provider")
    if down is None and up is None and not who:
        return None
    speed = f"{down or '?'}/{up or '?'} Mbps"
    return f"{who}, {speed}" if who else speed


def _aquifer(row: Row) -> str | None:
    """Yes or no as words, because a spreadsheet column of TRUE and FALSE reads as a bug."""
    over = row.enriched.get("over_principal_aquifer")
    if over is None:
        return None
    return "over a principal aquifer" if over else "not over a principal aquifer"


def _town_notes(row: Row) -> str | None:
    """What the person has written about this property's town, carried onto its row.

    The same note appears on every property in that town, which is the point: the sheet is sorted
    and filtered by whoever opens it, and a note that only exists on the second sheet is a note
    nobody sees while looking at a row.
    """
    city = (row.fields.city or "").strip()
    if not city:
        return None
    return row.area_notes.get(("city", city)) or row.area_notes.get(("city", city.casefold()))


def _flags(row: Row) -> str | None:
    return ", ".join(row.flags) or None


def _sources(row: Row) -> str | None:
    return ", ".join(row.sources) or None


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

COLUMNS: tuple[Column, ...] = (
    Column("Rank", "number", "annotation", _annotated("rank")),
    Column("Status", "text", "derived", _status),
    Column("Property", "text", "listing", _address, links=True),
    Column("Town/Area", "text", "listing", _listing("city")),
    Column("County/Region", "text", "listing", _listing("county")),
    Column("Price", "number", "listing", _listing("price")),
    Column("$/sq ft", "number", "derived", _price_per_sqft),
    Column("Price History & DOM", "text", "derived", _price_history),
    Column("Beds", "number", "listing", _listing("beds")),
    Column("Baths", "number", "listing", _listing("baths")),
    Column("Sq Ft", "number", "listing", _listing("sqft")),
    Column("Year Built", "number", "listing", _listing("year_built")),
    Column("Acres", "number", "derived", _acres),
    Column("Construction/Roof/Features", "text", "extracted", _extracted("roof")),
    Column("Garage/Outbuildings", "text", "unfilled", _nothing),
    Column("HVAC/Heat", "text", "extracted", _hvac),
    Column("Water Source", "text", "extracted", _extracted("water_source")),
    Column("Sewer/Septic", "text", "extracted", _extracted("sewer")),
    Column("Gas", "text", "extracted", _extracted("gas")),
    Column("FEMA Flood Zone", "text", "enriched", _enriched("flood_zone")),
    Column("Internet", "text", "enriched", _internet),
    Column("Principal Aquifer", "text", "enriched", _aquifer),
    Column("Annual Taxes", "number", "unfilled", _nothing),
    Column("Crime/Safety", "text", "unfilled", _nothing),
    Column("Fire/Egress/Terrain", "text", "unfilled", _nothing),
    Column("Sewage & Reclaimed-Water Exposure", "text", "unfilled", _nothing),
    Column("Town Analysis Notes", "text", "annotation", _town_notes),
    Column("Red Flags", "text", "annotation", _annotated("red_flags")),
    Column("Summary", "text", "annotation", _annotated("summary")),
    Column("Verdict", "text", "annotation", _annotated("verdict")),
    Column("Next Step", "text", "annotation", _annotated("next_step")),
    Column("Listing URL", "text", "listing", _listing("listing_url")),
    # -- beyond the default set -------------------------------------------
    # Real columns, filled by real data, and deliberately not in `default`, which is a promise about
    # a document somebody already has rather than a place to put everything this tool knows.
    Column("Wildfire Hazard", "text", "enriched", _enriched("wildfire_hazard")),
    Column("Elevation (ft)", "number", "enriched", _enriched("elevation_ft")),
    Column("Notes", "text", "annotation", _annotated("notes")),
    Column("Flags", "text", "derived", _flags),
    Column("Sources", "text", "derived", _sources),
    Column("Description", "text", "listing", _listing("description")),
    Column("Listing ID", "text", "derived", lambda row: row.listing_id),
    Column("First Seen", "text", "derived", lambda row: row.history.first_observed_at),
)

BY_NAME: dict[str, Column] = {column.name: column for column in COLUMNS}

#: The hand-built consolidated sheet, exactly, in order. Written out rather than filtered out of
#: `COLUMNS`, because it is a promise about a document and a promise that is a side effect of a
#: filter is a promise that changes when somebody adds a column.
DEFAULT: tuple[str, ...] = (
    "Rank",
    "Status",
    "Property",
    "Town/Area",
    "County/Region",
    "Price",
    "$/sq ft",
    "Price History & DOM",
    "Beds",
    "Baths",
    "Sq Ft",
    "Year Built",
    "Acres",
    "Construction/Roof/Features",
    "Garage/Outbuildings",
    "HVAC/Heat",
    "Water Source",
    "Sewer/Septic",
    "Gas",
    "FEMA Flood Zone",
    "Internet",
    "Principal Aquifer",
    "Annual Taxes",
    "Crime/Safety",
    "Fire/Egress/Terrain",
    "Sewage & Reclaimed-Water Exposure",
    "Town Analysis Notes",
    "Red Flags",
    "Summary",
    "Verdict",
    "Next Step",
    "Listing URL",
)


def names() -> tuple[str, ...]:
    """Every column a template may name, in the order they are declared."""
    return tuple(column.name for column in COLUMNS)


def find(name: str) -> Column | None:
    return BY_NAME.get(name)


def _check_the_default_is_real() -> None:
    """Every name in the default set is a column that exists.

    At import, because a default template naming a column nobody declared would be a workbook that
    fails to build, discovered by whoever exported first rather than by whoever edited last.
    """
    missing = [name for name in DEFAULT if name not in BY_NAME]
    if missing:
        raise AssertionError(f"the default template names columns that do not exist: {missing}")


_check_the_default_is_real()
