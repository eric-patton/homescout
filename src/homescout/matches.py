"""Property matches a machine would not decide on its own.

Non-negotiable 6: an ambiguous merge is flagged for a human, never guessed. Deciding that two
records describe one house is address matching's job (feat-006), and so is keeping the queue those
decisions are drawn from. What lives here is the shape both surfaces work against, so that
reviewing the queue from a terminal and reviewing it in a browser are one operation rather than two
implementations of a judgment call.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .errors import InvalidInput


@dataclass(frozen=True, slots=True)
class AmbiguousMatch:
    """Two or more records that might be one property, and why it is not obvious.

    `agreed` and `conflicted` are the signals as they were found: what lined up, and what did not.
    A person resolving this needs both, because "same street number, different city" and "same
    everything, different price" are not the same question.
    """

    id: str
    listing_ids: tuple[str, ...]
    agreed: tuple[str, ...] = ()
    conflicted: tuple[str, ...] = ()
    noticed_at: str | None = None


class UnknownMatch(InvalidInput):
    def __init__(self, match_id: str) -> None:
        super().__init__(f"There is no queued match with id {match_id!r}.")


@runtime_checkable
class MergeQueue(Protocol):
    """Where matches waiting for a human live."""

    def pending(self) -> tuple[AmbiguousMatch, ...]: ...

    def get(self, match_id: str) -> AmbiguousMatch: ...

    def record(self, match_id: str, verdict: str, merged_listing_id: str | None) -> None:
        """Note that a human decided this one, so nothing queues it again."""
        ...


class InMemoryQueue:
    """A queue with nothing behind it.

    Correct for a build with no address matching in it: there is nothing to queue, so the queue is
    empty, which is a different fact from the review being unavailable.
    """

    def __init__(self, matches: Iterable[AmbiguousMatch] = ()) -> None:
        self.matches: dict[str, AmbiguousMatch] = {m.id: m for m in matches}
        self.verdicts: dict[str, tuple[str, str | None]] = {}

    def pending(self) -> tuple[AmbiguousMatch, ...]:
        return tuple(m for m in self.matches.values() if m.id not in self.verdicts)

    def get(self, match_id: str) -> AmbiguousMatch:
        try:
            return self.matches[match_id]
        except KeyError:
            raise UnknownMatch(match_id) from None

    def record(self, match_id: str, verdict: str, merged_listing_id: str | None) -> None:
        self.verdicts[match_id] = (verdict, merged_listing_id)


#: How a queue is built for a store. Address matching registers the one that persists.
QueueFactory = Callable[[object], MergeQueue]

_FACTORY: QueueFactory | None = None


def register_queue(factory: QueueFactory) -> None:
    global _FACTORY
    _FACTORY = factory


def unregister_queue() -> None:
    global _FACTORY
    _FACTORY = None


def default_queue(store: object) -> MergeQueue:
    return _FACTORY(store) if _FACTORY is not None else InMemoryQueue(())
