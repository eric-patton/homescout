"""The merge pass: compare everything, then decide, then act. In that order and no other.

The order is the whole design and it is worth reading before the code.

**Nothing is merged until every candidate pair has been compared.** Merging as you go makes the
result depend on which pair you happened to look at first, which fails the spec's order-independence
requirement outright, and it does something worse: matches chain. A row from one source matches a
row from another, that row matches a third, and the first and third may not match each other at all.
Merging pair by pair fuses all three anyway, and nothing in the output ever says so.

So: compare every pair, build the groups the matches imply, and **merge a group only when every pair
inside it agreed**. A group with a disagreement anywhere in it is one question for a person, naming
every row in it, rather than two merges and a mystery.

**A person's decision is consulted before any of that.** It outranks every signal, in both
directions, for as long as the database exists, and a pair somebody has ruled on never comes back.
Evidence that turns up later and disagrees with a decision is recorded and shown; it changes
nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from ..store import Store, pair_key
from .address import of as address_of
from .candidates import pairs as candidate_pairs
from .compare import Outcome, outcome_for
from .queue import Queued, StoreQueue
from .signals import Candidate, Signals

#: What a merge this pass performed records as its reason, so provenance says which rule joined
#: two rows rather than only that something did.
AUTOMATIC = "address and coordinates agreed"
BY_PARCEL = "the same parcel number"


@dataclass(frozen=True, slots=True)
class Decided:
    """One pair, compared."""

    one: str
    other: str
    outcome: Outcome
    signals: Signals
    #: Set when a person had already ruled on this pair, in which case the outcome is theirs.
    by_person: bool = False
    #: What the signals alone would have said. Kept even when a person overruled it, because the
    #: disagreement between the two is exactly what a contradiction is.
    automatic: Outcome | None = None


@dataclass
class PassOutcome:
    """What the pass did, in the terms the digest and a person both want."""

    compared: int = 0
    merged: list[tuple[str, ...]] = field(default_factory=list)
    queued: list[tuple[str, ...]] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    honored: int = 0

    @property
    def waiting(self) -> int:
        return len(self.queued)


def candidates_from(store: Store) -> list[Candidate]:
    """Every live canonical listing, as the comparison sees it."""
    return [
        Candidate(
            listing_id=listing_id,
            address=address_of(snapshot.fields),
            latitude=snapshot.fields.latitude,
            longitude=snapshot.fields.longitude,
            parcel=snapshot.fields.parcel_number or "",
        )
        for listing_id, snapshot in sorted(store.latest_snapshots().items())
    ]


def _decide_pair(
    one: Candidate,
    other: Candidate,
    standing: dict[str, Any],
    *,
    limit: float | None,
) -> Decided:
    """One pair, with a person's answer preferred over anything this code can work out."""
    outcome, signals = outcome_for(one, other, limit=limit)
    decision = standing.get(pair_key((one.listing_id, other.listing_id)))
    if decision is None:
        return Decided(one.listing_id, other.listing_id, outcome, signals)

    # A person has ruled on this pair. Their answer stands whatever the signals now say, which is
    # the whole point of recording it, and the disagreement (if any) is surfaced elsewhere.
    settled: Outcome = "matched" if decision.same else "distinct"
    return Decided(
        one.listing_id, other.listing_id, settled, signals, by_person=True, automatic=outcome
    )


def _groups(matched: list[tuple[str, str]]) -> list[set[str]]:
    """The connected components of the agreements, which is what a merge is a candidate for."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for one, other in matched:
        a, b = find(one), find(other)
        if a != b:
            parent[b] = a

    found: dict[str, set[str]] = {}
    for node in parent:
        found.setdefault(find(node), set()).add(node)
    return [group for group in found.values() if len(group) > 1]


def run_pass(
    store: Store,
    *,
    queue: StoreQueue | None = None,
    run_id: str | None = None,
    limit: float | None = None,
    merging: bool = True,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome:
    """Compare everything, merge what agrees completely, and ask about the rest.

    With `merging` off it compares and asks and joins nothing, which is how the review queue works
    out its own questions when somebody opens it in a fresh process. The questions are derived from
    what is in the database rather than stored, so they can never be stale; the answers are stored,
    because an answer that could go stale would be a person's judgment lost.
    """
    review = queue if queue is not None else StoreQueue(store)
    review.clear()
    # A queue that works its own questions out needs telling that they have just been worked
    # out. One that is simply told its contents has nothing to do here.
    filled = getattr(review, "filled", None)
    if callable(filled):
        filled()
    standing = store.merge_decisions()
    outcome = PassOutcome()

    held = candidates_from(store)
    decided: dict[tuple[str, str], Decided] = {}
    for one, other in candidate_pairs(held):
        found = _decide_pair(one, other, standing, limit=limit)
        decided[(found.one, found.other)] = found
        outcome.compared += 1
        outcome.honored += int(found.by_person)
        if found.by_person and merging:
            _note_contradiction(store, found, outcome, run_id)

    matched = [(d.one, d.other) for d in decided.values() if d.outcome == "matched"]
    merged_ids: set[str] = set()

    for group in _groups(matched):
        members = sorted(group)
        if _complete(members, decided):
            if merging:
                signal = _signal_for(members, decided)
                store.supersede(members, join_signal=signal, decided_by="automatic")
                if progress is not None:
                    progress(f"merged {len(members)} records into one property")
            outcome.merged.append(tuple(members))
            merged_ids.update(members)
        else:
            # A group with a disagreement anywhere in it is one question, not several. This is the
            # spec's duplex edge case and its "matches more than one existing record" criterion,
            # both landing in the same place because they are the same situation.
            _offer(review, members, decided, outcome)
            merged_ids.update(members)

    for found in decided.values():
        if found.outcome != "ambiguous":
            continue
        if found.one in merged_ids or found.other in merged_ids:
            continue
        _offer(review, [found.one, found.other], decided, outcome)

    return outcome


def _complete(members: Sequence[str], decided: dict[tuple[str, str], Decided]) -> bool:
    """Did every pair inside this group agree?

    Every pair, not just the ones that formed the chain. A group of three where two pairs matched
    and the third was never compared, or came back distinct, is not three views of one property: it
    is a question. Requiring the group to be complete is what makes that true by construction rather
    than by hoping the comparison order was kind.
    """
    for one, other in combinations(members, 2):
        found = decided.get((one, other)) or decided.get((other, one))
        if found is None or found.outcome != "matched":
            return False
    return True


def _signal_for(members: Sequence[str], decided: dict[tuple[str, str], Decided]) -> str:
    """What to record as the reason these were joined, for the provenance to carry."""
    for one, other in combinations(members, 2):
        found = decided.get((one, other)) or decided.get((other, one))
        if found is None:
            continue
        if found.by_person:
            return "a person decided they are the same property"
        if found.signals.parcel == "agreed":
            return BY_PARCEL
    return AUTOMATIC


def _offer(
    review: StoreQueue,
    members: Sequence[str],
    decided: dict[tuple[str, str], Decided],
    outcome: PassOutcome,
) -> None:
    agreed: list[str] = []
    conflicted: list[str] = []
    for one, other in combinations(sorted(members), 2):
        found = decided.get((one, other)) or decided.get((other, one))
        if found is None:
            conflicted.append(f"{one} and {other} were never compared to each other")
            continue
        agreed.extend(found.signals.agreed)
        conflicted.extend(found.signals.conflicted)

    offered = review.offer(
        Queued(
            listing_ids=tuple(sorted(members)),
            agreed=tuple(dict.fromkeys(agreed)),
            conflicted=tuple(dict.fromkeys(conflicted)),
        )
    )
    if offered is not None:
        outcome.queued.append(tuple(sorted(members)))


def _note_contradiction(
    store: Store, found: Decided, outcome: PassOutcome, run_id: str | None
) -> None:
    """Evidence that disagrees with what a person decided.

    Recorded and surfaced; the merge state does not move. A decision is not overruled by evidence,
    it is questioned by it, and the difference matters: the person who answered this question knows
    something the signals do not, which is why they were asked.

    Which way the disagreement runs decides whether there is one. Somebody who said these are the
    same property is contradicted by a conflicting signal; somebody who said they are different is
    contradicted by the signals now agreeing. The other two combinations are the evidence and the
    person saying the same thing, which is not news.
    """
    said_same = found.outcome == "matched"
    if said_same and not found.signals.conflicted:
        return
    if not said_same and found.automatic != "matched":
        return

    detail = (
        "; ".join(found.signals.conflicted)
        if said_same
        else "; ".join(found.signals.agreed) or "the signals now say these are the same property"
    )
    store.record_contradiction((found.one, found.other), detail, run_id=run_id)
    outcome.contradictions.append(detail)
