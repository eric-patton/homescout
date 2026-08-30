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


def assess_search(
    store: Any,
    definition: Any,
    *,
    root: Any,
    limit: int | None = None,
    session: Any = None,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome:
    """Assess one saved search's properties, assembling everything the request needs.

    Here rather than in `api` because two callers need it and only one of them is a surface: a
    person asking for a pass, and a run that was told to assess what it found. Left in `api`, the
    second would have had to reach across into the first, or duplicate it, and duplicated assembly
    is how the pass a run does drifts from the pass a person asks for.

    Everything it reaches for is below it. `store` for the rows and the photographs, `enrich` for
    the hazard picture and the wind, `extract` for the account and the pacing. Nothing above.
    """
    from ..enrich import settings as enrich_settings
    from ..enrich import wind as wind_module
    from ..enrich.hazard import dimensions, rectangle, tile
    from ..export import latest_run, rows_of
    from ..extract import settings as model_settings
    from ..extract.notes import read as read_notes
    from ..extract.pass_ import _session
    from . import criteria as criteria_module
    from . import surroundings as around

    say = progress or (lambda _message: None)

    try:
        account = model_settings.account(root)
    except model_settings.ExtractionMisconfigured as exc:
        # Before anything is sent. Invariant 9 at the point of use: an installation with no model
        # configured is not broken, it simply does not have this.
        return PassOutcome(skipped=str(exc))

    name = definition.name
    rows = list(rows_of(store, latest_run(store, name), root=root))
    in_play = [row for row in rows if _still_deciding(store, row)]

    kept, passed = criteria_module.examples_from(rows)
    written = read_notes(root, definition)
    criteria = criteria_module.criteria_for(
        definition,
        notes=[n for n in (written.everywhere, written.search) if n],
        kept=kept,
        passed=passed,
    )

    already = store.assessed_fingerprints([row.listing_id for row in in_play])
    stations = _stations_for(root, rows)
    hazard_service = enrich_settings.picture_of("wildfire")

    def pictures_for(row: Any, dossier: Dossier) -> list[tuple[str, bytes]]:
        found: list[tuple[str, bytes]] = []
        path = store.preview_image_path(row.listing_id)
        if path is not None and path.is_file():
            found.append(("the listing's own photograph", path.read_bytes()))
        if dossier.has_place and hazard_service:
            try:
                box = around.bbox_around(dossier.latitude, dossier.longitude)
                found.append((
                    around.HAZARD_CAPTION,
                    tile(root, hazard_service, "wildfire", rectangle(box), dimensions(around.TILE)),
                ))
            except Exception:  # noqa: BLE001 - a missing picture is not a failed assessment
                pass
        return found

    def wind_for(dossier: Dossier) -> Mapping[str, Any] | None:
        if not dossier.has_place or not stations:
            return None
        near = around.nearest_station(dossier.latitude, dossier.longitude, stations)
        if near is None:
            return None
        station, miles = near
        try:
            found = wind_module.rose(
                root,
                enrich_settings.endpoint("wind").url,
                str(station["network"]),
                str(station["station"]),
                around.SEASON,
            )
        except Exception:  # noqa: BLE001 - a pass without wind is still a pass
            return None
        return around.wind_from(found.document(), station, miles)

    def record(listing_id: str, found: Any, mark: str) -> None:
        store.record_assessment(
            listing_id,
            model=found.model or account.model,
            fingerprint=mark,
            fit=found.fit,
            seen=found.seen,
            concerns=[
                {
                    "about": c.about,
                    "detail": c.detail,
                    "severity": c.severity,
                    "evidence_kind": c.evidence_kind,
                    "evidence": c.evidence,
                }
                for c in found.concerns
            ],
            before_visiting=found.before_visiting,
            could_not_tell=found.could_not_tell,
        )

    return run_pass(
        in_play,
        account=account,
        criteria=criteria,
        session=session or _session(),
        already=already,
        pictures_for=pictures_for,
        wind_for=wind_for,
        record=record,
        limit=limit,
        progress=say,
    )


def _still_deciding(store: Any, row: Any) -> bool:
    """Is this property still in play?

    Not passed on, still observed, still for sale. The set is what makes the whole feature
    affordable: on this workspace it is 155 of the 951 the latest run found.
    """
    if store.judgment_of(row.listing_id) == "pass":
        return False
    if getattr(row, "presence", "observed") != "observed":
        return False
    status = getattr(row.fields, "listing_status", None)
    return not status or str(status).lower() in ("for_sale", "for sale", "active")


def _stations_for(root: Any, rows: Sequence[Any]) -> list[dict[str, Any]]:
    """Every weather station in the states these properties are in, asked for once.

    The states come from the properties rather than from the search's name or its areas, which is
    the rule the map already follows: a search called `nm-statewide` that turned up something over
    the Colorado line needs Colorado's stations too.
    """
    from ..enrich import settings as enrich_settings
    from ..enrich import wind as wind_module

    states = {
        str(getattr(row.fields, "state", "") or "").strip().upper()
        for row in rows
    }
    found: list[dict[str, Any]] = []
    for state in sorted(s for s in states if len(s) == 2):
        try:
            found.extend(
                wind_module.stations(
                    root,
                    enrich_settings.endpoint("wind_stations").url,
                    wind_module.network_for(state),
                )
            )
        except Exception:  # noqa: BLE001 - one state failing is not the pass failing
            continue
    return found


def enabled_for(definition: Any) -> bool:
    """Has this saved search asked a run to assess what it finds? Absent means no."""
    return bool(getattr(definition, "model_assessment", False))


def for_run(
    store: Any,
    definition: Any,
    *,
    root: Any,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome | None:
    """The assessment as a run performs it, or nothing when the search did not ask for one.

    `None` rather than an empty outcome, so a caller can tell "off" from "on and found nothing to
    do", which are different things to report and different things to fix. The same shape the
    extraction pass uses, and off is the default, which is invariant 9.
    """
    if not enabled_for(definition):
        return None
    return assess_search(store, definition, root=root, progress=progress)
