"""Every column a template may name, and where each one gets its value.

One table, and the writer walks it. Nothing downstream of this module knows a column name, which is
what makes adding or reordering columns a configuration change rather than a code change, and what
lets a template naming `Wells` be refused before a single row is built.

Each column also declares its **origin**, which is not decoration. Eleven of the thirty-two default
columns come out blank on a fresh store, for three completely different reasons. Telling somebody
which one applies, "run `homescout enrich`" or "write some notes" or "no free national source
supplies this", is the difference between a useful sheet and an afternoon spent looking for a bug
in this tool.

Five of the defaults used to be a sixth kind, `unfilled`: headings the household's own sheet has
that nothing in this tool fills. They were a promise the interface could not keep, drawn empty on
every row and marked as the person's to fill in with no way to fill them in. They are annotations
now, like every other column a person writes, and no column is neither filled nor writable.
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
#: prose · `enriched` public data about the location · `annotation` the person wrote it.
#:
#: There is deliberately no sixth kind for a column nothing fills. There was one, and it meant a
#: column that was empty forever and could not be typed into either, which is not a column: it is a
#: heading with an apology under it.
Origin = Only["listing", "derived", "extracted", "enriched", "annotation", "assessed"]

#: What an empty column of each kind means, in words a person can act on.
WHY_EMPTY: dict[str, str] = {
    "extracted": "no listing description said so",
    "enriched": "the enrichment pass has not been run for these properties",
    "annotation": "nothing has been written about these properties yet",
    # Two different blanks and the difference matters: a property nothing has assessed, and one that
    # was assessed and had nothing raised about it. The column keeps them apart by holding `None`
    # for the first and `0` for the second; this sentence is for a whole column that is empty, which
    # means the pass has not been run.
    "assessed": "nothing has read these properties against your criteria yet",
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
    """What the FCC records as available in this property's census block.

    The word "advertised" is in the cell and is not decoration: this is what a provider filed for
    the block, not a measurement and not this property's own line. The block caveat is too long for
    a cell and lives on the surfaces with room for it (feat-007 AC-18).
    """
    down = row.enriched.get("download_mbps")
    up = row.enriched.get("upload_mbps")
    who = row.enriched.get("broadband_provider")
    if down is None and up is None and not who:
        return None
    speed = f"{down or '?'}/{up or '?'} Mbps advertised"
    return f"{speed}, {who}" if who else speed


def _aquifer(row: Row) -> str | None:
    """Yes or no as words, because a spreadsheet column of TRUE and FALSE reads as a bug."""
    over = row.enriched.get("over_principal_aquifer")
    if over is None:
        return None
    return "over a principal aquifer" if over else "not over a principal aquifer"


def _wui(row: Row) -> str | None:
    """The three readings of the interface value, told apart in a cell.

    The only column here whose known negative is `None`, which is why it reads the key rather than
    the value: a missing value is not in the mapping at all, so `in` separates "nobody asked" from
    "asked, and this place is in neither kind". Getting that wrong would print an empty cell for a
    real answer, and the export tells a person an empty enriched cell means the pass has not run.

    `outside coverage` is spelled out rather than left blank for the same reason in the other
    direction: it is not a negative and must never be read as one.
    """
    if "wildland_urban_interface" not in row.enriched:
        return None
    found = row.enriched.get("wildland_urban_interface")
    if found is None:
        return "not in the wildland-urban interface"
    if found == "outside coverage":
        return "outside coverage (New Mexico only)"
    return f"in the wildland-urban interface: {found}"


def _tags(row: Row) -> str | None:
    """The household's own words for this property, comma separated.

    Joined here rather than in either surface, so the sheet, the table and the terminal print one
    property's tags the same way. A comma is safe as the join because a tag cannot contain one:
    `Tag.cleaned` refuses it at the point a tag is made, which is the only place it can be refused
    once instead of escaped in every place a tag is written down.
    """
    return ", ".join(row.tags) or None


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


def _county(row: Row) -> str | None:
    """The county the listing named, or the one the public record puts this point in.

    Realtor sends a county on nearly every row. Zillow and Redfin send none at all, so on a
    statewide table a quarter of this column was blank, and a blank column tells a person filtering
    by county nothing at all — least of all that the blank is the site's silence rather than the
    property's.

    The listing's own word wins where there is one, and the plain name is what lands in the cell,
    with no marker appended: a cell reading `Roosevelt (looked up)` sorts and groups apart from
    `Roosevelt`, which would break the one thing this column is for. Where the answer came from is
    kept, and readable, in `County (looked up)` beside it.
    """
    said = (row.fields.county or "").strip()
    if said:
        return said
    found = row.enriched.get("county_name")
    return str(found) if found else None


def _flags(row: Row) -> str | None:
    return ", ".join(row.flags) or None


def _sources(row: Row) -> str | None:
    return ", ".join(row.sources) or None


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

def _concerns(row: Row) -> Any:
    """How many things the model raised about this property.

    `None` rather than zero when nothing was assessed, and zero when an assessment raised nothing.
    Those are different facts and the difference is the useful part: 55 of the 155 properties in
    this workspace were read and had nothing raised about them, which is a real answer and not an
    absence. Invariant 10's rule that an undetermined value is empty is what keeps them apart.
    """
    found = getattr(row, "assessment", None)
    return None if found is None else found.get("concerns")


def _in_favour(row: Row) -> Any:
    """How many things count for this property.

    Three states, exactly as `_concerns` has: nothing assessed it, it was read and nothing was said
    for it, or this many. There is a fourth state underneath that this deliberately flattens: an
    assessment written before the question existed at all. It reads as empty here, the same as a
    property nobody has assessed, because from a person's side those are the same fact — nobody has
    told them what is good about this house. The store keeps them apart so a pass knows which ones
    it still owes an answer for.
    """
    found = getattr(row, "assessment", None)
    return None if found is None else found.get("in_favour")


COLUMNS: tuple[Column, ...] = (
    Column("Rank", "number", "annotation", _annotated("rank")),
    Column("Status", "text", "derived", _status),
    Column("Property", "text", "listing", _address, links=True),
    # Third, beside the address, and deliberately not down with the other things a person writes.
    #
    # It went next to `Notes` first, which is where it belongs by family and is column thirty-nine
    # of forty-four on a real table. Nobody scrolls two screens right to find a feature they have
    # not been told about: "how do you create tags, I'm clicking the field on a row but it's not
    # letting me type." A tag is a label on a house and it is read the way the address is read,
    # down the column, so it goes where the address is. It stays out of the default sheet, which is
    # a promise about a document that already exists.
    Column("Tags", "text", "annotation", _tags),
    # An origin of its own, and the sixth. What a model made of a property is not a value a source
    # reported, one this tool computed, one read out of a description, public data about the place,
    # or something the person wrote, and the chooser groups by exactly that question.
    #
    # Declared here and deliberately not in `DEFAULT` below: declaring it is what makes the table
    # sort, filter, hide and choose it with no special case, and staying out of the default sheet is
    # what leaves the spreadsheet's header exactly as feat-011/AC-1 requires. Anybody who wants
    # it in a sheet puts it in a template, which is what a template is for.
    Column("In favour", "number", "assessed", _in_favour),
    Column("Concerns", "number", "assessed", _concerns),
    Column("Town/Area", "text", "listing", _listing("city")),
    Column("County/Region", "text", "derived", _county),
    Column("Price", "number", "listing", _listing("price")),
    Column("$/sq ft", "number", "derived", _price_per_sqft),
    Column("Price History & DOM", "text", "derived", _price_history),
    Column("Beds", "number", "listing", _listing("beds")),
    Column("Baths", "number", "listing", _listing("baths")),
    Column("Sq Ft", "number", "listing", _listing("sqft")),
    Column("Year Built", "number", "listing", _listing("year_built")),
    Column("Acres", "number", "derived", _acres),
    Column("Construction/Roof/Features", "text", "extracted", _extracted("roof")),
    Column("Garage/Outbuildings", "text", "annotation", _annotated("outbuildings")),
    Column("HVAC/Heat", "text", "extracted", _hvac),
    Column("Water Source", "text", "extracted", _extracted("water_source")),
    Column("Sewer/Septic", "text", "extracted", _extracted("sewer")),
    Column("Gas", "text", "extracted", _extracted("gas")),
    Column("FEMA Flood Zone", "text", "enriched", _enriched("flood_zone")),
    Column("Internet", "text", "enriched", _internet),
    Column("Principal Aquifer", "text", "enriched", _aquifer),
    Column("Annual Taxes", "text", "annotation", _annotated("taxes")),
    Column("Crime/Safety", "text", "annotation", _annotated("crime")),
    Column("Fire/Egress/Terrain", "text", "annotation", _annotated("fire_egress")),
    Column("Sewage & Reclaimed-Water Exposure", "text", "annotation",
           _annotated("sewage_exposure")),
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
    Column("Wildland-Urban Interface", "text", "enriched", _wui),
    Column("County (looked up)", "text", "enriched", _enriched("county_name")),
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
