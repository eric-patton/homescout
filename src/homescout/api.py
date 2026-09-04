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
from contextlib import contextmanager, suppress
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


@contextmanager
def open_beside(workspace: Workspace) -> Iterator[Workspace]:
    """A second view of one workspace, holding a database connection of its own.

    For work that takes minutes. The browser interface keeps one connection and a lock around every
    request that touches it, which is right for requests and wrong for a pass over the whole store:
    an operation that holds that lock through twenty minutes of paced network requests takes the
    whole site down for twenty minutes, including the progress endpoint that is meant to say how it
    is going. Measured, that is a request going from a third of a second to sixteen.

    So a pass gets its own connection and the two hold the file the way the interface and a
    scheduled command already do on this platform, which is write-ahead logging and a busy timeout
    rather than a lock. Both are short writers; neither blocks a reader at all.

    What is shared and what is not follows from what each thing is bound to. The catalog reads
    files, so it is shared. The queue is bound to a store, so it is rebuilt. Sources are adapters
    and carry no cursor.

    Geography is the subtle one, and it is why this is a context manager rather than a function. A
    saved search that filters by area resolves place names through a provider that reaches into a
    store, so a pass has to resolve them through the connection it actually holds. Registering that
    provider the usual way is process-wide and would hand every other thread a connection belonging
    to this one, which is the interleaved-cursor fault the interface's lock exists to prevent. So it
    is put in place for the calling thread alone, and taken away again on the way out, along with
    the connection. A pass that raised still has to give both back.
    """
    from .enrich.boundaries import CensusBoundaries
    from .search.boundaries import boundaries_on_this_thread

    with _translating():
        store = Store.open(workspace.store.path)
    mine = Workspace(
        store=store,
        catalog=workspace.catalog,
        queue=default_queue(store),
        sources=workspace.sources,
        delay=workspace.delay,
        images=workspace.images,
        owns_boundaries=False,
    )
    try:
        # Cache-only, which is what `open_workspace` registers and what the filtering loop needs:
        # this is asked once per property, and a provider allowed to fetch would put a paced
        # network request inside a loop that is meant to be local, arithmetic and instant.
        with boundaries_on_this_thread(CensusBoundaries(store, fetch=False)):
            yield mine
    finally:
        mine.close()


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
    """Change named keys in a saved search, through the round-tripping document layer.

    One thing is translated on the way through. A criterion is stored as an expression, and a person
    using the browser builds one out of rows: a field, a comparison, a value. A rule arriving with
    `parts` instead of `when` has its expression composed here, because the grammar belongs to the
    rule engine and non-negotiable 8 keeps it out of both interfaces. What lands in the file is the
    same line somebody would have typed.
    """
    return workspace.catalog.edit(name, _with_expressions(changes))


def _with_expressions(changes: Mapping[str, object]) -> dict[str, object]:
    """Any criterion given as rows, turned into the expression a saved search stores."""
    from .rules.phrase import CannotCompose, Part, compose

    if "rules" not in changes:
        return dict(changes)

    rules = changes["rules"]
    if not isinstance(rules, Sequence) or isinstance(rules, (str, bytes)):
        return dict(changes)

    made: list[Any] = []
    for index, entry in enumerate(rules):
        if not isinstance(entry, Mapping) or "parts" not in entry:
            made.append(entry)
            continue
        held = {key: value for key, value in entry.items() if key != "parts"}
        parts = entry["parts"]
        if not isinstance(parts, Sequence) or isinstance(parts, (str, bytes)):
            raise InvalidInput(f"criterion {index + 1} has conditions this cannot read.")
        try:
            held["when"] = compose(
                [
                    Part(
                        field=str(part.get("field") or ""),
                        comparison=str(part.get("comparison") or ""),
                        value=part.get("value"),
                        join=str(part.get("join") or ""),
                    )
                    for part in parts
                    if isinstance(part, Mapping)
                ]
            )
        except CannotCompose as exc:
            name = held.get("id") or f"number {index + 1}"
            raise InvalidInput(f"The criterion {name}: {exc}") from None
        made.append(held)

    return {**changes, "rules": made}


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


def delete_search(workspace: Workspace, name: str) -> dict[str, Any]:
    """Take a saved search out of the catalogue.

    It stops being a saved search at once: out of the list, skipped by a run of everything, and not
    found when asked for by name. Two things it deliberately does not do.

    **It does not destroy the definition.** The file is moved rather than unlinked, so the areas
    somebody drew and the comments they wrote can be brought back. Deleting a definition is not an
    act that needs to be irreversible to be useful.

    **It cannot remove what the runs recorded.** Non-negotiable 2 and product invariant 1 say
    snapshot history is append-only and no feature may delete a historical row, and this is not the
    feature that gets to be the exception. The properties this search found stay in the store, keep
    their price history, and keep whatever judgment was written on them. What the answer reports is
    exactly that, so nobody is left believing more was removed than was.
    """
    catalog = workspace.catalog
    if not hasattr(catalog, "delete"):
        raise InvalidInput(
            "These saved searches are not files, so there is nothing to delete. This happens only "
            "when a catalog was supplied in place of the searches directory."
        )
    with _translating():
        kept = catalog.delete(name)
        runs = len(workspace.store.runs(name))

    return {
        "name": name,
        "kept_at": str(kept),
        "runs_kept": runs,
        "restorable": True,
    }


def restore_search(workspace: Workspace, name: str) -> SearchDefinition:
    """Bring back a deleted definition, which is why deleting one only moved it."""
    catalog = workspace.catalog
    if not hasattr(catalog, "restore"):
        raise InvalidInput("These saved searches are not files, so there is nothing to restore.")
    with _translating():
        return catalog.restore(name)


def deleted_searches(workspace: Workspace) -> tuple[str, ...]:
    """Definitions that were deleted and can be brought back."""
    catalog = workspace.catalog
    return tuple(catalog.deleted()) if hasattr(catalog, "deleted") else ()


def discard_search(workspace: Workspace, name: str) -> dict[str, Any]:
    """Remove a deleted definition for good, and report what that did not touch.

    The one irreversible act in this product, and the only one that removes a file. Everything about
    how it is guarded is in the catalogue's own `discard`: the name is resolved before the folder is
    read, and a search that has not been deleted is refused.

    What it does not do is the part worth reporting. The properties this search's runs found, their
    price history and every judgment written on them stay exactly where they are, because snapshot
    history is append-only under non-negotiable 2 and product invariant 1 and a definition file is
    configuration rather than history. The counts come back with the answer for the same reason
    `delete_search` reports how many runs it kept: somebody who has just done something
    irreversible should be told what it did not reach, and told it in numbers they can go and check.
    """
    catalog = workspace.catalog
    if not hasattr(catalog, "discard"):
        raise InvalidInput(
            "These saved searches are not files, so there is nothing to discard. This happens only "
            "when a catalog was supplied in place of the searches directory."
        )
    with _translating():
        # Counted before the file goes, from the store, which is the only thing that knows, and
        # read in this same call rather than taken from whatever a page displayed a moment ago.
        runs = workspace.store.runs(name)
        properties = _properties_seen_by(workspace, runs)
        removed = catalog.discard(name)

    return {
        "name": name,
        "discarded": [str(path) for path in removed],
        "runs_kept": len(runs),
        "properties_kept": properties,
    }


def _properties_seen_by(workspace: Workspace, runs: Sequence[Any]) -> int:
    """How many distinct properties this search's runs ever recorded.

    The store holds properties, not properties-belonging-to-a-search: a house found by two searches
    is one row seen by both, which is the point of a shared store. So this counts what these runs
    observed rather than asking for a search's properties, and a house both searches found is
    counted here and stays in the store afterwards either way.
    """
    seen: set[str] = set()
    for run in runs:
        for snapshot in workspace.store.snapshots_for_run(run.id):
            seen.add(snapshot.listing_id)
    return len(seen)


def set_aside_searches(workspace: Workspace) -> dict[str, Any]:
    """Everything not being watched, as much of it as a person needs to decide about it.

    Two lists, because they are two different states and folding them into one would be a lie about
    what happened to each. An archived search is still a saved search that nobody is watching; a
    deleted one has stopped being a saved search. Both are still files with everything in them.

    What each entry carries is what a name alone cannot say. "portales" six months later is a name;
    "every listing within twenty miles of Portales, three areas, two sources, last run in March,
    set aside in June" is enough to decide whether you want it back. All of it is read from the
    definition itself, so there is no second copy of a description to fall out of step with the file
    somebody is about to restore.
    """
    catalog = workspace.catalog
    archived: list[dict[str, Any]] = []
    for name in list_searches(workspace):
        try:
            definition = show_search(workspace, name)
        except Exception:  # noqa: BLE001 - one unreadable file must not empty the list
            continue
        if getattr(definition, "archived", False):
            archived.append({**_set_aside(definition, name), **run_status(workspace, name)})

    deleted: list[dict[str, Any]] = []
    if hasattr(catalog, "deleted_entries"):
        for name, definition, when in catalog.deleted_entries():
            deleted.append(
                {
                    **_set_aside(definition, name),
                    **run_status(workspace, name),
                    "deleted_at": when.isoformat(),
                }
            )
    elif hasattr(catalog, "deleted"):
        # A catalogue that is not files. It can say what was deleted and nothing more about it.
        deleted = [{"name": name} for name in catalog.deleted()]

    return {"archived": archived, "deleted": deleted}


def _set_aside(definition: Any, name: str) -> dict[str, Any]:
    """What a set-aside search was, off its own definition."""
    return {
        "name": name,
        "description": getattr(definition, "description", None),
        "areas": len(getattr(definition, "areas", ())),
        "exclusions": len(getattr(definition, "exclusions", ())),
        "sources": list(getattr(definition, "sources", ())),
    }


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


def hazard_layers() -> dict[str, str]:
    """The public layers a map can draw behind a property, by the name a criterion knows them by.

    Derived from the addresses the enrichment pass already uses rather than written out again: the
    same ArcGIS service that answers "what is the hazard at this point" draws that hazard as a
    picture. So a map of where the fire is has nothing of its own to keep current, and pointing the
    provider at a different server moves the map with it.
    """
    from .enrich import settings as where

    found = {}
    for name in ("wildfire", "wui"):
        drawn = where.picture_of(name)
        if drawn:
            found[name] = drawn
    return found


def hazard_tile(workspace: Workspace, layer: str, bbox: str, size: str = "256,256") -> bytes:
    """One picture of one rectangle of a hazard layer, fetched by this machine and kept.

    Asked for by the map, and answered here rather than by the browser going and getting it. Two
    reasons, and the second is the one that matters: a browser refuses a cross-origin image it was
    not clearly offered, and this product says in one place what talks to the outside world and from
    where. A public layer fetched by the machine that already fetches public layers is that
    statement unchanged; a browser reaching out to a federal server is a new line in it.
    """
    from .enrich import hazard

    where = hazard_layers().get(layer)
    if where is None:
        raise InvalidInput(
            f"{layer!r} is not a layer this build draws. "
            f"Known layers: {', '.join(sorted(hazard_layers())) or 'none'}."
        )
    with _translating():
        return hazard.tile(
            workspace.root, where, layer, hazard.rectangle(bbox), hazard.dimensions(size)
        )


def _states_of(workspace: Workspace, name: str) -> list[str]:
    """The states one run actually found properties in.

    Read off the properties rather than off the search's name or its areas, so a search called
    "nm-statewide" that turned something up over the Colorado line gets Colorado too, and a search
    named after nothing at all still gets the right ones.
    """
    from .export import latest_run, rows_of

    with _translating():
        run_id = latest_run(workspace.store, name)
        return sorted(
            {
                (row.fields.state or "").strip().upper()
                for row in rows_of(workspace.store, run_id, root=workspace.root)
                if len((row.fields.state or "").strip()) == 2
            }
        )


def ground(workspace: Workspace, name: str) -> dict[str, Any]:
    """County lines and town names over the states this run found properties in.

    What this is for: the hazard layer is a wall of colour with no words on it, and the basemap's
    own names are underneath it. A person looks at a patch of red half an hour north of somewhere
    and cannot say where. These are the names put back on top.

    One request per state per thing, kept on disk. A county line moves roughly never and an urban
    area is redrawn once a decade.
    """
    from .enrich import ground as land
    from .enrich import settings as where

    service = where.endpoint("boundaries").url
    counties: list[dict[str, Any]] = []
    towns: list[dict[str, Any]] = []
    unreachable: list[str] = []
    for state in _states_of(workspace, name):
        try:
            counties.extend(land.counties(workspace.root, service, state))
        except Exception as exc:  # noqa: BLE001 - one state failing is not the map failing
            unreachable.append(f"{state} counties: {exc}")
        try:
            towns.extend(land.towns(workspace.root, service, state))
        except Exception as exc:  # noqa: BLE001
            unreachable.append(f"{state} towns: {exc}")

    towns.sort(key=lambda one: -int(one.get("size") or 0))
    return {"search": name, "counties": counties, "towns": towns, "unreachable": unreachable}


def data_centers(workspace: Workspace) -> dict[str, Any]:
    """Every data center this tool knows about, from both sources, nationally.

    National rather than per run, unlike the county lines above, because the indexes are national
    and splitting them by state would be work to make the answer smaller rather than better. It is
    a few thousand records; the map draws what is on screen.

    Each site arrives already carrying which of the three kinds it is. The tracker publishes seven
    statuses and collapsing them is core work, not the browser's: a `switch` over status strings in
    a page would be business logic on the wrong side of the line (`feat-010/AC-88`).

    Slow exactly once. The mapped buildings are a single large query to a volunteer service and take
    half a minute the first time; after that both indexes are read off the disk, and they are
    refreshed on their own schedules, three months for buildings and a week for the tracker, because
    a building does not move and a project's status is the whole point.
    """
    from .enrich import datacenters
    from .enrich import settings as where

    sites: list[dict[str, Any]] = []
    unreachable: list[str] = []
    for what, service in (
        ("the tracker", where.endpoint("data_centers").url),
        ("the mapped buildings", where.endpoint("data_centers_built").url),
    ):
        reader = datacenters.tracked if what == "the tracker" else datacenters.built
        try:
            sites.extend(reader(workspace.root, service))
        except Exception as exc:  # noqa: BLE001 - one source failing is not the layer failing
            unreachable.append(f"{what}: {exc}")

    return {
        "sites": sites,
        "unreachable": unreachable,
        #: Both sources are free and both require credit, which no layer on this map has needed
        #: before. Sent with the data rather than written into the page, so the page cannot drift
        #: from what it is actually drawing.
        "credits": [
            "Data centers and their status: FracTracker Alliance, used non-commercially.",
            "Mapped buildings: OpenStreetMap contributors, under the Open Database License.",
        ],
        "incomplete": (
            "An absence of shapes is not evidence of an absence of data centers. The tracker's "
            "interest is contested projects, so a quietly-running facility nobody objected to can "
            "be missing from it, and the mapped buildings only close part of that gap."
        ),
    }


def rainfall(workspace: Workspace, name: str) -> dict[str, Any]:
    """How much rain and snow each county on this map gets in a year, averaged over thirty of them.

    Snow included, as the water it melts down to, because that is how the national record measures
    it. Worth knowing before reading two counties against each other: most of the gap between the
    driest and the wettest county in New Mexico is snow that fell on a mountain.

    Fire hazard is modelled from fuel and terrain and says nothing about how dry a place is. In
    this state that is most of what somebody buying land is asking: nine inches a year and twenty
    inches a year are different countries, and no column in this tool says which one a property is
    in.

    Per county, because that is the finest grain the federal record publishes. Saying so is better
    than interpolating a number that would look like it was measured at the property.

    A county that will not answer is named and the rest are still drawn, which is the same rule
    every other layer on that map follows.
    """
    from concurrent import futures

    from .enrich import ground as land
    from .enrich import settings as where

    held = ground(workspace, name)
    service = where.endpoint("rainfall").url
    counties = [one for one in held["counties"] if one.get("fips")]

    found: list[dict[str, Any]] = []
    unreachable: list[str] = list(held["unreachable"])
    if counties:
        # Three at a time, which is what the module's own gate allows anyway; the pool is here so
        # thirty-three counties take five seconds rather than thirty.
        with futures.ThreadPoolExecutor(max_workers=land.AT_ONCE) as pool:
            asked = {
                pool.submit(
                    land.rainfall, workspace.root, service, one["state"], one["fips"]
                ): one
                for one in counties
            }
            for done in futures.as_completed(asked):
                one = asked[done]
                try:
                    answered = done.result()
                except Exception as exc:  # noqa: BLE001 - one county is not the map
                    unreachable.append(f"{one['name']}: {exc}")
                    continue
                found.append(
                    {**answered, "latitude": one["latitude"], "longitude": one["longitude"]}
                )

    found.sort(key=lambda one: (one["state"], one["fips"]))
    return {"search": name, "counties": found, "years": land.YEARS, "unreachable": unreachable}


def wind_stations(workspace: Workspace, name: str) -> dict[str, Any]:
    """The weather stations whose records cover the states this run found properties in.

    Where the states come from matters: they come from the properties themselves rather than from
    the search's name or its areas, so a search called "nm-statewide" that turned up something over
    the Colorado line gets Colorado's stations too, and a search named after nothing at all still
    gets the right ones. Nothing is fetched here beyond one small list per state, and that list is
    kept: an airport network changes about as often as an airport opens.
    """
    from .enrich import settings as where
    from .enrich import wind

    states = _states_of(workspace, name)
    service = where.endpoint("wind_stations").url
    found: list[dict[str, Any]] = []
    unreachable: list[str] = []
    for state in states:
        if len(state) != 2:
            continue
        try:
            found.extend(wind.stations(workspace.root, service, wind.network_for(state)))
        except Exception as exc:  # noqa: BLE001 - one state failing is not the map failing
            unreachable.append(f"{state}: {exc}")

    return {
        "search": name,
        "states": states,
        "stations": found,
        "seasons": sorted(wind.WHEN),
        "unreachable": unreachable,
    }


def wind_rose(
    workspace: Workspace, network: str, station: str, season: str = "year"
) -> dict[str, Any]:
    """One weather station's wind rose: how often the wind came from each of sixteen directions.

    Over the station's whole automated record rather than over a forecast, which is the only version
    of this question worth putting on a map somebody is buying a house from. Thursday's wind is a
    fact about Thursday.

    Fetched once ever and then read off the disk. The request is a query over tens of thousands of
    hourly observations on somebody else's public archive, and its answer is a summary of decades,
    so asking twice would be rude for no gain at all.
    """
    from .enrich import settings as where
    from .enrich import wind

    with _translating():
        found = wind.rose(
            workspace.root, where.endpoint("wind").url, network, station, season
        )
        document = found.document()

        # The rose itself carries no coordinates; the station list does. Filled in here so a page
        # drawing one has everything it needs from the one answer.
        for held in wind.stations(
            workspace.root, where.endpoint("wind_stations").url, wind.network_for(network[:2])
        ):
            if held["station"] == found.station:
                document["latitude"] = held["latitude"]
                document["longitude"] = held["longitude"]
                document["name"] = held["name"]
                break
    document["network"] = wind.named(network, "network")
    return document


def annotation_fields() -> tuple[str, ...]:
    """Every field of a person's own judgment, in the order they are declared.

    Asked for by both surfaces so neither writes the list out again. They had it twice, once as
    command-line flags and once as an allowed set of request keys, and a field added to the store
    without both being edited is a column that is writable on one surface and unreachable from the
    other, which non-negotiable 8 does not allow.
    """
    from .store import Annotation

    return tuple(Annotation.ANNOTATION_FIELDS)


def annotate(workspace: Workspace, listing_id: str, **values: object) -> Annotation:
    """Write the user's judgment about one property.

    The one thing this tool must never lose. A run never touches it, and this is the only way in.
    """
    try:
        with _translating():
            return workspace.store.set_annotation(listing_id, **values)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc


def judge(
    workspace: Workspace,
    listing_ids: Sequence[str],
    *,
    judgment: str | None,
    verdict: str | None = None,
) -> dict[str, Any]:
    """Set the same judgment on several properties, and say what happened to each.

    One operation rather than a loop in a surface, for two reasons that both matter.

    **Product invariant 5.** Every capability is reachable from both surfaces. A batch built by
    looping in the browser would be a thing the browser can do and the terminal cannot.

    **A loop of forty writes is forty chances to stop half way** with nothing recording which half.
    This reports every identifier it wrote and every one it could not, so the caller can show the
    difference rather than a number that might mean either. That is AC-6's rule about a failed edit
    never being presented as saved, over a batch rather than over one row.

    The reason, when there is one, is written to each of them. A reason typed at the moment forty
    houses were ruled out is as true of each of them as a reason typed on one, and storing it once
    against the batch would invent a second kind of annotation with its own answers for merging,
    unmerging and re-exporting. The annotation already has those answers.
    """
    if judgment not in (None, "keep", "pass"):
        raise InvalidInput(
            f"{judgment!r} is not a judgment. It is 'keep', 'pass', or nothing at all to clear one."
        )
    wanted = list(dict.fromkeys(listing_ids))
    if not wanted:
        raise InvalidInput("No properties were named, so there is nothing to judge.")

    written: list[str] = []
    refused: list[dict[str, str]] = []
    values: dict[str, object] = {"judgment": judgment}
    if verdict is not None:
        values["verdict"] = verdict or None
    for listing_id in wanted:
        try:
            with _translating():
                workspace.store.set_annotation(listing_id, **values)
            written.append(listing_id)
        except Exception as exc:  # noqa: BLE001 - one refusal must not lose the other thirty-nine
            refused.append({"listing_id": listing_id, "why": str(exc)})

    return {
        "judgment": judgment,
        "asked": len(wanted),
        "changed": len(written),
        "written": written,
        "refused": refused,
    }


# -- the household's own vocabulary ----------------------------------------


def tags(workspace: Workspace) -> tuple[dict[str, object], ...]:
    """Every tag the household has made up, with how many properties carry each one.

    Keeping and passing answer one question the tool asks. This is for the questions it does not:
    "septic unknown", "drive by on Saturday", "too close to the highway". A fixed field per idea
    would be a schema change per thought, so the words are theirs and this only keeps them.
    """
    with _translating():
        return tuple(
            {"name": tag.name, "created_at": tag.created_at, "used": tag.used}
            for tag in workspace.store.tags()
        )


def create_tag(workspace: Workspace, name: str) -> dict[str, object]:
    """Add a word to the vocabulary, whether or not anything carries it yet."""
    try:
        with _translating():
            tag = workspace.store.create_tag(name)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    return {"name": tag.name, "created_at": tag.created_at, "used": tag.used}


def rename_tag(workspace: Workspace, name: str, to: str) -> dict[str, object]:
    """Rename a tag everywhere it is used. Renaming onto an existing name merges the two."""
    try:
        with _translating():
            tag = workspace.store.rename_tag(name, to)
    except KeyError as exc:
        raise InvalidInput(str(exc).strip("'\"")) from exc
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    return {"name": tag.name, "created_at": tag.created_at, "used": tag.used}


def delete_tag(workspace: Workspace, name: str) -> int:
    """Take a tag out of the vocabulary and off every property. Answers with how many lost it."""
    try:
        with _translating():
            return workspace.store.delete_tag(name)
    except KeyError as exc:
        raise InvalidInput(str(exc).strip("'\"")) from exc


def tags_of(workspace: Workspace, listing_id: str) -> tuple[str, ...]:
    """What one property is tagged, including anything merged into it."""
    with _translating():
        workspace.store.get_listing(listing_id)
        return workspace.store.tags_for(listing_id)


def set_tags(workspace: Workspace, listing_id: str, names: Sequence[str]) -> tuple[str, ...]:
    """The whole list of tags for one property. Anything not named comes off.

    The full list rather than an add and a remove, because that is what a set of checkboxes and a
    line of typed words both are, and because two operations over the same list is how a surface
    and a store come to disagree about what is on a house.
    """
    try:
        with _translating():
            return workspace.store.set_tags(listing_id, list(names))
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc


def passed(workspace: Workspace) -> tuple[dict[str, object], object]:
    """Every property the person has passed on, and how many there are.

    The command line has no results table to put a "show passed" toggle on, and a capability that
    exists on one surface only is product invariant 5 broken. So this is the command line's way of
    asking the same question: what have I said no to, and can I still see it.
    """
    return _judged(workspace, "pass")


def kept(workspace: Workspace) -> tuple[dict[str, object], object]:
    """Every property the person has marked as one to keep, and how many there are.

    The other half of the same judgment, and the one that is read far more often: a shortlist is
    what somebody actually works from once a table of a thousand has been through it once. The
    command line asks for it here for the same reason it asks for the passed ones.
    """
    return _judged(workspace, "keep")


def _judged(workspace: Workspace, judgment: str) -> tuple[dict[str, object], object]:
    """The properties carrying one judgment, in the shape both surfaces read.

    One function for both answers, because "what have I kept" and "what have I passed on" differ by
    a single word and two copies of this would be two places for that word to end up wrong.
    """
    with _translating():
        store = workspace.store
        records = store.listings()
        #: Every one of these is read once for the whole list. The snapshots in particular: this
        #: asked for all of them inside the loop, which rebuilt every snapshot in the database once
        #: per listing and turned a question about a shortlist into several minutes of work with
        #: the interface's one-request-at-a-time lock held for all of it.
        judgments = store.judgments_for([record.id for record in records])
        snapshots = store.latest_snapshots()
        annotations = store.annotations_of_many([record.id for record in records])
        found = []
        for record in records:
            if judgments.get(record.id) != judgment:
                continue
            snapshot = snapshots.get(record.id)
            fields = snapshot.fields if snapshot is not None else None
            annotation = annotations.get(record.id)
            found.append(
                {
                    "listing_id": record.id,
                    "address": getattr(fields, "address_line", None),
                    "city": getattr(fields, "city", None),
                    "price": getattr(fields, "price", None),
                    "verdict": getattr(annotation, "verdict", None),
                }
            )
    return tuple(found), len(found)


# -- ambiguous matches -----------------------------------------------------


def pending_matches(workspace: Workspace) -> tuple[AmbiguousMatch, ...]:
    return workspace.queue.pending()


def review_queue(workspace: Workspace) -> tuple[dict[str, Any], ...]:
    """Every queued pair, with enough of each property to decide without opening either one.

    `pending_matches` answers what the queue holds: two identifiers and the signals that pointed
    both ways. That is the evidence about the *match*, and it turns out not to be the evidence a
    person actually decides on. Most queued pairs are one house that two sites geocoded differently,
    and the fastest way to see that is to look at the two photographs. Asking somebody to open two
    tabs to find that out, once per pair, over a queue of a hundred and sixty, is the difference
    between a review they do and a review they abandon.

    So the summary is assembled here rather than in either surface, which is non-negotiable 8: a
    terminal listing the queue gets the same address and price a browser does, and neither is
    working anything out for itself.

    A property whose latest snapshot cannot be found is summarised as far as it can be rather than
    skipped. A pair missing half its evidence is still a pair somebody has to rule on, and dropping
    it from the queue would be the tool quietly deciding by omission.
    """
    store = workspace.store
    with _translating():
        snapshots = store.latest_snapshots()
        found = workspace.queue.pending()

    made: list[dict[str, Any]] = []
    for match in found:
        properties = []
        for listing_id in match.listing_ids:
            snapshot = snapshots.get(listing_id)
            fields = snapshot.fields if snapshot is not None else None
            sources = sorted({link.source for link in store.source_links(listing_id)})
            properties.append(
                {
                    "listing_id": listing_id,
                    "address_line": getattr(fields, "address_line", None),
                    "city": getattr(fields, "city", None),
                    "price": getattr(fields, "price", None),
                    "beds": getattr(fields, "beds", None),
                    "baths": getattr(fields, "baths", None),
                    "sqft": getattr(fields, "sqft", None),
                    "year_built": getattr(fields, "year_built", None),
                    "listing_url": getattr(fields, "listing_url", None),
                    "sources": sources,
                    # Said rather than guessed at by the page: an <img> that 404s is a broken
                    # picture in a list somebody is trying to read quickly.
                    "has_image": store.get_preview_image(listing_id) is not None,
                }
            )
        made.append(
            {
                "id": match.id,
                "listing_ids": list(match.listing_ids),
                "agreed": list(match.agreed),
                "conflicted": list(match.conflicted),
                "noticed_at": match.noticed_at,
                "properties": properties,
            }
        )
    return tuple(made)


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
    from .extract.notes import read as read_notes
    from .extract.pass_ import run_pass

    with _translating():
        # The saved search carries the second note, so it has to be loaded to ask with it. A pass
        # over everything gets the installation's note only, because there is no one search whose
        # note would apply to every description in the store.
        definition = workspace.catalog.load(search) if search else None
        return run_pass(
            workspace.store,
            root=workspace.root,
            search=search,
            limit=limit,
            progress=progress,
            notes=read_notes(workspace.root, definition),
        )


def assess(
    workspace: Workspace,
    *,
    search: str | None = None,
    limit: int | None = None,
    progress: Any = None,
) -> Any:
    """Read the properties still in play against what this household has already said it wants.

    The second model pass, and a different one from `extract` in the only way that matters: this one
    is given the address, the coordinates, the photograph and a picture of the fire hazard around
    the point. That boundary is feat-013/AC-3 and is the whole reason this is its own feature.

    What it produces goes beside the person's own judgment and never into it, decides nothing, hides
    nothing and reorders nothing. It ranks, explains and flags; they keep and pass.

    Thin on purpose. The assembly lives in `assess.pass_` because a run performs the same pass when
    a saved search asks it to, and an assembly that lived here would have had to be reached across
    into or copied.
    """
    from .assess.pass_ import PassOutcome, assess_search

    with _translating():
        names = [search] if search else list(list_searches(workspace))
    if not names:
        return PassOutcome(skipped="there is no saved search to assess")

    with _translating():
        definition = workspace.catalog.load(names[0])
        return assess_search(
            workspace.store, definition, root=workspace.root, limit=limit, progress=progress
        )


def assessment_for(workspace: Workspace, listing_id: str) -> dict[str, Any]:
    """What a model made of one property, and whether it still describes it.

    The seam both surfaces read. Staleness is computed here rather than stored, because it is a fact
    about the present: an assessment is current exactly while what it was made from still holds.
    """
    from .assess.criteria import criteria_for
    from .assess.dossier import dossier_for
    from .assess.model import PICTURES
    from .assess.pass_ import fingerprint_of
    from .export import latest_run, rows_of
    from .extract.notes import read as read_notes

    with _translating():
        held = workspace.store.assessment_of(listing_id)
    if held is None:
        return {"listing_id": listing_id, "assessed": False}

    stale = False
    try:
        name = list(list_searches(workspace))[0]
        with _translating():
            definition = workspace.catalog.load(name)
            #: This one property, not the run it belongs to. Staleness is a comparison against the
            #: row as it stands, and building the row needs the same assembly a sheet does; asking
            #: for the sheet and keeping one row of it made opening an assessment cost exactly what
            #: opening the whole table costs, for one property somebody clicked on.
            rows = rows_of(
                workspace.store,
                latest_run(workspace.store, name),
                root=workspace.root,
                only=[listing_id],
            )
        row = next((r for r in rows if r.listing_id == listing_id), None)
        if row is not None:
            written = read_notes(workspace.root, definition)
            criteria = criteria_for(
                definition, notes=[n for n in (written.everywhere, written.search) if n]
            )
            stale = fingerprint_of(dossier_for(row), criteria.stated()) != held.fingerprint
    except Exception:  # noqa: BLE001 - unable to tell is reported as not stale, never as stale
        stale = False

    return {
        "listing_id": listing_id,
        "assessed": True,
        "model": held.model,
        "made_at": held.made_at,
        "stale": stale,
        "fit": held.fit,
        # Named by the core, so a page shows what a picture is called rather than inventing it.
        "seen": [
            {"where": where, "name": PICTURES.get(where, where), "said": said}
            for where, said in held.seen.items()
        ],
        "concerns": [dict(c) for c in held.concerns],
        #: `None`, not `[]`, when this reading was made before the question existed. A surface has
        #: to be able to say "nobody asked" rather than draw the silence as "nothing good about it".
        "in_favour": None if held.in_favour is None else [dict(one) for one in held.in_favour],
        "before_visiting": list(held.before_visiting),
        "could_not_tell": list(held.could_not_tell),
    }


def extracted_for(
    workspace: Workspace, listing_id: str, *, snapshot: Any = None
) -> dict[str, Any]:
    """What is known about one property's six recovered fields, and how each was determined.

    The seam both surfaces read: a value, its provenance, and the sentence it came from. Non-
    negotiable 8 says the command line and the browser are thin wrappers over one library, and
    this is the one thing either of them needs to show a person why a column says what it says.

    `snapshot` is for a caller that already holds one, and it exists because of a real failure.
    `latest_snapshots` answers for the listings that currently represent a property, which is not
    the same set as the listings that have one: a record merged into another still has its own
    history, its own page and its own link, and asking this function about it raised "no such
    listing" and took the page down with it. A merged constituent is not missing. It is exactly
    what product invariant 2 says must stay visible, because it is the evidence a merge can be
    inspected and undone.

    Passing the snapshot also stops a full scan of every latest snapshot running once per page view.
    """
    from .extract import values_for
    from .extract.pass_ import model_values

    store = workspace.store
    if snapshot is None:
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
    include_passed: bool = False,
) -> dict[str, Any]:
    """One run's properties as rows, with the columns they are rows of.

    The same rows and the same column declarations the spreadsheet is made of, so the table on a
    screen and the sheet in a file cannot disagree about what a column is called or where its value
    comes from. Served in one answer, because sending five thousand rows once and sorting them in
    the browser is what makes an interaction after that cost nothing.

    **What is hidden by default is decided here and nowhere else.** A property the person has passed
    on is marked rather than dropped, so the browser can still send every row once and toggle
    without a request, and the command line can ask the same question and get the same answer. The
    rule lives in one place because non-negotiable 8 says both surfaces are thin wrappers over one
    library, and two copies of "passed means hidden" in two languages is exactly how they come to
    disagree.
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
    with_pictures = workspace.store.listings_with_preview_images()
    # What each assessment was made from, against what the property looks like now. Computed here
    # rather than stored, because staleness is a fact about the present: an assessment is current
    # exactly while what it was made from still holds. The criteria are read once for the whole
    # table; the rest is a hash over values the row already carries.
    stated = _stated_criteria(workspace, name)
    documents = []
    passed = 0
    #: Asked once for the whole table, like the tags and the assessments beside it. Per row it was
    #: two queries apiece, and a table of a thousand does not get to spend two thousand round trips
    #: working out which rows to hide.
    judgments = workspace.store.judgments_for([row.listing_id for row in rows])
    for row in rows:
        judgment = judgments.get(row.listing_id)
        if judgment == "pass":
            passed += 1
        document = _row_document(row, cols.COLUMNS)
        document["judgment"] = judgment
        document["hidden_by_default"] = judgment == "pass" and not include_passed
        document["has_image"] = row.listing_id in with_pictures
        document["assessment"] = _assessment_summary(row, stated)
        documents.append(document)

    return {
        "search": name,
        "run_id": wanted,
        "columns": columns,
        "rows": documents,
        "passed": passed,
        "include_passed": include_passed,
    }


def _stated_criteria(workspace: Workspace, name: str) -> dict[str, Any] | None:
    """What this search says it wants, for deciding whether an assessment still describes a row.

    `None` when it cannot be read, which reads as "cannot tell" rather than as stale: telling
    somebody an assessment is out of date when it is not sends them to redo a pass that costs money.
    """
    from .assess.criteria import criteria_for
    from .extract.notes import read as read_notes

    try:
        with _translating():
            definition = workspace.catalog.load(name)
        written = read_notes(workspace.root, definition)
        return criteria_for(
            definition, notes=[n for n in (written.everywhere, written.search) if n]
        ).stated()
    except Exception:  # noqa: BLE001 - unable to tell is not the same as stale
        return None


def _assessment_summary(row: Any, stated: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The three values a table row carries about its assessment, or nothing.

    A count, the worst severity, and whether it still describes the property. Not the prose: the
    answer is already 2.7MB for this workspace and the text is fetched when a row is opened.
    """
    held = getattr(row, "assessment", None)
    if held is None:
        return None
    stale = False
    if stated is not None:
        from .assess.dossier import dossier_for
        from .assess.pass_ import fingerprint_of

        try:
            stale = fingerprint_of(dossier_for(row), stated) != held.get("fingerprint")
        except Exception:  # noqa: BLE001 - and again: unable to tell is not stale
            stale = False
    return {
        "concerns": held.get("concerns"),
        "worst": held.get("worst"),
        "in_favour": held.get("in_favour"),
        "made_at": held.get("made_at"),
        "stale": stale,
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
    #: Which records have stopped appearing, read once. `listings` is already the live, unretracted
    #: set, which is two of the three conditions this used to ask the database about per snapshot.
    gone = sorted(
        record.id
        for record in store.listings()
        if record.presence == "disappeared" and record.id not in already
    )
    #: Their snapshots and nobody else's. Sorted, because the answer used to come out of a query
    #: ordered by listing id and the rows it makes are still in that order.
    snapshots = store.latest_snapshots(gone)
    histories = store.histories_for(list(snapshots))
    made: list[Row] = []
    for listing_id, snapshot in snapshots.items():
        history = histories.get(listing_id)
        if history is None:
            continue
        made.append(
            Row(
                listing_id=listing_id,
                fields=snapshot.fields,
                history=history,
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
        # One way back per site, because a merged property is one row here and three pages out
        # there, and the person keeping a list on one of those sites needs that site's page.
        "links": [
            {"source": source, "url": url}
            for source, url in sorted(getattr(row, "source_links", {}).items())
            if url
        ],
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
        carried = store.tags_for(listing_id)

    fields = snapshot.fields if snapshot is not None else None
    extracted = (
        extracted_for(workspace, listing_id, snapshot=snapshot) if snapshot is not None else {}
    )
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
        "tags": list(carried),
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
            "listing_url": link.listing_url,
            "times_seen": 1,
        }
        if key in found:
            found[key]["times_seen"] += 1
            if link.linked_at and link.linked_at < found[key]["linked_at"]:
                found[key]["linked_at"] = link.linked_at
            # The newest address this source row was seen at, because a site that reorganises its
            # URLs leaves the old one answering nothing.
            if link.listing_url:
                found[key]["listing_url"] = link.listing_url
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


def places(workspace: Workspace) -> tuple[dict[str, Any], ...]:
    """The towns and counties this store's properties are actually in, with how many are in each.

    A note only reaches a property's row when its place matches that property's own town or county,
    exactly as the source spelled it. A box somebody types a place into by hand is therefore a box
    somebody can silently miss with: "Portales, NM" is the obvious thing to write and matches no
    listing, because the field says "Portales". Offering the spellings that are actually in the
    store removes the guess rather than warning about it.
    """
    with _translating():
        rows = workspace.store.connection.execute(
            "SELECT 'city' AS kind, city AS value, COUNT(*) AS properties "
            "FROM listing_snapshots WHERE city IS NOT NULL AND city != '' GROUP BY city "
            "UNION ALL "
            "SELECT 'county', county, COUNT(*) FROM listing_snapshots "
            "WHERE county IS NOT NULL AND county != '' GROUP BY county "
            "ORDER BY 1, 3 DESC"
        )
        return tuple(dict(row) for row in rows)


#: The kinds of place a note may be about. Only `city` and `county` reach a property's row today,
#: because those are the two a listing carries; the rest are recorded and read back but match
#: nothing, which the surfaces say rather than leaving somebody to find out from an empty column.
AREA_KINDS: tuple[str, ...] = ("city", "county", "zip", "state", "region")

#: The kinds that a property's row can actually be matched on.
MATCHING_KINDS: tuple[str, ...] = ("city",)


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
        "rules": [_rule_document(rule) for rule in getattr(definition, "rules", ())],
        "model_extraction": bool(getattr(definition, "model_extraction", False)),
        "extract_notes": str(getattr(definition, "extract_notes", "") or ""),
        "paused": bool(getattr(definition, "paused", False)),
        "archived": bool(getattr(definition, "archived", False)),
        "problems": [
            {"location": p.location, "message": p.message, "severity": p.severity}
            for p in definition.problems()
        ],
    }


def _rule_document(rule: Any) -> dict[str, Any]:
    """One criterion, as text and, when it is one, as the rows a person built it from.

    `parts` is `None` for an expression that is not a flat chain of comparisons: `(a or b) and c` is
    a perfectly good criterion and is not rows. A surface shows that one as text rather than showing
    rows that would quietly mean something else.
    """
    from .rules.phrase import readable

    found = readable(rule.when)
    return {
        "id": rule.id,
        "severity": rule.severity,
        "when": rule.when,
        "parts": [part.as_dict() for part in found] if found is not None else None,
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
        # Why, and not only what. A name identifies a shape; the reason is the part that decides
        # anything when somebody asks later why a whole county has no houses in it.
        "reason": getattr(area, "reason", None),
        "geometry": geometry,
    }


def vocabulary() -> dict[str, Any]:
    """What a person editing a saved search may name: the sources, and the criteria's fields.

    Read from the registries rather than restated, so a source added tomorrow appears without
    anything being edited, and a criterion cannot be offered a field the evaluator does not have.
    """
    from .rules import namespace
    from .rules.definition import SEVERITIES
    from .rules.phrase import COMPARISONS, MANY, WITHOUT_VALUE
    from .rules.tokens import KEYWORDS, OPERATORS
    from .sources import registered

    return {
        "sources": list(registered()),
        "rule_fields": list(namespace.names()),
        # The names on their own are half an answer: `cooling == "swamp cooler"` names a real field
        # and compares it to a word that can never be true, and a list of names would not have said
        # so. This carries the type, the closed set of values where there is one, and what the name
        # means where the name does not say.
        "rule_vocabulary": [dict(field) for field in namespace.vocabulary()],
        "rule_operators": list(OPERATORS) + ["in", "not in", "is null", "is not null"],
        "rule_keywords": sorted(KEYWORDS),
        # The comparisons a builder offers, each with the words to put in front of somebody who is
        # not writing code. `==` is "is", and nobody should have to learn otherwise to use this.
        "rule_comparisons": [
            {
                "comparison": name,
                "label": said,
                "takes": (
                    "nothing" if name in WITHOUT_VALUE else ("many" if name in MANY else "one")
                ),
            }
            for name, said in COMPARISONS
        ],
        "severities": list(SEVERITIES),
        # What firing does, said as an instruction rather than as a category. "drop" and "demote"
        # are the pair somebody has to guess between, so each says what happens to the row.
        "severity_labels": [
            {"severity": "flag", "label": "Point it out",
             "does": "badges the row with this criterion's name. Nothing is hidden or reordered."},
            {"severity": "boost", "label": "Show it first",
             "does": "moves the row up, one place for each boost that fires."},
            {"severity": "demote", "label": "Show it last",
             "does": "moves the row down, one place for each demote that fires."},
            {"severity": "drop", "label": "Hide it",
             "does": "takes the row out of the results. Nothing is deleted: the property keeps its "
                     "history and the run says what it removed and why."},
        ],
        "area_kinds": list(AREA_KINDS),
    }


#: Where to go to get each of the things this tool cannot get for you, kept beside the report that
#: says one is missing. Somebody told "set HOMESCOUT_BROADBAND_TOKEN" and left to search for it is
#: being told the name of their problem rather than the way out of it. Every one of these is a page
#: a person signs into as themselves; nothing here is fetched, and nothing is fetched for them.
WHERE: dict[str, list[dict[str, str]]] = {
    "model": [
        {
            "what": "An OpenAI key",
            "url": "https://platform.openai.com/api-keys",
            "note": "Create one, then set OPENAI_API_KEY in your environment. Asking a hosted "
            "model costs money per description; a local one costs nothing.",
        },
        {
            "what": "A model on this machine instead",
            "url": "https://lmstudio.ai/",
            "note": "LM Studio serves an OpenAI-compatible API on http://localhost:1234/v1 and "
            "needs no credential at all.",
        },
    ],
    "gmail": [
        {
            "what": "A Google App Password",
            "url": "https://myaccount.google.com/apppasswords",
            "note": "Sixteen characters, shown once. Needs 2-Step Verification turned on first. "
            "It can send mail and nothing else, and you can revoke it any time.",
        },
        {
            "what": "Turn on 2-Step Verification",
            "url": "https://myaccount.google.com/security",
            "note": "Only needed if the App Passwords page says it is unavailable.",
        },
    ],
    "broadband": [
        {
            "what": "An FCC broadband map account",
            "url": "https://broadbandmap.fcc.gov/login",
            "note": "Free. Sign in, then find the API key under your account. Two values are "
            "needed: the email you registered with, and the key. Without both the Internet column "
            "stays empty and everything else still works.",
        },
    ],
    "tiles": [
        {
            "what": "About OpenStreetMap's tiles",
            "url": "https://operations.osmfoundation.org/policies/tiles/",
            "note": "Free and needs no key. Their policy is worth a minute if this ever runs "
            "against a whole county at once.",
        },
    ],
    "satellite": [
        {
            "what": "Esri's World Imagery",
            "url": "https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9",
            "note": "Free and needs no key. About six times finer than the government's: measured "
            "at four New Mexico addresses, it has real pictures down to zoom twenty-one where the "
            "USGS cache stops at sixteen. It is a company's service rather than public domain, so "
            "the credit line it asks for is not optional and the service is theirs to change.",
        },
        {
            "what": "The USGS national imagery basemap",
            "url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer",
            "note": "Free, needs no key, and public domain because it is the government's own "
            "photography, refreshed June 2024. Coarser: it stops at zoom sixteen, which is about "
            "two metres to a pixel, so a house is a smudge. The safe fallback rather than the "
            "first choice, and the same kind of federal service the fire layer already comes from.",
        },
    ],
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
            "effort": found.get(model.REASONING_EFFORT) or "",
            "efforts": list(model.EFFORTS),
            "variables": list(model.VARIABLES),
            "where": WHERE["model"],
        },
        "mail": {
            "configured": bool(found.get(mail.MAIL_TO) and found.get(mail.SMTP_HOST)),
            "to": found.get(mail.MAIL_TO) or None,
            "host": found.get(mail.SMTP_HOST) or None,
            "port": found.get(mail.SMTP_PORT) or None,
            "security": found.get(mail.SMTP_SECURITY) or None,
            "username": found.get(mail.SMTP_USERNAME) or None,
            "sender": found.get(mail.MAIL_FROM) or None,
            "digest_path": found.get(mail.DIGEST_PATH) or None,
            # A password is never reported, only whether one is there, and the Gmail fallback
            # counts because it is a credential this installation can already use.
            "credential": bool(found.get(mail.SMTP_PASSWORD) or found.get(mail.GMAIL_APP_PASSWORD)),
            "gmail": {
                "host": mail.GMAIL_HOST,
                "address": found.get(mail.GMAIL_ADDRESS) or None,
                "credential": bool(found.get(mail.GMAIL_APP_PASSWORD)),
                "variables": [mail.GMAIL_ADDRESS, mail.GMAIL_APP_PASSWORD],
            },
            "variables": list(mail.VARIABLES),
            "where": WHERE["gmail"],
        },
        "broadband": {
            # Both halves, because the FCC's file API wants an account name beside the token and
            # half a credential configures nothing.
            "configured": bool(
                found.get(enrich_settings.BROADBAND_TOKEN)
                and found.get(enrich_settings.BROADBAND_USERNAME)
            ),
            "username": found.get(enrich_settings.BROADBAND_USERNAME) or None,
            "credential": bool(found.get(enrich_settings.BROADBAND_TOKEN)),
            "variable": enrich_settings.BROADBAND_TOKEN,
            "variables": [
                enrich_settings.BROADBAND_USERNAME,
                enrich_settings.BROADBAND_TOKEN,
            ],
            "states": _broadband_held(workspace)["states"],
            "where": WHERE["broadband"],
        },
        "map": {
            "tiles": web.tiles(root)[0],
            "attribution": web.tiles(root)[1],
            "variable": web.TILES_VARIABLE,
            "where": WHERE["tiles"],
            # The photographic background is reported beside the drawn one rather than under its
            # own heading, because to somebody configuring this they are one decision: which
            # backgrounds may this map ask somebody else for.
            "satellite": web.satellite(root)[0],
            "satellite_attribution": web.satellite(root)[1],
            "satellite_variable": web.SATELLITE_VARIABLE,
            "satellite_max_zoom": web.satellite_max_zoom(root),
            "satellite_where": WHERE["satellite"],
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


#: The settings a surface may write. Everything here is a plain choice: an address, a name, a
#: number, a preference. Every credential is absent, and absent twice: not on this list, and caught
#: again by the refusal of any name that looks like a secret. A password is never one edit away
#: from a page, however convenient that would be.
_WRITABLE_SETTINGS: tuple[str, ...] = (
    "HOMESCOUT_MAP_TILES",
    "HOMESCOUT_MAP_ATTRIBUTION",
    "HOMESCOUT_MAP_SATELLITE",
    "HOMESCOUT_MAP_SATELLITE_ATTRIBUTION",
    "HOMESCOUT_MAP_SATELLITE_MAX_ZOOM",
    "HOMESCOUT_EXTRACT_BASE_URL",
    "HOMESCOUT_EXTRACT_MODEL",
    "HOMESCOUT_EXTRACT_REASONING_EFFORT",
    "HOMESCOUT_DIGEST_PATH",
    "HOMESCOUT_EMAIL_MAX_NEW",
    "HOMESCOUT_SMTP_HOST",
    "HOMESCOUT_SMTP_PORT",
    "HOMESCOUT_SMTP_SECURITY",
    "HOMESCOUT_SMTP_USERNAME",
    "HOMESCOUT_MAIL_FROM",
    "HOMESCOUT_MAIL_TO",
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


def broadband(
    workspace: Workspace,
    *,
    state: str | None = None,
    progress: Any = None,
) -> dict[str, Any]:
    """What broadband data this installation holds, and load a state's worth of it.

    Its own action rather than part of an enrichment pass, and that boundary is the point. There is
    no per-property service to ask (feat-007 M-7), so this reads the FCC's own published files, and
    a pass that silently downloaded fifty megabytes the first time it met a new state would be a
    pass nobody could predict the cost of.
    """
    from .enrich import broadband as fcc
    from .enrich import settings as enrich_settings
    from .enrich import states

    if state is None:
        return _broadband_held(workspace)

    wanted = state.strip().upper()
    if not states.known(wanted):
        raise InvalidInput(
            f"{state!r} is not a state. Use the two-letter code, such as NM. "
            f"Known: {', '.join(states.codes())}."
        )
    account = fcc.credentials(None)
    if account is None:
        raise PreconditionNotMet(
            "The FCC's file API needs an account name and a token, and one of them is missing. "
            f"Set {enrich_settings.BROADBAND_USERNAME} and {enrich_settings.BROADBAND_TOKEN} in "
            "your environment or in the .env file beside the database. Register at "
            "https://broadbandmap.fcc.gov/login; the token is under your account."
        )

    session = _enrichment_session()
    try:
        index, as_of = fcc.build(session, account, wanted, progress=progress)
    except fcc.BroadbandUnavailable as exc:
        raise PreconditionNotMet(str(exc)) from None

    blocks = fcc.store_index(workspace.store, wanted, index, as_of)
    answer = _broadband_held(workspace)
    answer["loaded"] = {"state": wanted, "blocks": blocks, "as_of": as_of}
    return answer


def _broadband_held(workspace: Workspace) -> dict[str, Any]:
    from .enrich import broadband as fcc
    from .enrich import settings as enrich_settings

    try:
        states_held = workspace.store.broadband_states()
    except Exception:  # noqa: BLE001 - a database older than this table holds none of it
        states_held = {}
    return {
        "states": [dict(row) for row in states_held.values()],
        "configured": fcc.credentials(None) is not None,
        "variables": [enrich_settings.BROADBAND_USERNAME, enrich_settings.BROADBAND_TOKEN],
        "where": WHERE["broadband"],
    }


def _enrichment_session() -> Any:
    from .enrich.registry import registered
    from .enrich.settings import pacing
    from .sources import default_session

    return default_session(config=pacing(registered()))


def model_notes(workspace: Workspace) -> dict[str, Any]:
    """What this installation tells the model, and where that text is kept.

    Its own surface rather than a setting, because it is not one: the settings loader reads
    `KEY=value` lines and a note is a paragraph. It lives in a file beside the database, which is
    the same directory, the same backup and the same "yours, uncommitted" (feat-009 D-15).
    """
    from .extract import notes as written

    return {
        "notes": written.read_file(workspace.root),
        "limit": written.LIMIT,
        "path": str(written.path(workspace.root)),
    }


def set_model_notes(workspace: Workspace, text: str) -> dict[str, Any]:
    """Save what this installation tells the model, and say what will actually be sent.

    Over the limit the text is cut and the answer says so, because a note silently shortened is
    worse than one refused. Empty removes the file: "no note" is one state, not two.
    """
    from .extract import notes as written

    held = str(text or "")
    kept = written.write_file(workspace.root, held)
    answer = model_notes(workspace)
    answer["truncated"] = len(held.strip()) > len(kept)
    return answer


#: The kinds of long operation, as both surfaces name them. A page asks for one by name and a
#: terminal prints it, so these are the product's own words rather than an implementation's.
PASS_KINDS: tuple[str, ...] = ("run", "run-all", "enrich", "extract", "deliver", "broadband")


def under_way(workspace: Workspace) -> list[dict[str, Any]]:
    """Every long operation happening right now, whoever started it.

    Read from the store, so a pass started from a terminal or by the scheduled job is in the answer,
    a pass survives the process that began it, and the browser and the command line cannot give two
    accounts of one thing. A pass that stopped without saying so is not in here.
    """
    with _translating():
        return [_pass_document(held) for held in workspace.store.passes_running()]


def last_pass(workspace: Workspace, kind: str, *, subject: str | None = None) -> dict[str, Any]:
    """The most recent operation of one kind, running or not.

    What a screen showing one pass asks for. It answers with the pass rather than with nothing when
    the pass has finished, because "it finished, and here is what it said" is what somebody coming
    back to the page needs, and an empty panel is not.
    """
    with _translating():
        held = workspace.store.last_pass(kind, subject=subject)
    # `task` rather than `kind` for the same reason `_pass_document` gives: both branches are
    # splatted flat into an envelope whose own key is `kind`, so naming it that here passed the
    # argument twice and the endpoint answered 500 on every workspace where the pass had never run.
    return _pass_document(held) if held is not None else {"task": kind, "started": False}


def _pass_document(held: Any) -> dict[str, Any]:
    """One pass in the shape both surfaces read.

    The keys a page already used for a task are kept, so this replaces what the browser was holding
    in memory rather than asking every screen to learn a second vocabulary for the same thing.
    """
    return {
        "id": held.id,
        # Not `kind`: these documents are splatted flat into the envelope, whose own key is `kind`.
        # `task` is what the pages already called it, so nothing has a second vocabulary to learn.
        "task": held.kind,
        "subject": held.subject,
        "search": held.subject,
        "run_id": held.run_id,
        "started_at": held.started_at,
        "updated_at": held.updated_at,
        "finished_at": held.finished_at,
        "status": held.status,
        "running": held.running,
        "finished": held.finished,
        "started": True,
        "progress": list(held.lines),
        "outcome": held.outcome,
        "failed": held.failed,
    }


def already_running(
    workspace: Workspace, kind: str | None = None, *, subject: str | None = None
) -> Any:
    """A long operation that is already happening, or None. Any of them, unless one is named.

    Here rather than in a surface, which is the whole of AC-85. Each process knew only about its own
    work, so pressing a button in the browser while the scheduled job was extracting started a
    second extraction over the same store. Read from what the store says and the answer covers every
    process on this machine.

    Called with no kind, which is how `recording` calls it, this is the machine's one-at-a-time
    rule. Two heavy passes at once has never been faster: they are paced against the same sources
    and write to the same file, so the second one only makes the first take longer while doubling
    what it costs.
    """
    with _translating():
        for held in workspace.store.passes_running():
            if kind is not None and held.kind != kind:
                continue
            if subject is not None and held.subject != subject:
                continue
            return held
    return None


@contextmanager
def recording(
    workspace: Workspace,
    kind: str,
    *,
    subject: str | None = None,
    run_id: str | None = None,
    progress: Any = None,
    alone: bool = True,
) -> Iterator[Any]:
    """Record a long operation while it runs, and yield the callback it should report through.

    What comes back is a progress function: hand it to the operation and every line it would have
    printed is both printed and recorded. Both surfaces wrap their long work in this, which is what
    makes the answer to "what is happening" the same wherever it is asked and what makes it outlive
    the process that started the work.

    `alone` refuses to start when one of this kind is already under way, which is AC-85. It is the
    default because two extraction passes over one store is duplicated work and duplicated cost
    rather than a faster pass.

    The heartbeat runs on a thread with a connection of its own. It cannot share the caller's, which
    belongs to the calling thread, and it cannot be skipped: these operations are silent for minutes
    at a time by design, so a row whose freshness came only from its last line would read as
    abandoned while it was working.
    """
    import threading

    if alone:
        found = already_running(workspace)
        if found is not None:
            where = f" on {found.subject}" if found.subject else ""
            raise PreconditionNotMet(
                f"A {found.kind} pass{where} is already running, started {found.started_at}. "
                "It may have been started from a terminal or by the scheduled job. This machine "
                "runs one at a time: both are paced against the same sources and write to the same "
                "file, so a second only makes the first take longer."
            )

    with _translating():
        held = workspace.store.begin_pass(kind, subject=subject, run_id=run_id)

    store = workspace.store
    stop = threading.Event()

    def beat() -> None:
        from .store import Store
        from .store.core import PASS_HEARTBEAT_SECONDS

        try:
            beside = Store.open(store.path)
        except Exception:  # noqa: BLE001 - a missing heartbeat must never stop the work itself
            return
        try:
            while not stop.wait(PASS_HEARTBEAT_SECONDS):
                try:
                    beside.touch_pass(held.id)
                except Exception:  # noqa: BLE001 - and the same the other way round
                    return
        finally:
            beside.close()

    ticker = threading.Thread(target=beat, name=f"homescout-heartbeat-{kind}", daemon=True)
    ticker.start()

    def say(message: str) -> None:
        if progress is not None:
            progress(message)
        with suppress(Exception):
            # Recording a line must never be what fails an operation that is otherwise working.
            store.say_on_pass(held.id, message)

    say.pass_id = held.id  # type: ignore[attr-defined]
    say.outcome = None  # type: ignore[attr-defined]

    try:
        yield say
    except BaseException as exc:
        with suppress(Exception):
            store.finish_pass(held.id, failed=str(exc))
        raise
    else:
        # Closed here rather than by the caller, which is the difference between a rule and a hope.
        # An outcome is only known after the operation returns, so `recorded` leaves it on `say` and
        # this writes it; a caller who never calls `recorded` still gets a row that ends, instead of
        # one that says "running" until the clock decides otherwise.
        with suppress(Exception):
            store.finish_pass(held.id, outcome=getattr(say, "outcome", None))
    finally:
        stop.set()
        # Waited for, not merely signalled. A context manager that has returned should not have left
        # a thread of its own behind, and a command that exits with one still winding down is a
        # command whose next line of output can arrive after its own last one.
        ticker.join(timeout=2.0)


def recorded(workspace: Workspace, say: Any, outcome: Mapping[str, Any] | None = None) -> None:
    """Say what the operation `say` belongs to produced.

    Not a close. `recording` closes its own row on the way out, always, so that a caller who forgets
    this cannot leave a pass that never ends. This only supplies the outcome, which is knowable only
    after the operation has returned and therefore cannot be an argument to the context manager.
    """
    if say is not None:
        with suppress(AttributeError):
            say.outcome = dict(outcome) if outcome is not None else None


def overview(workspace: Workspace) -> dict[str, Any]:
    """What is in here, in the few numbers worth seeing before anything else.

    The landing surface used to be a list of searches and nothing more, which answers "what have I
    set up" and not "is there anything for me today". These are the second question: how much is
    being watched, what a run last turned up, and what is waiting on a person rather than on the
    tool.
    """
    names = list(list_searches(workspace))
    running: list[str] = []
    latest: str | None = None
    counted = 0

    for name in names:
        status = run_status(workspace, name)
        if status["running"]:
            running.append(name)
        when = status["last_completed_at"]
        if when and (latest is None or when > latest):
            latest = when

    with _translating():
        counted = workspace.store.listing_count()
        waiting = len(pending_matches(workspace))

    trouble = 0
    for name in names:
        try:
            trouble += 1 if blocking(show_search(workspace, name).problems()) else 0
        except HomescoutError:
            trouble += 1

    return {
        "searches": len(names),
        "properties": counted,
        "running": running,
        "last_run_at": latest,
        "waiting_to_review": waiting,
        "searches_with_problems": trouble,
        # Every long operation, not just the searches above. Here rather than behind a command of
        # its own because invariant 5 wants this reachable from both surfaces and `overview` already
        # is one, already takes `--json`, and already answers the question this is part of.
        "under_way": under_way(workspace),
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
