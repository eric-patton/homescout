"""Assessing everything still in play, and knowing what not to bother assessing again.

Two rules do most of the work here and both are about not spending money twice.

**In play is the set.** Found by the latest completed run, not passed on, not off the market. On
this workspace that is 155 properties out of 951 in the run and 1,328 in the store, which is the
difference between a pass somebody can afford and one they cannot.

**A fingerprint decides what is current.** An assessment records a digest of what it was made from,
and is current exactly while that digest still matches. The obvious alternative, reassessing when
the property changes, is wrong in the expensive direction: a live market moves a price every week
and a price has no bearing on whether the roof is metal or the arroyo runs behind the house.

What is deliberately outside the digest is the sample of kept and passed properties that calibrates
the model. It changes every time anybody passes on a house, so folding it in would mean one click
marking all 155 stale and paying for a full pass over a change nobody made to what they wanted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .dossier import Dossier, dossier_for
from .model import AssessmentFailed, ask

#: Seconds between requests, and the timeout, come from the model's own politeness. This pass adds
#: no second policy; see `model.PACING_KEY`.


@dataclass(frozen=True, slots=True)
class PassOutcome:
    """What one pass over a set of properties did."""

    considered: int = 0
    assessed: int = 0
    current: int = 0
    #: Named rather than dropped, which is the rule feat-009 already applies to a bounded pass.
    left_over: int = 0
    failures: tuple[str, ...] = ()
    skipped: str | None = None

    @property
    def degraded(self) -> bool:
        return bool(self.failures)


def fingerprint_of(dossier: Dossier, stated: Mapping[str, Any]) -> str:
    """A digest of everything this assessment would be made from.

    Order is fixed and the encoding is sorted, because a fingerprint that changes when a dictionary
    happens to iterate differently is a fingerprint that reassesses everything at random.

    The photograph is in it by identity rather than by content: a listing that swaps its picture is
    a listing worth looking at again, and hashing the bytes of every image on every pass to find out
    would cost more than the check saves.
    """
    material = {
        "description": dossier.description,
        # Sorted so that two runs over the same values agree.
        "enrichment": sorted((k, str(v)) for k, v in dossier.enrichment.items()),
        "recovered": sorted((k, str(v.get("value"))) for k, v in dossier.recovered.items()),
        "verdicts": sorted(dossier.verdicts),
        "place": [dossier.latitude, dossier.longitude],
        "criteria": stated,
    }
    encoded = json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()[:32]


def run_pass(
    rows: Sequence[Any],
    *,
    account: Any,
    criteria: Any,
    session: Any,
    already: Mapping[str, str] | None = None,
    pictures_for: Callable[[Any, Dossier], list[tuple[str, bytes]]] | None = None,
    wind_for: Callable[[Dossier], Mapping[str, Any] | None] | None = None,
    record: Callable[[str, Any, str], None] | None = None,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome:
    """Assess these properties, skipping the ones whose assessment still describes them.

    Everything that reaches outside is injected: what pictures to send, where the wind comes from,
    and what to do with an answer. That is what lets the whole of this be tested without a model,
    a network or a store, and it is the same shape `extract`'s own pass uses.
    """
    say = progress or (lambda _message: None)
    known = dict(already or {})
    stated = criteria.stated()

    wanted: list[tuple[Any, Dossier, str]] = []
    current = 0
    for row in rows:
        dossier = dossier_for(row)
        if wind_for is not None:
            wind = wind_for(dossier)
            if wind is not None:
                dossier = _with_wind(dossier, wind)
        mark = fingerprint_of(dossier, stated)
        if known.get(row.listing_id) == mark:
            current += 1
            continue
        wanted.append((row, dossier, mark))

    left_over = 0
    if limit is not None and len(wanted) > limit:
        left_over = len(wanted) - limit
        wanted = wanted[:limit]

    # Said before anything is asked, because this is the only operation in this product that costs
    # money per property and the number of requests is what somebody needs in order to say yes.
    say(
        f"assess: {len(wanted)} properties to ask about, {current} already current"
        + (f", {left_over} left for a later pass" if left_over else "")
    )

    assessed = 0
    failures: list[str] = []
    for row, dossier, mark in wanted:
        pictures = pictures_for(row, dossier) if pictures_for is not None else []
        try:
            found = ask(session, account, dossier, criteria, pictures)
        except AssessmentFailed as exc:
            failures.append(f"{row.listing_id}: {exc}")
            continue
        if record is not None:
            record(row.listing_id, found, mark)
        assessed += 1

    if failures:
        say(f"assess: {len(failures)} properties could not be assessed")
    if left_over:
        say(f"assess: {left_over} properties left for a later pass")

    return PassOutcome(
        considered=len(rows),
        assessed=assessed,
        current=current,
        left_over=left_over,
        failures=tuple(failures),
    )


def _with_wind(dossier: Dossier, wind: Mapping[str, Any]) -> Dossier:
    from dataclasses import replace

    return replace(dossier, wind=dict(wind))
