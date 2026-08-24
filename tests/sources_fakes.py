"""Stand-ins for the network and the clock, so the source tests are exact and instant.

The pacing rules are the hardest thing in this feature to test honestly. A test that really waits
three seconds between requests proves the rule and costs a suite nobody runs. So the clock, the
sleeper and the jitter are injected, and these fakes record exactly what was asked for. One test
with a real clock keeps the fakes honest about the production wiring.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from homescout.records import ListingFields, SourceRow
from homescout.sources import (
    BaseSource,
    Capabilities,
    PacedSession,
    Preview,
    SearchQuery,
    SearchResult,
    SourceFailed,
)
from homescout.sources.ceiling import Page, collect
from homescout.sources.politeness import BodyTooLarge, Request


class FakeClock:
    """A clock that only moves when something sleeps.

    That is the whole trick: pacing is about elapsed time, and if sleeping advances the clock then a
    test can assert real spacing without any real waiting.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class FakeResponse:
    status: int = 200
    body: bytes = b"{}"
    content_type: str | None = "application/json"

    def read(self, limit: int) -> bytes:
        if len(self.body) > limit:
            raise BodyTooLarge
        return self.body

    def header(self, name: str) -> str | None:
        return self.content_type if name.lower() == "content-type" else None


@dataclass
class FakeTransport:
    """Answers requests from a script, recording every one of them."""

    responses: Sequence[Any] = field(default_factory=list)
    default: Any = None
    requests: list[Request] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._queue = list(self.responses)

    def __call__(self, request: Request) -> FakeResponse:
        self.requests.append(request)
        answer = self._queue.pop(0) if self._queue else self.default or FakeResponse()
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return answer(request)
        return answer

    @property
    def bodies(self) -> list[str]:
        return [(r.body or b"").decode("utf-8") for r in self.requests]


def session_with(
    transport: Any,
    *,
    clock: FakeClock | None = None,
    config: Any = None,
    jitter: Callable[[], float] = lambda: 1.0,
    user_agent: str = "homescout/test (personal listing monitor)",
) -> PacedSession:
    clock = clock or FakeClock()
    return PacedSession(
        transport,
        config,
        user_agent=user_agent,
        clock=clock,
        sleeper=clock.sleep,
        jitter=jitter,
    )


def listing(identifier: str, **fields: Any) -> SourceRow:
    """One row, with defaults for everything a given test is not talking about."""
    defaults: dict[str, Any] = {
        "price": 350_000,
        "listing_status": "for_sale",
        "beds": 3,
        "baths": 2,
        "address_line": f"{identifier} Example Road",
        "city": "Portales",
        "state": "NM",
        "postal_code": "88130",
    }
    defaults.update(fields)
    return SourceRow(
        source="stub",
        fields=ListingFields(**defaults),
        payload={"id": identifier, **defaults},
        source_listing_id=identifier,
        fetched_at="2026-08-23T00:00:00.000000Z",
    )


class StubSource(BaseSource):
    """A source with a known population and a small ceiling.

    Small on purpose. A ceiling of 50 over a population of 500 exercises several levels of splitting
    in milliseconds, and the whole population is known, so completeness can be *shown* rather than
    inferred from a large number coming back.
    """

    name = "stub"

    def __init__(
        self,
        session: PacedSession,
        *,
        population: Iterable[str] = (),
        ceiling: int | None = 50,
        page_size: int = 10,
        applies: Iterable[str] = ("price_min",),
        fail_after: int | None = None,
        divisible: bool = True,
    ) -> None:
        super().__init__(session)
        self.population = list(population)
        self.ceiling = ceiling
        self.page_size = page_size
        self._applies = frozenset(applies)
        self.fail_after = fail_after
        self.divisible = divisible
        self.calls = 0

    def capabilities(self) -> Capabilities:
        return Capabilities(
            applies=self._applies,
            accepts_areas=(),
            ceiling=self.ceiling,
            page_size=self.page_size,
        )

    def run_search(self, query: SearchQuery) -> SearchResult:
        harvest = collect(
            query,
            fetch_page=self._page,
            split=self._split,
            ceiling=self.ceiling,
            page_size=self.page_size,
        )
        return SearchResult(
            source=self.name,
            outcome="ok",
            rows=harvest.rows,
            applied=self.capabilities().application(query),
            truncation=harvest.truncation,
            request_count=harvest.request_count,
        )

    # The stub's "date" dimension is a numeric span over the population's indices, which behaves
    # exactly like a date range and is far easier to reason about in a test.
    def _slice(self, query: SearchQuery) -> tuple[int, int]:
        span = query.listed_between
        if span is None:
            return 0, len(self.population)
        return int(span.start or 0), int(span.end or len(self.population))

    def _page(self, query: SearchQuery, offset: int) -> Page:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise SourceFailed("stub stopped answering")
        #: Every request goes through the session, so pacing applies to a split exactly as it
        #: applies to a single query.
        self.session.request(self.name, Request(url=f"https://stub.invalid/{offset}"))
        low, high = self._slice(query)
        matching = self.population[low:high]
        window = matching[offset : offset + self.page_size]
        return Page(rows=tuple(listing(i) for i in window), total=len(matching))

    def _split(self, query: SearchQuery) -> tuple[SearchQuery, SearchQuery] | None:
        if not self.divisible:
            return None
        from homescout.sources import DateRange

        low, high = self._slice(query)
        if high - low < 2:
            return None
        middle = (low + high) // 2
        return (
            query.within(DateRange(start=str(low), end=str(middle))),
            query.within(DateRange(start=str(middle), end=str(high))),
        )

    def fetch_preview(self, row: SourceRow) -> Preview | None:
        return Preview(
            source_url="https://stub.invalid/i.jpg", content_type="image/jpeg", data=b"x"
        )
