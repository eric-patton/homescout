"""The run loop: sources in, recorded history out.

One run of one saved search. For every configured source it reads what that source will filter on
its own side, sends it exactly that and no more, applies whatever is left over here, hands the rows
to the store, retrieves the images the store does not already have, and records how that source
did. Then it completes the run and asks the store what changed.

Three rules do most of the work, and each of them exists because getting it wrong is silent:

**Nothing here decides that a property is gone.** The loop reports honest per-source outcomes and
the store decides, because "absent from a response" and "no longer for sale" are only the same
thing when every source succeeded.

**A repeat across two of one search's areas is dropped; a repeat inside one response is kept.** The
first is the tool's own overlapping ask. The second is a source contradicting itself, and both
halves of a contradiction are evidence. Both layers underneath this one were caught getting that
boundary wrong once.

**A filter applied here never removes a property whose value is absent.** Reporting that a house
failed a test that could not be run is the same error as treating absence as evidence, one field
down. The search's own geometry answers the same way: a property a source returned without
coordinates is kept and counted as not locatable, never dropped as though it had failed a test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .assess.pass_ import for_run as assessment_pass
from .errors import InvalidInput
from .extract.pass_ import for_run as extraction_pass
from .merge.address import Address
from .merge.address import of as address_of
from .merge.address import parse as parse_address
from .merge.pass_ import run_pass as merge_pass
from .records import ListingFields, SourceRow
from .rules.verdicts import record as record_verdicts
from .search import Placement, SearchDefinition
from .search.addresses import AddressPlan, AddressQuery, NamedAddress
from .sources.base import Preview, SearchQuery, SearchResult, Source
from .store import Comparison, RunRecord, SourceOutcome, Store

#: Two query fields are pushed to a source that will take them and are never applied here. They are
#: not exceptions for convenience; applying either one locally would destroy something.
#:
#: `listed_since` because freshness is computed from this tool's own first observation, never from a
#: source's field (product invariant 7), so a local test on it would have nothing honest to read.
#:
#: `listing_status` because a property whose status just changed is the single most interesting
#: thing a run can find, and dropping its row would replace the source's positive evidence ("this
#: is pending now") with silence, which the store can then only read as an unexplained
#: disappearance. A status filter shapes what is asked for. It must not hide what came back.
NEVER_APPLIED_LOCALLY = frozenset({"listed_since", "listing_status"})

#: How a query field narrows a row. Each entry answers "does this value pass?", and is only ever
#: consulted when the value is present.
_LOCAL_TESTS: dict[str, tuple[str, Callable[[Any, Any], bool]]] = {
    "price_min": ("price", lambda value, limit: value >= limit),
    "price_max": ("price", lambda value, limit: value <= limit),
    "beds_min": ("beds", lambda value, limit: value >= limit),
    "beds_max": ("beds", lambda value, limit: value <= limit),
    "baths_min": ("baths", lambda value, limit: value >= limit),
    "baths_max": ("baths", lambda value, limit: value <= limit),
    "sqft_min": ("sqft", lambda value, limit: value >= limit),
    "sqft_max": ("sqft", lambda value, limit: value <= limit),
    "lot_sqft_min": ("lot_sqft", lambda value, limit: value >= limit),
    "lot_sqft_max": ("lot_sqft", lambda value, limit: value <= limit),
    "year_built_min": ("year_built", lambda value, limit: value >= limit),
    "year_built_max": ("year_built", lambda value, limit: value <= limit),
    "property_types": ("property_type", lambda value, allowed: value in allowed),
}


_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


@dataclass(frozen=True, slots=True)
class SourceReport:
    """How one source did, and who applied what.

    `applied_by_source` and `applied_locally` are the answer to "why did I get this?": the source's
    opinion and the tool's, told apart rather than merged into one number.
    """

    source: str
    outcome: str
    rows: int
    truncated: bool = False
    detail: str | None = None
    applied_by_source: tuple[str, ...] = ()
    applied_locally: tuple[str, ...] = ()
    #: Rows kept although the search's geometry could not be tested against them, because the source
    #: reported no coordinates. Counted rather than dropped: a property nobody could place is an
    #: unresolved case, and letting it vanish into the matched count would make it look like an
    #: absence instead.
    not_locatable: int = 0


@dataclass(frozen=True, slots=True)
class AddressReport:
    """One named address after a run: whether it was placed, and which sources found it (AC-21).

    Not finding a house is an ordinary answer. It is usually not for sale on that site, and the run
    says so plainly rather than treating it as a failure or leaving it out.
    """

    address: str
    #: False when nothing could say where it is, so no source was asked for it.
    placed: bool
    #: The address the lookup believes it found, so a match into the wrong town is visible.
    matched: str | None = None
    found_by: tuple[str, ...] = ()
    missed_by: tuple[str, ...] = ()

    @property
    def found(self) -> bool:
        return bool(self.found_by)


@dataclass(frozen=True, slots=True)
class RunOutcome:
    run: RunRecord
    comparison: Comparison
    sources: tuple[SourceReport, ...] = ()
    #: One entry per named address, in the order the file names them. Empty for a search that names
    #: none, which is every search written before they existed.
    addresses: tuple[AddressReport, ...] = ()
    #: What address matching did after the run: what it joined, and what it wants a person to
    #: settle. `None` on a path that did not run it.
    merge: Any = None
    #: What the optional assessment pass did, or `None` when this search did not ask for one.
    assessment: Any = None
    #: What the optional model extraction pass did, or `None` when this search did not ask for one.
    #: `None` and an empty outcome are different things: off, against on and found nothing.
    extraction: Any = None

    @property
    def degraded(self) -> bool:
        """At least one source failed, or a model could not be reached. The run still happened.

        Extraction is in here for the same reason a source is: it is an external service that can
        be down, and a run that quietly reported success while six columns went unfilled would be
        the observability minimum broken. What it is not is a failure: the run recorded everything
        it observed and the deterministic values are all still there.
        """
        if any(s.outcome != "ok" or s.truncated for s in self.sources):
            return True
        return bool(
            getattr(self.extraction, "degraded", False)
            or getattr(self.assessment, "degraded", False)
        )


def _extension_for(preview: Preview) -> str:
    kind = (preview.content_type or "").split(";")[0].strip().lower()
    return _IMAGE_EXTENSIONS.get(kind, "jpg")


def _identity(row: SourceRow) -> tuple[object, ...] | None:
    """What makes two rows the same property, for the purpose of our own overlapping asks.

    Deliberately the same shape the store matches on: a source's own identifier, or failing that its
    own address text. This is only ever used to drop a repeat *across* queries, never within one.
    """
    if row.source_listing_id and row.source_listing_id.strip():
        return (row.source_listing_id,)
    fields = row.fields
    if not fields.address_line or not fields.address_line.strip():
        return None
    return (
        (fields.address_line or "").strip().casefold(),
        (fields.unit or "").strip().casefold(),
        (fields.postal_code or "").strip(),
    )


def passes(fields: ListingFields, query: SearchQuery, locally: Iterable[str]) -> bool:
    """Does this row survive the filters the source did not apply?

    A field the row does not carry is never a reason to drop it. The tool does not get to report
    that a property failed a test it could not run, and an undeterminable field is empty rather than
    guessed (product invariant 10).
    """
    for name in locally:
        test = _LOCAL_TESTS.get(name)
        if test is None:
            continue
        attribute, holds = test
        value = getattr(fields, attribute, None)
        if value is None:
            continue
        if not holds(value, getattr(query, name)):
            return False
    return True


def _worst(outcomes: Sequence[str]) -> str:
    """One answer for a source asked several times.

    A source that answered for one area and failed for another has not covered this search, and
    saying so is what keeps the store from reading the gap as houses that sold.
    """
    if not outcomes:
        return "ok"
    if "failed" in outcomes:
        return "failed"
    if "unavailable" in outcomes:
        return "unavailable"
    return "ok"


def _cannot_cover(name: str, definition: SearchDefinition) -> SourceReport:
    """A source that can express none of this search's areas.

    Reported as unavailable rather than as a source that found nothing, because the two mean
    opposite things to the store: nothing found is evidence about a market, and nothing asked is
    evidence about nothing at all.
    """
    named = ", ".join(_name_of(area) for area in definition.areas)
    return SourceReport(
        source=name,
        outcome="unavailable",
        rows=0,
        detail=(
            f"{name} has no way to express any of this search's areas ({named}), "
            "so it was not asked. No substitute area was searched."
        ),
    )


def _name_of(area: object) -> str:
    """Whatever an area calls itself, for a message a person has to act on."""
    for attribute in ("name", "value"):
        found = getattr(area, attribute, None)
        if isinstance(found, str) and found:
            return found
    as_term = getattr(area, "as_term", None)
    return as_term() if callable(as_term) else str(area)


def _ask(
    source: Source, queries: Sequence[SearchQuery]
) -> tuple[list[SourceRow], list[SearchResult]]:
    """Every query this search implies, with our own overlaps removed."""
    rows: list[SourceRow] = []
    results: list[SearchResult] = []
    seen: set[tuple[object, ...]] = set()
    for query in queries:
        result = source.search(query)
        results.append(result)
        # Within one result, every row stands: a source repeating an identifier in one response is
        # contradicting itself and both halves are evidence. Across results, a repeat is ours.
        fresh = [
            row for row in result.rows
            if (identity := _identity(row)) is None or identity not in seen
        ]
        seen.update(
            identity for row in result.rows if (identity := _identity(row)) is not None
        )
        rows.extend(fresh)
    return rows, results


def _wanted(address: NamedAddress, plan: AddressPlan) -> Address:
    """The named address, read by the same parser every listing's address is read by.

    Its ZIP code is the one the person wrote, else the one the lookup matched, else none at all
    (an `at` with no ZIP), and with none it is simply not compared (AC-19).
    """
    placed = plan.where(address)
    postal = address.postal() or (placed.postal if placed is not None else None)
    return parse_address(address.street(), postal=postal)


def _at_address(fields: ListingFields, wanted: Address) -> bool:
    """Is this listing the named house? Three parts, from the address matcher's own rules.

    The house number and the street name must agree, read by the address matcher so that
    `Hwy 43 Hwy` and `Highway 43` are one road. The ZIP code must agree when both have one. The
    unit must agree when both carry one: a lot or unit only one side mentions does not separate
    them, which is feat-006's AC-24, while two different units are two homes.

    A listing whose address has no number or no street can never be the named house. Taking the
    nearest one, or the one with the right number, would be guessing which house somebody meant
    (plan D-24).
    """
    if not wanted.number or not wanted.street:
        return False
    row = address_of(fields)
    if not row.number or not row.street:
        return False
    if (row.number, row.street) != (wanted.number, wanted.street):
        return False
    if row.postal and wanted.postal and row.postal != wanted.postal:
        return False
    return not (row.unit and wanted.unit and row.unit != wanted.unit)


def _ask_for_addresses(
    source: Source,
    asking: Sequence[AddressQuery],
    wanted: Mapping[NamedAddress, Address],
    already: Sequence[SourceRow],
) -> tuple[list[SourceRow], list[SearchResult], set[NamedAddress]]:
    """Every circle around this search's named addresses, keeping only the named houses.

    Nothing the search filters on is applied to what is kept, and the exclusions are not consulted:
    a named house is wanted whatever they say (AC-20). Everything else a circle returned is dropped
    unrecorded, as a row outside a drawn area is (AC-19).

    A named house the area queries already kept is one observation, not two, by the same rule that
    drops a repeat across two areas; and within one response every row stands, as it does there.
    """
    seen = {identity for row in already if (identity := _identity(row)) is not None}
    rows: list[SourceRow] = []
    results: list[SearchResult] = []
    hits: set[NamedAddress] = set()
    for ask in asking:
        result = source.search(ask.query)
        results.append(result)
        fresh: list[SourceRow] = []
        for row in result.rows:
            members = [
                address for address in ask.circle.members
                if _at_address(row.fields, wanted[address])
            ]
            if not members:
                continue
            hits.update(members)
            identity = _identity(row)
            if identity is not None and identity in seen:
                continue
            fresh.append(row)
        seen.update(identity for row in fresh if (identity := _identity(row)) is not None)
        rows.extend(fresh)
    return rows, results, hits


def _store_previews(
    store: Store,
    source: Source,
    rows: Sequence[SourceRow],
    listing_ids: Sequence[str],
) -> int:
    """One image per property that has none, and no request for one that does.

    A nightly run re-downloading pictures already on disk would spend most of its pacing budget on
    them, so a stored copy is a cache hit and is never re-fetched. Retrieval cannot raise: the
    adapter guarantees that, because an image is the least important thing a run collects.
    """
    stored = 0
    done: set[str] = set()
    for row, listing_id in zip(rows, listing_ids, strict=True):
        if listing_id in done or store.get_preview_image(listing_id) is not None:
            continue
        done.add(listing_id)
        preview = source.preview(row)  # type: ignore[attr-defined]
        if preview is None or not preview.data:
            continue
        store.store_preview_image(
            listing_id,
            preview.data,
            extension=_extension_for(preview),
            source_url=preview.source_url,
        )
        stored += 1
    return stored


def run_search(
    store: Store,
    definition: SearchDefinition,
    sources: Mapping[str, Source],
    *,
    images: bool = True,
    progress: Callable[[str], None] | None = None,
    started: Callable[[RunRecord], None] | None = None,
    queue: Any = None,
) -> RunOutcome:
    """Run one saved search across its configured sources.

    Raises whatever it cannot handle. An error before observations complete marks the run failed.
    An error afterward is recorded separately, preserving the completed observation history.
    """
    say = progress or (lambda _message: None)
    named: tuple[NamedAddress, ...] = tuple(getattr(definition, "addresses", ()) or ())
    if not definition.areas and not named:
        raise InvalidInput(
            f"The saved search {definition.name!r} names no area and no address, so there is "
            f"nothing to ask a source for. Checked before the run started, so nothing was recorded."
        )
    # Placed once for the whole run, from what is already known: the looking up happened before
    # the run started, so nothing in here can reach the network to place an address (plan D-22).
    plan: AddressPlan = definition.address_plan() if named else AddressPlan()  # type: ignore[attr-defined]
    wanted = {address: _wanted(address, plan) for address, _ in plan.placed}
    found_by: dict[NamedAddress, list[str]] = {address: [] for address in named}
    run = store.start_run(
        definition.name, revision=getattr(definition, "observation_revision", None)
    )
    reports: list[SourceReport] = []
    stage = "start"

    try:
        if started is not None:
            started(run)
        stage = "sources"
        for name in definition.sources:
            source = sources[name]
            capabilities = source.capabilities()
            queries = definition.queries_for(capabilities)
            asking = plan.queries_for(capabilities)
            if not queries and not asking:
                reports.append(_cannot_cover(name, definition))
                store.record_source_outcome(
                    run.id,
                    SourceOutcome(
                        source=name,
                        outcome="unavailable",
                        row_count=0,
                        detail=reports[-1].detail,
                    ),
                )
                say(f"{name}: unavailable, no area it can express")
                continue

            by_source: tuple[str, ...] = ()
            locally: tuple[str, ...] = ()
            results: list[SearchResult] = []
            kept: list[SourceRow] = []
            unplaced = 0
            if queries:
                application = capabilities.application(queries[0])
                by_source = tuple(f for f, applied in application.items() if applied)
                locally = tuple(
                    f
                    for f, applied in application.items()
                    if not applied and f not in NEVER_APPLIED_LOCALLY
                )
                rows, results = _ask(source, queries)
                for row in rows:
                    if not passes(row.fields, queries[0], locally):
                        continue
                    where = definition.place(row.fields)
                    if where is Placement.outside:
                        continue
                    if where is Placement.unlocatable:
                        unplaced += 1
                    kept.append(row)

            # The named houses, asked for with no filters and kept by address alone (AC-18 to
            # AC-20). Their queries count toward this source's outcome like any other: a status
            # this source refuses is a failed query, and degrades it the ordinary way.
            if asking:
                named_rows, named_results, hits = _ask_for_addresses(
                    source, asking, wanted, kept
                )
                kept.extend(named_rows)
                results.extend(named_results)
                for address in hits:
                    found_by[address].append(name)
            outcome = _worst([r.outcome for r in results])

            listing_ids = store.record_observations(run.id, name, kept) if kept else []
            if images and kept:
                _store_previews(store, source, kept, listing_ids)

            details = [r.detail for r in results if r.detail]
            if asking:
                # Recorded with the source's outcome, so the stored run says how many named houses
                # each source found after the run's own report is gone (plan D-25).
                hits_here = sum(1 for address, _ in plan.placed if name in found_by[address])
                details.append(
                    f"found {hits_here} of {len(plan.placed)} named "
                    f"address{'es' if len(plan.placed) != 1 else ''}"
                )
                if "listing_status" not in capabilities.applies:
                    details.append(
                        f"{name} takes no listing status, so named addresses were asked for once"
                    )
            detail = "; ".join(details) or None
            truncated = any(r.truncated for r in results)
            store.record_source_outcome(
                run.id,
                SourceOutcome(
                    source=name,
                    outcome=outcome,  # type: ignore[arg-type]
                    row_count=len(kept),
                    truncated=truncated,
                    detail=detail,
                ),
            )
            reports.append(
                SourceReport(
                    source=name,
                    outcome=outcome,
                    rows=len(kept),
                    truncated=truncated,
                    detail=detail,
                    applied_by_source=by_source,
                    applied_locally=locally,
                    not_locatable=unplaced,
                )
            )
            unplaced_text = f", {unplaced} not locatable" if unplaced else ""
            say(f"{name}: {outcome}, {len(kept)} listings{unplaced_text}")

        completed = store.complete_run(run.id, freeze_identity=False)

        # Before the criteria and after the run, in that order and for that reason. A rule naming
        # `sewer` has to see this run's extracted value rather than last night's, and extraction
        # cannot happen during the run because it reads the descriptions the run just recorded.
        # Off unless this saved search turned it on, in which case none of it is reached at all.
        stage = "extraction"
        extraction = extraction_pass(
            store, definition, root=store.path.parent, progress=progress
        )
        if extraction is not None and extraction.skipped:
            say(f"extract: {extraction.skipped}")

        # After the run, never during it. A criterion decides what a person is shown, and nothing
        # about what is recorded: a property a rule drops is still observed, still snapshotted, and
        # still comparable, or the store would read the exclusion as a disappearance.
        rules = getattr(definition, "rules", ())
        stage = "rules"
        if rules:
            record_verdicts(store, rules, run.id)

        # Also after, and for a related reason. Merging changes which record a property is, and a
        # comparison computed across a merge would have to reason about that; computed before it,
        # this run's comparison is about the records this run actually observed. The next run's
        # comparison follows the merge, because the store resolves a superseded record to the one
        # that replaced it.
        stage = "merge"
        merging = merge_pass(store, queue=queue, run_id=run.id, progress=progress)
        stage = "identity"
        store.freeze_run_identity(run.id)
        stage = "comparison"
        comparison = store.compare(definition.name, target_run_id=run.id)

        # Last, and after the criteria rather than before them, because an assessment is handed
        # which rules fired on a property and there is nothing to hand it until they have. Off
        # unless this saved search turned it on, in which case none of it is reached at all: no
        # credential is read, no picture is fetched and no request is made.
        #
        # Its own switch rather than the extraction one, because the two send different things. A
        # description leaving the machine and an address, a photograph and a map leaving it are not
        # the same decision, and one switch over both would have taken the second one away.
        stage = "assessment"
        assessment = assessment_pass(
            store, definition, root=store.path.parent, progress=progress
        )
        if assessment is not None and assessment.skipped:
            say(f"assess: {assessment.skipped}")
    except Exception as exc:
        try:
            if store.get_run(run.id).status == "running":
                store.fail_run(run.id)
            else:
                store.record_postprocess_failure(run.id, stage, str(exc))
        except Exception as recording_error:
            exc.add_note(f"Run failure could not be recorded: {recording_error}")
        raise

    return RunOutcome(
        run=completed,
        comparison=comparison,
        sources=tuple(reports),
        addresses=tuple(
            AddressReport(
                address=address.text,
                placed=(placed := plan.where(address)) is not None,
                matched=placed.matched if placed is not None else None,
                found_by=tuple(found_by[address]),
                missed_by=(
                    tuple(n for n in definition.sources if n not in found_by[address])
                    if placed is not None
                    else ()
                ),
            )
            for address in named
        ),
        merge=merging,
        extraction=extraction,
        assessment=assessment,
    )
