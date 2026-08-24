"""The queue of pairs waiting on a person, kept in the database rather than in memory.

`homescout/matches.py` declared the shape of this before there was anything to put in it, and both
surfaces already work against that shape: `matches list` and `matches resolve` were written for
this feature and have been running against an empty queue since the command line shipped. This is
what fills it.

Two things it must never do, and both are non-negotiables rather than preferences. It must not lose
a decision (7), and it must not put a pair somebody has already ruled on back in front of them (6).
Both come out of the same table: a decision is recorded once, it is consulted before anything else,
and it is never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..matches import AmbiguousMatch, UnknownMatch
from ..store import Store, pair_key


@dataclass(frozen=True, slots=True)
class Queued:
    """A pair, and what the comparison found about it, on its way into the queue."""

    listing_ids: tuple[str, ...]
    agreed: tuple[str, ...] = ()
    conflicted: tuple[str, ...] = ()


class StoreQueue:
    """The real review queue.

    The questions are **derived** rather than stored. A queued pair is not history: it is a question
    that stops existing the moment somebody answers it, and one held in a table would go on being
    asked about two rows whose evidence has since changed. What *is* history is the answer, and that
    has its own append-only table.
    """

    def __init__(self, store: Store) -> None:
        self._store = store
        self._waiting: dict[str, AmbiguousMatch] = {}
        self._filled = False

    # -- what the port requires ---------------------------------------------

    def pending(self) -> tuple[AmbiguousMatch, ...]:
        """Every pair waiting on a person, decided ones removed.

        Worked out from what is in the database rather than read from a table, which is why
        `homescout matches list` in a fresh process sees what last night's run queued. A stored
        queue would be the alternative and would go stale: it would still be asking about two rows
        whose evidence has since changed, and a question nobody can answer any more is worse than
        no question.
        """
        self.refresh()
        settled = set(self._store.merge_decisions())
        return tuple(
            match
            for match in self._waiting.values()
            if pair_key(match.listing_ids) not in settled
        )

    def get(self, match_id: str) -> AmbiguousMatch:
        try:
            return self._waiting[match_id]
        except KeyError:
            raise UnknownMatch(match_id) from None

    def record(self, match_id: str, verdict: str, merged_listing_id: str | None) -> None:
        """Note that a person decided this one, so nothing queues it again.

        Written to the store, not to this object: a decision that lived only in memory would be a
        decision lost the next time the process exited, and losing a person's judgment is the one
        failure this tool cannot have.
        """
        match = self.get(match_id)
        self._store.record_merge_decision(
            match.listing_ids,
            "same" if verdict == "same" else "different",
            merged_id=merged_listing_id,
        )
        self._waiting.pop(match_id, None)

    # -- what the merge pass uses -------------------------------------------

    def offer(self, queued: Queued) -> AmbiguousMatch | None:
        """Put a pair in front of a person, unless one has already ruled on it.

        Returns None when the pair is already decided, which is AC-13: a pair with a recorded
        decision never comes back, however many runs later the same signals turn up again.
        """
        key = pair_key(queued.listing_ids)
        if key in self._store.merge_decisions():
            return None
        match = AmbiguousMatch(
            id=key,
            listing_ids=tuple(sorted(set(queued.listing_ids))),
            agreed=queued.agreed,
            conflicted=queued.conflicted,
            noticed_at=self._waiting[key].noticed_at if key in self._waiting else None,
        )
        self._waiting[key] = match
        return match

    def refresh(self) -> None:
        """Work out the questions, without deciding or merging anything.

        Cheap because the comparison is bucketed: a county's worth of rows produces a few hundred
        comparisons, not a few million.
        """
        if self._filled:
            return
        self._filled = True
        from .pass_ import run_pass

        run_pass(self._store, queue=self, merging=False)

    def filled(self) -> None:
        """Told by the pass that it has just populated this, so nothing recomputes it."""
        self._filled = True

    def waiting(self) -> int:
        """How many pairs are waiting on a person, which the digest reports."""
        return len(self.pending())

    def clear(self) -> None:
        """Forget the questions, keeping every answer.

        A run re-derives its own questions from what it observed, so carrying last night's forward
        would show a person a pair whose evidence has since changed. The decisions are in the
        database and are untouched by this.
        """
        self._waiting.clear()
        self._filled = False
