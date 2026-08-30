"""One property, as Realtor.com describes it, turned into one the tool understands.

Two rules govern everything here, and they pull in opposite directions on purpose.

**A field the response does not carry stays empty.** Never a zero, never a guess. An empty price and
a price of nothing are different facts and the product invariant says so.

**A field the response carries in a shape we did not expect fails the whole query.** Not a row with
a quietly missing value. This tool's entire worth is comparing today against last month, and a run
that wrote half-read rows as fact would poison that comparison in a way no later run could detect,
let alone repair. Loud and empty beats quiet and wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ...records import ListingFields, SourceRow
from ..errors import SourceFailed


def _as(kind: type, value: Any, where: str) -> Any:
    """Read one value, or say precisely which field could not be read."""
    if value is None:
        return None
    try:
        if kind is int:
            return int(value)
        if kind is float:
            return float(value)
        return str(value)
    except (TypeError, ValueError):
        raise SourceFailed(
            f"realtor: could not read {where} from {value!r}. "
            "The source's response shape has probably changed; no rows are returned rather than "
            "rows with a silently missing value."
        ) from None


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SourceFailed(
            f"realtor: expected {where} to be an object, got {type(value).__name__}. "
            "The source's response shape has probably changed."
        )
    return value


#: How much of a bathroom each kind the source counts separately is worth, in the decimal everyone
#: quotes. A three-quarter bath (basin, lavatory, shower, no tub) counts as a whole one: that is how
#: the listings themselves write it, and a house the source records as one full and one
#: three-quarter is a house whose own description says "two bath".
_BATH_KINDS = {
    "baths_full": 1.0,
    "baths_3qtr": 1.0,
    "baths_half": 0.5,
    "baths_1qtr": 0.25,
}


def _baths(description: Mapping[str, Any]) -> float | None:
    """How many bathrooms, in the decimal the listings are written in.

    The source counts four kinds separately and never states the decimal itself. It does publish a
    plain `baths`, but that one is a room count, so a house with two full and one half is a three
    there and a two-and-a-half everywhere else, including in the other two sources this tool merges
    against. Adding the kinds up here is what keeps one property's bath count the same number no
    matter which source found it.

    Asking for only two of the four kinds is what this used to do, and it was wrong for about half
    of the properties that have any: a three-quarter bath is the ordinary second bathroom of a small
    house, and dropping it left the field a whole bathroom short of the description beside it.
    """
    counted = {
        kind: _as(float, description.get(kind), f"description.{kind}") for kind in _BATH_KINDS
    }
    if all(value is None for value in counted.values()):
        return None
    return sum(_BATH_KINDS[kind] * value for kind, value in counted.items() if value is not None)


def _photo_urls(home: Mapping[str, Any]) -> tuple[str, ...] | None:
    photos = home.get("photos")
    if not photos:
        return None
    if not isinstance(photos, list):
        raise SourceFailed("realtor: expected photos to be a list. The response shape has changed.")
    urls = tuple(
        str(p["href"]) for p in photos if isinstance(p, Mapping) and p.get("href")
    )
    return urls or None


def _days_listed(home: Mapping[str, Any]) -> int | None:
    """How long the *source* says this has been listed.

    Recorded and never compared. Freshness in this tool always comes from its own first observation,
    so this exists to make the source's disagreement visible when someone is debugging, not to be
    believed.
    """
    raw = home.get("list_date")
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        listed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if listed.tzinfo is None:
        listed = listed.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC).date() - listed.date()).days)


def to_fields(home: Mapping[str, Any]) -> ListingFields:
    description = _mapping(home.get("description"), "description")
    location = _mapping(home.get("location"), "location")
    address = _mapping(location.get("address"), "location.address")
    coordinate = _mapping(address.get("coordinate"), "location.address.coordinate")
    county = _mapping(location.get("county"), "location.county")
    tax = _mapping(home.get("tax_record"), "tax_record")

    return ListingFields(
        price=_as(int, home.get("list_price"), "list_price"),
        listing_status=_as(str, home.get("status"), "status"),
        beds=_as(float, description.get("beds"), "description.beds"),
        baths=_baths(description),
        sqft=_as(int, description.get("sqft"), "description.sqft"),
        lot_sqft=_as(int, description.get("lot_sqft"), "description.lot_sqft"),
        year_built=_as(int, description.get("year_built"), "description.year_built"),
        property_type=_as(str, description.get("type"), "description.type"),
        address_line=_as(str, address.get("line"), "location.address.line"),
        unit=_as(str, address.get("unit"), "location.address.unit"),
        city=_as(str, address.get("city"), "location.address.city"),
        state=_as(str, address.get("state_code"), "location.address.state_code"),
        postal_code=_as(str, address.get("postal_code"), "location.address.postal_code"),
        county=_as(str, county.get("name"), "location.county.name"),
        latitude=_as(float, coordinate.get("lat"), "location.address.coordinate.lat"),
        longitude=_as(float, coordinate.get("lon"), "location.address.coordinate.lon"),
        parcel_number=_as(str, tax.get("apn") or tax.get("tax_parcel_id"), "tax_record.apn"),
        listing_url=_as(str, home.get("href"), "href"),
        description=_as(str, description.get("text"), "description.text"),
        photo_urls=_photo_urls(home),
        days_on_market_source=_days_listed(home),
    )


def to_row(home: Mapping[str, Any], *, fetched_at: str) -> SourceRow:
    """One row, carrying both the tool's reading of it and the source's own words.

    The original object is kept verbatim, so a normalization bug found in six months can be
    corrected against what was actually received rather than guessed at from what survived.
    """
    home = _mapping(home, "a search result")
    return SourceRow(
        source="realtor",
        fields=to_fields(home),
        payload=dict(home),
        source_listing_id=_as(str, home.get("property_id"), "property_id"),
        fetched_at=fetched_at,
    )


def preview_url(home: Mapping[str, Any]) -> str | None:
    """The small image the source offers, if it offers one.

    The source gives these as plaintext `http://` addresses and its image host answers every one of
    them with a redirect to the same address over `https`. Image fetches deliberately do not follow
    redirects, so taking the address as given retrieves a 167-byte redirect page instead of a
    picture, every time, for every property. Asking for `https` directly is not following the
    redirect, it is declining to make the plaintext request the redirect exists to correct.
    """
    photo = _mapping(home.get("primary_photo"), "primary_photo")
    href = photo.get("href")
    if not href:
        return None
    address = str(href)
    return f"https://{address[len('http://'):]}" if address.startswith("http://") else address
