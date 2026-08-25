"""Each public service, against a recorded shape of its answer.

Recorded from the real endpoints on the day they were verified, so a service changing its response
shape shows up here as a fixture that no longer matches reality rather than as a test that quietly
passes against a stale idea of the schema.
"""

from __future__ import annotations

import pytest

from enrich_fakes import CountingTransport, session
from homescout.enrich import settings
from homescout.enrich.provider import ProviderFailed
from homescout.enrich.providers import Aquifer, Broadband, Elevation, Flood, Wildfire
from homescout.enrich.registry import create, registered

PLACE = (34.1848, -103.3452)


def answering(payload) -> tuple:
    transport = CountingTransport({"http": payload})
    return session(transport), transport


def test_the_six_providers_exist_and_are_individually_named() -> None:
    """feat-007/AC-11: flood, broadband, aquifer, wildfire, elevation, and boundary resolution."""
    assert set(registered()) == {"flood", "elevation", "aquifer", "wildfire", "broadband"}

    from homescout.enrich.boundaries import CensusBoundaries

    assert CensusBoundaries.name == "boundaries", "the sixth is a port rather than a value provider"
    assert {provider.name for provider in create()} == set(registered())


def test_every_provider_declares_a_name_a_criterion_can_use() -> None:
    """feat-007/AC-1: checked at import too, and asserted here so the reason is written down."""
    from homescout.rules import namespace as ns

    for provider in create():
        for name in provider.values():
            field = ns.find(name)
            assert field is not None and field.origin == "enriched", name


def test_a_flood_zone_at_a_point() -> None:
    """feat-007/AC-11: the letter everybody means, with the qualifier that changes what it means."""
    paced, _ = answering({"features": [{"attributes": {"FLD_ZONE": "X",
                                                       "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE"}}]})

    found = Flood().fetch(paced, *PLACE)

    assert found == {"flood_zone": "X (0.2 PCT ANNUAL CHANCE)"}


def test_a_point_in_no_mapped_flood_zone_is_an_answer_rather_than_a_gap() -> None:
    """feat-007/AC-7: the spec's first edge case, at the provider that meets it most often."""
    paced, _ = answering({"features": []})

    assert Flood().fetch(paced, *PLACE) == {"flood_zone": None}


def test_an_elevation_comes_back_in_feet() -> None:
    """feat-007/AC-11: and rounded, because a tenth of a foot is more precision than exists."""
    paced, _ = answering({"value": 4009.3915325})

    assert Elevation().fetch(paced, *PLACE) == {"elevation_ft": 4009.4}


def test_an_aquifer_is_a_yes_or_a_no_and_never_a_shrug() -> None:
    """feat-007/AC-7: the layer covers the country, so no polygon means no aquifer."""
    over, _ = answering({"features": [{"attributes": {"AQ_NAME": "High Plains aquifer"}}]})
    outside, _ = answering({"features": []})

    assert Aquifer().fetch(over, *PLACE) == {"over_principal_aquifer": True}
    assert Aquifer().fetch(outside, *PLACE) == {"over_principal_aquifer": False}


@pytest.mark.parametrize(
    ("pixel", "word"), [("1", "very low"), ("3", "moderate"), ("5", "very high")]
)
def test_a_wildfire_class_becomes_a_word(pixel: str, word: str) -> None:
    """feat-007/AC-11: a criterion compares words, and nobody remembers what class four means."""
    paced, _ = answering({"value": pixel})

    assert Wildfire().fetch(paced, *PLACE) == {"wildfire_hazard": word}


def test_a_wildfire_class_nobody_recognizes_is_a_failure_rather_than_a_guess() -> None:
    """feat-007/AC-4: a changed legend leaves the cached value alone instead of overwriting it."""
    paced, _ = answering({"value": "42"})

    with pytest.raises(ProviderFailed, match="legend"):
        Wildfire().fetch(paced, *PLACE)


def test_no_data_from_the_raster_is_missing_rather_than_zero() -> None:
    """feat-007/AC-7: outside the raster's coverage is nothing, which is not a hazard rating."""
    paced, _ = answering({"value": "NoData"})

    assert Wildfire().fetch(paced, *PLACE) == {"wildfire_hazard": None}


def test_a_service_that_changed_its_shape_fails_rather_than_caching_a_blank() -> None:
    """feat-007/AC-4: the second edge case. Silence overwriting an answer is the worst outcome."""
    paced, _ = answering({"nothing": "recognizable"})

    with pytest.raises(ProviderFailed, match="features"):
        Flood().fetch(paced, *PLACE)


def test_an_arcgis_refusal_is_a_failure_even_though_it_arrives_as_a_success() -> None:
    """feat-007/AC-5: ArcGIS answers a refusal with HTTP 200 and an error object in the body."""
    paced, _ = answering({"error": {"code": 498, "message": "Invalid token"}})

    with pytest.raises(ProviderFailed, match="refused"):
        Flood().fetch(paced, *PLACE)


def test_broadband_is_absent_until_both_halves_are_supplied(monkeypatch, tmp_path) -> None:
    """feat-007/AC-20: the one that needs a credential says so, and asks nobody anything without it.

    The spec's security requirement was narrowed for this during planning, and the narrowing is what
    this asserts: no credential is required and none is embedded, and with none supplied the tool is
    fully functional and this provider is simply skipped.

    Both halves, because the FCC's file API wants an account name alongside the token. A token on
    its own is not a configured provider: it is somebody about to watch every request fail with a
    message about authentication and go looking at the wrong thing.

    Pointed at an empty workspace, because a credential is read from the environment or the `.env`
    beside the database and a test that says "none" has to mean both of them.
    """
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    monkeypatch.delenv(settings.BROADBAND_TOKEN, raising=False)
    monkeypatch.delenv(settings.BROADBAND_USERNAME, raising=False)
    provider = Broadband()

    assert provider.configured() is False
    assert settings.BROADBAND_TOKEN in provider.why_not()
    assert settings.BROADBAND_USERNAME in provider.why_not()

    paced, transport = answering({})
    with pytest.raises(ProviderFailed):
        provider.fetch(paced, *PLACE)
    assert transport.count == 0, "nothing was asked of anybody"

    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    assert Broadband().configured() is False, "half a credential is not a credential"


def test_a_credential_written_in_the_env_file_reaches_the_provider(monkeypatch, tmp_path) -> None:
    """feat-007/AC-20: the settings page counted that file, and this is what makes that true.

    Enabling this provider is documented in two places as "the environment or the `.env` file", and
    the page that reports whether a key is present has always read both. The provider read only the
    environment, so a key written in the file left the page saying ready and the provider saying not
    configured, which is the worst of the three possible states.

    It also settles a Windows question that has no other answer: this interface is started at log on
    and keeps the environment it was born with, so a variable set afterwards cannot reach it without
    a restart. A line in the file reaches it on the next lookup.
    """
    from homescout.enrich.broadband import credentials

    monkeypatch.delenv(settings.BROADBAND_TOKEN, raising=False)
    monkeypatch.delenv(settings.BROADBAND_USERNAME, raising=False)
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    assert credentials(None) is None, "nothing written anywhere yet"

    (tmp_path / ".env").write_text(
        "# a credential, the way a person writes one\n"
        f"{settings.BROADBAND_USERNAME}=someone@example.invalid\n"
        f"{settings.BROADBAND_TOKEN}=from-the-file\n",
        encoding="utf-8",
    )
    assert credentials(None) == ("someone@example.invalid", "from-the-file")

    # And the environment still wins over the file, which is the order every other setting uses.
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "from-the-environment")
    assert settings.token(settings.BROADBAND_TOKEN) == "from-the-environment"


def test_an_endpoint_can_be_moved_without_touching_the_code(monkeypatch) -> None:
    """feat-007/AC-14: the brief's flood address died before this feature was built.

    Which is the whole argument for this: these are public services run by agencies with their own
    reorganizations, and the next one to move should be a line in an environment file.
    """
    assert "hazards.fema.gov" in settings.endpoint("flood").url

    monkeypatch.setenv("HOMESCOUT_ENRICH_FLOOD_URL", "https://elsewhere.example/query")
    assert settings.endpoint("flood").url == "https://elsewhere.example/query"

    paced, transport = answering({"features": []})
    Flood().fetch(paced, *PLACE)
    assert transport.requests[0].startswith("https://elsewhere.example/query?")


def test_every_provider_is_paced_and_none_waits_on_another() -> None:
    """feat-007/AC-13: the same politeness the listing sources get, keyed per provider.

    Per provider rather than shared, so a slow federal service cannot make a fast one slower, and at
    the floor the politeness layer permits rather than below it.
    """
    from homescout.sources.politeness import DELAY_RANGE_SECONDS

    config = settings.pacing(("flood", "elevation"))

    assert config.policy_for("flood").delay == settings.PROVIDER_DELAY_SECONDS
    assert config.policy_for("flood").delay >= DELAY_RANGE_SECONDS[0]
    assert config.policy_for("elevation") is not None
    config.policy_for("flood").validated("flood")
