"""Manners: the pacing, the backoff, the honest name, and the limits on what we will read.

Being blocked is the one failure that ends this project rather than degrading it, so these are the
tests that protect the tool's ability to exist at all. The clock is injected, so they assert exact
spacing in microseconds of wall time; one test at the end uses the real clock, to keep the fake ones
honest about the production wiring.
"""

from __future__ import annotations

import time

import pytest

from homescout.sources import (
    DEFAULT_DELAY_SECONDS,
    DELAY_RANGE_SECONDS,
    ConfigurationError,
    PacedSession,
    PolitenessConfig,
    Request,
    SourceFailed,
)
from sources_fakes import FakeClock, FakeResponse, FakeTransport, session_with


def test_consecutive_requests_to_one_source_are_spaced(monkeypatch: pytest.MonkeyPatch) -> None:
    """feat-002/AC-6: at least the configured delay separates two requests to one source."""
    clock = FakeClock()
    session = session_with(FakeTransport(), clock=clock)

    session.request("realtor", Request(url="https://example.invalid/1"))
    first = clock.now
    session.request("realtor", Request(url="https://example.invalid/2"))

    assert clock.now - first >= DEFAULT_DELAY_SECONDS
    assert clock.slept == [DEFAULT_DELAY_SECONDS]


def test_time_already_spent_counts_towards_the_delay() -> None:
    """feat-002/AC-6: the delay is a minimum gap, not an unconditional sleep."""
    clock = FakeClock()
    session = session_with(FakeTransport(), clock=clock)

    session.request("realtor", Request(url="https://example.invalid/1"))
    clock.advance(DEFAULT_DELAY_SECONDS + 1)
    session.request("realtor", Request(url="https://example.invalid/2"))

    assert clock.slept == []


def test_pacing_is_per_source_not_global() -> None:
    """feat-002/AC-7: two sources have two clocks and never wait on each other."""
    clock = FakeClock()
    session = session_with(FakeTransport(), clock=clock)

    session.request("realtor", Request(url="https://a.invalid/"))
    session.request("zillow", Request(url="https://b.invalid/"))

    assert clock.slept == []

    session.request("realtor", Request(url="https://a.invalid/2"))
    assert clock.slept == [DEFAULT_DELAY_SECONDS]


def test_the_default_delay_sits_at_the_slow_end_of_the_range() -> None:
    """feat-002/AC-8: the shipped default is deliberately slow within the permitted range."""
    floor, ceiling = DELAY_RANGE_SECONDS

    assert floor * 3 <= DEFAULT_DELAY_SECONDS
    assert ceiling > DEFAULT_DELAY_SECONDS


def test_a_delay_below_the_floor_is_refused_with_the_floor_named() -> None:
    """feat-002/AC-8: configuration that would make the tool rude fails at load, not at run."""
    floor = DELAY_RANGE_SECONDS[0]

    with pytest.raises(ConfigurationError, match=f"floor of {floor}"):
        PolitenessConfig.from_mapping({"delay": 0.1})


def test_a_delay_above_the_ceiling_is_refused_too() -> None:
    """feat-002/AC-8: the range has two ends, so 'the slow end' names something."""
    with pytest.raises(ConfigurationError, match="above the ceiling"):
        PolitenessConfig.from_mapping({"delay": 600})


def test_a_per_source_override_is_validated_against_the_same_floor() -> None:
    """feat-002/AC-8: per-source settings cannot be a way around the floor."""
    with pytest.raises(ConfigurationError, match="politeness.sources.realtor"):
        PolitenessConfig.from_mapping({"sources": {"realtor": {"delay": 0.5}}})


def test_a_misspelled_setting_is_refused_rather_than_ignored() -> None:
    """feat-002/AC-8: a setting that silently does nothing is how a tool ends up rude."""
    with pytest.raises(ConfigurationError, match="unknown politeness settings"):
        PolitenessConfig.from_mapping({"delayy": 5})


def test_per_source_settings_override_the_default() -> None:
    """feat-002/AC-8: sources differ in tolerance, so overriding upward must be possible."""
    config = PolitenessConfig.from_mapping({"delay": 3, "sources": {"redfin": {"delay": 10}}})

    assert config.policy_for("redfin").delay == 10
    assert config.policy_for("realtor").delay == 3


def test_a_refusal_is_waited_out_on_a_growing_interval() -> None:
    """feat-002/AC-9: each successive refusal waits longer than the last."""
    clock = FakeClock()
    transport = FakeTransport(
        responses=[FakeResponse(status=429), FakeResponse(status=429), FakeResponse(status=200)]
    )
    session = session_with(transport, clock=clock)

    session.request("realtor", Request(url="https://example.invalid/"))

    backoffs = [s for s in clock.slept if s not in (DEFAULT_DELAY_SECONDS,)]
    assert backoffs == [5.0, 10.0]


def test_backoff_carries_random_variation() -> None:
    """feat-002/AC-9: two runs meeting the same refusal do not retry in lockstep."""
    waits = []
    for jitter in (0.5, 1.5):
        clock = FakeClock()
        transport = FakeTransport(responses=[FakeResponse(status=403), FakeResponse(status=200)])
        session = session_with(transport, clock=clock, jitter=lambda j=jitter: j)
        session.request("realtor", Request(url="https://example.invalid/"))
        #: The first request to a source waits for nothing, so the first sleep is the backoff.
        #: (Anything after it is the ordinary delay topping up whatever the backoff did not cover.)
        waits.append(clock.slept[0])

    assert waits[0] != waits[1]
    assert waits == [2.5, 7.5]


def test_backoff_is_capped() -> None:
    """feat-002/AC-9: a growing interval still has a ceiling, or a run never ends."""
    clock = FakeClock()
    config = PolitenessConfig.from_mapping({"max_retries": 6, "backoff": 5, "backoff_cap": 20})
    transport = FakeTransport(default=FakeResponse(status=503))
    session = session_with(transport, clock=clock, config=config)

    with pytest.raises(SourceFailed):
        session.request("realtor", Request(url="https://example.invalid/"))

    backoffs = [s for s in clock.slept if s != DEFAULT_DELAY_SECONDS]
    assert backoffs == [5.0, 10.0, 20.0, 20.0, 20.0, 20.0]


def test_retries_are_bounded_and_then_the_source_has_failed() -> None:
    """feat-002/AC-10: after the bound, the source failed and nothing more is asked of it."""
    config = PolitenessConfig.from_mapping({"max_retries": 2})
    transport = FakeTransport(default=FakeResponse(status=429))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed, match="429"):
        session.request("realtor", Request(url="https://example.invalid/"))

    #: One original attempt plus two retries. Not a fourth.
    assert len(transport.requests) == 3


def test_zero_retries_is_a_legitimate_setting() -> None:
    """feat-002/AC-10: the bound is configuration, including all the way down."""
    config = PolitenessConfig.from_mapping({"max_retries": 0})
    transport = FakeTransport(default=FakeResponse(status=429))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed):
        session.request("realtor", Request(url="https://example.invalid/"))

    assert len(transport.requests) == 1


def test_every_request_names_this_tool_and_nothing_else() -> None:
    """feat-002/AC-11: an honest user agent, and no fingerprint of a browser or another product."""
    transport = FakeTransport()
    session = session_with(transport)

    session.request("realtor", Request(url="https://example.invalid/"))

    headers = {k.lower(): v for k, v in transport.requests[0].headers.items()}
    assert "homescout" in headers["user-agent"].lower()
    for forbidden in ("mozilla", "chrome", "safari", "applewebkit", "windows nt", "macintosh"):
        assert forbidden not in headers["user-agent"].lower()
    for absent in ("sec-ch-ua", "sec-ch-ua-platform", "x-is-bot", "cookie", "authorization"):
        assert absent not in headers


def test_a_source_that_errors_becomes_a_failure_with_a_readable_reason() -> None:
    """feat-002/AC-12: transport trouble is one source's outcome, not an exception."""
    config = PolitenessConfig.from_mapping({"max_retries": 0})
    transport = FakeTransport(default=OSError("connection reset"))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed, match="connection reset"):
        session.request("realtor", Request(url="https://example.invalid/"))


def test_a_timeout_is_retried_and_then_reported_as_one() -> None:
    """feat-002/AC-12: a hung socket is a failed source, not a hung run."""
    config = PolitenessConfig.from_mapping({"max_retries": 1})
    transport = FakeTransport(default=TimeoutError("read timed out"))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed, match="timed out after 2 attempts"):
        session.request("realtor", Request(url="https://example.invalid/"))


def test_a_body_past_the_limit_is_abandoned_rather_than_read() -> None:
    """feat-002/AC-12: an unbounded body is a denial of service nobody had to intend."""
    config = PolitenessConfig.from_mapping({"max_body_bytes": 32})
    transport = FakeTransport(default=FakeResponse(body=b"x" * 4096))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed, match="more than the 32 bytes"):
        session.request("realtor", Request(url="https://example.invalid/"))


def test_images_are_held_to_a_much_smaller_limit() -> None:
    """feat-002/AC-23: a preview image is tens of kilobytes; anything else is not a preview."""
    config = PolitenessConfig.from_mapping({"max_body_bytes": 10_000, "max_image_bytes": 64})
    transport = FakeTransport(default=FakeResponse(body=b"x" * 1024, content_type="image/jpeg"))
    session = session_with(transport, config=config)

    with pytest.raises(SourceFailed, match="more than the 64 bytes"):
        session.fetch_image("realtor", "https://example.invalid/photo.jpg")


def test_an_image_fetch_does_not_follow_redirects() -> None:
    """feat-002/AC-23: the address that was checked must be the address that is retrieved."""
    transport = FakeTransport(default=FakeResponse(content_type="image/jpeg", body=b"jpeg"))
    session = session_with(transport)

    session.fetch_image("realtor", "https://example.invalid/photo.jpg")

    assert transport.requests[0].allow_redirects is False


def test_image_fetches_are_paced_like_everything_else() -> None:
    """feat-002/AC-23: images go through the same gate, so a page of them is not a burst."""
    clock = FakeClock()
    transport = FakeTransport(default=FakeResponse(content_type="image/jpeg", body=b"jpeg"))
    session = session_with(transport, clock=clock)

    for _ in range(3):
        session.fetch_image("realtor", "https://example.invalid/photo.jpg")

    assert clock.slept == [DEFAULT_DELAY_SECONDS, DEFAULT_DELAY_SECONDS]


def test_a_client_error_is_not_retried() -> None:
    """feat-002/AC-10: a malformed request will be malformed again; retrying is just noise."""
    transport = FakeTransport(default=FakeResponse(status=400))
    session = session_with(transport)

    with pytest.raises(SourceFailed, match="400"):
        session.request("realtor", Request(url="https://example.invalid/"))

    assert len(transport.requests) == 1


@pytest.mark.slow
def test_the_real_clock_is_wired_the_same_way() -> None:
    """feat-002/AC-6: the injected clock is not a fiction; the shipped wiring really waits.

    Every other pacing test uses a fake clock, which is the only way to keep the suite fast. This
    one exists so that the fake cannot drift away from what the tool actually does.
    """
    config = PolitenessConfig.from_mapping({"delay": DELAY_RANGE_SECONDS[0]})
    session = PacedSession(
        FakeTransport(), config, user_agent="homescout/test (personal listing monitor)"
    )

    started = time.monotonic()
    session.request("realtor", Request(url="https://example.invalid/1"))
    session.request("realtor", Request(url="https://example.invalid/2"))
    elapsed = time.monotonic() - started

    assert elapsed >= DELAY_RANGE_SECONDS[0]
