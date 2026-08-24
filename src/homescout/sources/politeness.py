"""The gate every outbound request passes through.

Being blocked is the failure that ends this project rather than degrading it, so politeness is not
a habit here, it is the only road to the network. An adapter is handed one of these and nothing
else, which means it *cannot* make an unpaced request, cannot retry without jitter, and cannot
announce itself as something it is not. Splitting a query into forty pieces therefore cannot become
a burst, because there is no code path that would let it.

Four things are injected: the clock, the sleeper, the jitter source, and the transport. That is what
lets the pacing be tested exactly and instantly, instead of by a test suite that actually waits.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from .errors import ConfigurationError, SourceFailed

#: The delay between two requests to one source may be configured anywhere in here and nowhere
#: else. The lower bound is the whole point of the module: a floor a caller could lower is not a
#: floor. The upper bound exists so that "the slow end of the permitted range" names something.
DELAY_RANGE_SECONDS = (1.0, 60.0)

#: Deliberately three times the floor. Slow enough that a scheduled county run takes minutes, which
#: is the intended shape of this tool, and slow enough to be unremarkable in anyone's traffic.
DEFAULT_DELAY_SECONDS = 3.0

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 5.0
DEFAULT_BACKOFF_CAP_SECONDS = 120.0
DEFAULT_TIMEOUT_SECONDS = 30.0

#: Read in chunks and abandoned past the limit, rather than trusting a Content-Length the other side
#: supplies. A preview image is tens of kilobytes; a search page is well under a megabyte.
DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_IMAGE_BYTES = 4 * 1024 * 1024

#: Statuses that mean "not now" rather than "no". These are the ones worth waiting out.
RETRYABLE_STATUSES = frozenset({403, 408, 429, 500, 502, 503, 504})


class Response(Protocol):
    """The little that this module needs from whatever performed the request."""

    status: int

    def read(self, limit: int) -> bytes:
        """Body bytes, reading at most `limit` and raising `BodyTooLarge` past it."""

    def header(self, name: str) -> str | None: ...


class BodyTooLarge(Exception):
    """The other side sent more than we agreed to read."""


#: A transport takes a fully-formed request and performs it. Substituting one is how tests run
#: without a network, and how a proxy would be introduced later without touching anything here.
Transport = Callable[["Request"], Response]


@dataclass(frozen=True, slots=True)
class Request:
    url: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    allow_redirects: bool = True
    #: Left unset, both come from the source's policy. A caller only names them to go smaller,
    #: which is what an image fetch does.
    timeout: float | None = None
    max_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    """How to behave towards one source."""

    delay: float = DEFAULT_DELAY_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff: float = DEFAULT_BACKOFF_SECONDS
    backoff_cap: float = DEFAULT_BACKOFF_CAP_SECONDS
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES

    def validated(self, where: str) -> SourcePolicy:
        low, high = DELAY_RANGE_SECONDS
        if self.delay < low:
            raise ConfigurationError(
                f"{where}: a delay of {self.delay}s is below the floor of {low}s. "
                "The floor is not configurable: being blocked ends this tool, "
                "and slowness is the price of not being."
            )
        if self.delay > high:
            raise ConfigurationError(
                f"{where}: a delay of {self.delay}s is above the ceiling of {high}s. "
                "A run that slow will not finish; raise the ceiling deliberately if you mean it."
            )
        if self.max_retries < 0:
            raise ConfigurationError(f"{where}: retries cannot be negative, got {self.max_retries}")
        if self.backoff <= 0 or self.backoff_cap < self.backoff:
            raise ConfigurationError(
                f"{where}: backoff must be positive and no greater than its cap, "
                f"got {self.backoff}s with a cap of {self.backoff_cap}s"
            )
        if self.timeout <= 0:
            raise ConfigurationError(f"{where}: a timeout must be positive, got {self.timeout}s")
        if self.max_body_bytes <= 0 or self.max_image_bytes <= 0:
            raise ConfigurationError(f"{where}: body limits must be positive")
        return self


@dataclass(frozen=True, slots=True)
class PolitenessConfig:
    """One default policy, and per-source overrides of it.

    Per source because sites differ in tolerance and there is no single right number. Over a shared
    default because the common case should not require anyone to think about it.
    """

    default: SourcePolicy = field(default_factory=SourcePolicy)
    per_source: Mapping[str, SourcePolicy] = field(default_factory=dict)

    def policy_for(self, source: str) -> SourcePolicy:
        return self.per_source.get(source, self.default)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> PolitenessConfig:
        """Read configuration, refusing anything impolite before a request is ever made.

        Everything is validated here rather than at the point of use, so a bad number is a message
        at startup rather than a surprise forty minutes into a scheduled run.
        """
        raw = raw or {}
        unknown = set(raw) - {"delay", "max_retries", "backoff", "backoff_cap", "timeout",
                              "max_body_bytes", "max_image_bytes", "sources"}
        if unknown:
            raise ConfigurationError(
                f"unknown politeness settings: {sorted(unknown)}. "
                "A misspelled setting silently doing nothing is how a tool ends up rude."
            )
        base = _policy_from(raw, SourcePolicy()).validated("politeness")
        per_source = {
            name: _policy_from(over or {}, base).validated(f"politeness.sources.{name}")
            for name, over in (raw.get("sources") or {}).items()
        }
        return cls(default=base, per_source=per_source)


def _policy_from(raw: Mapping[str, Any], base: SourcePolicy) -> SourcePolicy:
    changes = {
        name: float(raw[name]) if name != "max_retries" else int(raw[name])
        for name in ("delay", "max_retries", "backoff", "backoff_cap", "timeout")
        if name in raw
    }
    for name in ("max_body_bytes", "max_image_bytes"):
        if name in raw:
            changes[name] = int(raw[name])
    return replace(base, **changes)


@dataclass(frozen=True, slots=True)
class Fetched:
    """A response that came back within its limits."""

    status: int
    body: bytes
    content_type: str | None


class PacedSession:
    """One source's worth of manners, applied to every request that goes through it.

    Pacing is keyed by source name, so two sources have two independent clocks and never wait on
    each other: a slow site cannot make a fast one slower.
    """

    def __init__(
        self,
        transport: Transport,
        config: PolitenessConfig | None = None,
        *,
        user_agent: str,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        self._transport = transport
        self._config = config or PolitenessConfig()
        #: Deliberately not configurable. Every other setting here can be tuned because the right
        #: value depends on the source; this one is the tool's identity, and a knob for it is a knob
        #: for claiming to be something else, which is the one thing the honesty rule forbids.
        self._user_agent = user_agent
        self._clock = clock
        self._sleeper = sleeper
        #: Half again either way, so two schedules that collide do not stay in step.
        self._jitter = jitter or (lambda: random.uniform(0.5, 1.5))
        self._last_request_at: dict[str, float] = {}

    @property
    def user_agent(self) -> str:
        return self._user_agent

    def policy_for(self, source: str) -> SourcePolicy:
        return self._config.policy_for(source)

    def request(
        self,
        source: str,
        request: Request,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Fetched:
        """Perform one request on behalf of one source, politely.

        Waits out the configured delay, then retries a refusal or a throttle on a growing,
        jittered backoff until the bound is reached. Anything the source could not answer becomes a
        `SourceFailed` naming why, so the caller reports one source's outcome rather than dying.
        """
        policy = self.policy_for(source)
        prepared = replace(
            request,
            headers={**self._base_headers(), **dict(request.headers), **dict(headers or {})},
            timeout=request.timeout if request.timeout is not None else policy.timeout,
            max_bytes=request.max_bytes if request.max_bytes is not None else policy.max_body_bytes,
        )
        limit = prepared.max_bytes or policy.max_body_bytes

        attempt = 0
        while True:
            self._wait_turn(source, policy)
            try:
                response = self._transport(prepared)
                body = response.read(limit)
            except BodyTooLarge:
                raise SourceFailed(
                    f"{source} sent more than the {limit} bytes we agreed to read"
                ) from None
            except TimeoutError as exc:
                if attempt >= policy.max_retries:
                    raise SourceFailed(f"{source} timed out after {attempt + 1} attempts") from exc
                attempt += 1
                self._back_off(attempt, policy)
                continue
            except Exception as exc:  # noqa: BLE001 - one source's trouble, deliberately contained
                if attempt >= policy.max_retries:
                    raise SourceFailed(f"{source} could not be reached: {exc}") from exc
                attempt += 1
                self._back_off(attempt, policy)
                continue

            if response.status in RETRYABLE_STATUSES:
                if attempt >= policy.max_retries:
                    raise SourceFailed(
                        f"{source} answered {response.status} on all "
                        f"{attempt + 1} attempts; giving up rather than pressing"
                    )
                attempt += 1
                self._back_off(attempt, policy)
                continue

            if response.status >= 400:
                raise SourceFailed(f"{source} answered {response.status}")

            return Fetched(
                status=response.status,
                body=body,
                content_type=response.header("content-type"),
            )

    def fetch_image(self, source: str, url: str) -> Fetched:
        """Retrieve one image, under a much smaller limit and following no redirects.

        Redirects are refused because the address that was checked must be the address that is
        retrieved. A preview image that only exists behind a redirect is not worth the hole.
        """
        policy = self.policy_for(source)
        return self.request(
            source,
            Request(
                url=url,
                method="GET",
                allow_redirects=False,
                max_bytes=policy.max_image_bytes,
                headers={"Accept": "image/*"},
            ),
        )

    def _base_headers(self) -> dict[str, str]:
        return {"User-Agent": self._user_agent}

    def _wait_turn(self, source: str, policy: SourcePolicy) -> None:
        last = self._last_request_at.get(source)
        now = self._clock()
        if last is not None:
            owed = policy.delay - (now - last)
            if owed > 0:
                self._sleeper(owed)
                now = self._clock()
        self._last_request_at[source] = now

    def _back_off(self, attempt: int, policy: SourcePolicy) -> None:
        wait = min(policy.backoff * (2 ** (attempt - 1)), policy.backoff_cap)
        self._sleeper(wait * self._jitter())
