"""One property, normalized, and the row a source produced it from.

These two shapes are the seam between the layers: a source adapter builds them, the store writes
them. They live here, above both, so that neither layer has to import the other to describe its own
input or output. The architecture runs `sources` before `store`, and a source that had to import the
database package to say what it returns would be reaching backwards through the whole product.

Nothing here knows about SQLite, HTTP, or any particular listing site.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True, slots=True)
class ListingFields:
    """One property's values as a source reported them.

    Every field is optional. A source that does not know a value leaves it absent, and absent is a
    distinct thing from zero or from false: a listing with no price is not a listing priced at
    nothing.
    """

    price: int | None = None
    listing_status: str | None = None
    beds: float | None = None
    baths: float | None = None
    sqft: int | None = None
    lot_sqft: int | None = None
    year_built: int | None = None
    property_type: str | None = None
    address_line: str | None = None
    unit: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    parcel_number: str | None = None
    listing_url: str | None = None
    description: str | None = None
    photo_urls: tuple[str, ...] | None = None
    #: What the source claims about time on market. Recorded, never used: this tool's own
    #: figure comes from its own first observation and is never overwritten by this one.
    days_on_market_source: int | None = None

    def as_row(self) -> dict[str, Any]:
        """Column values for a database row. The photo list is stored as JSON text."""
        values = asdict(self)
        urls = values.pop("photo_urls")
        values["photo_urls"] = json.dumps(list(urls)) if urls is not None else None
        return values

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> ListingFields:
        present = set(row.keys())
        values = {name: row[name] for name in FIELD_NAMES if name in present}
        urls = values.get("photo_urls")
        values["photo_urls"] = tuple(json.loads(urls)) if urls else None
        return cls(**values)


#: Every field on a normalized listing, read from the dataclass itself rather than restated. The
#: two must agree, and the only way to guarantee that is to have one of them.
FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in fields(ListingFields))


@dataclass(frozen=True, slots=True)
class SourceRow:
    """What a source adapter hands the store: one property, as that source returned it.

    The source's own response is retained alongside the normalized fields, so a normalization bug
    found later can be corrected against what was actually received rather than guessed at.
    """

    source: str
    fields: ListingFields
    payload: Mapping[str, Any] | str
    source_listing_id: str | None = None
    fetched_at: str | None = None

    def payload_text(self) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, sort_keys=True, default=str)
