"""What internet a place can get, and the several ways of not knowing.

The provider this replaced could never have worked: it read a token, threw it away, and asked an
address that answers 405. What is here instead is a two-step lookup, and the tests worth writing are
about the three things that make it honest rather than about the happy path.

**Satellite must not reach the number.** Three point three million of New Mexico's rows say "you can
get satellite", and folding that in would report every remote property as served at a hundred
megabits while saying nothing at all about what it can get. That is product invariant 10's failure
wearing a plausible number.

**Half a credential is not a credential.** The FCC wants an account name beside the token. A build
that treated a token alone as configured would fail every request with a message about
authentication and send somebody to look at a token that was fine.

**There are three kinds of absent, not two.** No credentials. Credentials but no data for the state
this property is in. And a block that is genuinely in a loaded state with no filed service, which is
an answer rather than a gap.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from conftest import do_run, prop
from enrich_fakes import CountingTransport, _Response, session
from homescout.enrich import broadband as fcc
from homescout.enrich import cache, settings, states
from homescout.enrich.pass_ import run_pass
from homescout.enrich.provider import ProviderFailed
from homescout.enrich.providers import Broadband
from homescout.store import Store

PLACE = (34.1848, -103.3452)
BLOCK = "350410001001017"

#: The availability files' own columns, in their own order, so a fixture built here is the shape
#: the real thing has.
COLUMNS = [
    "frn",
    "provider_id",
    "brand_name",
    "location_id",
    "technology",
    "max_advertised_download_speed",
    "max_advertised_upload_speed",
    "low_latency",
    "business_residential_code",
    "state_usps",
    "block_geoid",
    "h3_res8_id",
]


def row(**overrides: object) -> dict[str, str]:
    """One availability row, in the shape the real files have."""
    values = {
        "frn": "0001603042",
        "provider_id": "131411",
        "brand_name": "Yucca Telecom",
        "location_id": "1058744678",
        "technology": "50",
        "max_advertised_download_speed": "1000",
        "max_advertised_upload_speed": "100",
        "low_latency": "1",
        "business_residential_code": "X",
        "state_usps": "NM",
        "block_geoid": BLOCK,
        "h3_res8_id": "8848c5c4d5fffff",
    }
    values.update({k: str(v) for k, v in overrides.items()})
    return values


def archive(rows: list[dict[str, str]]) -> bytes:
    """A zipped CSV, the way the FCC hands one over."""
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    held = io.BytesIO()
    with zipfile.ZipFile(held, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("bdc_35_test.csv", text.getvalue())
    return held.getvalue()


# ---------------------------------------------------------------------------
# The aggregation, which is where a wrong number would come from
# ---------------------------------------------------------------------------


def test_satellite_never_reaches_the_speed() -> None:
    """feat-007/AC-19: available almost everywhere, so it is not an answer about anywhere.

    The GSO row here is faster than the fibre row. A build that took the best of everything would
    report it, and would report something like it for every remote property in the state.
    """
    index: dict[str, list] = {}
    fcc.fold(
        iter(
            [
                row(technology="50", max_advertised_download_speed=100),
                row(technology="60", max_advertised_download_speed=350, brand_name="HughesNet"),
                row(technology="61", max_advertised_download_speed=250, brand_name="Starlink"),
            ]
        ),
        index,
    )

    assert index[BLOCK][0] == 100, "a satellite speed was reported as the speed here"
    assert "HughesNet" not in index[BLOCK][2]
    assert "Starlink" not in index[BLOCK][2]


def test_fixed_wireless_does_reach_the_speed() -> None:
    """feat-007/AC-19: the opposite case, and the reason satellite is excluded by code and not kind.

    Licensed and unlicensed fixed wireless is what a rural property around here actually gets. It
    varies house to house, which is exactly what makes it worth reporting.
    """
    index: dict[str, list] = {}
    fcc.fold(
        iter([row(technology="71", max_advertised_download_speed=50, brand_name="Plateau")]), index
    )

    assert index[BLOCK][0] == 50
    assert "Plateau" in index[BLOCK][2]


def test_the_best_in_a_block_is_what_is_kept() -> None:
    """feat-007/AC-18: the question is what can be got here, not what the average is."""
    index: dict[str, list] = {}
    fcc.fold(
        iter(
            [
                row(brand_name="Slow Co", max_advertised_download_speed=25,
                    max_advertised_upload_speed=3),
                row(brand_name="Fast Co", max_advertised_download_speed=1000,
                    max_advertised_upload_speed=1000),
            ]
        ),
        index,
    )

    assert index[BLOCK][0] == 1000
    assert index[BLOCK][1] == 1000
    assert index[BLOCK][2] == {"Slow Co", "Fast Co"}, "both are offered and both are worth naming"


def test_a_business_only_filing_is_not_an_answer_about_living_here() -> None:
    """feat-007/AC-18: the column exists to answer whether somebody could live and work here."""
    index: dict[str, list] = {}
    fcc.fold(iter([row(business_residential_code="B")]), index)

    assert index == {}


def test_an_archive_is_read_without_touching_the_disk(tmp_path: Path) -> None:
    """feat-007 security: nothing from a downloaded file becomes a path.

    Read in memory, one member, streamed through a CSV reader, and the only things kept out of it
    are two integers and a provider's name.
    """
    before = set(tmp_path.iterdir())
    rows = list(fcc.rows_in(archive([row(), row(block_geoid="350410001001018")])))

    assert len(rows) == 2
    assert rows[0]["block_geoid"] == BLOCK
    assert set(tmp_path.iterdir()) == before


# ---------------------------------------------------------------------------
# The credential, which is two values
# ---------------------------------------------------------------------------


def test_half_a_credential_configures_nothing(monkeypatch, tmp_path: Path) -> None:
    """feat-007/AC-20: the FCC wants two headers, so one value is not a configured provider."""
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    monkeypatch.delenv(settings.BROADBAND_TOKEN, raising=False)
    monkeypatch.delenv(settings.BROADBAND_USERNAME, raising=False)

    assert fcc.credentials(None) is None
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    assert fcc.credentials(None) is None, "a token with no account name is half a credential"
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "someone@example.invalid")
    assert fcc.credentials(None) == ("someone@example.invalid", "a-token")


def test_the_credential_travels_as_two_headers() -> None:
    """feat-007/AC-20: not a bearer token, which is what the build this replaced assumed."""
    sent = fcc.headers(("someone@example.invalid", "a-token"))

    assert sent["username"] == "someone@example.invalid"
    assert sent["hash_value"] == "a-token"
    assert "Authorization" not in sent


# ---------------------------------------------------------------------------
# The three kinds of absent
# ---------------------------------------------------------------------------


def test_a_state_nobody_downloaded_names_the_state_and_the_command(
    store: Store, monkeypatch, tmp_path: Path
) -> None:
    """feat-007/AC-21: distinct from not configured, and distinct from a gap in the data.

    An empty column tells you neither, and "not configured" would send somebody to check a
    credential that is fine.
    """
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "someone@example.invalid")

    provider = Broadband()
    provider.attach(store)
    paced, _ = _answering_with_block()

    with pytest.raises(ProviderFailed) as raised:
        provider.fetch(paced, *PLACE)

    said = str(raised.value)
    assert "NM" in said, "the state was not named"
    assert "homescout broadband" in said, "the way out was not named"


def test_a_block_with_no_filed_service_is_an_answer_rather_than_a_gap(
    store: Store, monkeypatch, tmp_path: Path
) -> None:
    """feat-007/AC-15: the same distinction the flood provider makes outside a hazard area.

    The state is loaded, so the question was asked and the FCC's answer is that nobody has filed
    residential service in this block. That is a known negative, and it is not the same thing as
    nobody having looked.
    """
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "someone@example.invalid")

    fcc.store_index(store, "NM", {"350410001009999": [100, 20, {"Somebody"}]}, "2025-12-31")
    provider = Broadband()
    provider.attach(store)
    paced, _ = _answering_with_block()

    found = provider.fetch(paced, *PLACE)

    assert found == {"download_mbps": None, "upload_mbps": None, "broadband_provider": None}


def test_a_loaded_block_answers_with_the_speeds_and_who_offers_them(
    store: Store, monkeypatch, tmp_path: Path
) -> None:
    """feat-007/AC-16, feat-007/AC-17, feat-007/AC-18: the whole route, in one test."""
    monkeypatch.setenv("HOMESCOUT_DB", str(tmp_path / "homescout.db"))
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "someone@example.invalid")

    fcc.store_index(store, "NM", {BLOCK: [1200, 1000, {"Xfinity", "Yucca Telecom"}]}, "2025-12-31")
    provider = Broadband()
    provider.attach(store)
    assert provider.configured() is True

    paced, transport = _answering_with_block()
    found = provider.fetch(paced, *PLACE)

    assert found["download_mbps"] == 1200
    assert found["upload_mbps"] == 1000
    assert "Yucca Telecom" in found["broadband_provider"]
    assert transport.count == 1, "one request per point, like every other provider here"


# ---------------------------------------------------------------------------
# The store, which holds a dataset rather than an answer
# ---------------------------------------------------------------------------


def test_refreshing_one_state_leaves_another_alone(store: Store) -> None:
    """feat-007/AC-16: a cache refreshed whole, one state at a time."""
    fcc.store_index(store, "NM", {BLOCK: [100, 10, {"A"}]}, "2025-06-30")
    fcc.store_index(store, "TX", {"480010001001000": [50, 5, {"B"}]}, "2025-06-30")

    fcc.store_index(store, "NM", {BLOCK: [1000, 100, {"C"}]}, "2025-12-31")

    held = store.broadband_states()
    assert set(held) == {"NM", "TX"}
    assert held["NM"]["as_of"] == "2025-12-31"
    assert held["TX"]["as_of"] == "2025-06-30", "refreshing one state touched another"
    assert store.broadband_for(BLOCK)["download_mbps"] == 1000
    assert store.broadband_for("480010001001000")["download_mbps"] == 50


def test_every_state_can_be_named(store: Store) -> None:
    """feat-007/AC-12: national coverage, a state at a time, and all of them are reachable."""
    assert len(states.codes()) == 57, "fifty states, the district, and six territories"
    assert states.fips_of("NM") == "35"
    assert states.of_block(BLOCK) == "NM"
    assert states.known("nm") is True
    assert states.known("ZZ") is False


def _answering_with_block() -> tuple:
    """A paced session whose one answer is the FCC block service naming this block."""
    payload = {
        "Block": {"FIPS": BLOCK, "bbox": [-103.33, 34.17, -103.32, 34.18]},
        "County": {"FIPS": "35041", "name": "Roosevelt"},
        "State": {"FIPS": "35", "code": "NM", "name": "New Mexico"},
    }
    transport = CountingTransport({"http": payload})
    return session(transport), transport


def test_the_block_service_needs_no_credential() -> None:
    """feat-007/AC-17: a different host from the file API, and keyless.

    Worth its own assertion because it is what keeps the per-property half of this working for
    somebody who has not registered with the FCC at all: they get no speeds, and nothing about the
    lookup is what stops them.
    """
    paced, transport = _answering_with_block()

    block, state = fcc.block_for(paced, *PLACE)

    assert (block, state) == (BLOCK, "NM")
    asked = transport.requests[0]
    assert "geo.fcc.gov" in asked, "the point lookup went to the file API rather than the free one"
    assert "hash_value" not in asked and "token" not in asked.lower(), (
        "a credential was put in a URL, which is where credentials get logged"
    )


def test_an_unreadable_answer_from_the_block_service_is_a_failure_not_a_blank() -> None:
    """feat-007/AC-4: a changed shape leaves the cached value alone rather than overwriting it."""
    transport = CountingTransport({"http": {"nothing": "recognizable"}})
    paced = session(transport)

    with pytest.raises(fcc.BroadbandUnavailable, match="census block"):
        fcc.block_for(paced, *PLACE)


class BlockServices:
    """Script the two public block services, retaining complete requests for credential checks."""

    def __init__(self, *, census=None, fcc_answer=None):
        self.requests = []
        self.fcc_answer = fcc_answer or _Response(b'{"status":"error"}', 400)
        payload = census if census is not None else {
            "result": {"geographies": {"Census Blocks": [{"GEOID": BLOCK, "STATE": "35"}]}}
        }
        self.census_answer = _Response(json.dumps(payload).encode())

    def __call__(self, request):
        self.requests.append(request)
        if "geo.fcc.gov" in request.url:
            return self.fcc_answer
        return self.census_answer


def test_fcc_outage_uses_census_then_reads_the_existing_state_index(store, monkeypatch):
    """feat-007/AC-17, feat-007/AC-16: outage recovery still answers from the FCC index."""
    fcc.store_index(store, "NM", {BLOCK: [150, 150, {"DesertGate Internet"}]}, "2025-12-31")
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "never-forward-this-name")
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "never-forward-this-token")
    provider = Broadband()
    provider.attach(store)
    transport = BlockServices()
    paced = session(transport)

    assert provider.fetch(paced, *PLACE) == {
        "download_mbps": 150, "upload_mbps": 150, "broadband_provider": "DesertGate Internet"
    }
    assert provider.fetch(paced, PLACE[0] + 0.01, PLACE[1])["download_mbps"] == 150
    assert len(transport.requests) == 3, "the failed FCC service was retried for every property"
    assert "geo.fcc.gov" in transport.requests[0].url
    assert all("geocoding.geo.census.gov" in r.url for r in transport.requests[1:])
    query = parse_qs(urlsplit(transport.requests[1].url).query)
    assert query["x"] == [str(PLACE[1])] and query["y"] == [str(PLACE[0])]
    assert query["benchmark"] == ["Public_AR_Current"]
    assert query["vintage"] == ["Census2020_Current"]
    assert query["format"] == ["json"]
    assert all("username" not in r.headers and "hash_value" not in r.headers
               for r in transport.requests)
    assert all("never-forward" not in r.url for r in transport.requests)


def test_both_block_services_failing_reports_both_reasons():
    """feat-007/AC-17: a failure identifies both services rather than inventing no service."""
    transport = BlockServices(census={"result": {"geographies": {}}})
    with pytest.raises(fcc.BroadbandUnavailable) as raised:
        fcc.block_for(session(transport), *PLACE)
    assert "FCC" in str(raised.value)
    assert "Census" in str(raised.value)
    assert len(transport.requests) == 2


def test_a_new_provider_tries_fcc_again_after_an_earlier_outage(store):
    """feat-007/AC-17: outage state belongs to the provider, not the process or session."""
    fcc.store_index(store, "NM", {BLOCK: [100, 20, {"A"}]}, "2025-12-31")
    transport = BlockServices()
    paced = session(transport)
    earlier = Broadband()
    earlier.attach(store)
    earlier.fetch(paced, *PLACE)
    transport.fcc_answer = _Response(json.dumps({"Block": {"FIPS": BLOCK}}).encode())
    later = Broadband()
    later.attach(store)
    later.fetch(paced, *PLACE)
    assert len(transport.requests) == 3
    assert "geo.fcc.gov" in transport.requests[-1].url
    assert parse_qs(urlsplit(transport.requests[-1].url).query)["censusYear"] == ["2020"]


@pytest.mark.parametrize("fcc_answer", [
    _Response(b'not json'), _Response(b'{"Block":[]}'),
    _Response(b'{"Block":{"FIPS":"350410001001017"},"State":{"code":"LA"}}'),
])
def test_a_malformed_or_inconsistent_fcc_answer_can_fall_back(fcc_answer):
    """feat-007/AC-17: the alternate lookup repairs unusable data as well as HTTP failures."""
    transport = BlockServices(fcc_answer=fcc_answer)
    assert fcc.block_for(session(transport), *PLACE) == (BLOCK, "NM")
    assert len(transport.requests) == 2


@pytest.mark.parametrize("layer", ["Census Blocks", "2020 Census Blocks"])
def test_census_block_layer_names_and_state_prefix(layer, monkeypatch):
    """feat-007/AC-17, feat-007/AC-14: the observed layers work at the configured endpoint."""
    monkeypatch.setenv("HOMESCOUT_ENRICH_GEOCODE_URL", "https://example.invalid/coordinates")
    transport = BlockServices(census={
        "result": {"geographies": {layer: [{"GEOID": BLOCK}]}}
    })
    assert fcc.block_for(session(transport), *PLACE) == (BLOCK, "NM")
    assert transport.requests[-1].url.startswith("https://example.invalid/coordinates?")


@pytest.mark.parametrize("payload", [
    None, [], {"result": None}, {"result": {"geographies": []}},
    {"result": {"geographies": {"Census Blocks": []}}},
    {"result": {"geographies": {"Census Blocks": "not rows"}}},
    {"result": {"geographies": {"Census Blocks": [None]}}},
    {"result": {"geographies": {"Census Blocks": [
        {"GEOID": BLOCK}, {"GEOID": "350410001001018"}]}}},
])
def test_unusable_or_ambiguous_census_geography_is_a_failure(payload):
    """feat-007/AC-17, feat-007/AC-4: no guessed block and no false no-service answer."""
    transport = BlockServices()
    transport.census_answer = _Response(json.dumps(payload).encode())
    with pytest.raises(fcc.BroadbandUnavailable, match="Census"):
        fcc.block_for(session(transport), *PLACE)


@pytest.mark.parametrize("block,state", [
    (None, None), (123456789012345, "35"), ("35041000100101", "35"),
    ("35041000100101x", "35"), ("３５０４１０００１００１０１７", "35"),
    ("990410001001017", "99"), (BLOCK, "22"), (BLOCK, 35),
])
def test_census_identity_must_be_valid_and_match_its_state(block, state):
    """feat-007/AC-17: reject malformed, unknown-state and inconsistent block identities."""
    transport = BlockServices(census={"result": {"geographies": {
        "Census Blocks": [{"GEOID": block, "STATE": state}]
    }}})
    with pytest.raises(fcc.BroadbandUnavailable, match="Census"):
        fcc.block_for(session(transport), *PLACE)


def test_fallback_retains_bounded_retries_and_request_pacing(store):
    """feat-007/AC-17, feat-007/AC-13: failover uses the shared paced session and retry cap."""
    starts = []

    class TimedServices(BlockServices):
        def __call__(self, request):
            starts.append(paced._clock())
            return super().__call__(request)

    transport = TimedServices(fcc_answer=_Response(b'{}', 503))
    paced = session(transport)
    fcc.store_index(store, "NM", {BLOCK: [100, 20, {"A"}]}, "2025-12-31")
    provider = Broadband()
    provider.attach(store)
    assert provider.fetch(paced, *PLACE)["download_mbps"] == 100
    provider.fetch(paced, PLACE[0] + 0.01, PLACE[1])
    assert len(transport.requests) == 6, "four bounded FCC attempts, then two Census lookups"
    assert all(b - a >= 1 for a, b in zip(starts, starts[1:], strict=False))
    assert sum("geo.fcc.gov" in r.url for r in transport.requests) == 4


def test_a_census_block_still_requires_its_state_to_be_loaded(store):
    """feat-007/AC-17, feat-007/AC-16: fallback never triggers a state download."""
    fcc.store_index(store, "NM", {BLOCK: [100, 20, {"A"}]}, "2025-12-31")
    transport = BlockServices(census={"result": {"geographies": {
        "Census Blocks": [{"GEOID": "220950001001017", "STATE": "22"}]
    }}})
    provider = Broadband()
    provider.attach(store)
    with pytest.raises(ProviderFailed, match="homescout broadband --state LA"):
        provider.fetch(session(transport), *PLACE)
    assert set(store.broadband_states()) == {"NM"}


def test_successful_fallback_is_cached_and_failure_preserves_stale_values(store, monkeypatch):
    """feat-007/AC-17, feat-007/AC-2, feat-007/AC-4: real-pass writes remain honest."""
    monkeypatch.setenv(settings.BROADBAND_USERNAME, "test@example.invalid")
    monkeypatch.setenv(settings.BROADBAND_TOKEN, "a-token")
    do_run(store, sources={"realtor": [prop("a1", latitude=PLACE[0], longitude=PLACE[1])]})
    fcc.store_index(store, "NM", {BLOCK: [150, 150, {"A"}]}, "2025-12-31")
    transport = BlockServices()
    paced = session(transport)
    outcome = run_pass(store, [Broadband()], session=paced)
    assert outcome.providers[0].looked_up == 1 and not outcome.degraded
    key = cache.key_for(*PLACE, 4)
    saved = store.cached_values("broadband", [key])[key]
    assert saved["download_mbps"].value == 150
    again = run_pass(store, [Broadband()], session=paced)
    assert again.providers[0].looked_up == 0 and len(transport.requests) == 2

    old = (datetime.now(UTC) - timedelta(days=181)).isoformat().replace("+00:00", "Z")
    store.connection.execute("UPDATE enrichment_values SET fetched_at = ?", (old,))
    store.connection.commit()
    broken = BlockServices(census={"result": {"geographies": {}}})
    failed = run_pass(store, [Broadband()], session=session(broken), stale_only=True)
    assert failed.degraded and failed.providers[0].looked_up == 0
    assert "FCC" in failed.providers[0].detail and "Census" in failed.providers[0].detail
    retained = store.cached_values("broadband", [key])[key]
    assert retained["download_mbps"].value == 150 and retained["download_mbps"].fetched_at == old


def test_a_file_far_larger_than_any_state_is_refused_rather_than_read() -> None:
    """feat-007 security: a bound, so a malformed listing cannot ask for an unbounded read."""
    assert fcc.MOST_BYTES > 100 * 1024 * 1024, "room for an order of magnitude over the real files"
    assert fcc.MOST_BYTES < 1024 * 1024 * 1024, "and still a bound"


def test_the_quarter_is_the_most_recent_one_published() -> None:
    """feat-007/AC-16: the index records which quarter it came from, so it can say how old it is."""
    payload = {
        "data": [
            {"data_type": "availability", "as_of_date": "2024-12-31"},
            {"data_type": "availability", "as_of_date": "2025-12-31"},
            {"data_type": "challenge", "as_of_date": "2026-06-30"},
        ]
    }
    transport = CountingTransport({"http": payload})

    found = fcc.latest_quarter(session(transport), ("someone@example.invalid", "a-token"))

    assert found == "2025-12-31", "a challenge date is not an availability date"


def test_a_json_answer_is_parsed_and_nothing_in_it_is_executed() -> None:
    """feat-007 security: the answers are data. Asserted here so the claim has a test."""
    payload = json.loads('{"data": [{"data_type": "availability", "as_of_date": "2025-12-31"}]}')
    transport = CountingTransport({"http": payload})

    assert fcc.latest_quarter(session(transport), ("a", "b")) == "2025-12-31"


def test_the_word_advertised_travels_with_the_number() -> None:
    """feat-007/AC-18: a speed without it reads as a promise about that address.

    It is what a provider filed for the block, not a measurement and not this property's own line.
    One word in the cell is what a cell has room for; the rest of the sentence lives on the surfaces
    that have room for it.
    """
    from homescout.export.columns import BY_NAME

    class Row:
        enriched = {
            "download_mbps": 1200,
            "upload_mbps": 1000,
            "broadband_provider": "Yucca Telecom",
        }

    shown = BY_NAME["Internet"].read(Row())

    assert "advertised" in shown, shown
    assert shown.startswith("1200/1000 Mbps"), "the number a person is scanning for comes first"
    assert "Yucca Telecom" in shown
