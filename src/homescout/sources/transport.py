"""The one place that actually touches the network.

Kept apart from the pacing so that neither has to know about the other: `PacedSession` decides
*when* a request may go, this decides *how* it goes. Substituting this is how tests run offline, and
how a proxy would be introduced later without editing a line of policy.

Bodies are read in chunks against a limit rather than in one call, because the size the other side
announces is the size the other side chose to announce.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from .politeness import BodyTooLarge, Request

CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    _body: bytes
    _headers: dict[str, str]

    def read(self, limit: int) -> bytes:
        if len(self._body) > limit:
            raise BodyTooLarge
        return self._body

    def header(self, name: str) -> str | None:
        return self._headers.get(name.lower())


class RequestsTransport:
    """`requests`, with connection pooling and no opinions of its own.

    Pooling matters here for the same reason everything else in this package does: fewer handshakes
    is less noise directed at a site we are trying not to bother.
    """

    def __init__(self) -> None:
        self._session = requests.Session()

    def __call__(self, request: Request) -> _Response:
        limit = request.max_bytes or 0
        try:
            response = self._session.request(
                request.method,
                request.url,
                headers=dict(request.headers),
                data=request.body,
                timeout=request.timeout,
                allow_redirects=request.allow_redirects,
                stream=True,
            )
        except requests.Timeout as exc:
            #: Translated so that the pacing layer, which knows nothing about `requests`, can still
            #: tell a timeout from a refusal.
            raise TimeoutError(str(exc)) from exc

        with response:
            chunks: list[bytes] = []
            read = 0
            for chunk in response.iter_content(CHUNK_BYTES):
                read += len(chunk)
                if limit and read > limit:
                    raise BodyTooLarge
                chunks.append(chunk)
            body = b"".join(chunks)

        return _Response(
            status=response.status_code,
            _body=body,
            _headers={k.lower(): v for k, v in response.headers.items()},
        )

    def close(self) -> None:
        self._session.close()
