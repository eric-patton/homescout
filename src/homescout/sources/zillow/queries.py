"""The request Zillow answers, and the table it is built from.

The endpoint every write-up names, `GetSearchPageState.htm`, answers 404 with four hundred kilobytes
of Zillow's own error page. The one that answers is a `PUT` with a JSON body, and it is here as a
default with an environment override, because this is the third public endpoint in this project to
have moved between a document being written and the code being built.

Everything in the body comes from walking the tables below. A query field with no row here has no
path into a request, which is what makes the capability declaration true rather than aspirational.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ..base import BoundingBox, SearchQuery

ENDPOINT = "https://www.zillow.com/async-create-search-page-state"
ENDPOINT_VARIABLE = "HOMESCOUT_SOURCE_ZILLOW_URL"

#: Observed at 502 and 503 for boxes matching 2,067 and 20,181. Undocumented, so the smaller round
#: number is declared: splitting once more than strictly necessary costs a request, and splitting
#: once less loses properties nobody will know are missing.
RESULT_CEILING = 500

#: One request is a whole box (the map results carry every property in it), so the walk must never
#: try for a second page. Setting this to the ceiling is what tells it so.
PAGE_SIZE = RESULT_CEILING

#: Every filter measured to change what comes back. Anything not here is never sent and is reported
#: to the caller as still needing local filtering.
APPLIES = frozenset(
    {
        "price_min",
        "price_max",
        "beds_min",
        "beds_max",
        "baths_min",
        "sqft_min",
        "sqft_max",
        "lot_sqft_min",
        "lot_sqft_max",
        "year_built_min",
        "year_built_max",
        "property_types",
        "listing_status",
    }
)

#: Query field to (filter name, bound). Zillow's `baths` takes a minimum only, which is why there is
#: no `baths_max` row and why `baths_max` is absent from the declaration above.
_RANGES: dict[str, tuple[str, str]] = {
    "price_min": ("price", "min"),
    "price_max": ("price", "max"),
    "beds_min": ("beds", "min"),
    "beds_max": ("beds", "max"),
    "baths_min": ("baths", "min"),
    "sqft_min": ("sqft", "min"),
    "sqft_max": ("sqft", "max"),
    # In square feet on the way in. The response reports lot area in whatever `lotAreaUnit` says,
    # which is usually acres, and the normalizer converts it back.
    "lot_sqft_min": ("lotSize", "min"),
    "lot_sqft_max": ("lotSize", "max"),
    "year_built_min": ("built", "min"),
    "year_built_max": ("built", "max"),
}

#: The tool's property vocabulary, and the flag Zillow uses for each. The filter works by exclusion:
#: to search for houses only, every other flag is turned off. So a query naming types is expressed
#: by switching off the ones it did not name, and a query naming none switches nothing off.
_HOME_TYPES: dict[str, str] = {
    "single_family": "isSingleFamily",
    "multi_family": "isMultiFamily",
    "townhouse": "isTownhouse",
    "condo": "isCondo",
    "land": "isLotLand",
    "farm": "isLotLand",
    "mobile": "isManufactured",
    "apartment": "isApartment",
}

#: What the tool's statuses look like in the filter. `for_sale` is the site's default and needs
#: nothing said; the others turn their own flag on and the for-sale ones off.
_STATUS_FLAGS: dict[str, dict[str, bool]] = {
    "for_sale": {},
    "pending": {"isPendingListingsSelected": True},
    "contingent": {"isPendingListingsSelected": True},
    "sold": {
        "isRecentlySold": True,
        "isForSaleByAgent": False,
        "isForSaleByOwner": False,
        "isNewConstruction": False,
        "isComingSoon": False,
        "isAuction": False,
        "isForSaleForeclosure": False,
    },
}


def endpoint() -> str:
    return os.environ.get(ENDPOINT_VARIABLE) or ENDPOINT


def _flag(value: bool) -> dict[str, bool]:
    return {"value": value}


def filter_state(query: SearchQuery, applies: frozenset[str]) -> dict[str, Any]:
    """The filters, built only from what the source declared it applies."""
    state: dict[str, Any] = {"sortSelection": {"value": "days"}}

    grouped: dict[str, dict[str, Any]] = {}
    for name, (filter_name, bound) in _RANGES.items():
        if name not in applies:
            continue
        value = getattr(query, name, None)
        if value is None:
            continue
        grouped.setdefault(filter_name, {})[bound] = value
    state.update(grouped)

    if "property_types" in applies and query.property_types:
        wanted = {str(kind) for kind in query.property_types}
        flags_on = {_HOME_TYPES[kind] for kind in wanted if kind in _HOME_TYPES}
        if flags_on:
            # Only switch off the ones this query did not ask for. A type the table does not know
            # switches nothing off, so an unrecognized name widens the search rather than emptying
            # it, and the caller filters it locally.
            for flag in set(_HOME_TYPES.values()) - flags_on:
                state[flag] = _flag(False)

    if "listing_status" in applies and query.listing_status:
        for flag, value in _STATUS_FLAGS.get(query.listing_status, {}).items():
            state[flag] = _flag(value)

    return state


def body(query: SearchQuery, box: BoundingBox, applies: frozenset[str]) -> dict[str, Any]:
    """The whole request. Map results, because one request is then a whole box."""
    return {
        "searchQueryState": {
            "pagination": {},
            "mapBounds": {
                "west": box.west,
                "east": box.east,
                "south": box.south,
                "north": box.north,
            },
            "isMapVisible": True,
            "isListVisible": True,
            "filterState": filter_state(query, applies),
        },
        "wants": {"cat1": ["mapResults"], "cat2": ["total"]},
        "requestId": 2,
    }


def headers() -> Mapping[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json"}
