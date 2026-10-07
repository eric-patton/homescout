"""Collection cards are advertisements, not individual property observations."""

from __future__ import annotations

import json

import pytest

from export_fakes import listing, load
from homescout.export import rows_of
from homescout.sources import BoundingBox, SearchQuery
from homescout.sources.zillow import ZillowSource
from homescout.store import Store
from sources_fakes import FakeResponse, FakeTransport, session_with

BOX = BoundingBox(30.0, -91.0, 31.0, -90.0)
HOUSE = {
    "zpid": "123",
    "detailUrl": "/homedetails/123_zpid/",
    "hdpData": {"homeInfo": {"zpid": "123", "streetAddress": "123 Example Rd"}},
}
COMMUNITY = {
    "isCdpResult": True,
    "isBuilding": True,
    "plid": "30151161",
    "buildingId": "30.240332--90.979996",
    "address": "Clare Ct, Geismar, LA",
    "detailUrl": "/community/clare-court/30151161_plid/",
    "latLong": {"latitude": 30.240332, "longitude": -90.979996},
}


def source_for(cards: list[dict], *, total: int | None = None) -> ZillowSource:
    category = {"searchResults": {"mapResults": cards}}
    if total is not None:
        category["searchList"] = {"totalResultCount": total}
    payload = {"cat1": category}
    transport = FakeTransport(default=FakeResponse(body=json.dumps(payload).encode()))
    return ZillowSource(session_with(transport))


@pytest.mark.parametrize("collection", [
    COMMUNITY,
    {"isCdpResult": True, "plid": "30151161"},
    {"isBuilding": True, "buildingId": "30.4,-90.0"},
    {"detailUrl": "/community/a/123_plid/"},
    {"detailUrl": "https://www.zillow.com/b/building/30.4,-90.0_ll/"},
])
def test_collection_cards_do_not_become_property_observations(collection: dict) -> None:
    """feat-005/AC-1, feat-005/AC-10: one property per row, not a community advertisement."""
    result = source_for([HOUSE, collection]).run_search(SearchQuery(area=BOX))
    assert [row.source_listing_id for row in result.rows] == ["123"]
    assert result.rows[0].payload == HOUSE


def test_a_sparse_individual_property_is_not_mistaken_for_a_collection() -> None:
    """feat-005/AC-10: a missing address is not evidence that a result is an advertisement."""
    sparse = {"zpid": "456", "isBuilding": True, "isCdpResult": True}
    address_only = {"addressStreet": "789 Example Rd"}
    result = source_for([sparse, address_only]).run_search(SearchQuery(area=BOX))
    assert len(result.rows) == 2
    assert result.rows[0].source_listing_id == "456"
    assert result.rows[1].fields.address_line == "789 Example Rd"


def test_collection_filtering_does_not_lower_the_ceiling_total() -> None:
    """feat-005/AC-3: removing advertisements cannot hide the need to subdivide a box."""
    for reported in (None, 900):
        page = source_for([COMMUNITY] * 550, total=reported)._page(SearchQuery(area=BOX), 0)
        assert page.rows == ()
        assert page.total == (550 if reported is None else 900)


def test_retracting_a_non_property_keeps_its_history_but_removes_current_rows(store: Store) -> None:
    """feat-011/AC-2, feat-001/AC-14, feat-001/AC-15: cleanup does not destroy evidence."""
    loaded = load(store, [listing("real"), listing("card", address_line=None)])
    bad = loaded["card"]
    store.set_annotation(bad, notes="Keep the original evidence")
    snapshot = store.snapshot_at(bad, loaded.run_id)
    source_rows = store.source_links(bad)
    with store._conn:
        store._conn.execute("UPDATE listings SET retracted=1 WHERE id=?", (bad,))

    assert [row.listing_id for row in rows_of(store, loaded.run_id)] == [loaded["real"]]
    assert store.snapshot_at(bad, loaded.run_id) == snapshot
    assert store.source_links(bad) == source_rows
    assert store.get_annotation(bad).notes == "Keep the original evidence"
    assert store.get_listing(bad).retracted
