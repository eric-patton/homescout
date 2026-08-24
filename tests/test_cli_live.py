"""The whole thing, against the real site.

Everything else in this suite is exact and instant because the network is not in it. This one is the
opposite on purpose: a real saved search, a real source, a real database, run twice through the real
command line. It is the only test that can catch the class of mistake where every part works and the
assembly does not.

Marked slow and excluded from the default run. It fetches from a live site, at the shipped pacing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli_fakes import invoke
from homescout.search import InMemorySearch, register_catalog, unregister_catalog
from homescout.sources import City, SearchQuery
from homescout.store import Store

pytestmark = pytest.mark.slow

#: Small enough that a whole run is quick and cheap for the site, real enough to prove the point.
PLACE = City("Portales", "NM")


@pytest.fixture
def portales():
    """A saved search over one small market, registered the way a definition file will be."""
    definition = InMemorySearch(
        name="portales",
        sources=("realtor",),
        asks=(SearchQuery(area=PLACE, price_max=400_000),),
    )
    register_catalog(lambda _root: __import__(
        "homescout.search", fromlist=["x"]
    ).InMemoryCatalog([definition]))
    try:
        yield definition
    finally:
        unregister_catalog()


def test_a_real_search_runs_end_to_end_and_the_second_run_finds_nothing_new(
    portales, tmp_path: Path
) -> None:
    """feat-003/AC-4, feat-003/AC-9, feat-003/AC-10: the assembly, not the parts.

    Two runs minutes apart over the same market. The first is all new because there is no history;
    the second must find nothing new, because new is computed by comparing what was recorded rather
    than read from any field. If the identity rule, the recording, or the comparison were wrong,
    the second run would report the whole market again.

    Images are off. This is about the loop, and fetching one picture per property at the shipped
    pacing would make it the slowest test in the suite by an order of magnitude.
    """
    db = tmp_path / "live" / "homescout.db"
    db.parent.mkdir()

    code, out, err = invoke(["run", "portales", "--json", "--no-images"], db=db)
    assert code == 0, err
    first = json.loads(out)["searches"][0]

    assert first["sources"][0]["source"] == "realtor"
    assert first["sources"][0]["outcome"] == "ok"
    assert first["counts"]["matched"] > 0, "the market is not empty"
    assert first["counts"]["new"] == first["counts"]["matched"], "nothing was known before"
    assert "price_max" in first["sources"][0]["applied_by_source"]

    code, out, err = invoke(["run", "portales", "--json", "--no-images"], db=db)
    assert code == 0, err
    second = json.loads(out)["searches"][0]

    assert second["counts"]["matched"] > 0
    assert second["counts"]["new"] == 0, "the same market twice is not two markets"
    assert second["counts"]["gone"] == 0

    with Store.open(db) as store:
        runs = store.runs("portales", only_completed=True)
        assert len(runs) == 2
        assert all(r.all_sources_succeeded for r in runs)


def test_a_real_digest_stays_small_over_a_real_market(portales, tmp_path: Path) -> None:
    """feat-003/AC-11: the size claim, against rows nobody wrote for a test.

    Real listings carry long descriptions and photo lists, which is exactly the material that would
    make a digest balloon if any of it leaked into one. Two runs of the same market: the second
    changed nothing, so the second digest has to be small however large the market is.
    """
    db = tmp_path / "sized" / "homescout.db"
    db.parent.mkdir()

    code, first_out, err = invoke(["run", "portales", "--json", "--no-images"], db=db)
    assert code == 0, err
    code, second_out, err = invoke(["run", "portales", "--json", "--no-images"], db=db)
    assert code == 0, err

    second = json.loads(second_out)["searches"][0]
    matched = second["counts"]["matched"]

    assert matched > 20, "too small a market to say anything about size"
    assert second["counts"]["new"] == 0
    assert len(second_out) < 1_500, f"a digest of {len(second_out)} bytes over {matched} properties"
    assert len(second_out) < len(first_out), "the run with nothing to report is the smaller one"


def test_a_real_run_retrieves_one_preview_image_and_not_twice(portales, tmp_path: Path) -> None:
    """feat-003/AC-27: the caller contract the source adapters left on record, against the site.

    One small market, images on, run twice. The second run must make no image request at all, which
    is the difference between a nightly run costing seconds and costing minutes.
    """
    db = tmp_path / "images" / "homescout.db"
    db.parent.mkdir()
    portales.asks = (SearchQuery(area=PLACE, price_max=200_000),)

    code, _, err = invoke(["run", "portales", "--json"], db=db)
    assert code == 0, err

    with Store.open(db) as store:
        stored = [store.get_preview_image(listing.id) for listing in store.listings()]
        kept = [image for image in stored if image is not None]
        assert kept, "the site offered no image for anything, which would be a surprise"
        first_times = {image.listing_id: image.retrieved_at for image in kept}
        for image in kept:
            on_disk = db.parent / image.path
            assert on_disk.exists() and on_disk.stat().st_size > 0

    code, _, err = invoke(["run", "portales", "--json"], db=db)
    assert code == 0, err

    with Store.open(db) as store:
        again = {
            image.listing_id: image.retrieved_at
            for image in (store.get_preview_image(listing.id) for listing in store.listings())
            if image is not None
        }
    assert again == first_times, "an image already on disk was fetched again"


def test_a_drawn_shape_in_a_file_runs_against_the_real_site(tmp_path: Path) -> None:
    """feat-004/AC-4, feat-004/AC-5: the whole two-stage chain, outside the fakes.

    A definition file with a shape nobody can search for, a source that has never heard of a
    polygon, and a run that turns one into the other. Realtor takes named places and a radius, so
    the shape goes out as a circle containing it, and what falls outside is removed here.

    The assertion that matters is the last one: everything recorded is inside the shape, and the
    circle was wider than the shape, so something was necessarily thrown away.
    """
    from homescout.search.geometry import contains, prepare, to_geometry

    shape = {
        "type": "Polygon",
        "coordinates": [
            [
                [-103.36, 34.16],
                [-103.32, 34.16],
                [-103.32, 34.20],
                [-103.36, 34.20],
                [-103.36, 34.16],
            ]
        ],
    }
    searches = tmp_path / "live" / "searches"
    searches.mkdir(parents=True)
    (searches / "drawn.yaml").write_text(
        "name: drawn\n"
        "description: A shape no listing site can be asked for\n"
        "areas:\n"
        f"  - {{type: polygon, name: mid-portales, geometry: {json.dumps(shape)}}}\n"
        "filters:\n"
        "  price: {max: 600000}\n"
        "sources: [realtor]\n",
        encoding="utf-8",
        newline="\n",
    )
    db = tmp_path / "live" / "homescout.db"

    code, out, err = invoke(["run", "drawn", "--json", "--no-images"], db=db)
    assert code == 0, err
    entry = json.loads(out)["searches"][0]
    assert entry["sources"][0]["outcome"] == "ok"
    assert entry["counts"]["matched"] > 0, "the middle of Portales is not empty"

    prepared = prepare(to_geometry(shape))
    with Store.open(db) as store:
        run_id = entry["run_id"]
        recorded = store.snapshots_for_run(run_id)
        assert recorded
        for snapshot in recorded:
            fields = snapshot.fields
            assert fields.latitude is not None and fields.longitude is not None
            assert contains(prepared, fields.latitude, fields.longitude), (
                f"{fields.address_line} is outside the shape that was asked for"
            )
