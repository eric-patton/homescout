"""What internet a place can get, out of the FCC's own files rather than out of a service.

Every other provider in this feature is a function of a point: one address, one latitude and
longitude, one answer. Broadband was written that way too, and it could never have worked. Measured
against the live service on 2026-08-24, once there was a real token to measure with:

- The address the first build asked, `.../api/public/map/location`, answers **405 Method Not
  Available**. It is not an endpoint and never was.
- The public API is a **bulk file** API. It lists the quarters it has published, lists the files for
  one of them (eleven thousand of them), and hands over a zipped CSV.
- Authentication is two headers, `username` and `hash_value`. A token on its own is half a
  credential.
- The map's own per-location endpoint is closed to anything that is not the map, and the Fabric
  coordinates that would let anybody build a point query are licensed data.

So there is no point query to make, and this module is what to do instead. Every availability row
carries the census block it is in, and the FCC will name the census block for a point with no
credential at all. A state's files reduce to one row per block: the best advertised residential
speeds and who offers them. New Mexico is 47.5 MB, twenty-one seconds, and 60,287 blocks.

**Satellite is left out of the speed on purpose.** Three point three million of New Mexico's rows
are satellite, and all of them say the same thing: you can get satellite. Folding that in would
report every remote property as served at a hundred megabits while saying nothing whatever about
what it can actually get, which is product invariant 10's failure exactly. Fixed wireless is left
in, because that is the opposite case: it is what a rural property here really gets, and it varies
house to house.

**Nothing is extracted to disk.** The archive is read in memory, one member, streamed through a CSV
reader, and the only things kept out of it are two integers and a provider's name. Nothing from a
downloaded file becomes a path, a URL, or anything that runs.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..sources.errors import SourceError
from ..sources.politeness import PacedSession, Request

#: The file API. Configuration like every other address here, for the same reason (D-10).
API = "https://broadbandmap.fcc.gov/api/public/map"

#: The keyless service that turns a point into a census block. A different host, no credential, and
#: the only per-property request this provider makes.
BLOCKS = "https://geo.fcc.gov/api/census/block/find"

#: The pacing key. Its own, so downloading files does not spend the block service's budget.
PACING_KEY = "broadband"

#: Technology codes in the availability files, and what to call each in a sentence. Satellite is
#: deliberately absent: see the module docstring and D-13.
TERRESTRIAL: dict[str, str] = {
    "10": "copper",
    "40": "cable",
    "50": "fiber",
    "70": "fixed wireless",
    "71": "fixed wireless",
    "72": "fixed wireless",
}

#: `R` is residential, `X` is both. A row filed as business only is not an answer to "could I live
#: here and work", which is the question this column exists for.
RESIDENTIAL = ("R", "X")

#: A ceiling on any one downloaded file, so a malformed listing cannot ask for an unbounded read.
#: The largest state file measured was 22 MB uncompressed; this is room for an order of magnitude.
MOST_BYTES = 400 * 1024 * 1024


class BroadbandUnavailable(Exception):
    """The FCC would not give this build what it asked for. One refresh, never a run."""


@dataclass(frozen=True, slots=True)
class Service:
    """What one census block can get."""

    block: str
    state: str
    download_mbps: int | None
    upload_mbps: int | None
    providers: tuple[str, ...]
    as_of: str


def credentials(values: Mapping[str, str]) -> tuple[str, str] | None:
    """The account name and the token, or nothing at all when either is missing.

    Both or neither. The FCC wants two headers, and half a credential is not a configured provider:
    it is a person who will otherwise watch every request fail with a message about authentication
    and go looking for a problem with their token.
    """
    from .settings import BROADBAND_TOKEN, BROADBAND_USERNAME, token

    name = token(BROADBAND_USERNAME) if values is None else (values.get(BROADBAND_USERNAME) or "")
    key = token(BROADBAND_TOKEN) if values is None else (values.get(BROADBAND_TOKEN) or "")
    name, key = (name or "").strip(), (key or "").strip()
    return (name, key) if name and key else None


def headers(account: tuple[str, str]) -> dict[str, str]:
    """The two the FCC wants. Not a bearer token, which is what the first build assumed."""
    name, key = account
    return {"username": name, "hash_value": key, "Accept": "application/json"}


def _json(session: PacedSession, url: str, account: tuple[str, str]) -> Any:
    try:
        answer = session.request(PACING_KEY, Request(url=url, headers=headers(account)))
    except SourceError as exc:
        raise BroadbandUnavailable(f"the FCC refused {url}: {exc}") from None
    try:
        return json.loads(answer.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BroadbandUnavailable(f"the FCC's answer to {url} was not readable: {exc}") from None


def latest_quarter(session: PacedSession, account: tuple[str, str]) -> str:
    """The most recent quarter with availability data published."""
    found = _json(session, f"{API}/listAsOfDates", account).get("data") or []
    dates = [row.get("as_of_date") for row in found if row.get("data_type") == "availability"]
    dates = [held for held in dates if held]
    if not dates:
        raise BroadbandUnavailable(
            "the FCC listed no published availability data at all, which has not happened before "
            "and is more likely a change at their end than an empty quarter."
        )
    return max(dates)


def files_for(
    session: PacedSession, account: tuple[str, str], state: str, as_of: str
) -> list[dict[str, Any]]:
    """One state's fixed-broadband availability files, out of the eleven thousand published.

    Filtered on the state's whole-state files rather than the per-provider ones, which are the same
    data split four thousand ways.
    """
    from .states import fips_of, name_of

    fips, full = fips_of(state), name_of(state)
    listing = _json(session, f"{API}/downloads/listAvailabilityData/{as_of}", account)
    rows = listing.get("data") or []
    # The listing says FIPS and the full name; the rows inside the files say the two-letter code.
    # Match on either of the two the listing has, because which one it fills has moved before.
    wanted = [
        row
        for row in rows
        if (row.get("state_fips") == fips or row.get("state_name") == full)
        and row.get("category") == "State"
        and row.get("subcategory") == "Location Coverage"
        and row.get("technology_type") == "Fixed Broadband"
        and row.get("file_type") == "csv"
    ]
    if not wanted:
        raise BroadbandUnavailable(
            f"the FCC published no fixed-broadband files for {state.upper()} as of {as_of}."
        )
    return wanted


def rows_in(blob: bytes) -> Iterator[dict[str, str]]:
    """Every row of the one CSV inside a downloaded archive, without touching the disk."""
    with zipfile.ZipFile(io.BytesIO(blob)) as bundle:
        names = [name for name in bundle.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise BroadbandUnavailable("a downloaded file held no CSV")
        with bundle.open(names[0]) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))


def fold(rows: Iterator[dict[str, str]], into: dict[str, list[Any]]) -> None:
    """Reduce availability rows to the best residential service per census block.

    Satellite never reaches this, which is D-13 and is the reason the column means anything.
    """
    for row in rows:
        if row.get("technology") not in TERRESTRIAL:
            continue
        if (row.get("business_residential_code") or "") not in RESIDENTIAL:
            continue
        block = (row.get("block_geoid") or "").strip()
        if not block:
            continue
        held = into.setdefault(block, [0, 0, set()])
        held[0] = max(held[0], _speed(row.get("max_advertised_download_speed")))
        held[1] = max(held[1], _speed(row.get("max_advertised_upload_speed")))
        name = (row.get("brand_name") or "").strip()
        if name:
            held[2].add(name)


def _speed(raw: Any) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


def build(
    session: PacedSession,
    account: tuple[str, str],
    state: str,
    *,
    progress: Any = None,
) -> tuple[dict[str, list[Any]], str]:
    """One state's index, and the quarter it came from.

    Held in memory while it is built and handed to the caller to store. A state is tens of megabytes
    of download and a few tens of thousands of blocks, which is small enough to assemble whole and
    large enough that nobody should be doing it inside an enrichment pass (D-12).
    """
    say = progress or (lambda _message: None)
    as_of = latest_quarter(session, account)
    files = files_for(session, account, state, as_of)
    say(f"broadband: {len(files)} files for {state.upper()}, as of {as_of}")

    index: dict[str, list[Any]] = {}
    for number, row in enumerate(files, start=1):
        name = row.get("file_name") or row.get("file_id")
        try:
            answer = session.request(
                PACING_KEY,
                Request(
                    url=f"{API}/downloads/downloadFile/availability/{row['file_id']}",
                    headers=headers(account),
                ),
            )
        except SourceError as exc:
            raise BroadbandUnavailable(f"{name} could not be downloaded: {exc}") from None
        if len(answer.body) > MOST_BYTES:
            raise BroadbandUnavailable(
                f"{name} is {len(answer.body) / 1e6:.0f} MB, which is far past anything this has "
                "seen. Refusing to read it rather than filling memory with it."
            )
        fold(rows_in(answer.body), index)
        say(f"broadband: {number} of {len(files)}, {len(index):,} blocks so far")

    if not index:
        raise BroadbandUnavailable(
            f"{state.upper()}'s files held no residential terrestrial service at all, which is not "
            "a thing any state looks like. Something has changed in the file format."
        )
    return index, as_of


def store_index(
    store: Any, state: str, index: Mapping[str, list[Any]], as_of: str
) -> int:
    """Replace this state's rows with these. A cache, refreshed whole, never history."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rows = [
        (block, state.upper(), held[0] or None, held[1] or None,
         ", ".join(sorted(held[2])), as_of, now)
        for block, held in index.items()
    ]
    return store.record_broadband(state.upper(), rows)


def block_for(session: PacedSession, latitude: float, longitude: float) -> tuple[str, str]:
    """The census block a point is in, and its state. Keyless, and the only per-point request."""
    url = f"{BLOCKS}?latitude={latitude}&longitude={longitude}&format=json"
    try:
        answer = session.request(PACING_KEY, Request(url=url))
    except SourceError as exc:
        raise BroadbandUnavailable(
            f"the block for this point could not be looked up: {exc}"
        ) from None
    try:
        found = json.loads(answer.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BroadbandUnavailable(f"the block service's answer was not readable: {exc}") from None

    block = ((found.get("Block") or {}).get("FIPS") or "").strip()
    state = ((found.get("State") or {}).get("code") or "").strip().upper()
    if not block:
        raise BroadbandUnavailable(
            "the FCC could not say which census block this point is in, which happens for a point "
            "in open water or outside the United States."
        )
    return block, state or block[:2]
