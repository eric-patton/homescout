"""The model pass: which descriptions, which fields, and what happened.

It runs inside a run when the saved search turns it on, and on its own when somebody backfills a
store that predates the setting. Both go through here, because there is one right answer to "which
descriptions still need asking about" and it should not exist twice.

Three rules shape it, and each is a cost or a correctness problem the obvious version gets wrong:

**Distinct descriptions, not properties.** A county of five thousand properties is fewer distinct
descriptions than that, and the same description seen on a hundred nights is one question. The pass
reduces before it asks.

**Only what the patterns could not settle.** The deterministic baseline is free and runs first. The
model is asked about the fields it left empty on that text, and nothing else, so a market where
everybody writes "central heat and air" costs almost nothing.

**A failure is one description wide.** It is recorded with the credential taken out of it, the
deterministic values for that property stand untouched because they never involved a network, the
affected fields stay empty rather than being filled by a fallback, and the pass carries on. That is
the reliability minimum, and it is why a model outage costs six columns rather than a night.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..store import Store
from . import NAMES, cache, patterns, settings
from . import model as client
from . import notes as notes_for
from .text import Prose
from .text import read as read_prose


@dataclass(frozen=True, slots=True)
class PassOutcome:
    """What the pass did, in the same shape a run reports a source."""

    descriptions: int = 0
    distinct: int = 0
    #: Descriptions whose answers were already held, and which cost nothing.
    cached: int = 0
    asked: int = 0
    #: Field values recorded from what the model said.
    recorded: int = 0
    #: Answers that did not survive checking, with their reasons, so a model being rejected nine
    #: times in ten is visible rather than merely quiet.
    rejected: tuple[str, ...] = field(default_factory=tuple)
    failures: tuple[str, ...] = field(default_factory=tuple)
    truncated: int = 0
    #: Notes that were too long and were cut before being sent, by the name a person calls them.
    #: Separate from `truncated`, which counts descriptions: one is somebody else's writing being
    #: too long and the other is yours, and only one of them is worth telling you about.
    notes_truncated: tuple[str, ...] = field(default_factory=tuple)
    #: Set when the pass could not run at all: no search turned it on, or nothing configured it.
    skipped: str | None = None

    @property
    def degraded(self) -> bool:
        return bool(self.failures)


def _fields_left(prose: Prose) -> tuple[str, ...]:
    """The fields the deterministic patterns did not settle for this text.

    A conflicted field counts as settled. The description said two different things, and a model
    reading the same two sentences is not better placed to choose between them than the person who
    will see both quotes.
    """
    found = patterns.read(prose)
    return tuple(name for name in NAMES if name not in found)


def descriptions_in(
    store: Store, *, search: str | None = None
) -> list[tuple[str, Prose]]:
    """Every distinct description worth asking about, with one property id apiece.

    The id is carried only so a progress line can name something a person recognizes. Nothing about
    the property reaches a request.
    """
    if search is None:
        listings = [listing.id for listing in store.listings()]
    else:
        seen: dict[str, None] = {}
        for run in store.runs(search, only_completed=True):
            for snapshot in store.snapshots_for_run(run.id):
                seen[snapshot.listing_id] = None
        listings = list(seen)

    found: dict[str, tuple[str, Prose]] = {}
    for listing_id in listings:
        prose = read_prose(_latest_description(store, listing_id))
        if prose is None:
            continue
        found.setdefault(prose.digest, (listing_id, prose))
    return list(found.values())


def _latest_description(store: Store, listing_id: str) -> str | None:
    history = store.history(listing_id)
    if not history.prices:
        return None
    snapshot = store.snapshot_at(listing_id, history.prices[-1].run_id)
    return snapshot.fields.description if snapshot is not None else None


def run_pass(
    store: Store,
    *,
    root: Path,
    search: str | None = None,
    environ: Any = None,
    session: Any = None,
    progress: Callable[[str], None] | None = None,
    limit: int | None = None,
    notes: notes_for.Notes | None = None,
) -> PassOutcome:
    """Ask the model about every description that still needs it.

    `limit` is for a caller that wants a bounded first pass. It is not a default and never a silent
    one: whatever is left over is named in the outcome, because a truncation nobody reports reads as
    a market where nobody mentions a septic tank.

    `notes` is what the person running searches wrote for the model. A caller that knows which saved
    search this is passes both notes; one that does not gets the installation's only, because there
    is no search here to read the other from.
    """
    say = progress or (lambda _message: None)
    written = notes if notes is not None else notes_for.read(root)

    try:
        account = settings.account(root, environ)
    except settings.ExtractionMisconfigured as exc:
        # Reported before anything is asked, which is the spec's own edge case: a missing credential
        # is a configuration problem, not a failure per property.
        return PassOutcome(skipped=str(exc))

    found = descriptions_in(store, search=search)
    if not found:
        return PassOutcome(skipped="no property in this store carries a description")

    # The model's own name when nobody has written a note, and its name plus a fingerprint of the
    # notes when somebody has. A changed note is a different key, so this pass asks again rather
    # than reusing an answer given under different instructions (D-16, AC-18).
    key = written.key(account.model)
    held = cache.answered(store, key, [prose.digest for _, prose in found])
    wanted: list[tuple[str, Prose, tuple[str, ...]]] = []
    cached = 0
    for listing_id, prose in found:
        left = tuple(name for name in _fields_left(prose) if name not in held.get(prose.digest, ()))
        if not left:
            cached += 1
            continue
        wanted.append((listing_id, prose, left))

    truncated = sum(1 for _, prose in found if prose.truncated)
    over = 0
    if limit is not None and len(wanted) > limit:
        over = len(wanted) - limit
        wanted = wanted[:limit]

    paced = session or _session()
    asked = recorded = 0
    rejected: list[str] = []
    failures: list[str] = []

    say(f"extract: {len(wanted)} descriptions to ask about, {cached} already answered")
    for cut in written.truncated:
        say(f"extract: {cut} is over {notes_for.LIMIT} characters and was cut before being sent")
    # Which spelling this server wants, settled on the first answer and reused. A pass over five
    # thousand descriptions must not pay a refused request per property to find out.
    dialect = client.Dialect.for_account(account)
    for listing_id, prose, left in wanted:
        try:
            answer = client.ask(paced, account, prose, left, dialect, written)
        except client.ExtractionFailed as exc:
            failures.append(settings.without_credential(f"{listing_id}: {exc}", account))
            continue
        asked += 1
        cache.write(
            store,
            key,
            prose.digest,
            values=answer.values,
            undetermined=answer.undetermined,
        )
        recorded += len(answer.values)
        rejected.extend(f"{listing_id}: {r.field} {r.reason}" for r in answer.rejected)

    if over:
        say(f"extract: {over} descriptions left for a later pass")
    if failures:
        say(f"extract: {len(failures)} descriptions could not be processed")

    return PassOutcome(
        descriptions=len(found),
        distinct=len(found),
        cached=cached,
        asked=asked,
        recorded=recorded,
        rejected=tuple(rejected),
        failures=tuple(failures),
        truncated=truncated,
        notes_truncated=written.truncated,
        skipped=(f"{over} descriptions left for a later pass" if over else None),
    )


def _session() -> Any:
    from ..sources import default_session

    return default_session(config=settings.pacing())


def model_values(
    store: Store, snapshots: Iterable[Any], *, root: Path, environ: Any = None
) -> dict[str, dict[str, Any]]:
    """Every property's cached model values, in one query rather than one per property.

    Returns nothing at all when no model is configured, which is the common case and must cost
    nothing: an installation with the pass off does not read a credential to find out it has none.
    """
    rows = list(snapshots)
    if not rows:
        return {}
    try:
        account = settings.account(root, environ)
    except settings.ExtractionMisconfigured:
        return {}

    prose = {}
    for snapshot in rows:
        found = read_prose(getattr(snapshot.fields, "description", None))
        if found is not None:
            prose[snapshot.listing_id] = found
    if not prose:
        return {}

    # Whatever this model most recently said, under whichever note was in force when it said it.
    # This is a display path: a note edited an hour ago must not blank six columns until the next
    # pass runs.
    held = cache.read(store, account.model, [p.digest for p in prose.values()], any_notes=True)
    return {
        listing_id: held.get(found.digest, {}) for listing_id, found in prose.items()
    }


def enabled_for(definition: Any) -> bool:
    """Has this saved search turned the model pass on? Absent means no."""
    return bool(getattr(definition, "model_extraction", False))


def for_run(
    store: Store,
    definition: Any,
    *,
    root: Path,
    environ: Any = None,
    session: Any = None,
    progress: Callable[[str], None] | None = None,
) -> PassOutcome | None:
    """The model pass as a run performs it, or nothing when the search did not ask for one.

    `None` rather than an empty outcome, so a caller can tell "off" from "on and found nothing",
    which are different things to report and different things to fix.
    """
    if not enabled_for(definition):
        return None
    return run_pass(
        store,
        root=root,
        search=getattr(definition, "name", None),
        environ=environ,
        session=session,
        progress=progress,
        notes=notes_for.read(root, definition),
    )


def named_fields(wanted: Sequence[str]) -> str:
    return ", ".join(wanted)
