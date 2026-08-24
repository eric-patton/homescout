"""Every provider, against the real service, at points three thousand miles apart.

The criterion is national coverage, and the only way to check national coverage is to ask about
places that are nothing like each other. New Mexico is high, dry and over an aquifer; Louisiana is
at sea level and floods; Alaska is neither.

Marked slow and excluded from the default run. Five providers by three points is fifteen requests at
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
    silently, so the output says what was not checked. Today that is broadband, which needs a token.
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

    # Broadband on an installation with no token, nothing on one that has a key. Anything else is
    # a provider that stopped being runnable without anybody deciding it should.
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


def test_the_broadband_provider_is_honest_about_needing_a_key() -> None:
    """feat-007/AC-11: the one that cannot run says why, rather than failing mysteriously."""
    from homescout.enrich.providers import Broadband

    provider = Broadband()
    if provider.configured():
        pytest.skip("a token is configured, so this installation can run it")

    assert settings.BROADBAND_TOKEN in provider.why_not()
    with pytest.raises(ProviderFailed):
        provider.fetch(default_session(), *DISTANT["New Mexico"])
