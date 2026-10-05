"""Shared admission and cooldown, with independent HTTP sessions for concurrent callers."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from homescout.sources import PolitenessConfig, Request
from homescout.sources.politeness import _retry_after_seconds
from homescout.sources.transport import RequestsTransport
from sources_fakes import FakeClock, FakeResponse, FakeTransport, session_with


def test_simultaneous_waiters_recheck_shared_admission():
    """feat-002/AC-6, AC-16; feat-013/AC-23: two awakened workers cannot share a slot."""
    clock = FakeClock()
    wave = threading.Barrier(2)
    first_admitted = threading.Event()
    guard = threading.Lock()
    sleeps = 0
    starts = []

    def sleep(seconds):
        nonlocal sleeps
        with guard:
            sleeps += 1
            number = sleeps
        if number <= 2:
            wave.wait(timeout=4)
            clock.now = 3
            wave.wait(timeout=4)
        else:
            assert first_admitted.wait(4)
            clock.advance(seconds)

    def transport(request):
        if not request.url.endswith("seed"):
            starts.append(clock.now)
            first_admitted.set()
        return FakeResponse()

    session = session_with(transport, clock=clock)
    session._sleeper = sleep
    session.request("assess", Request(url="https://example.invalid/seed"))
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(session.request, "assess", Request(url="https://example.invalid/"))
                   for _ in range(2)]
        for future in futures:
            future.result(timeout=4)
    assert sorted(starts) == [3, 6]


def test_network_calls_overlap_while_request_starts_remain_paced():
    """feat-002/AC-6, AC-7; feat-013/AC-23: the gate releases during network I/O."""
    clock = FakeClock()
    entered = [threading.Event() for _ in range(3)]
    release = threading.Event()
    starts = []

    def transport(_request):
        index = len(starts)
        starts.append(clock.now)
        entered[index].set()
        assert release.wait(4)
        return FakeResponse()

    session = session_with(transport, clock=clock)
    with ThreadPoolExecutor(max_workers=3) as workers:
        futures = []
        try:
            for i in range(3):
                futures.append(workers.submit(session.request, "assess",
                                               Request(url="https://example.invalid/")))
                assert entered[i].wait(4)
            assert not any(future.done() for future in futures)
        finally:
            release.set()
        for future in futures:
            future.result(timeout=4)
    assert starts == [0, 3, 6]


def test_retry_after_cooldown_applies_to_other_workers_but_not_other_sources():
    """feat-002/AC-7, AC-9, AC-10; feat-013/AC-23: a refusal pauses all model workers."""
    clock = FakeClock()
    paused = threading.Event()
    release = threading.Event()
    worker_id = []

    class Throttled(FakeResponse):
        def header(self, name):
            return "10" if name == "retry-after" else super().header(name)

    transport = FakeTransport(responses=[Throttled(status=429)], default=FakeResponse())
    session = session_with(transport, clock=clock)

    def sleep(seconds):
        if threading.get_ident() == worker_id[0] and not release.is_set():
            paused.set()
            assert release.wait(4)
        clock.advance(seconds)

    session._sleeper = sleep

    def first():
        worker_id.append(threading.get_ident())
        return session.request("assess", Request(url="https://example.invalid/first"))

    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(first)
        try:
            assert paused.wait(4)
            session.request("other-source", Request(url="https://example.invalid/other"))
            assert clock.now == 0
            session.request("assess", Request(url="https://example.invalid/peer"))
            assert clock.now == 10
        finally:
            release.set()
        future.result(timeout=4)
    assert len(transport.requests) == 4


def test_exhausted_throttle_still_defers_peer_requests():
    """feat-013/AC-23; feat-002/AC-10: a zero-retry job cannot bypass server cooldown."""
    from homescout.sources import SourceFailed

    class Throttled(FakeResponse):
        def header(self, name):
            return "11" if name == "retry-after" else super().header(name)

    clock = FakeClock()
    transport = FakeTransport(responses=[Throttled(status=429)], default=FakeResponse())
    session = session_with(transport, clock=clock,
                           config=PolitenessConfig.from_mapping({"max_retries": 0}))
    with pytest.raises(SourceFailed):
        session.request("assess", Request(url="https://example.invalid/first"))
    assert clock.now == 0
    session.request("assess", Request(url="https://example.invalid/next"))
    assert clock.now == 11


@pytest.mark.parametrize("value,expected", [(None, 0), ("", 0), ("garbage", 0),
    ("nan", 0), ("inf", 0), ("-1", 0), ("0.25", 0.25), ("123", 123)])
def test_retry_after_numeric_and_invalid_values(value, expected):
    """feat-013/AC-23: invalid hints cannot poison admission or produce infinite sleep."""
    assert _retry_after_seconds(value) == expected


def test_retry_after_http_date(monkeypatch):
    """feat-013/AC-23: the date form of Retry-After also sets a minimum wait."""
    now = datetime(2026, 10, 4, 12, tzinfo=UTC)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, _tz):
            return now

    monkeypatch.setattr("homescout.sources.politeness.datetime", FrozenDatetime)
    when = now + timedelta(minutes=2)
    assert _retry_after_seconds(format_datetime(when, usegmt=True)) == 120


def test_http_connection_pool_is_owned_by_each_thread_and_closed(monkeypatch):
    """feat-013/AC-23; feat-002/AC-7: concurrent calls do not share mutable HTTP state."""
    sessions = []
    barrier = threading.Barrier(2)

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def iter_content(self, _size):
            yield b"{}"

    class Session:
        def __init__(self):
            self.owner = threading.get_ident()
            self.calls = 0
            self.closed = False
            sessions.append(self)

        def request(self, *_args, **_kwargs):
            assert threading.get_ident() == self.owner
            self.calls += 1
            barrier.wait(timeout=4)
            return Response()

        def close(self):
            self.closed = True

    monkeypatch.setattr("homescout.sources.transport.requests.Session", Session)
    transport = RequestsTransport()

    def work():
        for _ in range(2):
            response = transport(Request(url="https://example.invalid/", max_bytes=100))
            assert response.read(100) == b"{}"

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(work) for _ in range(2)]
        for future in futures:
            future.result(timeout=4)
    assert len(sessions) == 2
    assert len({session.owner for session in sessions}) == 2
    assert [session.calls for session in sessions] == [2, 2]
    transport.close()
    assert all(session.closed for session in sessions)
