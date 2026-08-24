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
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .claim import claim_run
from .errors import InvalidInput, PreconditionNotMet
from .matches import AmbiguousMatch, MergeQueue, default_queue
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
    _session: Any = None

    @property
    def root(self) -> Path:
        return self.store.path.parent

    def close(self) -> None:
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
) -> Workspace:
    """Open the database and assemble everything that reads it.

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
        store = Store.open(path)
    return Workspace(
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


def edit_search(
    workspace: Workspace, name: str, changes: Mapping[str, object]
) -> SearchDefinition:
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


def enrich(workspace: Workspace, *, stale_only: bool = False, search: str | None = None) -> None:
    raise NotYetBuilt("Enrichment", "location enrichment providers")


def export(workspace: Workspace, *, search: str | None = None) -> None:
    raise NotYetBuilt("Export", "spreadsheet export")


def serve(workspace: Workspace, *, port: int = 8765) -> None:
    raise NotYetBuilt("The local server", "the browser interface")
