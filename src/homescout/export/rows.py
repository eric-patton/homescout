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

from collections.abc import Mapping, Sequence
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
    area_notes: Mapping[tuple[str, str], str] = field(default_factory=dict)


def rows_for(
    store: Store,
    run_id: str,
    *,
    include_dropped: bool = False,
    root: Any = None,
) -> tuple[Row, ...]:
    """Every property this run's criteria kept, as rows, in the order the results come out in.

    `include_dropped` is the spec's "unless explicitly requested". A property a `drop` rule removed
    is still observed, still snapshotted and still in the store; it is simply not in the sheet
    somebody asked for, unless they asked for it.
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

    annotations = _annotations(store, [entry.listing_id for entry in wanted])
    enriched = _enriched(store, wanted)
    from_model = _model_values(store, run_id, root)
    notes = _area_notes(store)

    return tuple(
        Row(
            listing_id=entry.listing_id,
            fields=entry.fields,
            history=store.history(entry.listing_id),
            presence=store.get_listing(entry.listing_id).presence,
            annotation=annotations.get(entry.listing_id),
            extracted=extracted_values(entry.fields, model=from_model.get(entry.listing_id)),
            enriched=enriched.get(entry.listing_id, {}),
            flags=entry.flags,
            sources=_sources_of(store, entry.listing_id),
            area_notes=notes,
        )
        for entry in wanted
    )


@dataclass(frozen=True, slots=True)
class _Kept:
    """One property on its way into the sheet, before anything was looked up about it."""

    listing_id: str
    fields: ListingFields
    flags: tuple[str, ...] = ()
    dropped: bool = False


def _annotations(store: Store, listing_ids: Sequence[str]) -> dict[str, Annotation]:
    """Every annotation these properties carry.

    One call apiece for now, because the store has no bulk read for them and adding one is that
    feature's business rather than this one's. It is a lookup by primary key against a local file,
    which is the cheapest thing in this module by a wide margin.
    """
    found: dict[str, Annotation] = {}
    for listing_id in listing_ids:
        held = store.get_annotation(listing_id)
        if held is not None:
            found[listing_id] = held
    return found


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


def _sources_of(store: Store, listing_id: str) -> tuple[str, ...]:
    """Which listing sites this property was seen on, which is its provenance in one cell."""
    return tuple(sorted({link.source for link in store.source_links(listing_id)}))
