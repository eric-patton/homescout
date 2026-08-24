"""Everything either surface can do, in one place.

Non-negotiable 8 and product invariant 5 say the same thing twice: neither the command line nor the
browser holds business logic, and anything one can do the other can do. That is only structurally
true if there is exactly one set of operations and both surfaces call it. This is that set.

A surface's whole job is to turn a request into one call here and turn the answer into text. When
something needs to be added to this module to make a command work, that is the signal that logic was
about to be written in the wrong place.

This layer also translates the store's own errors into the two kinds a surface has to tell apart, so
the surface never imports the store to find out what went wrong.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .claim import claim_run
from .errors import HomescoutError, InvalidInput, PreconditionNotMet
from .matches import AmbiguousMatch, MergeQueue, default_queue
from .records import FIELD_NAMES as _FIELD_NAMES
from .runner import RunOutcome
from .runner import run_search as _run_search
from .search import (
    InvalidSearch,
    SearchCatalog,
    SearchDefinition,
    SearchProblem,
    blocking,
    default_catalog,
)
from .store import (
    Annotation,
    Comparison,
    NoBaselineError,
    RunNotCompletedError,
    SchemaTooNewError,
    Store,
    StoreLockedError,
    UnknownListingError,
    to_utc_text,
)

#: Where the database lives when nobody says. A relative default keeps a checkout self-contained and
#: keeps the path out of scheduler configuration, where it would be one more thing to get wrong.
DEFAULT_DB_NAME = "homescout.db"
DB_ENVIRONMENT_VARIABLE = "HOMESCOUT_DB"


class NotYetBuilt(PreconditionNotMet):
    """A command that exists, whose feature does not yet.

    The surface is the contract, so every command in it is reachable from the first release: an
    automated caller can discover what this tool does without keeping a version matrix. "Valid, but
    cannot proceed yet" is exactly what this is.
    """

    def __init__(self, what: str, arrives_with: str) -> None:
        super().__init__(f"{what} is not built yet. It arrives with {arrives_with}.")


#: Which of the store's errors is which kind of answer. A name that does not exist is something the
#: caller passed, so it is invalid input; everything else here is a valid request that cannot
#: proceed right now. Anything not listed is a bug rather than a condition, and stays unexpected.
_AS_INVALID = (UnknownListingError,)
_AS_PRECONDITION = (
    NoBaselineError,
    StoreLockedError,
    RunNotCompletedError,
    SchemaTooNewError,
)


@contextmanager
def _translating() -> Iterator[None]:
    """Turn the store's vocabulary into the two answers a surface knows how to give.

    Here rather than in each surface, so the command line never has to import the store to find out
    what went wrong, and so the browser cannot answer the same failure differently.
    """
    try:
        yield
    except _AS_INVALID as exc:
        raise InvalidInput(str(exc)) from exc
    except _AS_PRECONDITION as exc:
        raise PreconditionNotMet(str(exc)) from exc


@dataclass
class Workspace:
    """One database and the things that read and write it.

    Built once per invocation and handed to every operation, so that a test can substitute a
    saved-search catalog, a merge queue, or a set of sources without any of them being reached for
    through global state.
    """

    store: Store
    catalog: SearchCatalog
    queue: MergeQueue
    sources: Mapping[str, Any] = field(default_factory=dict)
    delay: float | None = None
    images: bool = True
    #: Whether this workspace put the boundary provider in place, and should therefore take it away
    #: again. Registering is process-wide, so a workspace that leaves one behind changes how the
    #: next one in the same process resolves geography.
    owns_boundaries: bool = False
    _session: Any = None

    @property
    def root(self) -> Path:
        return self.store.path.parent

    def close(self) -> None:
        if self.owns_boundaries:
            from .search.boundaries import unregister_boundaries

            unregister_boundaries()
        self.store.close()

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def sources_for(self, definition: SearchDefinition) -> dict[str, Any]:
        """The adapters this search needs, built or supplied.

        Supplied ones win, which is how a test runs the real loop without a network. Otherwise they
        are built from the registry against one paced session, so every request a run makes passes
        through the same politeness gate.
        """
        if self.sources:
            missing = [n for n in definition.sources if n not in self.sources]
            if missing:
                raise InvalidInput(
                    f"The saved search {definition.name!r} names sources that are not "
                    f"registered: {', '.join(missing)}."
                )
            return {n: self.sources[n] for n in definition.sources}

        from .sources import create, registered

        unknown = [n for n in definition.sources if n not in registered()]
        if unknown:
            raise InvalidInput(
                f"The saved search {definition.name!r} names sources that are not registered: "
                f"{', '.join(unknown)}. Known sources: {', '.join(registered()) or 'none'}."
            )
        return {n: create(n, self._paced_session()) for n in definition.sources}

    def _paced_session(self) -> Any:
        """One session for the whole invocation.

        Pacing is kept per source inside a session, so building a fresh one for each saved search
        would let a run of five searches ask one site five times in a row with no wait between them.
        The delay is a property of the relationship with a site, not of a search.
        """
        if self._session is None:
            from .sources import PolitenessConfig, default_session

            settings = {} if self.delay is None else {"delay": self.delay}
            self._session = default_session(config=PolitenessConfig.from_mapping(settings))
        return self._session


def database_path(given: str | Path | None = None) -> Path:
    if given is not None:
        return Path(given)
    from_environment = os.environ.get(DB_ENVIRONMENT_VARIABLE)
    if from_environment:
        return Path(from_environment)
    return Path(DEFAULT_DB_NAME)


def open_workspace(
    db: str | Path | None = None,
    *,
    catalog: SearchCatalog | None = None,
    queue: MergeQueue | None = None,
    sources: Mapping[str, Any] | None = None,
    delay: float | None = None,
    images: bool = True,
    shared: bool = False,
) -> Workspace:
    """Open the database and assemble everything that reads it.

    `shared` lifts SQLite's thread check, and exactly one caller passes it: the browser interface,
    where a web server hands requests to worker threads and holds a lock around every one of them.
    See `store.db.connect` for why that is the only place it is safe.

    The pacing delay is validated here, through the source layer's own policy, so that the permitted
    range lives in one place and an impossible value is refused before anything is fetched.
    """
    if delay is not None:
        from .sources import ConfigurationError, PolitenessConfig

        try:
            PolitenessConfig.from_mapping({"delay": delay})
        except (ConfigurationError, ValueError) as exc:
            raise InvalidInput(str(exc)) from exc

    path = database_path(db)
    with _translating():
        store = Store.open(path, shared=shared)

    # Saved searches asks something to turn a place name into a shape, and this is where that
    # something is supplied. Cache-only: a boundary this workspace has not already fetched answers
    # None rather than reaching for the network in the middle of a filtering loop.
    from .enrich.boundaries import register as register_boundaries

    register_boundaries(store)

    return Workspace(
        owns_boundaries=True,
        store=store,
        catalog=catalog if catalog is not None else default_catalog(path.parent),
        queue=queue if queue is not None else default_queue(store),
        sources=sources or {},
        delay=delay,
        images=images,
    )


# -- saved searches --------------------------------------------------------


def list_searches(workspace: Workspace) -> tuple[str, ...]:
    return workspace.catalog.names()


def show_search(workspace: Workspace, name: str) -> SearchDefinition:
    return workspace.catalog.load(name)


def validate_search(workspace: Workspace, name: str) -> tuple[SearchProblem, ...]:
    """Everything worth saying about one definition, in one pass. Nothing is fetched.

    Both severities come back together. The caller decides what a notice means for it; what a
    problem means is settled here, in `run_search`, which refuses.
    """
    return workspace.catalog.load(name).problems()


def create_search(workspace: Workspace, name: str) -> SearchDefinition:
    return workspace.catalog.create(name)


def edit_search(workspace: Workspace, name: str, changes: Mapping[str, object]) -> SearchDefinition:
    return workspace.catalog.edit(name, changes)


# -- runs ------------------------------------------------------------------


def run_search(
    workspace: Workspace,
    name: str,
    *,
    progress: Any = None,
) -> RunOutcome:
    """Run one saved search, once.

    A run of a search already running declines here rather than waiting, and declines before the
    database is touched, so the run in progress is entirely unaffected.
    """
    definition = workspace.catalog.load(name)
    # Only a problem refuses a run. A notice (a search whose exclusions cover all of it, an area no
    # configured source can express) is said out loud and run anyway, because it describes a search
    # that is valid and disappointing rather than one that is wrong.
    stopping = blocking(definition.problems())
    if stopping:
        raise InvalidSearch(name, stopping)
    sources = workspace.sources_for(definition)

    with _translating(), claim_run(workspace.root, name) as claim:
        return _run_search(
            workspace.store,
            definition,
            sources,
            images=workspace.images,
            progress=progress,
            started=lambda run: claim.announce(run_id=run.id, started_at=run.started_at),
            queue=workspace.queue,
        )


@dataclass(frozen=True, slots=True)
class SkippedSearch:
    """A saved search a run of everything could not start, and why.

    `reason` is `invalid` for a definition that does not validate or names a source that is not
    registered, and `in progress` for one another process is already running. They are different
    things to a person and they carry different exit codes, so the digest says which.
    """

    name: str
    reason: str
    problems: tuple[SearchProblem, ...] = ()
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class RunAll:
    outcomes: tuple[RunOutcome, ...]
    skipped: tuple[SkippedSearch, ...]


def run_all(workspace: Workspace, *, progress: Any = None) -> RunAll:
    """Run every saved search.

    A definition that does not validate is reported and skipped, and the rest still run. An
    observation not made tonight can never be made later, so one unreadable file must not cost a
    night of history for the searches that were fine.
    """
    outcomes: list[RunOutcome] = []
    skipped: list[SkippedSearch] = []
    for name in workspace.catalog.names():
        try:
            standing = _standing_of(workspace, name)
            if standing:
                # Paused or put away. Reported rather than passed over in silence, because a
                # scheduled run that quietly stops covering a town is the kind of absence this
                # whole product exists to make visible.
                skipped.append(
                    SkippedSearch(
                        name=name,
                        reason=standing,
                        detail=(
                            f"{name} is {standing}, so a run of everything leaves it alone. "
                            f"Run it by name to run it anyway."
                        ),
                    )
                )
                continue
            outcomes.append(run_search(workspace, name, progress=progress))
        except InvalidSearch as exc:
            skipped.append(
                SkippedSearch(name=name, reason="invalid", problems=exc.problems, detail=str(exc))
            )
        except InvalidInput as exc:
            # A definition naming a source nobody registered. Same shape of problem as one that
            # does not parse: a file a human has to edit, and no reason to abandon the others.
            skipped.append(SkippedSearch(name=name, reason="invalid", detail=str(exc)))
        except PreconditionNotMet as exc:
            # Almost always this search already running somewhere else, which is the collision the
            # whole feature was blocked on. Skipping it costs one search's night; letting it escape
            # would cost every remaining search's night as well.
            skipped.append(SkippedSearch(name=name, reason="in progress", detail=str(exc)))
    return RunAll(outcomes=tuple(outcomes), skipped=tuple(skipped))


def _standing_of(workspace: Workspace, name: str) -> str | None:
    """`paused`, `archived`, or nothing at all, without letting a bad file decide anything.

    A definition that cannot be read is not paused; it is broken, and the loop below reports it as
    that. So an unreadable file falls through here rather than being quietly skipped as put away.
    """
    try:
        definition = workspace.catalog.load(name)
    except HomescoutError:
        return None
    if getattr(definition, "archived", False):
        return "archived"
    if getattr(definition, "paused", False):
        return "paused"
    return None


def set_standing(
    workspace: Workspace,
    name: str,
    *,
    paused: bool | None = None,
    archived: bool | None = None,
) -> SearchDefinition:
    """Pause, resume, put away or bring back one saved search.

    Both are properties of the file, so both go through the same edit operation everything else
    does and the file keeps its comments and its shape. Neither deletes anything: a search is
    something somebody wrote, and the tool's job is to stop running it, not to lose it.
    """
    changes: dict[str, object] = {}
    if paused is not None:
        changes["paused"] = bool(paused)
    if archived is not None:
        changes["archived"] = bool(archived)
    if not changes:
        return show_search(workspace, name)
    return edit_search(workspace, name, changes)


def duplicate_search(workspace: Workspace, name: str, new_name: str) -> SearchDefinition:
    """Copy a saved search under a new name, so a variation starts from something that works.

    A copy of the file, byte for byte apart from its own name, which is what makes it a duplicate
    rather than a new search that happens to look similar: the comments, the ordering and every
    filter come with it.
    """
    return workspace.catalog.duplicate(name, new_name)


def moment(text: str) -> str:
    """Read a date or a timestamp the way a person means it.

    A bare date means the end of that day, because "what changed since Tuesday" includes Tuesday.
    A date in the future is invalid input rather than an empty answer: it is a typo every time.
    """
    raw = text.strip()
    now = datetime.now(UTC)
    try:
        if len(raw) == 10:
            begins = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
            ends = begins.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            begins = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if begins.tzinfo is None:
                begins = begins.replace(tzinfo=UTC)
            ends = begins
    except ValueError as exc:
        raise InvalidInput(
            f"{text!r} is not a date. Write it as 2026-08-01, or as a full timestamp."
        ) from exc
    if begins > now:
        raise InvalidInput(
            f"{text!r} is in the future, so there is nothing between then and now to compare."
        )
    # Today's date ends later than this moment, and "what changed since today" is a thing people
    # ask on the day. So the end of a day that has not finished is now.
    return to_utc_text(min(ends, now))


def changes(workspace: Workspace, name: str, *, since: str | None = None) -> Comparison:
    """What changed for one saved search, against the previous run or against a date."""
    if name not in workspace.catalog.names():
        workspace.catalog.load(name)  # raises with the known names
    with _translating():
        return workspace.store.compare(name, since=moment(since) if since else None)


# -- delivery --------------------------------------------------------------


def delivery_settings(root: Path, environ: Mapping[str, str] | None = None) -> Any:
    """What this installation has been told about delivery, validated.

    Separate from `deliver` so a surface can check the configuration before a run starts. That is
    the difference between a scheduled task that says "your mail account has no recipient" in the
    first second and one that fetches for an hour, records the night correctly, and then discovers
    it has nobody to tell.
    """
    from .deliver import load

    return load(root, environ)


def deliver(
    workspace: Workspace,
    document: Mapping[str, Any],
    *,
    settings: Any = None,
    transport: Any = None,
) -> Any:
    """Write a finished run's digest where it belongs, and send the email if there is one to send.

    Nothing here can reach the run. The document is already built and the store is only appended to,
    so a mail server that refuses the message costs a report and never a night of history.
    """
    from .deliver import deliver as _deliver

    chosen = settings if settings is not None else delivery_settings(workspace.root)
    with _translating():
        return _deliver(workspace.store, document, chosen, transport=transport)


# -- annotations -----------------------------------------------------------


def annotate(workspace: Workspace, listing_id: str, **values: object) -> Annotation:
    """Write the user's judgment about one property.

    The one thing this tool must never lose. A run never touches it, and this is the only way in.
    """
    try:
        with _translating():
            return workspace.store.set_annotation(listing_id, **values)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc


# -- ambiguous matches -----------------------------------------------------


def pending_matches(workspace: Workspace) -> tuple[AmbiguousMatch, ...]:
    return workspace.queue.pending()


def resolve_match(workspace: Workspace, match_id: str, *, same: bool) -> str | None:
    """Settle one queued match, from either surface.

    Resolving as the same property writes a merge, which every later run follows because the store
    follows merge chains. Resolving as different records that verdict against the queue so nothing
    puts it back. The decision is here rather than in either surface, which is what makes a
    resolution made from a terminal indistinguishable from one made in a browser.
    """
    match = workspace.queue.get(match_id)
    merged: str | None = None
    if same:
        with _translating():
            merged = workspace.store.supersede(
                list(match.listing_ids), join_signal="human review", decided_by="human"
            )
    workspace.queue.record(match_id, "same" if same else "different", merged)
    return merged


# -- not built yet ---------------------------------------------------------


def enrich(
    workspace: Workspace,
    *,
    stale_only: bool = False,
    search: str | None = None,
    providers: Sequence[str] | None = None,
    progress: Any = None,
) -> Any:
    """Attach what the public record says about where these properties are.

    Its own pass, deliberately: a backfill over a county is thousands of points at a second each,
    and no nightly listing run should wait for it. Nothing here can fail a run, because nothing here
    is part of one.
    """
    from .enrich.pass_ import run_pass
    from .enrich.registry import create

    try:
        built = create(providers)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from None

    with _translating():
        outcome = run_pass(
            workspace.store, built, search=search, stale_only=stale_only, progress=progress
        )
    _resolve_boundaries(workspace, search=search, progress=progress)
    return outcome


def _resolve_boundaries(workspace: Workspace, *, search: str | None, progress: Any = None) -> None:
    """Put the shapes a saved search names into the cache, where its geography test can read them.

    This is the half of enrichment that saved searches has been waiting for. A named area cannot be
    tested exactly until something turns its name into a boundary, and the place to do that is here,
    once, rather than inside the loop that tests every property.
    """
    from .enrich.boundaries import resolve

    names = [search] if search else list(workspace.catalog.names())
    wanted: list[tuple[str, str]] = []
    for name in names:
        try:
            definition = workspace.catalog.load(name)
        except HomescoutError:
            continue
        for area in (*getattr(definition, "areas", ()), *getattr(definition, "exclusions", ())):
            kind = getattr(area, "kind", None)
            value = getattr(area, "value", None)
            if kind in ("city", "county", "zip", "state") and value:
                wanted.append((kind, value))

    if wanted:
        found = resolve(workspace.store, tuple(dict.fromkeys(wanted)))
        if found and progress is not None:
            progress(f"boundaries: {found} named places resolved")


def extract(
    workspace: Workspace,
    *,
    search: str | None = None,
    limit: int | None = None,
    progress: Any = None,
) -> Any:
    """Ask the configured model about descriptions the patterns could not settle.

    Its own command as well as part of a run, for the case a run cannot cover: a store that was
    filled before anybody turned the model pass on. Nothing here is needed to use the six extracted
    fields, which the deterministic patterns fill on every property with a description, with no
    configuration at all.
    """
    from .extract.pass_ import run_pass

    with _translating():
        return run_pass(
            workspace.store,
            root=workspace.root,
            search=search,
            limit=limit,
            progress=progress,
        )


def extracted_for(workspace: Workspace, listing_id: str) -> dict[str, Any]:
    """What is known about one property's six recovered fields, and how each was determined.

    The seam both surfaces read: a value, its provenance, and the sentence it came from. Non-
    negotiable 8 says the command line and the browser are thin wrappers over one library, and
    this is the one thing either of them needs to show a person why a column says what it says.
    """
    from .extract import values_for
    from .extract.pass_ import model_values

    store = workspace.store
    with _translating():
        snapshots = store.latest_snapshots()
    snapshot = snapshots.get(listing_id)
    if snapshot is None:
        raise UnknownListingError(listing_id)
    held = model_values(store, [snapshot], root=workspace.root)
    return values_for(snapshot.fields, model=held.get(listing_id))


def export(
    workspace: Workspace,
    *,
    search: str | None = None,
    to: str | Path | None = None,
    template: str | None = None,
    format: str = "xlsx",
    force: bool = False,
    include_dropped: bool = False,
) -> Any:
    """Write one saved search's latest results as a spreadsheet.

    Reads and writes one file. Nothing in the store changes, and nothing is ever read back from a
    spreadsheet: the app is where edits are made and this is an output.
    """
    from .export import default_path, export_run, latest_run

    if search is None:
        names = list_searches(workspace)
        if len(names) != 1:
            raise InvalidInput(
                "Say which saved search to export with --search. "
                f"Available: {', '.join(names) or 'none'}."
            )
        search = names[0]

    with _translating():
        run_id = latest_run(workspace.store, search)
        destination = Path(to) if to else default_path(workspace.root, search, format)
        return export_run(
            workspace.store,
            run_id,
            destination,
            root=workspace.root,
            template=template,
            format=format,
            force=force,
            include_dropped=include_dropped,
        )


def export_templates(workspace: Workspace) -> tuple[str, ...]:
    """Every column set that can be asked for, the built-in one first."""
    from .export import templates

    return templates.available(workspace.root)


# -- what a screen needs, and therefore what both surfaces get ------------
#
# Five operations the browser interface needed and no surface had asked for. They live here rather
# than in that feature, because non-negotiable 8 says both surfaces are thin wrappers over one
# library and product invariant 5 says every capability is reachable from both. Two of them got a
# command as well, for exactly that reason.

#: Every field a property carries, for the detail answer. Read from the record rather than restated.
_LISTING_FIELDS: tuple[str, ...] = tuple(_FIELD_NAMES)


def results(
    workspace: Workspace,
    name: str,
    *,
    run_id: str | None = None,
    include_dropped: bool = False,
) -> dict[str, Any]:
    """One run's properties as rows, with the columns they are rows of.

    The same rows and the same column declarations the spreadsheet is made of, so the table on a
    screen and the sheet in a file cannot disagree about what a column is called or where its value
    comes from. Served in one answer, because sending five thousand rows once and sorting them in
    the browser is what makes an interaction after that cost nothing.
    """
    from .export import cols, latest_run, rows_of

    with _translating():
        wanted = run_id or latest_run(workspace.store, name)
        rows = list(
            rows_of(workspace.store, wanted, include_dropped=include_dropped, root=workspace.root)
        )
        rows.extend(_disappeared(workspace, wanted, {row.listing_id for row in rows}))

    columns = [
        {"name": column.name, "kind": column.kind, "origin": column.origin, "links": column.links}
        for column in cols.COLUMNS
    ]
    return {
        "search": name,
        "run_id": wanted,
        "columns": columns,
        "rows": [_row_document(row, cols.COLUMNS) for row in rows],
    }


def _disappeared(workspace: Workspace, run_id: str, already: set[str]) -> list[Any]:
    """The properties this run did not see and nobody has seen sold.

    The spreadsheet leaves these out, because a sheet is what a run found. A table does not, because
    a person catching up wants to know a house they were watching has stopped appearing, and
    "stopped appearing" is a status rather than a deletion. Hidden by default on the screen and
    shown by a filter that says how many it is hiding.
    """
    from .export.rows import Row

    store = workspace.store
    made: list[Row] = []
    for listing_id, snapshot in store.latest_snapshots().items():
        if listing_id in already:
            continue
        record = store.get_listing(listing_id)
        if record.presence != "disappeared" or record.superseded_by or record.retracted:
            continue
        made.append(
            Row(
                listing_id=listing_id,
                fields=snapshot.fields,
                history=store.history(listing_id),
                presence="disappeared",
            )
        )
    return made


def _row_document(row: Any, columns: Sequence[Any]) -> dict[str, Any]:
    """One property, as a screen reads it: its values, its identity and its badges."""
    return {
        "listing_id": row.listing_id,
        "presence": row.presence,
        "flags": list(row.flags),
        "sources": list(row.sources),
        "listing_url": row.fields.listing_url,
        "latitude": row.fields.latitude,
        "longitude": row.fields.longitude,
        "values": {column.name: column.value(row) for column in columns},
    }


def listing(workspace: Workspace, listing_id: str) -> dict[str, Any]:
    """Everything known about one property, in one answer.

    Its current values, its whole price and status history, the source rows it was built from, what
    the public record says about where it is, what its description gave up, and the person's own
    judgment. A screen showing a property needs all of it and a terminal command printing one needs
    the same, so it is assembled once, here.
    """
    store = workspace.store
    with _translating():
        record = store.get_listing(listing_id)
        history = store.history(listing_id)
        snapshot = None
        if history.prices:
            snapshot = store.snapshot_at(listing_id, history.prices[-1].run_id)
        links = store.source_links(listing_id)
        events = store.events(listing_id)
        annotation = store.get_annotation(listing_id)
        image = store.get_preview_image(listing_id)

    fields = snapshot.fields if snapshot is not None else None
    extracted = extracted_for(workspace, listing_id) if fields is not None else {}
    return {
        "listing_id": listing_id,
        "presence": record.presence,
        "first_observed_at": history.first_observed_at,
        "days_on_market": history.days_on_market,
        "superseded_by": record.superseded_by,
        "fields": (
            {name: getattr(fields, name, None) for name in _LISTING_FIELDS}
            if fields is not None
            else {}
        ),
        "photo_urls": list(getattr(fields, "photo_urls", None) or ()),
        "has_image": image is not None,
        "prices": [
            {"price": entry.price, "observed_at": entry.observed_at, "run_id": entry.run_id}
            for entry in history.prices
        ],
        "events": [
            {"kind": event.kind, "occurred_at": event.occurred_at, "detail": event.detail}
            for event in events
        ],
        "sources": _distinct_sources(links),
        "enrichment": _enrichment_for(workspace, fields),
        "extracted": {
            field: {
                "value": entry.value,
                "provenance": entry.provenance,
                "evidence": list(entry.evidence),
                "conflicted": entry.conflicted,
            }
            for field, entry in extracted.items()
        },
        "annotation": annotation.content() if annotation else {},
        "annotation_updated_at": annotation.updated_at if annotation else None,
    }


def _distinct_sources(links: Sequence[Any]) -> list[dict[str, Any]]:
    """One entry per source row, rather than one per time that row was linked.

    A property seen on twenty consecutive nights has twenty link records for the same source row,
    which is correct in the store and wrong on a screen: this list is what a person reads to tell a
    real record from a bad merge, and the same row appearing twice is exactly what a bad merge looks
    like. Earliest link kept, because that is when this record first became that source's.
    """
    found: dict[tuple[str, str | None], dict[str, Any]] = {}
    for link in links:
        key = (link.source, link.source_listing_id)
        entry = {
            "source": link.source,
            "source_listing_id": link.source_listing_id,
            "join_signal": link.join_signal,
            "linked_at": link.linked_at,
            "times_seen": 1,
        }
        if key in found:
            found[key]["times_seen"] += 1
            if link.linked_at and link.linked_at < found[key]["linked_at"]:
                found[key]["linked_at"] = link.linked_at
            continue
        found[key] = entry
    return list(found.values())


def _enrichment_for(workspace: Workspace, fields: Any) -> dict[str, Any]:
    if fields is None or fields.latitude is None or fields.longitude is None:
        return {}
    from .enrich.cache import known_values, values_for
    from .enrich.registry import create

    return known_values(values_for(workspace.store, create(), fields.latitude, fields.longitude))


def preview_image(workspace: Workspace, listing_id: str) -> tuple[bytes, str] | None:
    """The thumbnail this tool stored itself, and what kind of picture it is.

    Stored rather than fetched, which is why a digest renders for a property that has since
    disappeared and why opening one tells the listing site nothing.
    """
    with _translating():
        # The store keeps a path relative to the database, so that a workspace can be moved without
        # every image record becoming a lie. `preview_image_path` is the one place that resolves it.
        path = workspace.store.preview_image_path(listing_id)
    if path is None or not path.is_file():
        return None
    return path.read_bytes(), IMAGE_TYPES.get(path.suffix.lower().lstrip("."), "image/jpeg")


#: What a stored preview's extension means. A short closed list rather than the system's own guess:
#: what is served here is only ever an image this tool retrieved and wrote itself, and the point of
#: naming the type is that a browser must never be free to decide it is something else.
IMAGE_TYPES: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def area_notes(workspace: Workspace) -> tuple[Any, ...]:
    """What the person has written about places rather than about properties."""
    with _translating():
        return tuple(workspace.store.area_notes())


AREA_KINDS: tuple[str, ...] = ("city", "county", "zip", "state", "region")


def set_area_note(workspace: Workspace, area_type: str, area_value: str, notes: str | None) -> Any:
    """Write a note about a place. The same notes the spreadsheet's second sheet carries."""
    if area_type not in AREA_KINDS:
        raise InvalidInput(
            f"{area_type!r} is not a kind of area. Use one of: {', '.join(AREA_KINDS)}."
        )
    if not (area_value or "").strip():
        raise InvalidInput("A note has to be about a named place.")
    with _translating():
        return workspace.store.set_area_note(area_type, area_value.strip(), notes)


def search_document(workspace: Workspace, name: str) -> dict[str, Any]:
    """One saved search in the shape a person edits it, rather than the shape a source is asked.

    A definition holds `price_min` and `price_max`, because that is what a query carries. A person
    edits `price: {min, max}`, because that is what a range is. The conversion is here rather than
    in a surface, so both surfaces show a range the same way and neither has to know the query
    vocabulary.
    """
    from .search.validate import RANGES, SQUARE_FEET_PER_ACRE

    definition = show_search(workspace, name)
    reading = getattr(definition, "reading", None)
    query = dict(getattr(reading, "filters", {}) or {})

    filters: dict[str, Any] = {}
    for field_name, (low, high) in RANGES.items():
        bounds: dict[str, Any] = {}
        if query.get(low) is not None:
            bounds["min"] = query[low]
        if query.get(high) is not None:
            bounds["max"] = query[high]
        if field_name == "lot_acres":
            bounds = {
                edge: round(value / SQUARE_FEET_PER_ACRE, 4) for edge, value in bounds.items()
            }
        if bounds:
            filters[field_name] = bounds
    if query.get("property_types"):
        filters["property_type"] = list(query["property_types"])
    statuses = tuple(getattr(reading, "statuses", ()) or ())
    if statuses and statuses != ("for_sale",):
        filters["listing_type"] = list(statuses)

    return {
        "name": name,
        "description": getattr(definition, "description", None),
        "sources": list(getattr(definition, "sources", ())),
        "areas": [_area_document(area) for area in getattr(definition, "areas", ())],
        "exclusions": [_area_document(area) for area in getattr(definition, "exclusions", ())],
        "filters": filters,
        "rules": [
            {"id": rule.id, "severity": rule.severity, "when": rule.when}
            for rule in getattr(definition, "rules", ())
        ],
        "model_extraction": bool(getattr(definition, "model_extraction", False)),
        "paused": bool(getattr(definition, "paused", False)),
        "archived": bool(getattr(definition, "archived", False)),
        "problems": [
            {"location": p.location, "message": p.message, "severity": p.severity}
            for p in definition.problems()
        ],
    }


def _area_document(area: Any) -> dict[str, Any]:
    """One geographic component, in this tool's own vocabulary rather than any map library's."""
    shape = getattr(area, "geometry", None) or getattr(area, "shape", None)
    geometry = None
    if shape is not None:
        for attribute in ("geojson", "as_geojson", "__geo_interface__"):
            found = getattr(shape, attribute, None)
            if callable(found):
                geometry = found()
                break
            if found is not None:
                geometry = found
                break
    return {
        "kind": getattr(area, "kind", None),
        "name": getattr(area, "name", None),
        "value": getattr(area, "value", None),
        "excluded": bool(getattr(area, "excluded", False)),
        "geometry": geometry,
    }


def vocabulary() -> dict[str, Any]:
    """What a person editing a saved search may name: the sources, and the criteria's fields.

    Read from the registries rather than restated, so a source added tomorrow appears without
    anything being edited, and a criterion cannot be offered a field the evaluator does not have.
    """
    from .rules import namespace
    from .sources import registered

    return {
        "sources": list(registered()),
        "rule_fields": list(namespace.names()),
        "severities": ["drop", "flag", "boost", "demote"],
        "area_kinds": list(AREA_KINDS),
    }


def _model_needs(named: str | None, credential: bool, address: str, model: Any) -> str | None:
    """The one thing still to do before a model can be asked anything, in a sentence."""
    if not (named or "").strip():
        if credential:
            return (
                "A credential is already in your environment, so naming a model is all that is "
                "left. Something like 'gpt-4o-mini' for a hosted service, or whatever a local "
                "server calls the model it has loaded."
            )
        return (
            "Name a model below. A local server needs nothing else; a hosted one also needs a "
            "credential, which goes in your environment and never on this page."
        )
    if not credential and not model._loopback(address):
        return (
            f"{address} is not on this machine, so it needs a credential. Put one in "
            f"{model.API_KEY} or {model.FALLBACK_API_KEY} in your environment, or by hand in the "
            ".env file beside the database."
        )
    return None


def configuration(workspace: Workspace) -> dict[str, Any]:
    """What this installation has set up, and what it has not.

    So a person can find out whether the optional parts are working without opening a file or
    reading a traceback. **No value here is ever a secret.** Whether a credential is present is a
    fact somebody needs; the credential itself is not, so this reports the first and never the
    second, and there is no endpoint anywhere that returns one.
    """
    from .deliver import settings as mail
    from .enrich import settings as enrich_settings
    from .extract import settings as model
    from .web import settings as web

    root = workspace.root
    found = mail.environment(root)

    account: Any = None
    trouble: str | None = None
    try:
        account = model.account(root)
    except model.ExtractionMisconfigured as exc:
        trouble = str(exc)

    # Asked of the environment rather than of the account, because the account does not exist until
    # everything is set up and this is exactly the fact somebody needs while it is not: "the key is
    # already there, naming a model is all that is left" is a different next step from "find a key".
    credential = bool(found.get(model.API_KEY) or found.get(model.FALLBACK_API_KEY))
    address = (found.get(model.BASE_URL) or model.DEFAULT_BASE_URL).strip()

    return {
        "workspace": str(root),
        "database": str(workspace.store.path),
        "model": {
            "configured": account is not None,
            "model": account.model if account else (found.get(model.MODEL) or None),
            "base_url": account.base_url if account else address,
            "credential": credential,
            "local": model._loopback(account.base_url if account else address),
            "why_not": trouble,
            # `why_not` is the message a run would raise, written for somebody who turned the model
            # pass on for a search. On a settings page, before any of that, what is wanted is the
            # thing still to do, so this says that instead and leaves the other for the detail.
            "needs": _model_needs(found.get(model.MODEL), credential, address, model),
            "variables": list(model.VARIABLES),
        },
        "mail": {
            "configured": bool(found.get(mail.MAIL_TO) and found.get(mail.SMTP_HOST)),
            "to": found.get(mail.MAIL_TO) or None,
            "host": found.get(mail.SMTP_HOST) or None,
            "digest_path": found.get(mail.DIGEST_PATH) or None,
            "variables": list(mail.VARIABLES),
        },
        "broadband": {
            "configured": bool(found.get(enrich_settings.BROADBAND_TOKEN)),
            "variable": enrich_settings.BROADBAND_TOKEN,
        },
        "map": {
            "tiles": web.tiles(root)[0],
            "variable": web.TILES_VARIABLE,
        },
        "interface": {
            "port": web.port(root),
            "allowed_hosts": list(web.allowed_hosts(root)),
            "variables": [web.PORT_VARIABLE, web.ALLOWED_HOSTS_VARIABLE],
        },
    }


def set_configuration(workspace: Workspace, values: Mapping[str, str]) -> dict[str, Any]:
    """Write settings into the `.env` beside the database, and refuse to write a secret there.

    A person turning the map on or naming a local model should not have to find a file. A person
    typing an API key into a web page should be stopped, which is what the refusal below is: the
    constitution says a credential comes from the environment or an uncommitted file and never from
    anywhere a surface can put it, and a page that accepted one would be that anywhere.
    """
    from .deliver.settings import ENV_FILE

    forbidden = {
        name
        for name in values
        if any(word in name.upper() for word in ("KEY", "TOKEN", "PASSWORD", "SECRET"))
    }
    if forbidden:
        raise InvalidInput(
            f"{', '.join(sorted(forbidden))} holds a credential, and this will not write one. "
            "Set it in your environment, or by hand in the .env file beside the database, which is "
            "never committed. Nothing that can be reached from a browser writes a secret."
        )

    allowed = set(_WRITABLE_SETTINGS)
    unknown = [name for name in values if name not in allowed]
    if unknown:
        raise InvalidInput(
            f"{', '.join(sorted(unknown))} is not a setting this writes. "
            f"It writes: {', '.join(sorted(allowed))}."
        )

    path = workspace.root / ENV_FILE
    body = _env_file_with(path, {name: str(value) for name, value in values.items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".partial")
    staging.write_text(body, encoding="utf-8", newline="\n")
    os.replace(staging, path)

    # The file is what survives a restart; this is what makes the change true right now. Everything
    # that reads these settings reads the environment, and a page that said "saved" while the map
    # stayed blank until somebody restarted the server would be lying about what it had done.
    for name, value in values.items():
        if str(value):
            os.environ[name] = str(value)
        else:
            os.environ.pop(name, None)
    return configuration(workspace)


def _env_file_with(path: Path, values: Mapping[str, str]) -> str:
    """The file as it stands, with these names changed, and everything else left exactly alone.

    Rewriting the file from the values it parses out would be four lines shorter and would throw
    away every comment in it. This file is one a person is told to edit by hand, for the credentials
    nothing else may write, so the notes they leave themselves in it are part of it. A setting
    changed from a browser edits its own line and touches nothing else; one set to nothing has its
    line removed rather than left as an empty assignment.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(values)
    kept: list[str] = []

    for line in lines:
        name = line.split("=", 1)[0].strip() if "=" in line else None
        if name is None or name not in remaining:
            kept.append(line)
            continue
        value = remaining.pop(name)
        if value:
            kept.append(f"{name}={value}")
        # An empty value means the line goes, so that turning something off leaves no trace of it.

    added = [f"{name}={value}" for name, value in remaining.items() if value]
    if added:
        if not lines:
            kept += [
                "# HomeScout settings for this workspace. Never committed.",
                "# See .env.example for everything it reads, including the ones only you can set.",
            ]
        if kept and kept[-1].strip():
            kept.append("")
        kept += sorted(added)

    return "\n".join(kept).rstrip("\n") + "\n"


#: The settings a surface may write. Everything else is a credential or a path, and both belong to
#: whoever runs the machine rather than to a page.
_WRITABLE_SETTINGS: tuple[str, ...] = (
    "HOMESCOUT_MAP_TILES",
    "HOMESCOUT_MAP_ATTRIBUTION",
    "HOMESCOUT_EXTRACT_BASE_URL",
    "HOMESCOUT_EXTRACT_MODEL",
    "HOMESCOUT_DIGEST_PATH",
    "HOMESCOUT_EMAIL_MAX_NEW",
)


def run_status(workspace: Workspace, name: str) -> dict[str, Any]:
    """Whether a run of this search is under way, and what the last completed one found.

    Read from the store rather than from anything this process happens to be holding, so the answer
    is the same whoever asks: a run started from a terminal is visible to a browser, and a run
    started from a browser is visible to a terminal.
    """
    store = workspace.store
    with _translating():
        every = store.runs(name)
    completed = [run for run in every if run.status == "completed"]
    running = [run for run in every if run.status == "running"]
    latest = completed[-1] if completed else None
    return {
        "search": name,
        "running": bool(running),
        "started_at": running[-1].started_at if running else None,
        "last_completed_run": latest.id if latest else None,
        "last_completed_at": latest.finished_at if latest else None,
        "runs": len(completed),
    }


def serve(
    workspace: Workspace,
    *,
    port: int = 8765,
    host: str = "127.0.0.1",
    open_browser: bool = False,
) -> None:
    """Start the local interface.

    Bound to the loopback address by default. There is no authentication, by design and by the
    constitution, which is exactly why the bind address is a parameter with a safe default rather
    than something buried where it can be forgotten.
    """
    from .web.serve import serve as start

    start(workspace, host=host, port=port, open_browser=open_browser)
