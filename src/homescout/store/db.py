"""Opening the database, and turning its failures into things a person can act on."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from .errors import HistoryIsAppendOnlyError, StoreLockedError

DEFAULT_TIMEOUT_SECONDS = 10.0


_clock_lock = Lock()
_last_issued = ""


def utc_now() -> str:
    """The current time, as ISO-8601 UTC text, never the same value twice.

    Text rather than a number so the values are readable when someone opens the file directly, and
    UTC always so that lexicographic order is chronological order. Nothing local is ever stored,
    which is what makes a run spanning a daylight-saving transition unremarkable.

    The strictly-increasing part is deliberate. A listing's timeline has to distinguish the moment
    it vanished from the moment it came back, and two events recorded microseconds apart would
    otherwise share a timestamp and become one indistinguishable smear. When the clock has not
    moved since the last call, this advances by the smallest step the format can express.

    This holds within one process, which is where consecutive events are actually written. Two
    processes writing in the same microsecond would still collide; nothing in this product
    records two events for one listing from two processes at once.
    """
    global _last_issued
    with _clock_lock:
        candidate = to_utc_text(datetime.now(UTC))
        if candidate <= _last_issued:
            candidate = _next_after(_last_issued)
        _last_issued = candidate
        return candidate


def to_utc_text(moment: datetime) -> str:
    """Render a datetime the way this store stores time. Naive input is treated as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _next_after(stamp: str) -> str:
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return to_utc_text(moment + timedelta(microseconds=1))


def connect(
    path: str | Path,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    shared: bool = False,
) -> sqlite3.Connection:
    """Open the database file, creating the directory if needed.

    Write-ahead logging and an explicit busy timeout, because on the target platform the browser
    interface and a scheduled command routinely hold this file at the same time, and the default
    behavior there is to fail immediately.

    `shared` lifts SQLite's own refusal to be used from a thread other than the one that opened it.
    **It is only safe when the caller serializes access**, and there is exactly one caller that
    does: the browser interface, where a web server hands requests to worker threads and holds a
    lock around every one of them. Everything else in this product is one thread, leaves this alone,
    and keeps SQLite's check as a real guard rather than a formality.
    """
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(path), timeout=timeout, isolation_level=None, check_same_thread=not shared
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA does not accept a bound parameter, and this value is always an int we produced.
    conn.execute(f"PRAGMA user_version = {int(version)}")


@contextmanager
def translating_errors(
    path: str | Path, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> Iterator[None]:
    """Turn SQLite's own wording into something worth showing a user.

    "database is locked" tells a person nothing about what to do. On the target platform the answer
    is almost always "your browser interface is open", so say that.
    """
    try:
        yield
    except sqlite3.IntegrityError as exc:
        message = str(exc)
        if "append-only" in message or "never deleted" in message or "are fixed" in message:
            raise HistoryIsAppendOnlyError(
                f"Refused an attempt to rewrite recorded history: {message}. "
                f"Recorded observations are never edited; corrections are written as new rows."
            ) from exc
        raise
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise StoreLockedError(str(path), timeout) from exc
        raise


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a unit of work atomically.

    A failure part-way leaves the database exactly as it was, so the previous completed run is
    always still a usable comparison baseline.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
