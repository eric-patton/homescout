"""One row of a Redfin download, turned into one property the tool understands.

The same two rules the other adapters are built on: a value the download does not carry stays empty,
and a value it carries in a shape we did not expect fails the whole query rather than becoming a row
with something quietly missing.

There is one thing here the other adapters do not have to deal with. This is a CSV written for a
spreadsheet, so every value is a string and an empty cell and a zero look almost alike. `''` is
absent; `'0'` is zero. Getting that backwards would record every property with no year built as
having been built in the year nothing.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Mapping
from typing import Any

from ...records import ListingFields, SourceRow
from ..errors import SourceFailed

#: The line the download carries in every region, whatever the local rules actually are. It is
#: boilerplate, not a signal, and the adapter reports it as a standing caveat rather than reading
#: anything into its presence.
MLS_NOTICE = (
    "In accordance with local MLS rules, some MLS listings are not included in the download"
)

#: The columns this adapter reads. A download missing one of them is a download whose shape has
#: changed, which is a failure rather than a row full of blanks.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "PROPERTY TYPE",
    "ADDRESS",
    "CITY",
    "STATE OR PROVINCE",
    "ZIP OR POSTAL CODE",
    "PRICE",
    "BEDS",
    "BATHS",
    "SQUARE FEET",
    "LOT SIZE",
    "YEAR BUILT",
    "DAYS ON MARKET",
    "STATUS",
    "LATITUDE",
    "LONGITUDE",
)

#: Redfin's names for what a property is, in the tool's vocabulary. A name not here is kept exactly
#: as the site wrote it.
PROPERTY_TYPES: dict[str, str] = {
    "single family residential": "single_family",
    "condo/co-op": "condo",
    "townhouse": "townhouse",
    "multi-family (2-4 unit)": "multi_family",
    "multi-family (5+ unit)": "multi_family",
    "vacant land": "land",
    "ranch": "farm",
    "mobile/manufactured home": "mobile",
    "timeshare": "other",
    "other": "other",
    "unknown": "",
}

#: And what it says about where a property is in its sale.
STATUSES: dict[str, str] = {
    "active": "for_sale",
    "coming soon": "for_sale",
    "pending": "pending",
    "contingent": "contingent",
    "sold": "sold",
}


def _column(row: Mapping[str, str], name: str) -> str:
    return (row.get(name) or "").strip()


def _as(kind: type, row: Mapping[str, str], name: str) -> Any:
    """Read one cell, or say precisely which column could not be read.

    An empty cell is absent, which is not the same as zero and must never become it.
    """
    raw = _column(row, name)
    if not raw:
        return None
    try:
        if kind is int:
            return int(float(raw))
        if kind is float:
            return float(raw)
        return raw
    except (TypeError, ValueError):
        raise SourceFailed(
            f"redfin: could not read the {name!r} column from {raw!r}. "
            "The download's columns have probably changed; no rows are returned rather than rows "
            "with a silently missing value."
        ) from None


def _known(table: Mapping[str, str], value: str | None) -> str | None:
    if not value:
        return None
    mapped = table.get(value.strip().lower())
    if mapped == "":
        return None
    return mapped if mapped is not None else value


def _url(row: Mapping[str, str]) -> str | None:
    """The listing's page. Its column name carries a whole sentence, so it is found by prefix."""
    for name, value in row.items():
        if name and name.upper().startswith("URL"):
            found = (value or "").strip()
            return found or None
    return None


def read(text: str) -> tuple[list[dict[str, str]], bool]:
    """The download, as rows, and whether it carried the site's standing MLS notice.

    Every download this adapter has seen carries a header, one notice line, and then the
    properties. The notice is not a property and is not an error; it is the site saying, in every
    region, that its download may be incomplete.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise SourceFailed(
            "redfin returned a download with no header row. "
            "That is what its block page and its error envelope both look like."
        )
    missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
    if missing:
        raise SourceFailed(
            f"redfin's download is missing the {', '.join(missing)} column(s). "
            "Its columns have changed; no rows are returned rather than rows with silently "
            "missing values."
        )

    notice = False
    rows: list[dict[str, str]] = []
    for row in reader:
        if MLS_NOTICE in " ".join(value or "" for value in row.values()):
            notice = True
            continue
        if not _column(row, "ADDRESS"):
            continue
        rows.append(dict(row))
    return rows, notice


def to_fields(row: Mapping[str, str]) -> ListingFields:
    return ListingFields(
        price=_as(int, row, "PRICE"),
        listing_status=_known(STATUSES, _column(row, "STATUS")),
        beds=_as(float, row, "BEDS"),
        baths=_as(float, row, "BATHS"),
        sqft=_as(int, row, "SQUARE FEET"),
        lot_sqft=_as(int, row, "LOT SIZE"),
        year_built=_as(int, row, "YEAR BUILT"),
        property_type=_known(PROPERTY_TYPES, _column(row, "PROPERTY TYPE")),
        address_line=_as(str, row, "ADDRESS"),
        city=_as(str, row, "CITY"),
        state=_as(str, row, "STATE OR PROVINCE"),
        postal_code=_as(str, row, "ZIP OR POSTAL CODE"),
        latitude=_as(float, row, "LATITUDE"),
        longitude=_as(float, row, "LONGITUDE"),
        listing_url=_url(row),
        days_on_market_source=_as(int, row, "DAYS ON MARKET"),
    )


def _identifier(row: Mapping[str, str]) -> str | None:
    """What this download calls this property.

    The listing number from the local multiple listing service, qualified by which service it came
    from, because two services can and do issue the same number. Without a source there is nothing
    stable to key on and the row is left unidentified, which the store handles.
    """
    number = _column(row, "MLS#")
    source = _column(row, "SOURCE")
    if number and source:
        return f"{source}:{number}"
    return number or None


def to_row(row: Mapping[str, str], *, fetched_at: str) -> SourceRow:
    """One row, carrying both the tool's reading of it and the download's own cells."""
    return SourceRow(
        source="redfin",
        fields=to_fields(row),
        payload=dict(row),
        source_listing_id=_identifier(row),
        fetched_at=fetched_at,
    )


def to_rows(rows: Iterator[Mapping[str, str]] | list[dict[str, str]], *, fetched_at: str):
    return tuple(to_row(row, fetched_at=fetched_at) for row in rows)
