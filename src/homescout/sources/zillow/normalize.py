"""One property, as Zillow describes it, turned into one the tool understands.

The same two rules the first adapter is built on, for the same reasons.

**A field the response does not carry stays empty.** Never a zero, never a guess.

**A field the response carries in a shape we did not expect fails the whole query.** A run that
wrote half-read rows as fact would poison every later comparison in a way no later run could detect.
Loud and empty beats quiet and wrong.

The one conversion worth knowing about: Zillow's lot area comes with its own unit, usually acres,
and the tool records square feet.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...records import ListingFields, SourceRow
from ..errors import SourceFailed

#: One acre in square feet, exact, as the saved-search validator already uses.
SQUARE_FEET_PER_ACRE = 43_560

#: Zillow's names for what a property is, in the tool's vocabulary. A name not here is kept exactly
#: as the site wrote it: an unfamiliar property type is a fact about the market, and a silently
#: empty one would be a fact about this code.
PROPERTY_TYPES: dict[str, str] = {
    "SINGLE_FAMILY": "single_family",
    "MULTI_FAMILY": "multi_family",
    "TOWNHOUSE": "townhouse",
    "CONDO": "condo",
    "APARTMENT": "apartment",
    "MANUFACTURED": "mobile",
    "LOT": "land",
    "HOME_TYPE_UNKNOWN": "",
}

#: And what it says about where a property is in its sale.
STATUSES: dict[str, str] = {
    "FOR_SALE": "for_sale",
    "PENDING": "pending",
    "PRE_FORECLOSURE": "for_sale",
    "FOR_RENT": "off_market",
    "RECENTLY_SOLD": "sold",
    "SOLD": "sold",
    "OTHER": "off_market",
}


def _as(kind: type, value: Any, where: str) -> Any:
    """Read one value, or say precisely which field could not be read."""
    if value is None or value == "":
        return None
    try:
        if kind is int:
            return int(float(value))
        if kind is float:
            return float(value)
        return str(value)
    except (TypeError, ValueError):
        raise SourceFailed(
            f"zillow: could not read {where} from {value!r}. "
            "The source's response shape has probably changed; no rows are returned rather than "
            "rows with a silently missing value."
        ) from None


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SourceFailed(
            f"zillow: expected {where} to be an object, got {type(value).__name__}. "
            "The source's response shape has probably changed."
        )
    return value


def _lot_sqft(info: Mapping[str, Any]) -> int | None:
    """Lot area in square feet, whatever unit the response chose to report it in.

    The filter takes square feet and the response answers in acres, which is the kind of asymmetry
    that produces a number that is wrong by a factor of forty-three thousand and looks plausible in
    a table.
    """
    value = _as(float, info.get("lotAreaValue"), "hdpData.homeInfo.lotAreaValue")
    if value is None:
        return None
    unit = str(info.get("lotAreaUnit") or "").strip().lower()
    if unit in ("acres", "acre"):
        return int(round(value * SQUARE_FEET_PER_ACRE))
    if unit in ("sqft", "square feet", "squarefeet", ""):
        return int(round(value))
    raise SourceFailed(
        f"zillow: lot area came in {unit!r}, which this adapter does not know how to convert. "
        "No rows are returned rather than a lot size that is wrong by an unknown factor."
    )


def _known(table: Mapping[str, str], value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value)
    mapped = table.get(raw.upper())
    if mapped == "":
        return None
    return mapped if mapped is not None else raw


def to_fields(home: Mapping[str, Any]) -> ListingFields:
    info = _mapping(_mapping(home.get("hdpData"), "hdpData").get("homeInfo"), "hdpData.homeInfo")

    return ListingFields(
        price=_as(int, info.get("price") or home.get("unformattedPrice"), "homeInfo.price"),
        listing_status=_known(STATUSES, info.get("homeStatus")),
        beds=_as(float, info.get("bedrooms"), "homeInfo.bedrooms"),
        baths=_as(float, info.get("bathrooms"), "homeInfo.bathrooms"),
        sqft=_as(int, info.get("livingArea"), "homeInfo.livingArea"),
        lot_sqft=_lot_sqft(info),
        year_built=_as(int, info.get("yearBuilt"), "homeInfo.yearBuilt"),
        property_type=_known(PROPERTY_TYPES, info.get("homeType")),
        address_line=_as(str, info.get("streetAddress") or home.get("addressStreet"),
                         "homeInfo.streetAddress"),
        unit=_as(str, info.get("unit"), "homeInfo.unit"),
        city=_as(str, info.get("city") or home.get("addressCity"), "homeInfo.city"),
        state=_as(str, info.get("state") or home.get("addressState"), "homeInfo.state"),
        postal_code=_as(str, info.get("zipcode") or home.get("addressZipcode"),
                        "homeInfo.zipcode"),
        latitude=_as(float, info.get("latitude"), "homeInfo.latitude"),
        longitude=_as(float, info.get("longitude"), "homeInfo.longitude"),
        listing_url=_detail_url(home),
        photo_urls=_photo_urls(home),
        days_on_market_source=_as(int, info.get("daysOnZillow"), "homeInfo.daysOnZillow"),
    )


def _detail_url(home: Mapping[str, Any]) -> str | None:
    """The page for this property, made absolute.

    The site gives this relative about half the time, and a relative URL in a digest email is a
    link to nowhere.
    """
    url = _as(str, home.get("detailUrl"), "detailUrl")
    if not url:
        return None
    if url.startswith("/"):
        return f"https://www.zillow.com{url}"
    return url


def _photo_urls(home: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Whatever images this result carries. The map results carry one; the list results carry more.

    Only `http` and `https` are kept, which is the rule for anything that later becomes a request
    from this machine.
    """
    found: list[str] = []
    for value in (home.get("imgSrc"), *(home.get("carouselPhotos") or ())):
        url = value.get("url") if isinstance(value, Mapping) else value
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            found.append(url)
    return tuple(dict.fromkeys(found)) or None


def to_row(home: Mapping[str, Any], *, fetched_at: str) -> SourceRow:
    """One row, carrying both the tool's reading of it and the source's own words."""
    home = _mapping(home, "a search result")
    identifier = home.get("zpid") or _mapping(
        _mapping(home.get("hdpData"), "hdpData").get("homeInfo"), "hdpData.homeInfo"
    ).get("zpid")
    return SourceRow(
        source="zillow",
        fields=to_fields(home),
        payload=dict(home),
        source_listing_id=_as(str, identifier, "zpid"),
        fetched_at=fetched_at,
    )


def preview_url(home: Mapping[str, Any]) -> str | None:
    """The small image the source offers, if it offers one and it is safe to ask for."""
    url = home.get("imgSrc")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    return None
