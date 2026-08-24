"""Public services that are not public services, so the pass can be tested without asking anyone.

What is faked is the transport, which is the only part of this feature that reaches outside the
machine. The providers, the cache, the pass, the store and the pacing are all real, because the
things that go wrong here are about counting requests and telling three states apart, and both of
those are exactly what a fake transport can show and a real one cannot.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from homescout.enrich.provider import ProviderFailed
from homescout.sources.politeness import PacedSession
from homescout.sources.transport import Request


@dataclass
class Recorded:
    """One canned response, and how many times it was asked for."""

    body: Any
    status: int = 200


class CountingTransport:
    """A transport that answers from a script and counts what it was asked.

    The count is the point of half these tests: a cache that works makes no request, and the only
    way to prove that is to have something that would have noticed.
    """

    def __init__(self, answers: Mapping[str, Any] | None = None) -> None:
        self.answers = dict(answers or {})
        self.requests: list[str] = []
        self.fail_with: str | None = None

    def __call__(self, request: Request) -> Any:
        self.requests.append(request.url)
        if self.fail_with is not None:
            raise ConnectionError(self.fail_with)
        for fragment, answer in self.answers.items():
            if fragment in request.url:
                return _Response(json.dumps(answer).encode(), 200)
        return _Response(json.dumps({"error": {"message": "nothing scripted"}}).encode(), 200)

    @property
    def count(self) -> int:
        return len(self.requests)


@dataclass
class _Response:
    payload: bytes
    status: int = 200

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]

    def header(self, name: str) -> str | None:
        return "application/json" if name.lower() == "content-type" else None


def session(transport: CountingTransport, delay: float = 1.0) -> PacedSession:
    """A real paced session over a fake transport, with the waiting taken out.

    The clock and the sleeper are supplied rather than real, because a test that actually waited a
    second per request would take a minute to say what it can say instantly. The pacing logic is the
    real one: what is faked is time.
    """
    from homescout.sources.politeness import PolitenessConfig, SourcePolicy

    ticks = {"now": 0.0}

    def clock() -> float:
        return ticks["now"]

    def sleeper(seconds: float) -> None:
        ticks["now"] += seconds

    return PacedSession(
        transport,
        PolitenessConfig(default=SourcePolicy(delay=delay)),
        user_agent="homescout-test/0.1",
        clock=clock,
        sleeper=sleeper,
        jitter=lambda: 1.0,
    )


@dataclass
class FakeProvider:
    """A provider that answers from a script, or refuses, without leaving the machine."""

    name: str = "fake"
    supplies: tuple[str, ...] = ("flood_zone",)
    answer: Mapping[str, Any] = field(default_factory=lambda: {"flood_zone": "X"})
    decimals: int = 3
    ttl: int | None = 30
    ready: bool = True
    fails: str | None = None
    asked: list[tuple[float, float]] = field(default_factory=list)

    def values(self) -> tuple[str, ...]:
        return self.supplies

    def precision(self) -> int:
        return self.decimals

    def ttl_days(self) -> int | None:
        return self.ttl

    def configured(self) -> bool:
        return self.ready

    def why_not(self) -> str:
        return "this fake was told it is not configured"

    def fetch(self, session: Any, latitude: float, longitude: float) -> Mapping[str, Any]:
        self.asked.append((latitude, longitude))
        if self.fails:
            raise ProviderFailed(self.fails)
        return dict(self.answer)


#: What each real provider's service answers, keyed by a fragment of its address, so a test can wire
#: the real providers to a fake network.
CANNED: dict[str, Any] = {
    "NFHL": {"features": [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": None}}]},
    "epqs": {"value": 4009.39},
    "USGS_Aquifers": {"features": [{"attributes": {"AQ_NAME": "High Plains aquifer"}}]},
    "WildfireHazardPotentialClassified": {"value": "3"},
    "tigerWMS": {"features": [{"geometry": {"type": "Polygon", "coordinates": [[[0, 0]]]}}]},
    "geocoder": {"result": {"geographies": {}}},
}


@contextmanager
def provided(*providers: Any) -> Iterator[tuple[Any, ...]]:
    """Swap the shipped providers for fakes, for a test that drives the command line.

    Necessary rather than tidy. The `enrich` command builds providers from the registry and asks
    them, so a test that ran it against the real registry would make real requests to five
    government services, paced, in the middle of an offline suite.
    """
    from homescout.enrich import registry

    made = providers or (
        FakeProvider(name="flood"),
        FakeProvider(name="elevation", supplies=("elevation_ft",),
                     answer={"elevation_ft": 4009.4}),
        FakeProvider(name="aquifer", supplies=("over_principal_aquifer",),
                     answer={"over_principal_aquifer": True}),
        FakeProvider(name="wildfire", supplies=("wildfire_hazard",),
                     answer={"wildfire_hazard": "very low"}),
        FakeProvider(name="broadband", supplies=("upload_mbps",), ready=False),
    )
    was = registry.registered()
    for provider in made:
        registry.register(provider.name, lambda provider=provider: provider, replace=True)
    for name in was:
        if name not in {provider.name for provider in made}:
            registry.unregister(name)
    try:
        yield made
    finally:
        registry.restore_shipped()
