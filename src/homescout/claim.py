"""One run of a saved search at a time.

A scheduled task and a person at a terminal collide easily, and two runs of one search interleaving
their observations into the store would be a mess no later run could untangle. So a run claims its
saved search, and a second run declines rather than waiting: a scheduled task reads the precondition
code and tries again on its next tick, instead of queueing behind a manual run somebody left open
and then fetching the same listings twice.

The claim is an operating-system file lock rather than a file holding a process id, and the reason
is the one property a hand-rolled staleness rule cannot get right: the operating system releases the
lock when the holder dies for any reason, including being killed and including losing power. Any
timeout short enough to free a crashed run's claim is short enough to steal a slow one's, and a
paced run over a county is legitimately slow.

The first byte of the file is the lock. The holder's identity is written after it, in the part
nobody locks, so a process that could not take the lock can still say who has it.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .errors import PreconditionNotMet

#: Byte 0 is the lock and holds no data. Everything from byte 1 on is the holder's note about
#: itself, readable by a process that has just failed to take the lock.
_LOCK_BYTE = 1
_NOTE_OFFSET = 1
_NOTE_LIMIT = 4096

if sys.platform == "win32":  # pragma: no cover - the other branch is exercised on other platforms
    import msvcrt

    def _take(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, _LOCK_BYTE)

    def _release(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_BYTE)

else:  # pragma: no cover - not the primary platform
    import fcntl

    def _take(fd: int) -> None:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, _LOCK_BYTE, 0, os.SEEK_SET)

    def _release(fd: int) -> None:
        fcntl.lockf(fd, fcntl.LOCK_UN, _LOCK_BYTE, 0, os.SEEK_SET)


class RunInProgress(PreconditionNotMet):
    """Another run of this saved search is already going."""

    def __init__(self, search_name: str, holder: dict[str, object]) -> None:
        self.search_name = search_name
        self.holder = holder
        run_id = holder.get("run_id")
        started_at = holder.get("started_at")
        which = f"run {run_id}" if run_id else "a run that is just starting"
        when = f", started at {started_at}" if started_at else ""
        super().__init__(
            f"A run of {search_name!r} is already in progress ({which}{when}). "
            f"This one declined rather than waiting, so nothing was fetched. "
            f"Run it again once that one has finished."
        )


def claim_path(directory: Path, search_name: str) -> Path:
    """Where one saved search's claim lives.

    The name is slugged and then given a short digest of the original, because a saved search may be
    called anything a person can type and two different names must never share one claim.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", search_name.lower()).strip("-") or "search"
    digest = sha256(search_name.encode("utf-8")).hexdigest()[:8]
    return directory / "runs" / f"{slug[:40]}-{digest}.lock"


@dataclass
class Claim:
    """A held claim. Its note can be updated once the run it belongs to has an identifier."""

    path: Path
    search_name: str
    _fd: int

    def announce(self, **facts: object) -> None:
        """Rewrite the note about who is holding this claim."""
        note = json.dumps({"search": self.search_name, "pid": os.getpid(), **facts})
        payload = note.encode("utf-8")[: _NOTE_LIMIT - 1]
        os.lseek(self._fd, _NOTE_OFFSET, os.SEEK_SET)
        os.write(self._fd, payload)
        os.ftruncate(self._fd, _NOTE_OFFSET + len(payload))


def _read_note(fd: int) -> dict[str, object]:
    try:
        os.lseek(fd, _NOTE_OFFSET, os.SEEK_SET)
        raw = os.read(fd, _NOTE_LIMIT)
    except OSError:  # pragma: no cover - only if the holder is mid-write
        return {}
    try:
        found = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


@contextmanager
def claim_run(directory: Path, search_name: str, **facts: object) -> Iterator[Claim]:
    """Hold this saved search for the duration, or decline.

    Declining is immediate. There is no wait and no retry, by decision od-1.
    """
    path = claim_path(directory, search_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            _take(fd)
        except OSError:
            raise RunInProgress(search_name, _read_note(fd)) from None
        claim = Claim(path=path, search_name=search_name, _fd=fd)
        claim.announce(**facts)
        try:
            yield claim
        finally:
            _release(fd)
    finally:
        os.close(fd)
