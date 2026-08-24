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
from typing import Any, Protocol, runtime_checkable

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
    """Where matches waiting for a human live.

    Five things, in two groups. The first three are what a surface does with a queue: read it, look
    at one, answer one. The last two are what fills it, and they are on the same protocol rather
    than on a second one because a queue that cannot be filled is not a queue.
    """

    def pending(self) -> tuple[AmbiguousMatch, ...]: ...

    def get(self, match_id: str) -> AmbiguousMatch: ...

    def record(self, match_id: str, verdict: str, merged_listing_id: str | None) -> None:
        """Note that a human decided this one, so nothing queues it again."""
        ...

    def offer(self, queued: Any) -> AmbiguousMatch | None:
        """Put a pair in front of a person, unless one has already ruled on it."""
        ...

    def clear(self) -> None:
        """Forget the questions, keeping every answer.

        A run works its own questions out from what it observed, so carrying last night's forward
        would show a person a pair whose evidence has since changed.
        """
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

    def offer(self, queued: Any) -> AmbiguousMatch | None:
        """Accept a pair, so that a test can drive the real merge pass against this.

        The identity is the sorted pair, matching the real queue, so the same pair offered twice is
        one question rather than two.
        """
        identifier = ",".join(sorted(set(queued.listing_ids)))
        if identifier in self.verdicts:
            return None
        match = AmbiguousMatch(
            id=identifier,
            listing_ids=tuple(sorted(set(queued.listing_ids))),
            agreed=tuple(getattr(queued, "agreed", ())),
            conflicted=tuple(getattr(queued, "conflicted", ())),
        )
        self.matches[identifier] = match
        return match

    def clear(self) -> None:
        self.matches.clear()

    def filled(self) -> None:
        """Nothing to do: this queue is told its contents rather than working them out."""


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
    """The queue this installation uses.

    A registered one wins, which is how a test substitutes it. Otherwise the real one, backed by the
    database, which works its questions out from what is recorded rather than reading them from a
    table: a stored question can go stale, and a stale question is one nobody can answer.
    """
    if _FACTORY is not None:
        return _FACTORY(store)
    from .merge.queue import StoreQueue
    from .store import Store

    return StoreQueue(store) if isinstance(store, Store) else InMemoryQueue(())
