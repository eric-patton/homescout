"""The request Redfin answers, and the tables it is built from.

This one is not an API and does not pretend to be. It is the download button behind the map, which
returns a CSV, and it takes a polygon rather than a rectangle, which happens to be exactly what a
bounding box already is.

Two paths that would have been the obvious way in are refused at the edge: `location-autocomplete`
and `query-location` both answer 403 with CloudFront's own error page. That would have been fatal
for a design that needed to look up a region id first. Passing a polygon needs no region and no
prior request at all, which is both simpler and one fewer request per search.

The address is configuration, like every other external address in this project.
"""

from __future__ import annotations

import os

from ..base import BoundingBox, SearchQuery
from ..boxes import ring

ENDPOINT = "https://www.redfin.com/stingray/api/gis-csv"
ENDPOINT_VARIABLE = "HOMESCOUT_SOURCE_REDFIN_URL"

#: The site's cap, observed exactly: 350 properties and not one more, with nothing in the response
#: to say that anything was left out. See the adapter for what is done about that.
ROW_CAP = 350
PAGE_SIZE = ROW_CAP

#: Every filter measured to change what comes back. Lot size is the conspicuous absence and it is
#: deliberate: `min_lot_size`, `min_lot_sq_ft` and `lot_sq_ft` were each tried and each changed
#: nothing, so lot size is filtered locally and the caller is told so.
APPLIES = frozenset(
    {
        "price_min",
        "price_max",
        "beds_min",
        "beds_max",
        "baths_min",
        "sqft_min",
        "sqft_max",
        "year_built_min",
        "year_built_max",
        "listing_status",
    }
)

#: Query field to the parameter that expresses it. A field with no row here has no path into a
#: request even if somebody adds it to the declaration above.
_PARAMETERS: dict[str, str] = {
    "price_min": "min_price",
    "price_max": "max_price",
    "beds_min": "num_beds",
    "beds_max": "max_num_beds",
    "baths_min": "num_baths",
    "sqft_min": "min_listing_approx_size",
    "sqft_max": "max_listing_approx_size",
    "year_built_min": "min_year_built",
    "year_built_max": "max_year_built",
}

#: The tool's property vocabulary against the codes Redfin's `uipt` parameter takes, and the reason
#: this table narrows nothing.
#:
#: **There is no code for a farm.** Redfin's list is house, condo, townhouse, multi-family, land,
#: other, manufactured, co-op, and a ranch is not on it, so `farm` was pointed at land as the
#: nearest thing. That is not a near miss, it is a different question: a search for "houses and
#: farms" went out as "houses and land" and came back with every vacant lot in the state. Six of
#: them were sitting in a household's results, and the reason nobody spotted it sooner is that a lot
#: has no photograph, so it looked like a picture problem rather than a filter problem.
#:
#: The site does honour this parameter. Measured on one box: asked for houses, three hundred and
#: forty-nine rows and not one lot; asked for houses and farms, four lots. So the fault is entirely
#: in what we can say to it, which is why the fix is to stop claiming we said it. `property_types`
#: is no longer declared and so is no longer sent, and the caller filters by kind locally. Exactly
#: what lot size does, three fields up, and for the same reason: a narrowing this source cannot
#: express honestly is one the caller has to do itself.
#:
#: Kept rather than deleted because the mapping is true about the site and the next person to reach
#: for it needs to find this note rather than write the table again.
_PROPERTY_CODES: dict[str, str] = {
    "single_family": "1",
    "condo": "2",
    "townhouse": "3",
    "multi_family": "4",
    "land": "5",
    "farm": "5",  # Wrong, and unreachable. See above.
    "other": "6",
    "mobile": "7",
    "apartment": "8",
}
ALL_PROPERTY_CODES = "1,2,3,4,5,6,7,8"

#: And what it calls the stage a property is at. 9 is everything for sale, which is the default the
#: site itself uses.
_STATUS_CODES: dict[str, str] = {
    "for_sale": "9",
    "pending": "8",
    "contingent": "8",
    "sold": "9",
    "off_market": "9",
}


def endpoint() -> str:
    return os.environ.get(ENDPOINT_VARIABLE) or ENDPOINT


def poly(box: BoundingBox) -> str:
    """The box as the ring this endpoint takes: longitude, a space, latitude, comma separated.

    Built by formatting numbers, never by joining anything that came out of a response. There is
    nothing here to inject because there is nothing here that is not a float.
    """
    return ",".join(f"{longitude:.6f} {latitude:.6f}" for longitude, latitude in ring(box))


def parameters(query: SearchQuery, box: BoundingBox, applies: frozenset[str]) -> dict[str, str]:
    """The whole query string, built only from what the source declared it applies."""
    values: dict[str, str] = {
        "al": "1",
        "poly": poly(box),
        # Asked for explicitly rather than left to the default, so the number this adapter believes
        # and the number it requests cannot drift apart.
        "num_homes": str(ROW_CAP),
        "ord": "redfin-recommended-asc",
        "page_number": "1",
        "uipt": ALL_PROPERTY_CODES,
        "status": _STATUS_CODES["for_sale"],
        "v": "8",
    }

    for name, parameter in _PARAMETERS.items():
        if name not in applies:
            continue
        value = getattr(query, name, None)
        if value is None:
            continue
        values[parameter] = f"{value:g}" if isinstance(value, float) else str(value)

    # `uipt` stays at every code. This source is asked for all kinds and the caller keeps the ones
    # the search wanted; see `_PROPERTY_CODES` for why it is not asked to narrow.

    if "listing_status" in applies and query.listing_status:
        values["status"] = _STATUS_CODES.get(query.listing_status, _STATUS_CODES["for_sale"])

    return values
