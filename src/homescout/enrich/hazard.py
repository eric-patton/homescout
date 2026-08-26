"""Pictures of the hazard layers, fetched by this machine and kept.

The map that puts properties on the fire model needs the fire model drawn. The obvious way is to
let the browser ask the federal server for it, and that way does not work and should not: Chrome
refuses a cross-origin image it was not clearly offered (`ERR_BLOCKED_BY_ORB`), and, more to the
point, it would make the browser talk to a server nothing else in this tool makes it talk to. This
product's privacy statement lists what goes out and from where. So the tiles come the way every
other public fact about a location does: this machine asks, and keeps the answer.

Two things make that polite as well as possible.

**Every tile is kept.** The model behind it is republished every few years, which is why the
wildfire provider's own answers last five. A tile already fetched is read off the disk, so looking
at the same part of New Mexico twice costs nothing at all, and the second person to open the map
pays for none of it.

**A few at a time.** Not the one-second spacing the providers use, which would take half a minute
to draw one screen, and not as fast as the browser would like either. A handful at once, which is
what a person panning a map actually generates and what any map client would send.
"""

from __future__ import annotations

import hashlib
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..errors import InvalidInput
from .provider import ProviderFailed

#: How many tiles this machine will ask for at once.
AT_ONCE = 4

#: How long to wait for one.
TIMEOUT_SECONDS = 30.0

#: Said on every request, because a server has a right to know who is asking.
AGENT = "HomeScout (a personal house-search tool; one household)"

_room = threading.Semaphore(AT_ONCE)


def _named(bbox: str, size: str) -> str:
    return hashlib.sha256(f"{bbox}|{size}".encode()).hexdigest()[:24] + ".png"


def rectangle(bbox: str) -> str:
    """The rectangle to draw, checked.

    Four numbers, and nothing else reaches a URL. The value arrives from a page and a page's
    values are never trusted: a rectangle is arithmetic, and what is not four numbers is not one.
    """
    parts = [part.strip() for part in (bbox or "").split(",")]
    if len(parts) != 4:
        raise InvalidInput("A rectangle is four numbers: left, bottom, right, top.")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        raise InvalidInput("A rectangle is four numbers: left, bottom, right, top.") from None
    return ",".join(repr(number) for number in numbers)


def dimensions(size: str) -> str:
    """How big a picture, checked and bounded. A page asking for a ten-thousand pixel tile is not
    drawing a map."""
    parts = [part.strip() for part in (size or "256,256").split(",")]
    if len(parts) != 2:
        raise InvalidInput("A size is two whole numbers: width and height.")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        raise InvalidInput("A size is two whole numbers: width and height.") from None
    if not all(1 <= number <= 1024 for number in numbers):
        raise InvalidInput("A tile is between one and 1024 pixels on a side.")
    return ",".join(str(number) for number in numbers)


def tile(root: Path, service: str, layer: str, bbox: str, size: str = "256,256") -> bytes:
    """One picture of one rectangle, from the disk if it is there and from the service if not."""
    where = Path(root) / "tiles" / layer
    kept = where / _named(bbox, size)
    if kept.is_file():
        return kept.read_bytes()

    query = urllib.parse.urlencode(
        {
            "bbox": bbox,
            "bboxSR": "3857",
            "imageSR": "3857",
            "size": size,
            "format": "png32",
            "transparent": "true",
            "f": "image",
        }
    )
    request = urllib.request.Request(  # noqa: S310 - the address is this tool's own configuration
        f"{service}?{query}", headers={"User-Agent": AGENT, "Accept": "image/png,image/*"}
    )
    with _room:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:  # noqa: S310
                kind = (answer.headers.get("Content-Type") or "").split(";")[0].strip()
                body = answer.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderFailed(f"{layer}: the map service did not answer ({exc})") from None

    if kind != "image/png":
        # An ArcGIS service answers an unusable request with a JSON error and a 200, so the only
        # honest test is what came back rather than what the status said.
        raise ProviderFailed(f"{layer}: the map service answered with {kind or 'nothing'}, not a "
                             "picture. The layer has probably moved.")

    where.mkdir(parents=True, exist_ok=True)
    # Written beside and moved into place, so a half-written tile is never read as a whole one.
    beside = kept.with_suffix(".part")
    beside.write_bytes(body)
    beside.replace(kept)
    return body
