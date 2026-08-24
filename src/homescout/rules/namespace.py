"""Every name a criterion may use, declared once.

A rule can reach exactly what is in this table and nothing else, which is the other half of the
safety argument: the grammar has no way to construct a name, and this is the only list of names
there is.

The table also carries what fills each field, which is what lets three different situations get
three different messages instead of one shrug:

- a name that is not here at all is a mistake in the rule
- a name that is here but that nothing in this build fills is a rule that can only ever be
  undetermined, which is worth being told once rather than discovering per property
- a name that is here and filled, but empty for one property, is that property's own answer

One field a source reports is deliberately absent. `days_on_market_source` is what a listing site
claims about time on market, and this tool records it and never believes it: freshness here is
computed from this tool's own first observation (product invariant 7). Putting it in reach of a
criterion would let a rule quietly prefer the site's story to ours, which is the exact substitution
the invariant exists to prevent. `dom` is the honest one, and it is here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal as Only

from ..records import FIELD_NAMES

Origin = Only["listing", "derived", "enriched", "extracted"]


@dataclass(frozen=True, slots=True)
class Type:
    """What kind of thing a value is, for checking a criterion before it runs."""

    name: Only["number", "text", "boolean", "list"]
    item: Type | None = None

    def __str__(self) -> str:
        return f"a list of {self.item}" if self.item is not None else _ARTICLES[self.name]


_ARTICLES = {"number": "a number", "text": "text", "boolean": "true or false", "list": "a list"}

NUMBER = Type("number")
TEXT = Type("text")
BOOLEAN = Type("boolean")
TEXT_LIST = Type("list", TEXT)


@dataclass(frozen=True, slots=True)
class Field:
    name: str
    type: Type
    origin: Origin
    #: Whether anything in this build ever puts a value here.
    populated: bool
    #: What will, when it does not yet. Named in the message a rule gets.
    populated_by: str = ""


def _listing(name: str, type_: Type) -> Field:
    return Field(name, type_, "listing", populated=True)


#: What a listing site reports, as this tool records it.
_LISTING: tuple[Field, ...] = (
    _listing("price", NUMBER),
    _listing("listing_status", TEXT),
    _listing("beds", NUMBER),
    _listing("baths", NUMBER),
    _listing("sqft", NUMBER),
    _listing("lot_sqft", NUMBER),
    _listing("year_built", NUMBER),
    _listing("property_type", TEXT),
    _listing("address_line", TEXT),
    _listing("unit", TEXT),
    _listing("city", TEXT),
    _listing("state", TEXT),
    _listing("postal_code", TEXT),
    _listing("county", TEXT),
    _listing("latitude", NUMBER),
    _listing("longitude", NUMBER),
    _listing("parcel_number", TEXT),
    _listing("listing_url", TEXT),
    _listing("description", TEXT),
    _listing("photo_urls", TEXT_LIST),
)

#: Kept out of reach on purpose. See this module's own explanation.
WITHHELD: frozenset[str] = frozenset({"days_on_market_source"})

#: Computed here, from this tool's own history of a property.
_DERIVED: tuple[Field, ...] = (
    Field("dom", NUMBER, "derived", populated=True),
    Field("is_new", BOOLEAN, "derived", populated=True),
    Field("presence", TEXT, "derived", populated=True),
    Field("price_cut", BOOLEAN, "derived", populated=True),
    Field("price_raised_after_days", NUMBER, "derived", populated=True),
)

#: Public data attached to a location. Declared here, filled by location enrichment (feat-007).
_ENRICHED: tuple[Field, ...] = (
    Field("flood_zone", TEXT, "enriched", False, "location enrichment"),
    Field("upload_mbps", NUMBER, "enriched", False, "location enrichment"),
    Field("download_mbps", NUMBER, "enriched", False, "location enrichment"),
    Field("broadband_provider", TEXT, "enriched", False, "location enrichment"),
    Field("over_principal_aquifer", BOOLEAN, "enriched", False, "location enrichment"),
    Field("wildfire_hazard", TEXT, "enriched", False, "location enrichment"),
    Field("elevation_ft", NUMBER, "enriched", False, "location enrichment"),
)

#: Recovered from a listing's prose. Declared here, filled by description field extraction
#: (feat-009).
_EXTRACTED: tuple[Field, ...] = (
    Field("heating", TEXT, "extracted", False, "description field extraction"),
    Field("cooling", TEXT, "extracted", False, "description field extraction"),
    Field("water_source", TEXT, "extracted", False, "description field extraction"),
    Field("sewer", TEXT, "extracted", False, "description field extraction"),
    Field("gas", TEXT, "extracted", False, "description field extraction"),
    Field("roof", TEXT, "extracted", False, "description field extraction"),
)

FIELDS: dict[str, Field] = {
    field.name: field for field in (*_LISTING, *_DERIVED, *_ENRICHED, *_EXTRACTED)
}

# Every listing field is either reachable by a rule or withheld on purpose. Without this, a field
# added to a listing tomorrow would quietly be unreachable, and nobody would find out until they
# wrote a rule naming it.
assert {f.name for f in _LISTING} | WITHHELD == set(FIELD_NAMES), (
    "every listing field must be declared here or withheld deliberately"
)


def names() -> tuple[str, ...]:
    """Every name a rule may use, in a stable order."""
    return tuple(sorted(FIELDS))


def find(name: str) -> Field | None:
    return FIELDS.get(name)
