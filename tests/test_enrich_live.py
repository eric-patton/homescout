"""Every provider, against the real service, at points three thousand miles apart.

The criterion is national coverage, and the only way to check national coverage is to ask about
places that are nothing like each other. New Mexico is high, dry and over an aquifer; Louisiana is
at sea level and floods; Alaska is neither.

Marked slow and excluded from the default run. Six providers by three points is eighteen requests at
the shipped pacing, against public services that are there to be asked, once.

These are also the tests that catch the failure this feature was planned around: a public endpoint
that has moved or started refusing. When one of these fails, read it as news about the service
rather than about the code, and remember that the address is configuration.
"""

from __future__ import annotations

import pytest

from homescout.enrich import settings
from homescout.enrich.provider import ProviderFailed
from homescout.enrich.registry import create
from homescout.sources import default_session

pytestmark = pytest.mark.slow

#: Three places chosen to disagree with each other about everything this feature asks.
DISTANT = {
    "New Mexico": (34.1848, -103.3452),
    "Louisiana": (29.9511, -90.0715),
    "Alaska": (61.2181, -149.9003),
}


@pytest.fixture(scope="module")
def paced():
    return default_session(config=settings.pacing(tuple(p.name for p in create())))


@pytest.mark.parametrize("where", list(DISTANT), ids=list(DISTANT))
def test_every_provider_answers_at_a_point_in_this_state(where: str, paced) -> None:
    """feat-007/AC-12: national coverage, checked where the country stops looking alike.

    A provider that cannot be run on this installation is skipped by name rather than passed over
    silently, so the output says what was not checked. Broadband is the one that usually is: it
    needs an FCC account, and it needs that state's data downloaded, which is deliberately not
    something a test does on its own.
    """
    latitude, longitude = DISTANT[where]
    skipped: list[str] = []
    answered: dict[str, object] = {}

    for provider in create():
        if not provider.configured():
            skipped.append(provider.name)
            continue
        found = provider.fetch(paced, latitude, longitude)
        assert set(found) == set(provider.values()), provider.name
        answered.update(found)

    # Broadband on an installation with no FCC account or no downloaded state, nothing on one that
    # has both. Anything else is a provider that stopped being runnable without anybody deciding it
    # should.
    assert skipped in ([], ["broadband"]), f"unexpected providers skipped: {skipped}"
    assert set(answered) >= {
        "flood_zone",
        "elevation_ft",
        "over_principal_aquifer",
        "wildfire_hazard",
    }
    assert isinstance(answered["over_principal_aquifer"], bool)
    assert answered["elevation_ft"] is not None, "every one of these points is on land"


def test_the_places_these_points_are_in_disagree_with_each_other(paced) -> None:
    """feat-007/AC-12: coverage means different answers, not the same answer everywhere.

    A provider that returned the same value for New Mexico and coastal Louisiana would pass a
    per-point test and be useless, which is the failure this one is for.
    """
    from homescout.enrich.providers import Elevation

    heights = {
        where: Elevation().fetch(paced, *point)["elevation_ft"]
        for where, point in DISTANT.items()
    }

    assert heights["New Mexico"] > 3_000, heights
    assert heights["Louisiana"] < 100, heights
    assert len(set(heights.values())) == 3


def test_a_named_place_resolves_to_a_shape_and_a_point(tmp_path) -> None:
    """feat-007/AC-11: the boundary resolution saved searches has been waiting for.

    Two runs, on purpose: the second answers from the cache and asks the Census nothing, which is
    what makes a boundary usable inside a filtering loop.
    """
    from homescout.enrich.boundaries import CensusBoundaries
    from homescout.store import Store

    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, fetch=True)

        shape = provider.boundary("county", "Roosevelt, NM")
        assert shape is not None, "Roosevelt County, New Mexico is a real county"
        assert shape["type"] in ("Polygon", "MultiPolygon")

        point = provider.locate("Portales, NM")
        assert point is not None
        assert 34.0 < point[0] < 34.5 and -103.6 < point[1] < -103.1

        cached = CensusBoundaries(store, fetch=False)
        assert cached.boundary("county", "Roosevelt, NM") is not None
        assert cached.locate("Portales, NM") == point


def test_a_place_that_does_not_exist_is_nothing_rather_than_an_error(tmp_path) -> None:
    """feat-007/AC-4: and it is remembered, so it is not asked about again every night."""
    from homescout.enrich.boundaries import CensusBoundaries
    from homescout.store import Store

    with Store.open(tmp_path / "homescout.db") as store:
        provider = CensusBoundaries(store, fetch=True)

        assert provider.boundary("county", "Nowhere, ZZ") is None
        assert CensusBoundaries(store, fetch=False).boundary("county", "Nowhere, ZZ") is None


def test_the_broadband_provider_is_honest_about_what_it_is_missing() -> None:
    """feat-007/AC-20, feat-007/AC-21: three kinds of absent, and it says which one it is in.

    No account is one thing and no downloaded data is another, and an empty column tells you
    neither. Whichever this installation is in, the sentence has to name the way out of it.
    """
    from homescout.enrich.providers import Broadband

    provider = Broadband()
    if provider.configured():
        pytest.skip("this installation has an account and a downloaded state, so it can run it")

    said = provider.why_not()
    assert settings.BROADBAND_TOKEN in said or "homescout broadband" in said, said
    with pytest.raises(ProviderFailed):
        provider.fetch(default_session(), *DISTANT["New Mexico"])


def test_the_fcc_still_publishes_the_files_this_reads(paced) -> None:
    """feat-007/AC-16: the whole design rests on a listing that could be reorganized.

    Skipped without an account, because it needs one. What it asserts is the shape the index is
    built from: a published quarter, and a state's fixed-broadband files inside it. If the FCC
    reorganizes the listing, this is where that shows up, rather than in a refresh that quietly
    finds nothing.
    """
    from homescout.enrich import broadband as fcc

    account = fcc.credentials(None)
    if account is None:
        pytest.skip("no FCC account is configured on this installation")

    as_of = fcc.latest_quarter(paced, account)
    assert as_of and as_of[:4].isdigit(), as_of

    files = fcc.files_for(paced, account, "NM", as_of)
    assert files, "no fixed-broadband files for New Mexico"
    assert all(row.get("file_type") == "csv" for row in files)


def test_a_provider_covering_one_state_answers_inside_it_and_says_so_outside(paced) -> None:
    """feat-007/AC-26, feat-007/AC-12: partial coverage, checked on both sides of its boundary.

    Inside New Mexico this has to be a real reading, and the two acceptable ones are a kind of
    interface or the known negative. Outside it the one unacceptable answer is the known negative,
    because that is the sentence "this house is not in the wildland-urban interface" said about a
    house nobody looked at.
    """
    from homescout.enrich.providers import WildlandUrbanInterface

    provider = WildlandUrbanInterface()
    assert provider.coverage() == "New Mexico"

    inside = provider.fetch(paced, 35.6870, -105.9110)["wildland_urban_interface"]
    assert inside in ("intermix", "interface", None), inside

    for where, point in (("Louisiana", DISTANT["Louisiana"]), ("Alaska", DISTANT["Alaska"])):
        outside = provider.fetch(paced, *point)["wildland_urban_interface"]
        assert outside == "outside coverage", f"{where} read as {outside!r}"


def test_a_texas_point_inside_the_new_mexico_box_is_not_called_a_negative(paced) -> None:
    """feat-007/AC-24: El Paso, which is the case a bounding box on its own gets wrong.

    Worth its own live test rather than a fixture, because what it is really checking is that the
    county layer still answers. If this one starts failing, the second request is the thing to look
    at, and the failure mode it guards against is silent.
    """
    from homescout.enrich.providers import WildlandUrbanInterface

    found = WildlandUrbanInterface().fetch(paced, 31.7619, -106.4850)

    assert found == {"wildland_urban_interface": "outside coverage"}


def test_the_trackers_status_vocabulary_is_still_the_one_this_build_knows(tmp_path) -> None:
    """feat-007/AC-31: the assertion most likely to fail first, and failing loudly is the point.

    Every other provider here reads a value out of a response. This one reads a *vocabulary*: seven
    status words that decide which of three kinds a site is. A tracker that adds an eighth is
    not a broken tracker, it is one that has learned a distinction, and a build that quietly
    bucketed the new word would put a data centre in the wrong category on somebody's map.

    So when this fails, read it as news about the source. The fix is a line in `KIND_BY_STATUS`
    after somebody has decided what the new word means, which is a decision rather than a mapping.
    """
    from homescout.enrich import datacenters

    sites = datacenters.tracked(tmp_path, settings.endpoint("data_centers").url)

    assert len(sites) > 500, f"the tracker answered with only {len(sites)} sites"
    assert {site["kind"] for site in sites} >= {"operating", "approved", "proposed"}
    # Every record was collapsible, or `tracked` would have raised naming the status it could not
    # place. This asserts the other half: that the confidences are still the three we handle.
    seen = {site["confidence"] for site in sites}
    assert seen <= {"high", "medium", "low", ""}, f"unknown siting confidences: {seen}"


def test_both_data_centre_sources_answer_and_the_second_closes_the_first_ones_gap(tmp_path) -> None:
    """feat-007/AC-12 and feat-007/AC-35: national, and the gap is a real one that is really closed.

    Los Lunas is the case this second source exists for. Meta's campus has been running there since
    2018 and the tracker does not have it, so a build with only the tracker would tell somebody in
    Valencia County that the nearest running data centre is a hundred and ninety miles away.
    """
    from homescout.enrich import datacenters

    built = datacenters.built(tmp_path, settings.endpoint("data_centers_built").url)
    assert len(built) > 500, f"OpenStreetMap answered with only {len(built)} buildings"

    nearby = datacenters.Nearby(
        datacenters.tracked(tmp_path, settings.endpoint("data_centers").url) + built
    )
    got = nearby.nearest("operating", 34.8100, -106.7300)
    assert got is not None
    _, miles = got
    assert miles < 10, f"the nearest running data centre to Los Lunas read as {miles:.0f} miles"
