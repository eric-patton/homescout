"""National records held a state at a time beside the database (feat-007 D-18).

Two providers answer from records rather than from a question per point: the flash-flood history,
because "which warnings ever covered here" is asked of a set, and the dams, because "which is
nearest" is. Both records are national and both are published a state at a time, so what they share
lives here and nothing else does:

- which states the store's properties are in, which is which states are worth holding;
- writing a file whole and moving it into place, so nothing ever reads half of one, and a move that
  Windows refuses (the server reading the file that moment) keeps the old file rather than failing;
- reading a held file back with its age, so a stale record is still used and still labelled stale,
  because last week's record of where it flooded is worth more than no record (AC-4, AC-7);
- one fetch, with the honest user agent, a pause between requests and one patient retry when a
  server says it is busy, because these are somebody else's servers being asked a favour;
- which loaded state a point is in, from the county outlines `ground.py` already keeps.

`datacenters.py`, `ground.py` and `wind.py` grew their own versions of some of this first and are
left as they are: rewriting three working modules is not what a flood change is for.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .provider import ProviderFailed
from .states import STATES

AGENT = "HomeScout (a personal house-search tool; one household)"
TIMEOUT_SECONDS = 180.0

#: The floor between two requests to these hosts, the same one second every provider is held to.
PAUSE_SECONDS = 1.0

#: How long to wait before the one retry a busy server gets.
BUSY_SECONDS = 20.0

#: What a fetch looks like to the code that uses one, so a test can hand in its own.
Fetcher = Callable[[str, str], bytes]

#: The most one answer may be. A year of New Mexico's warnings is about three megabytes; this is the
#: same ceiling the listing sources are held to, so a server that starts sending without end costs
#: a failure rather than the machine's memory.
LIMIT_BYTES = 64 * 1024 * 1024


class _SameHost(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same host over https, and nowhere else.

    A redirect is the server choosing where this machine goes next. These are public records on
    hosts named in configuration, and one that moves is a settings change, not a hop to wherever an
    answer points.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        was, now = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if now.scheme != "https" or now.hostname != was.hostname:
            raise urllib.error.HTTPError(newurl, code, "redirected elsewhere", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameHost)

_last = {"at": 0.0}
_turn = threading.Lock()


def fetch(url: str, what: str) -> bytes:
    """One request, paced, retried once if the server says it is busy, or a failure naming it."""
    for attempt in (1, 2):
        with _turn:
            # The floor, plus up to half again at random, so two passes never fall into step.
            spacing = PAUSE_SECONDS * (1.0 + random.random() * 0.5)  # noqa: S311 - not security
            wait = spacing - (time.monotonic() - _last["at"])
            if wait > 0:
                time.sleep(wait)
            _last["at"] = time.monotonic()
        request = urllib.request.Request(  # noqa: S310 - the address is this tool's own configuration
            url, headers={"User-Agent": AGENT, "Accept": "*/*"}
        )
        try:
            with _opener.open(request, timeout=TIMEOUT_SECONDS) as answer:
                body = answer.read(LIMIT_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if attempt == 1 and exc.code in (429, 502, 503, 504):
                time.sleep(BUSY_SECONDS)
                continue
            raise ProviderFailed(f"{what}: the public record answered {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderFailed(f"{what}: the public record did not answer ({exc})") from None
        if len(body) > LIMIT_BYTES:
            raise ProviderFailed(f"{what}: the answer was larger than this tool will read")
        return body
    raise ProviderFailed(f"{what}: the public record stayed busy")  # pragma: no cover


def write(where: Path, held: Any, *, now: datetime | None = None) -> None:
    """Keep `held` at `where`, whole or not at all."""
    where.parent.mkdir(parents=True, exist_ok=True)
    # A name of its own, so two writers at once (a pass and the server) never share a half file.
    beside = where.with_name(f".{where.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.part")
    stamp = (now or datetime.now(UTC)).isoformat()
    beside.write_text(json.dumps({"fetched_at": stamp, "held": held}), encoding="utf-8")
    try:
        beside.replace(where)
    except OSError:
        # Windows will not replace a file another process has open, and the server reads these.
        # The old file is still whole and still labelled with its own age, which is the right
        # thing for a reader to get; the next pass tries again.
        beside.unlink(missing_ok=True)


def read(where: Path, *, now: datetime | None = None) -> tuple[Any, float] | None:
    """What is held at `where` and how many days old it is, or None when nothing readable is."""
    if not where.is_file():
        return None
    try:
        found = json.loads(where.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(str(found["fetched_at"]))
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        return None
    held = found.get("held")
    if not isinstance(held, list):
        # A file in a shape this build did not write is not a record; it reads as nothing held.
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    age = ((now or datetime.now(UTC)) - when).total_seconds() / 86_400
    return held, age


def plain(value: object, longest: int) -> str:
    """Words from somebody else's server made safe to keep: one line, no control characters.

    Bounded, shown as text and only as text, and also read by the optional assessment model, which
    is why a newline or a control character does not survive into the record.
    """
    text = "".join(ch if ch.isprintable() else " " for ch in str(value or ""))
    return " ".join(text.split())[:longest]


def store_states(store: Any) -> tuple[str, ...]:
    """The states the store's properties are in, as two-letter codes this tool knows.

    Read from what the sources reported rather than worked out from coordinates, which costs one
    query. A property whose source wrote the state wrongly is a property this record may not cover,
    and reads as missing rather than as a zero (AC-47).
    """
    import sqlite3

    try:
        rows = store.connection.execute(
            "SELECT DISTINCT upper(trim(state)) FROM listing_snapshots "
            "WHERE state IS NOT NULL AND length(trim(state)) = 2"
        ).fetchall()
    except sqlite3.OperationalError:
        # A database from before snapshots existed holds no states. Only that: a broader catch
        # here once hid a wiring mistake that left every property in every state unanswered.
        return ()
    return tuple(sorted(code for (code,) in rows if code in STATES))


class Outlines:
    """Which of a handful of states a point is in, from county outlines already kept on disk.

    The outlines are drawn to about a kilometre (`ground.DETAIL`), so a point within a kilometre of
    a state line can land on the wrong side. That costs a property right on a border its values,
    read as missing, which is the honest failure; it never makes one state's record answer for
    another.
    """

    def __init__(self, shapes: dict[str, Any]) -> None:
        from shapely.prepared import prep

        self._shapes = {state: prep(shape) for state, shape in shapes.items()}

    @classmethod
    def of(cls, root: Path, service: str, states: Iterable[str]) -> Outlines:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        from . import ground

        shapes: dict[str, Any] = {}
        for state in states:
            try:
                counties = ground.counties(root, service, state)
            except Exception:  # noqa: BLE001 - one state's outline, not the whole record
                continue
            parts = []
            for county in counties:
                for ring in county.get("outline") or []:
                    if len(ring) >= 3:
                        polygon = Polygon([(point[1], point[0]) for point in ring])
                        parts.append(polygon if polygon.is_valid else polygon.buffer(0))
            if parts:
                shapes[state] = unary_union(parts)
        return cls(shapes)

    def state_of(self, latitude: float, longitude: float) -> str | None:
        from shapely.geometry import Point

        here = Point(longitude, latitude)
        for state, shape in self._shapes.items():
            if shape.contains(here):
                return state
        return None

    def states(self) -> tuple[str, ...]:
        return tuple(sorted(self._shapes))
