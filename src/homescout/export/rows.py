"""One run's results, turned into the rows a sheet is made of.

Everything a column could ask about one property, gathered once. That is the whole design decision
here: the obvious version asks the store per property per column, which for five thousand properties
and thirty-two columns is a hundred and sixty thousand queries against a file on the same disk, and
the thirty-second budget in the requirements would go entirely to round trips.

So each kind of value is collected in one pass, in this order: the snapshots, the annotations, the
criteria's verdicts, the enriched values, the cached model answers, and the area notes. Only the
deterministic extraction is computed per row, because it is regular expressions rather than a query
and was measured at well under a millisecond apiece.

Nothing here writes. The store is opened, read, and left exactly as it was.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..extract import Extracted
from ..records import ListingFields
from ..store import Annotation, ListingHistory, Store


@dataclass(frozen=True, slots=True)
class Row:
    """One property, with everything any column might ask it for."""

    listing_id: str
    fields: ListingFields
    history: ListingHistory
    presence: str = "observed"
    annotation: Annotation | None = None
    extracted: Mapping[str, Extracted] = field(default_factory=dict)
    enriched: Mapping[str, Any] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    #: One address per site this property was seen on. A merged record has several and they are not
    #: interchangeable: somebody keeping a list on one site needs that site's page for it.
    source_links: Mapping[str, str] = field(default_factory=dict)
    area_notes: Mapping[tuple[str, str], str] = field(default_factory=dict)
    #: The household's own words for this property, in name order. Their vocabulary, not this
    #: tool's: keeping and passing answer one fixed question and everything else somebody wants to
    #: say about a house is a word they made up.
    tags: tuple[str, ...] = ()
    #: What a model made of this property, in summary: how many concerns, the worst of them, and
    #: whether it still describes the property. `None` when nothing has assessed it.
    #:
    #: The summary and not the prose. A hundred and fifty-five assessments' text on every page load,
    #: to show the one a person opens, is the wrong trade against an answer that is already 2.7MB.
    assessment: dict[str, Any] | None = None


def rows_for(
    store: Store,
    run_id: str,
    *,
    include_dropped: bool = False,
    root: Any = None,
    only: Sequence[str] | None = None,
) -> tuple[Row, ...]:
    """Every property this run's criteria kept, as rows, in the order the results come out in.

    `include_dropped` is the spec's "unless explicitly requested". A property a `drop` rule removed
    is still observed, still snapshotted and still in the store; it is simply not in the sheet
    somebody asked for, unless they asked for it.

    `only` narrows it to named properties, and exists for the callers that want one row rather than
    a sheet. Asking about a single property used to mean building every row of the run and throwing
    all but one away, which cost the same second as opening the whole table. Named by the record
    that represents a property now, because that is the id anything reading a table is holding.
    """
    from ..extract import values_for as extracted_values
    from ..rules.results import excluded, results

    #: One flat list of what goes in the sheet, so everything after this is one loop rather than two
    #: that have to be kept in step.
    wanted: list[_Kept] = [
        _Kept(r.listing_id, r.fields, tuple(r.flags)) for r in results(store, run_id)
    ]
    if include_dropped:
        seen = {entry.listing_id for entry in wanted}
        wanted.extend(
            _Kept(gone.listing_id, gone.fields, tuple(gone.rules), dropped=True)
            for gone in excluded(store, run_id)
            if gone.listing_id not in seen
        )
    if only is not None:
        asked = set(only)
        #: The whole set resolved in one query, before the narrowing rather than after it: this
        #: still has every row of the run in hand at this point, and asking per row which record
        #: represents it would be the cost the narrowing exists to avoid.
        live_of = store.live_listing_ids([entry.listing_id for entry in wanted])
        wanted = [
            entry
            for entry in wanted
            if entry.listing_id in asked or live_of[entry.listing_id] in asked
        ]

    wanted = _as_they_stand_now(store, wanted)
    #: Asked once for the whole sheet, every one of them. One query per row is how a table of a
    #: thousand becomes a table somebody waits for, and this loop used to make six of those trips
    #: per row: its annotation, its tags, its assessment, its sources, its history and the record
    #: behind it. The first three were paid off when they were written; the rest are here.
    asked = [entry.listing_id for entry in wanted]
    annotations = _annotations(store, asked)
    tags = store.tags_for_many(asked)
    #: What a model made of each property, in summary.
    assessed = store.assessment_summaries(asked)
    #: Which sites each was seen on, and how each has moved. The history carries the record's
    #: presence with it, so the row does not go back for the record as well.
    linked = store.source_links_for_many(asked)
    histories = store.histories_for(asked)
    enriched = _enriched(store, wanted)
    from_model = _model_values(store, run_id, root)
    notes = _area_notes(store)

    made: list[Row] = []
    for entry in wanted:
        links = _sources_from(linked.get(entry.listing_id, ()))
        #: A property the batch could not find is asked about on its own, which raises the way it
        #: always did rather than quietly leaving a row half built.
        history = histories.get(entry.listing_id) or store.history(entry.listing_id)
        made.append(
            Row(
                listing_id=entry.listing_id,
                fields=entry.fields,
                history=history,
                presence=history.presence,
                annotation=annotations.get(entry.listing_id),
                extracted=extracted_values(entry.fields, model=from_model.get(entry.listing_id)),
                enriched=enriched.get(entry.listing_id, {}),
                flags=entry.flags,
                sources=tuple(sorted(links)),
                source_links=links,
                area_notes=notes,
                tags=tags.get(entry.listing_id, ()),
                assessment=assessed.get(entry.listing_id),
            )
        )
    return tuple(made)


def _as_they_stand_now(store: Store, wanted: list[_Kept]) -> list[_Kept]:
    """One row per property, under the record that represents it now.

    A run records its verdicts and its snapshots against the records it observed, and *then* merges
    what turned out to be the same house. So between a merge and the next run, the run's own results
    name the halves: the same property appears twice, each half carrying only the sites it happened
    to be seen on, and the merged record that carries both is in the results not at all. Measured on
    a statewide run right after a merge pass: 1,083 rows for 964 properties, and 147 merged records
    absent while their 266 constituents were shown.

    That is a display fault rather than a bad merge, so it is fixed where the display is assembled.
    Each kept row is re-keyed to the record that represents it now, and where several land on the
    same one, the fullest is kept: the halves rarely carry the same amount, and the point of the
    merge is to show the more complete house rather than an arbitrary one of the two.
    """
    #: Read once for the whole list rather than per row, twice. Both loops below need the same
    #: answer for the same property, and asking the database for it each time was two queries per
    #: row of a table already assembled from one.
    live_of = store.live_listing_ids([entry.listing_id for entry in wanted])
    best: dict[str, _Kept] = {}
    for entry in wanted:
        live = live_of[entry.listing_id]
        held = entry
        if live != entry.listing_id:
            held = _Kept(live, entry.fields, entry.flags, entry.dropped)
        standing = best.get(live)
        if standing is None or _told(held) > _told(standing):
            best[live] = held
    #: The order the results came in, which is the order the criteria put them in.
    seen: set[str] = set()
    ordered: list[_Kept] = []
    for entry in wanted:
        live = live_of[entry.listing_id]
        if live in seen:
            continue
        seen.add(live)
        ordered.append(best[live])
    return ordered


def _told(entry: _Kept) -> tuple[int, int]:
    """How much this row actually says, for choosing between two halves of one property."""
    fields = entry.fields
    filled = sum(
        1
        for name in dir(fields)
        if not name.startswith("_") and getattr(fields, name, None) not in (None, "", ())
    )
    return (filled, len(entry.flags))


@dataclass(frozen=True, slots=True)
class _Kept:
    """One property on its way into the sheet, before anything was looked up about it."""

    listing_id: str
    fields: ListingFields
    flags: tuple[str, ...] = ()
    dropped: bool = False


def _annotations(store: Store, listing_ids: Sequence[str]) -> dict[str, Annotation]:
    """Every annotation these properties carry, in one query.

    It was a call apiece, on the grounds that a lookup by primary key against a local file is the
    cheapest thing here. That is true of one and stops being true of a thousand: cheap and per-row
    is still a thousand round trips, and this loop had six of those.
    """
    return store.annotations_of_many(list(listing_ids))


def _enriched(store: Store, results: Sequence[Any]) -> dict[str, dict[str, Any]]:
    """What the public record says about where these properties are, in one query per provider."""
    from ..enrich.cache import known_values, read
    from ..enrich.registry import create

    providers = create()
    places = [
        (r.fields.latitude, r.fields.longitude)
        for r in results
        if r.fields.latitude is not None and r.fields.longitude is not None
    ]
    held = read(store, providers, places) if places else {}
    return {
        r.listing_id: known_values(held.get((r.fields.latitude, r.fields.longitude), {}))
        for r in results
    }


def _model_values(store: Store, run_id: str, root: Any) -> dict[str, dict[str, Extracted]]:
    """Cached model answers, in one query, and nothing at all when no model is configured."""
    if root is None:
        return {}
    from ..extract.pass_ import model_values

    return model_values(store, store.snapshots_for_run(run_id), root=root)


def _area_notes(store: Store) -> dict[tuple[str, str], str]:
    """Everything the person has written about places rather than about properties."""
    found: dict[tuple[str, str], str] = {}
    for note in store.area_notes():
        if note.notes:
            found[(note.area_type, note.area_value)] = note.notes
            found[(note.area_type, note.area_value.casefold())] = note.notes
    return found


def _sources_from(links: Iterable[Any]) -> dict[str, str]:
    """Which listing sites this property was seen on, and where on each, keyed by site.

    Provenance in one cell and a way back to each site in the next. The last address wins per site
    because the links come back oldest first and a site that reorganises its URLs leaves the old
    one answering nothing.

    Given the links rather than fetching them, so the whole sheet can ask the store once.
    """
    found: dict[str, str] = {}
    for link in links:
        if link.listing_url:
            found[link.source] = link.listing_url
        else:
            found.setdefault(link.source, "")
    return found
