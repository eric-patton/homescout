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
down.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import InvalidInput
from .records import ListingFields, SourceRow
from .search import SearchDefinition
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


@dataclass(frozen=True, slots=True)
class RunOutcome:
    run: RunRecord
    comparison: Comparison
    sources: tuple[SourceReport, ...] = ()

    @property
    def degraded(self) -> bool:
        """At least one source failed or was unavailable. The run still happened."""
        return any(s.outcome != "ok" for s in self.sources)


def _extension_for(preview: Preview) -> str:
    kind = (preview.content_type or "").split(";")[0].strip().lower()
    return _IMAGE_EXTENSIONS.get(kind, "jpg")


def _identity(row: SourceRow) -> tuple[object, ...]:
    """What makes two rows the same property, for the purpose of our own overlapping asks.

    Deliberately the same shape the store matches on: a source's own identifier, or failing that its
    own address text. This is only ever used to drop a repeat *across* queries, never within one.
    """
    if row.source_listing_id is not None:
        return (row.source_listing_id,)
    fields = row.fields
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
        fresh = [row for row in result.rows if _identity(row) not in seen]
        seen.update(_identity(row) for row in result.rows)
        rows.extend(fresh)
    return rows, results


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
) -> RunOutcome:
    """Run one saved search across its configured sources.

    Raises whatever it cannot handle, after marking the run failed. A failed run is never a
    comparison baseline, so an unexpected error costs this run and leaves the last completed one
    exactly as usable as it was.
    """
    say = progress or (lambda _message: None)
    queries = definition.queries()
    if not queries:
        raise InvalidInput(
            f"The saved search {definition.name!r} names no area, so there is nothing to ask a "
            f"source for. Checked before the run started, so nothing was recorded."
        )
    run = store.start_run(definition.name)
    if started is not None:
        started(run)
    reports: list[SourceReport] = []

    try:
        for name in definition.sources:
            source = sources[name]
            capabilities = source.capabilities()
            application = capabilities.application(queries[0])
            by_source = tuple(f for f, applied in application.items() if applied)
            locally = tuple(
                f
                for f, applied in application.items()
                if not applied and f not in NEVER_APPLIED_LOCALLY
            )

            rows, results = _ask(source, queries)
            outcome = _worst([r.outcome for r in results])
            kept = [
                row
                for row in rows
                if passes(row.fields, queries[0], locally) and definition.keeps(row.fields)
            ]

            listing_ids = store.record_observations(run.id, name, kept) if kept else []
            if images and kept:
                _store_previews(store, source, kept, listing_ids)

            detail = "; ".join(r.detail for r in results if r.detail) or None
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
                )
            )
            say(f"{name}: {outcome}, {len(kept)} listings")

        completed = store.complete_run(run.id)
        comparison = store.compare(definition.name, target_run_id=run.id)
    except Exception:
        store.fail_run(run.id)
        raise

    return RunOutcome(run=completed, comparison=comparison, sources=tuple(reports))
