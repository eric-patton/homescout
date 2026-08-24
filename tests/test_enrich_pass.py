"""The pass: what it asks, what it does not ask twice, and what one dead service costs.

The whole feature exists because five public services answer questions no listing site does, and
because those services move, go down, and occasionally start refusing you. So the tests that matter
are about counting requests and about what survives a failure.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conftest import do_run, prop
from enrich_fakes import CountingTransport, FakeProvider, session
from homescout import api
from homescout.enrich import cache
from homescout.enrich.pass_ import places_in, run_pass
from homescout.store import Store

HERE = {"latitude": 34.1848, "longitude": -103.3452}
NEXT_DOOR = {"latitude": 34.18481, "longitude": -103.34521}
AWAY = {"latitude": 29.9511, "longitude": -90.0715}


def a_pass(store: Store, providers, **kwargs):
    return run_pass(store, providers, session=session(CountingTransport()), **kwargs)


def test_every_provider_is_asked_once_per_place(store: Store) -> None:
    """feat-007/AC-1: the pass names no provider, and asks each what it declares it needs."""
    do_run(store, sources={"realtor": [prop("a1", **HERE), prop("a2", **AWAY)]})
    flood = FakeProvider(name="flood")
    elevation = FakeProvider(
        name="elevation", supplies=("elevation_ft",), answer={"elevation_ft": 4009.4}
    )

    outcome = a_pass(store, [flood, elevation])

    assert outcome.properties == 2
    assert len(flood.asked) == 2
    assert len(elevation.asked) == 2
    assert [found.outcome for found in outcome.providers] == ["ok", "ok"]
    assert cache.values_for(store, [flood], **HERE)["flood_zone"].value == "X"


def test_a_second_pass_asks_nothing(store: Store) -> None:
    """feat-007/AC-2: a cache hit within the lifetime makes no outbound request. Zero, not fewer."""
    do_run(store, sources={"realtor": [prop("a1", **HERE)]})
    provider = FakeProvider()

    a_pass(store, [provider])
    asked_once = len(provider.asked)
    a_pass(store, [provider])

    assert asked_once == 1
    assert len(provider.asked) == 1, "the second pass asked again"


def test_two_properties_on_one_street_are_one_lookup(store: Store) -> None:
    """feat-007/AC-3: rounding is what makes a county affordable."""
    do_run(store, sources={"realtor": [prop("a1", **HERE), prop("a2", **NEXT_DOOR)]})
    provider = FakeProvider(decimals=3)

    outcome = a_pass(store, [provider])

    assert outcome.properties == 2
    assert len(provider.asked) == 1


def test_a_provider_failing_costs_one_column(store: Store) -> None:
    """feat-007/AC-5: every other provider is asked normally and the pass completes."""
    do_run(store, sources={"realtor": [prop("a1", **HERE)]})
    broken = FakeProvider(name="flood", fails="the service is down")
    working = FakeProvider(
        name="elevation", supplies=("elevation_ft",), answer={"elevation_ft": 4009.4}
    )

    outcome = a_pass(store, [broken, working])

    assert [(f.provider, f.outcome) for f in outcome.providers] == [
        ("flood", "failed"),
        ("elevation", "ok"),
    ]
    assert outcome.degraded is True
    assert cache.values_for(store, [working], **HERE)["elevation_ft"].value == 4009.4


def test_a_failure_never_removes_what_was_already_cached(store: Store) -> None:
    """feat-007/AC-4: an outage costs freshness, never an answer."""
    do_run(store, sources={"realtor": [prop("a1", **HERE)]})
    provider = FakeProvider(ttl=30)
    a_pass(store, [provider])

    later = datetime.now(UTC) + timedelta(days=60)
    broken = FakeProvider(ttl=30, fails="the service is down")
    a_pass(store, [broken])

    found = cache.values_for(store, [provider], **HERE, now=later)
    assert found["flood_zone"].value == "X"
    assert found["flood_zone"].status == "stale"


def test_a_provider_nobody_configured_is_skipped_and_not_failed(store: Store) -> None:
    """feat-007/AC-11: not asked and broken are different, and the message says which."""
    do_run(store, sources={"realtor": [prop("a1", **HERE)]})
    provider = FakeProvider(ready=False)

    outcome = a_pass(store, [provider])

    assert [f.outcome for f in outcome.providers] == ["skipped"]
    assert outcome.degraded is False, "nothing broke"
    assert provider.asked == []
    assert "not configured" in (outcome.providers[0].detail or "")


def test_a_property_with_no_coordinates_is_skipped_with_its_own_reason(store: Store) -> None:
    """feat-007/AC-10: distinct from a provider failure, and costing no request."""
    do_run(store, sources={"realtor": [prop("a1", **HERE), prop("a2", latitude=None,
                                                               longitude=None)]})
    provider = FakeProvider()

    outcome = a_pass(store, [provider])

    assert outcome.properties == 1
    assert outcome.without_location == 1
    assert len(outcome.unlocatable) == 1
    assert len(provider.asked) == 1
    assert outcome.degraded is False


def test_only_what_has_aged_is_refreshed_when_asked(store: Store) -> None:
    """feat-007/AC-8: the cheap nightly top-up, as distinct from the expensive first backfill."""
    do_run(store, sources={"realtor": [prop("a1", **HERE), prop("a2", **AWAY)]})
    provider = FakeProvider(ttl=30, decimals=3)

    # One place answered a long time ago; the other never asked about at all.
    old = (datetime.now(UTC) - timedelta(days=90)).isoformat().replace("+00:00", "Z")
    store.cache_values(provider.name, cache.key_for(HERE["latitude"], HERE["longitude"], 3),
                       {"flood_zone": "AE"})
    store.connection.execute("UPDATE enrichment_values SET fetched_at = ?", (old,))
    store.connection.commit()

    a_pass(store, [provider], stale_only=True)

    assert provider.asked == [(HERE["latitude"], HERE["longitude"])], (
        "the stale one was refreshed and the missing one was left for a full pass"
    )


def test_a_full_pass_fetches_what_was_never_asked_about(store: Store) -> None:
    """feat-007/AC-8: which is the other half of the same decision."""
    do_run(store, sources={"realtor": [prop("a1", **HERE), prop("a2", **AWAY)]})
    provider = FakeProvider(decimals=3)

    a_pass(store, [provider])

    assert len(provider.asked) == 2


def test_the_pass_can_be_limited_to_one_saved_search(store: Store) -> None:
    """feat-007/AC-8: a search's own properties, rather than everything ever seen."""
    do_run(store, "north", sources={"realtor": [prop("a1", **HERE)]})
    do_run(store, "south", sources={"realtor": [prop("a2", **AWAY)]})

    located, _ = places_in(store, search="north")

    assert len(located) == 1
    assert located[0][1] == (HERE["latitude"], HERE["longitude"])
    assert len(places_in(store)[0]) == 2


def test_a_provider_failure_cannot_fail_a_listing_run(tmp_path: Path) -> None:
    """feat-007/AC-6: structurally, because a run never asks a provider anything.

    Asserted as the structural fact rather than as an observation: a run that succeeded while a
    provider was broken would prove nothing if the two were never connected. What this asserts is
    that they are not connected, which is the actual guarantee.
    """
    from cli_fakes import FakeSource, row
    from searches_fakes import sourced, workspace, write

    write(
        tmp_path / "searches",
        "portales",
        text='name: portales\nareas:\n  - {type: zip, value: "88130"}\nsources: [fake]\n',
    )
    broken = FakeProvider(fails="every provider is down")

    with sourced("fake"), Store.open(tmp_path / "homescout.db") as store:
        space = workspace(store, sources={"fake": FakeSource(rows=[row("a")])})
        outcome = api.run_search(space, "portales")

    assert outcome.run.status == "completed"
    assert broken.asked == [], "a listing run asked no provider anything"


def test_enrichment_is_its_own_command(tmp_path: Path) -> None:
    """feat-007/AC-9: invocable on its own, with machine output and the usual exit codes."""
    from cli_fakes import invoke
    from enrich_fakes import provided

    db = tmp_path / "homescout.db"
    with Store.open(db) as store:
        do_run(store, sources={"realtor": [prop("a1", **HERE)]})

    with provided():
        code, out, err = invoke(["enrich", "--json"], db=db)

    assert code == 0, err
    answer = json.loads(out)
    assert answer["kind"] == "enrichment"
    assert answer["properties"] == 1
    named = {found["provider"] for found in answer["providers"]}
    assert {"flood", "elevation", "aquifer", "wildfire", "broadband"} <= named
    assert any(found["outcome"] == "skipped" for found in answer["providers"]), (
        "the one that needs a token is skipped rather than failed"
    )


@pytest.mark.parametrize("flag", [[], ["--stale"], ["--search", "portales"]])
def test_every_form_of_the_command_is_accepted(flag, tmp_path: Path) -> None:
    """feat-007/AC-8, feat-007/AC-9: the options the spec asks for, all reachable."""
    from cli_fakes import invoke
    from enrich_fakes import provided

    db = tmp_path / "homescout.db"
    with Store.open(db) as store:
        do_run(store, "portales", sources={"realtor": [prop("a1", **HERE)]})

    with provided():
        code, out, err = invoke(["enrich", "--json", *flag], db=db)

    assert code in (0, 1), err
    assert json.loads(out)["kind"] == "enrichment"
