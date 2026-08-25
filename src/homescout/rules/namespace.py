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

#: Recovered from a listing's prose by description field extraction (feat-009).
#:
#: Every one of these is a word from a closed vocabulary, so a criterion compares against a word:
#: `water_source == "well"`, `sewer != "septic"`, `cooling in ["refrigerated", "central"]`. The
#: vocabulary lives in `extract/fields.py`, which checks itself against this table at import.
#:
#: `"none"` is a value and means the description said the property does not have the thing. It is
#: not the same as the field being empty, which means nobody said either way and leaves a criterion
#: undetermined rather than false.
_EXTRACTED: tuple[Field, ...] = (
    Field("heating", TEXT, "extracted", populated=True),
    Field("cooling", TEXT, "extracted", populated=True),
    Field("water_source", TEXT, "extracted", populated=True),
    Field("sewer", TEXT, "extracted", populated=True),
    Field("gas", TEXT, "extracted", populated=True),
    Field("roof", TEXT, "extracted", populated=True),
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


#: Fields whose set of values is genuinely open, with a few real ones so somebody writing a
#: criterion can see the shape of what they are comparing against. Not a promise about the whole
#: set, which is why these are examples rather than values.
_EXAMPLES: dict[str, tuple[str, ...]] = {
    "flood_zone": ("X (AREA OF MINIMAL FLOOD HAZARD)", "X (0.2 PCT ANNUAL CHANCE FLOOD HAZARD)",
                   "A", "AE"),
    "property_type": ("single_family", "land", "mobile", "farm"),
    "broadband_provider": ("CenturyLink, Xfinity, Yucca Telecom",),
    "state": ("NM", "TX"),
}

#: What to call each field on a page, for somebody who did not choose the name in the code. Every
#: field has one: without it a builder shows `over_principal_aquifer` in a dropdown, and a person
#: who has to translate a variable name before they can pick it is a person the tool has failed.
_LABELS: dict[str, str] = {
    "price": "Price",
    "listing_status": "Listing status",
    "beds": "Bedrooms",
    "baths": "Bathrooms",
    "sqft": "House size (sq ft)",
    "lot_sqft": "Lot size (sq ft)",
    "year_built": "Year built",
    "property_type": "Kind of property",
    "address_line": "Street address",
    "unit": "Unit number",
    "city": "Town",
    "state": "State",
    "postal_code": "ZIP code",
    "county": "County",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "parcel_number": "Parcel number",
    "listing_url": "Link to the listing",
    "description": "The listing's description",
    "photo_urls": "Photos",
    "dom": "Days on the market",
    "is_new": "New since the last run",
    "presence": "Still listed",
    "price_cut": "Price has come down",
    "price_raised_after_days": "Days before the price went up",
    "flood_zone": "FEMA flood zone",
    "upload_mbps": "Upload speed (Mbps)",
    "download_mbps": "Download speed (Mbps)",
    "broadband_provider": "Internet providers",
    "over_principal_aquifer": "Over a principal aquifer",
    "wildfire_hazard": "Wildfire hazard",
    "elevation_ft": "Elevation (feet)",
    "heating": "Heating",
    "cooling": "Cooling",
    "water_source": "Water source",
    "sewer": "Sewer or septic",
    "gas": "Gas",
    "roof": "Roof",
}

#: What to call each value on a page. Only where the stored word is not the word a person says: a
#: source's `for_sale` and an extraction's `co-op` are both fine to store and neither is fine to put
#: in front of somebody choosing from a list.
_VALUE_LABELS: dict[str, str] = {
    "for_sale": "for sale",
    "off_market": "off market",
    "single_family": "single family",
    "co-op": "a shared or co-op system",
    "none": "none (the listing said it does not have one)",
    "observed": "yes, the last run saw it",
    "disappeared": "no, it has gone",
}

#: What each field means, in the words somebody writing a criterion would use. Here rather than in a
#: surface, because both surfaces need it and a second copy would drift from the first.
_MEANS: dict[str, str] = {
    "dom": "days on market, counted from this tool's own first sighting, never the site's claim",
    "is_new": "first seen by this tool in the run being looked at",
    "presence": "whether the last run still saw it",
    "price_cut": "the price is lower than it was",
    "price_raised_after_days": "days it sat before the price went up, if it did",
    "lot_sqft": "lot size in square feet, so an acre is 43560",
    "elevation_ft": "feet above sea level",
    "upload_mbps": "best advertised residential upload in this property's census block",
    "download_mbps": "best advertised residential download in this property's census block",
    "broadband_provider": "who offers it in that block, comma separated",
    "over_principal_aquifer": "the point is over a USGS principal aquifer",
    "photo_urls": "a list, so use `is null` rather than comparing it",
    "description": "the listing's prose, which is what the extracted fields below were read from",
}


def closed_values(name: str) -> tuple[str, ...]:
    """The complete set of values a field may hold, or nothing when the set is open.

    Read from the tables that actually decide each set rather than restated here, so a value added
    to the extraction vocabulary or the wildfire legend reaches anybody writing a criterion in the
    same edit. Imported inside the function because those tables import this one.
    """
    if name in ("heating", "cooling", "water_source", "sewer", "gas", "roof"):
        from ..extract.fields import find as extracted

        found = extracted(name)
        return found.values if found is not None else ()
    if name == "wildfire_hazard":
        from ..enrich.providers import WILDFIRE_CLASSES

        return tuple(WILDFIRE_CLASSES.values())
    if name == "listing_status":
        from ..search.validate import LISTING_TYPES

        return tuple(LISTING_TYPES)
    if name == "presence":
        return ("observed", "disappeared")
    return ()


def vocabulary() -> tuple[dict[str, object], ...]:
    """Every field a criterion may name, with what it holds and what it may say.

    The list of names on its own is half an answer: somebody writing `cooling == "swamp cooler"`
    has named a real field and compared it to a word that can never be true, and nothing in a bare
    list of names would have told them. So this carries the closed set where there is one, a few
    real examples where the set is open, and a sentence for the fields whose name does not say what
    they mean.
    """
    found: list[dict[str, object]] = []
    for name in sorted(FIELDS):
        field = FIELDS[name]
        found.append(
            {
                "name": name,
                "type": field.type.name,
                "of": field.type.item.name if field.type.item is not None else None,
                "origin": field.origin,
                "populated": field.populated,
                "populated_by": field.populated_by,
                "label": _LABELS.get(name, name.replace("_", " ").capitalize()),
                "values": [
                    {"value": value, "label": _VALUE_LABELS.get(value, value)}
                    for value in closed_values(name)
                ],
                "examples": list(_EXAMPLES.get(name, ())),
                "means": _MEANS.get(name, ""),
            }
        )
    return tuple(found)


def names() -> tuple[str, ...]:
    """Every name a rule may use, in a stable order."""
    return tuple(sorted(FIELDS))


def find(name: str) -> Field | None:
    return FIELDS.get(name)
