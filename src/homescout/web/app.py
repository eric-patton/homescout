"""The local interface's HTTP surface: fourteen endpoints, each of them a translation.

Every route does one thing, and it is the same thing: read the request, call one function in
`homescout.api`, serialize the answer. No route reads the store, and no route decides anything.
That is non-negotiable 8, and a test scans this package to prove it rather than taking its word.

**There is no authentication, and that is why there is a guard.** The constitution settles who may
use this: one person, on this machine. It settles nothing about *what* may use it, and the gap is
the classic hole in every tool that serves an unauthenticated API on a loopback port. Any page the
person visits, in any tab, can send a request here; the same-origin policy stops it reading the
answer but not sending the request, and a `POST` that overwrites a saved search has done its damage
either way. A hostile domain resolving to `127.0.0.1` can read the answers too, because to the
browser that is then the same origin.

`_guard` closes both, in three checks that cost nothing and are invisible in ordinary use. See its
own explanation.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import api, digest
from ..errors import HomescoutError, InvalidInput, PreconditionNotMet
from . import runs, wire

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
VENDOR = HERE / "vendor"

#: The header every request that changes something has to carry. A form posted by a hostile page
#: cannot set one without a preflight, and a preflight is refused by the host and origin checks.
GUARD_HEADER = "x-homescout"

#: The only hosts this will answer to. A page on `evil.invalid` whose DNS points here still sends
#: `Host: evil.invalid`, which is what stops rebinding.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")

CHANGES_THINGS = ("POST", "PUT", "PATCH", "DELETE")


def _host_is_loopback(header: str | None) -> bool:
    if not header:
        return False
    host = header.rsplit(":", 1)[0] if header.count(":") == 1 else header
    return host.strip().casefold() in LOOPBACK_HOSTS or header.strip().casefold() in LOOPBACK_HOSTS


def _origin_is_ours(origin: str | None, host: str | None) -> bool:
    """An `Origin`, when the browser sends one, has to be this server.

    Absent is allowed: a plain `GET` typed into the address bar has no origin, and neither does a
    terminal. What is not allowed is one that names somebody else, which is exactly what a
    cross-site request carries.
    """
    if not origin:
        return True
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https"):
        return False
    return bool(host) and parsed.netloc.casefold() == (host or "").casefold()


def refusal(which: str) -> JSONResponse:
    """A refusal that says which check refused it.

    A person who changed the port and cannot work out why nothing saves deserves a sentence rather
    than a bare 403.
    """
    return JSONResponse(
        status_code=403,
        content={"error": which, "kind": "refused"},
    )


def build(workspace: api.Workspace) -> FastAPI:
    """The application, over one workspace."""
    app = FastAPI(title="HomeScout", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.workspace = workspace
    app.state.runs = runs.Tracker()
    # One request at a time. A web server hands work to a pool of threads and the database
    # underneath is a single connection, so this is what makes the store's `shared` flag safe. For
    # one person on one machine it is not a constraint anybody will notice, and the alternative is a
    # connection per thread, which would put five copies of a write-ahead log in play to serve a
    # single user.
    app.state.lock = threading.RLock()

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        host = request.headers.get("host")
        if not _host_is_loopback(host):
            return refusal(
                "This server answers on this machine only, and the request named a different host. "
                "Open it as http://127.0.0.1 rather than by any other name."
            )
        if not _origin_is_ours(request.headers.get("origin"), host):
            return refusal(
                "That request came from another site. This interface is not reachable from one, "
                "which is what stops a page you happen to have open from using it."
            )
        if request.method in CHANGES_THINGS and not request.headers.get(GUARD_HEADER):
            return refusal(
                f"A request that changes something has to carry the {GUARD_HEADER} header. "
                "The interface's own pages set it; a form posted by another site cannot."
            )
        with app.state.lock:
            response = await call_next(request)
        # Nothing here is meant to be embedded anywhere, cached by anything, or sniffed.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(HomescoutError)
    async def _known(request: Request, exc: HomescoutError) -> JSONResponse:
        """The product's two kinds of failure, as the two status codes that mean them."""
        status = 400 if isinstance(exc, InvalidInput) else 409
        if isinstance(exc, PreconditionNotMet):
            status = 409
        return JSONResponse(status_code=status, content={"error": str(exc), "kind": "problem"})

    def held() -> api.Workspace:
        return app.state.workspace

    def answer(kind: str, **payload: Any) -> dict[str, Any]:
        return digest.envelope(kind, **payload)

    # -- saved searches ----------------------------------------------------

    @app.get("/api/searches")
    def list_searches() -> dict[str, Any]:
        return answer("searches", searches=wire.searches(held()))

    @app.get("/api/searches/{name}")
    def one_search(name: str) -> dict[str, Any]:
        return answer("search", search=wire.search(held(), name))

    @app.put("/api/searches/{name}")
    async def create_search(name: str) -> dict[str, Any]:
        api.create_search(held(), name)
        return answer("search", search=wire.search(held(), name))

    @app.post("/api/searches/{name}")
    async def edit_search(name: str, request: Request) -> dict[str, Any]:
        body = await _body(request)
        changes = body.get("set")
        if not isinstance(changes, Mapping) or not changes:
            raise InvalidInput("Nothing to change: send {\"set\": {...}}.")
        api.edit_search(held(), name, dict(changes))
        return answer("search", search=wire.search(held(), name))

    # -- runs --------------------------------------------------------------

    @app.post("/api/searches/{name}/run")
    async def start_run(name: str) -> dict[str, Any]:
        started = app.state.runs.start(held(), name, app.state.lock)
        return answer("run-started", **started)

    @app.get("/api/runs/{name}/status")
    def status(name: str) -> dict[str, Any]:
        return answer("run-status", **app.state.runs.status(held(), name))

    # -- results -----------------------------------------------------------

    @app.get("/api/results/{name}")
    def results(name: str, include_dropped: bool = False) -> dict[str, Any]:
        return answer("results", **api.results(held(), name, include_dropped=include_dropped))

    @app.get("/api/changes/{name}")
    def changes(name: str, since: str | None = None) -> dict[str, Any]:
        return answer("comparison", **wire.comparison(held(), name, since))

    # -- one property ------------------------------------------------------

    @app.get("/api/listings/{listing_id}")
    def one_listing(listing_id: str) -> dict[str, Any]:
        return answer("listing", listing=api.listing(held(), listing_id))

    @app.get("/api/listings/{listing_id}/image")
    def listing_image(listing_id: str) -> Response:
        found = api.preview_image(held(), listing_id)
        if found is None:
            return Response(status_code=404)
        body, content_type = found
        # The stored type, and never sniffed: a mislabelled image must not be read as a page.
        return Response(
            content=body,
            media_type=content_type,
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    @app.post("/api/listings/{listing_id}/annotation")
    async def annotate(listing_id: str, request: Request) -> dict[str, Any]:
        body = await _body(request)
        values = {
            name: body[name]
            for name in ("rank", "verdict", "red_flags", "summary", "next_step", "notes")
            if name in body
        }
        if not values:
            raise InvalidInput("Nothing to record.")
        written = api.annotate(held(), listing_id, **values)
        return answer(
            "annotation",
            listing_id=written.listing_id,
            updated_at=written.updated_at,
            **written.content(),
        )

    # -- matches -----------------------------------------------------------

    @app.get("/api/matches")
    def matches() -> dict[str, Any]:
        return answer("matches", matches=wire.matches(held()))

    @app.post("/api/matches/{match_id}")
    async def resolve(match_id: str, request: Request) -> dict[str, Any]:
        body = await _body(request)
        verdict = body.get("verdict")
        if verdict not in ("same", "different"):
            raise InvalidInput("A decision is 'same' or 'different'.")
        merged = api.resolve_match(held(), match_id, same=verdict == "same")
        return answer(
            "resolution", match_id=match_id, verdict=verdict, merged_listing_id=merged
        )

    # -- area notes --------------------------------------------------------

    @app.get("/api/areas")
    def areas() -> dict[str, Any]:
        return answer("areas", areas=wire.areas(held()))

    @app.post("/api/areas")
    async def write_area(request: Request) -> dict[str, Any]:
        body = await _body(request)
        api.set_area_note(
            held(),
            str(body.get("area_type") or ""),
            str(body.get("area_value") or ""),
            body.get("notes"),
        )
        return answer("areas", areas=wire.areas(held()))

    # -- the pages themselves ----------------------------------------------

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return answer("settings", **wire.settings(held()))

    for path, page in wire.PAGES.items():
        _serve_page(app, path, page)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    if VENDOR.is_dir():
        app.mount("/vendor", StaticFiles(directory=VENDOR), name="vendor")
    return app


def _serve_page(app: FastAPI, path: str, page: str) -> None:
    """One surface, served as the file it is.

    AC-16 says the served assets are the files as committed, and this is what makes that true: the
    file is sent, unmodified, with no build step to have failed to run.
    """

    async def handler() -> FileResponse:
        return FileResponse(STATIC / page, media_type="text/html; charset=utf-8")

    app.add_api_route(path, handler, methods=["GET"], include_in_schema=False)


async def _body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        found = json.loads(raw)
    except ValueError:
        raise InvalidInput("That request body is not JSON.") from None
    if not isinstance(found, dict):
        raise InvalidInput("That request body is not an object.")
    return found
