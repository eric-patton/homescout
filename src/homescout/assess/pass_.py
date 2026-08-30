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
from .model import AssessmentFailed, ask, ask_in_favour

#: Seconds between requests, and the timeout, come from the model's own politeness. This pass adds
#: no second policy; see `model.PACING_KEY`.


@dataclass(frozen=True, slots=True)
class PassOutcome:
    """What one pass over a set of properties did."""

    considered: int = 0
    assessed: int = 0
    #: Read before, and asked one narrow question to fill in a section that did not exist when they
    #: were read. Counted apart from `assessed` because they are not the same spend and not the same
    #: claim: nothing about these properties was read again.
    topped_up: int = 0
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


def owed_a_section(store: Any, listing_ids: Sequence[str], model: str) -> dict[str, Any]:
    """Readings that still hold but were made before the favourable half of the question existed.

    Two conditions, and the second is the one that is easy to miss.

    `in_favour` is null for them. It is an empty list for a property that was asked and had nothing
    said for it, and that difference is the whole reason the column holds three states rather than
    two: only one of them is worth spending money on again.

    And the model that wrote the reading has to be the one configured now. A row carries one
    `model`, so a reading whose concerns came from one model and whose favourable points came from
    another cannot be labelled honestly: naming either makes the row claim work it did not do. Where
    they differ the property falls through to a full reading instead, which is the right answer
    anyway, because a different model would have found different concerns too.
    """
    found: dict[str, Any] = {}
    for listing_id, summary in store.assessment_summaries(list(listing_ids)).items():
        if summary.get("in_favour") is not None:
            continue
        held = store.assessment_of(listing_id)
        if held is not None and held.model == model:
            found[listing_id] = held
    return found


def run_pass(
    rows: Sequence[Any],
    *,
    account: Any,
    criteria: Any,
    session: Any,
    already: Mapping[str, str] | None = None,
    owed: Mapping[str, Any] | None = None,
    pictures_for: Callable[[Any, Dossier], list[tuple[str, bytes]]] | None = None,
    wind_for: Callable[[Dossier], Mapping[str, Any] | None] | None = None,
    record: Callable[[str, Any, str], None] | None = None,
    add: Callable[[str, tuple, Any], None] | None = None,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome:
    """Ask each of these properties only what it is still missing.

    Three answers, and which one a property gets is decided here rather than by a flag somebody has
    to remember:

    - Its assessment still describes it and is complete. Nothing is asked and nothing is spent.
    - Its assessment still describes it but was written before a section of the question existed.
      That section is asked for on its own and added beside what is already recorded. `owed` names
      these and carries the earlier reading; nothing about the property is read again, and no
      judgment already recorded is replaced.
    - Anything else: the whole question, which is a new property or one whose facts have moved.

    The narrow question exists because the alternative is not narrow. Adding a section to two
    hundred and sixty-eight finished readings by asking all of them the whole question again would
    pay for every part that was already answered, and would quietly replace concerns somebody may
    have read and acted on.

    Everything that reaches outside is injected: what pictures to send, where the wind comes from,
    and what to do with an answer. That is what lets the whole of this be tested without a model,
    a network or a store, and it is the same shape `extract`'s own pass uses.
    """
    say = progress or (lambda _message: None)
    known = dict(already or {})
    stated = criteria.stated()

    owing = dict(owed or {})
    wanted: list[tuple[Any, Dossier, str]] = []
    topping: list[tuple[Any, Dossier, str]] = []
    current = 0
    for row in rows:
        dossier = dossier_for(row)
        if wind_for is not None:
            wind = wind_for(dossier)
            if wind is not None:
                dossier = _with_wind(dossier, wind)
        mark = fingerprint_of(dossier, stated)
        if known.get(row.listing_id) == mark:
            if row.listing_id in owing and add is not None:
                topping.append((row, dossier, mark))
            else:
                current += 1
            continue
        wanted.append((row, dossier, mark))

    # The narrow questions go first when a limit cuts the pass short. They are the cheaper half and
    # they finish something already begun, where a full assessment starts something new.
    left_over = 0
    if limit is not None and len(topping) + len(wanted) > limit:
        left_over = len(topping) + len(wanted) - limit
        topping, wanted = topping[:limit], wanted[: max(0, limit - len(topping))]

    # Said before anything is asked, because this is the only operation in this product that costs
    # money per property and the number of requests is what somebody needs in order to say yes.
    say(
        f"assess: {len(wanted)} properties to ask about"
        + (f", {len(topping)} to add what is in their favour" if topping else "")
        + f", {current} already current"
        + (f", {left_over} left for a later pass" if left_over else "")
    )

    assessed = 0
    topped_up = 0
    failures: list[str] = []

    #: The fingerprint is not used here on purpose. A top-up is only ever offered to a reading
    #: whose fingerprint already matches, so the one to record is the one already recorded.
    for row, dossier, _mark in topping:
        pictures = pictures_for(row, dossier) if pictures_for is not None else []
        try:
            points = ask_in_favour(
                session, account, dossier, criteria, owing[row.listing_id], pictures
            )
        except AssessmentFailed as exc:
            failures.append(f"{row.listing_id}: {exc}")
            continue
        add(row.listing_id, points, owing[row.listing_id])
        topped_up += 1

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
        topped_up=topped_up,
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
    #: The ones read before the favourable half of the question existed. `in_favour` is null for
    #: them and an empty list for a property that was asked and had nothing said for it, which is
    #: the whole reason the column holds three states rather than two.
    #:
    #: Only where the model that wrote the reading is the one configured now. A row carries one
    #: `model`, so a reading whose concerns came from one model and whose favourable points came
    #: from another cannot be labelled honestly: naming either one makes the row claim work it did
    #: not do. Where they differ the property falls through to a full reading instead, which is the
    #: right answer anyway, because a different model would have found different concerns too.
    owed = owed_a_section(store, [row.listing_id for row in in_play], account.model)
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
            in_favour=[
                {
                    "about": one.about,
                    "detail": one.detail,
                    "evidence_kind": one.evidence_kind,
                    "evidence": one.evidence,
                }
                for one in (found.in_favour or ())
            ],
            before_visiting=found.before_visiting,
            could_not_tell=found.could_not_tell,
        )

    def add(listing_id: str, points: tuple, earlier: Any) -> None:
        """Write the earlier reading again with the missing section filled in.

        A new row rather than an edit, because this table is append-only and the row before it is
        how somebody sees what was added and when. Everything else is copied across untouched: this
        pass asked one narrow question and has no business changing an account or a concern.

        The date comes across too. The property was read then, from a dossier that has not moved
        since, and stamping today on it would say it was read again.
        """
        store.record_assessment(
            listing_id,
            model=earlier.model,
            fingerprint=earlier.fingerprint,
            made_at=earlier.made_at,
            fit=earlier.fit,
            seen=earlier.seen,
            concerns=list(earlier.concerns),
            in_favour=[
                {
                    "about": one.about,
                    "detail": one.detail,
                    "evidence_kind": one.evidence_kind,
                    "evidence": one.evidence,
                }
                for one in points
            ],
            before_visiting=earlier.before_visiting,
            could_not_tell=earlier.could_not_tell,
        )

    return run_pass(
        in_play,
        account=account,
        criteria=criteria,
        session=session or _session(),
        already=already,
        owed=owed,
        pictures_for=pictures_for,
        wind_for=wind_for,
        record=record,
        add=add,
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
