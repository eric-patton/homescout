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
from urllib.parse import quote

import anyio
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from .. import api, digest
from ..errors import HomescoutError, InvalidInput, PreconditionNotMet
from . import runs, settings, wire

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
VENDOR = HERE / "vendor"

#: The header every request that changes something has to carry. A form posted by a hostile page
#: cannot set one without a preflight, and a preflight is refused by the host and origin checks.
GUARD_HEADER = "x-homescout"

#: The hosts this answers to with no configuration at all. A page on `evil.invalid` whose DNS points
#: here still sends `Host: evil.invalid`, which is what stops rebinding.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")

CHANGES_THINGS = ("POST", "PUT", "PATCH", "DELETE")

#: How hard to compress, and how small a response has to be before it is not worth it.
#:
#: This interface is served over loopback and it is also served over Tailscale, which is how the
#: second person in the household reads it, and the two are not the same journey at all. A statewide
#: result is two and a half megabytes of JSON. On this machine that is free. Over a tailnet that
#: has not managed a direct connection it goes out to a relay and back, and a relay is a shared
#: fallback rather than a fast path, so the same page that opens instantly here takes as long as
#: the link is slow, which is why it is slow only sometimes.
#:
#: Level five rather than the library's nine. Measured on a real statewide result: 2663 KB down to
#: 553 KB at five in 36 ms, and to 540 KB at nine in 54 ms. Thirteen kilobytes is not worth
#: eighteen milliseconds on every request when the whole point is the time to the first painted
#: row. Below the minimum, compression costs more than the bytes it saves.
#:
#: Pictures are left alone. A stored preview is already a JPEG, and the library's own exclusion list
#: covers those, so this never spends time re-compressing something incompressible.
COMPRESS_LEVEL = 5
COMPRESS_ABOVE_BYTES = 1024


#: What never reaches the database, and so must not queue behind anything that does.
#:
#: Two of these are somebody else's network with a disk cache in front: a wind rose is a ten-second
#: query on a public archive and a hazard tile is a picture of a rectangle of the country. Holding
#: the one-request-at-a-time lock through ten seconds of that would stop the whole interface
#: answering, and would turn the wind overlay from "three at a time" into "one at a time" for no
#: reason at all.
#:
#: The other two are files on this disk. A page opening asks for a stylesheet, four scripts and a
#: map library before it asks the database anything, and making each of those take a turn at the
#: store's lock is queueing behind a queue for no reason: they cannot see the store and could not
#: disturb it if they tried.
#:
#: A list rather than a flag on each route, so that adding a route is not also a chance to opt out
#: of the store's only protection by accident. Anything not named here waits its turn.
WITHOUT_THE_DATABASE: tuple[str, ...] = (
    "/api/wind/rose/",
    "/api/hazard/",
    "/static/",
    "/vendor/",
)


def _needs_the_database(path: str) -> bool:
    return not path.startswith(WITHOUT_THE_DATABASE)


def _host_is_allowed(header: str | None, also: tuple[str, ...] = ()) -> bool:
    """Is this a name this server answers to?

    Loopback always, plus whatever `HOMESCOUT_ALLOWED_HOSTS` names, which is how a reverse proxy on
    this machine reaches it: the request arrives on loopback either way, and only the `Host` the
    browser sent differs. A list rather than the removal of the check, so a name nobody put there is
    still refused and rebinding is still refused with it.
    """
    if not header:
        return False
    said = header.strip().casefold()
    bare = said.rsplit(":", 1)[0] if said.count(":") == 1 else said
    if bare in LOOPBACK_HOSTS or said in LOOPBACK_HOSTS:
        return True
    return said in also or bare in also


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
    #
    # A plain lock rather than a reentrant one, and taken in a worker thread rather than here. See
    # the note in `guard`: the reentrant version read as though it serialised requests and did not.
    app.state.lock = threading.Lock()
    app.state.allowed_hosts = settings.allowed_hosts(workspace.root)

    # Added last, so it wraps everything including the lock: the compressing happens after a
    # request has let go of the database, and never while another one is waiting for its turn.
    app.add_middleware(
        GZipMiddleware, minimum_size=COMPRESS_ABOVE_BYTES, compresslevel=COMPRESS_LEVEL
    )

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        host = request.headers.get("host")
        if not _host_is_allowed(host, app.state.allowed_hosts):
            return refusal(
                f"This server does not answer to the name {host!r}. It answers on this machine, "
                f"and to whatever {settings.ALLOWED_HOSTS_VARIABLE} names, which is how a reverse "
                "proxy such as Tailscale reaches it. Refusing a name nobody put there is what "
                "stops a domain that points here from reading your data."
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
        # Serialised, and this is the third attempt at it. The first two are worth knowing about
        # because each fixed the one before and broke something worse.
        #
        # It began as `with app.state.lock:` around the await, over a reentrant lock. That reads
        # exactly like one request at a time and is not: this middleware runs on the event loop's
        # own thread, so a second request arriving while the first is suspended takes the same
        # reentrant lock and goes straight through. Two requests then read one database connection,
        # their cursors interleave, and sqlite refuses both. Switching on two overlays at once was
        # enough.
        #
        # The fix for that was to take the lock in a worker thread, which serialised correctly and
        # wedged the whole server. `to_thread` draws from a pool of about forty, shared with every
        # sync endpoint, and a request waiting for its turn was sitting in one of them. Open the
        # fire map: a burst of scripts, stylesheets, settings, results and overlays arrives at
        # once, forty of them park in the pool waiting for the lock, and the request that HOLDS the
        # lock cannot get a thread to run its endpoint in. It never finishes, so it never releases,
        # so nobody ever gets a turn. The process stays up and the port stays open and the site
        # answers nothing at all, which is exactly what was reported.
        #
        # So: wait for a turn without occupying anything. `acquire(blocking=False)` takes no thread
        # and no time when the lock is free, which is almost always; when it is not, the sleep is
        # the only cost and it is a millisecond of nothing. One person on one machine will never
        # measure it, and there is no pool to run out of. It is also the only version that cannot
        # leak the lock: the sole await is the sleep, which happens before the lock is held.
        if _needs_the_database(request.url.path):
            while not app.state.lock.acquire(blocking=False):
                await anyio.sleep(0.005)
            try:
                response = await call_next(request)
            finally:
                app.state.lock.release()
        else:
            response = await call_next(request)
        # Nothing here is meant to be embedded anywhere, cached by anything, or sniffed.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Said out loud rather than left to a heuristic. With no `Cache-Control` at all a browser
        # gets to guess a lifetime from the last-modified date, and the guess is wrong in the way
        # that matters here: this tool is updated in place under a running browser, and a page that
        # holds a script from before the update runs half of one version and half of another. The
        # answer is not "never cache" but "always ask", which over loopback with an etag costs a
        # 304 and nothing else. Anything carrying the person's own data is not stored at all.
        response.headers.setdefault(
            "Cache-Control",
            "no-cache" if request.url.path.startswith(("/static/", "/vendor/")) else "no-store",
        )
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
        return answer(
            "searches", searches=wire.searches(held()), overview=api.overview(held())
        )

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

    @app.post("/api/searches/{name}/standing")
    async def standing(name: str, request: Request) -> dict[str, Any]:
        """Pause, resume, put away, bring back. Never delete: a search is a file somebody wrote."""
        body = await _body(request)
        api.set_standing(
            held(),
            name,
            paused=body.get("paused"),
            archived=body.get("archived"),
        )
        return answer("search", search=wire.search(held(), name))

    @app.delete("/api/searches/{name}")
    def delete_search(name: str) -> dict[str, Any]:
        """Out of the catalogue, and still on disk. See `api.delete_search` for why both."""
        return answer("deleted", **api.delete_search(held(), name))

    @app.post("/api/searches/{name}/restore")
    def restore_search(name: str) -> dict[str, Any]:
        made = api.restore_search(held(), name)
        return answer("search", search=wire.search(held(), made.name))

    @app.get("/api/deleted")
    def deleted_searches() -> dict[str, Any]:
        return answer("deleted", searches=list(api.deleted_searches(held())))

    @app.post("/api/judgments")
    async def judge(request: Request) -> dict[str, Any]:
        """One judgment over several properties.

        Passing is the daily work of the results table and it was one row at a time, each through a
        dialog. The core does the writing and reports what it wrote, so a batch that does not
        entirely succeed can be shown as what it was rather than as a number that might mean
        either.
        """
        body = await _body(request)
        held_ids = body.get("listing_ids")
        if not isinstance(held_ids, list):
            raise InvalidInput("listing_ids has to be a list of property identifiers.")
        return answer(
            "judged",
            **api.judge(
                held(),
                [str(one) for one in held_ids],
                judgment=body.get("judgment"),
                verdict=body.get("verdict"),
            ),
        )

    @app.get("/api/set-aside")
    def set_aside() -> dict[str, Any]:
        """Everything not being watched, with enough of each to decide about it."""
        return answer("set_aside", **api.set_aside_searches(held()))

    @app.post("/api/searches/{name}/discard")
    def discard_search(name: str) -> dict[str, Any]:
        """Remove a deleted definition for good.

        A path of its own rather than a second meaning for `DELETE /api/searches/{name}`, which
        already means the reversible one. Two operations that differ in whether they can be undone
        should not differ only in a verb.

        Behind the same host, origin and header guard as every other write, which is what actually
        stands between this and a page on another origin. The name typed into the dialog upstairs
        guards the hand at the keyboard and is not sent here as permission: whether this search is
        really deleted is read from the catalogue inside this request, by `api.discard_search`.
        """
        return answer("discarded", **api.discard_search(held(), name))

    @app.post("/api/searches/{name}/duplicate")
    async def duplicate(name: str, request: Request) -> dict[str, Any]:
        body = await _body(request)
        made = api.duplicate_search(held(), name, str(body.get("name") or ""))
        return answer("search", search=wire.search(held(), made.name))

    # -- runs --------------------------------------------------------------

    @app.post("/api/searches/{name}/run")
    async def start_run(name: str) -> dict[str, Any]:
        started = app.state.runs.start(held(), name)
        return answer("run-started", **started)

    @app.get("/api/runs/{name}/status")
    def status(name: str) -> dict[str, Any]:
        return answer("run-status", **app.state.runs.status(held(), name))

    @app.post("/api/run-all")
    async def start_all(request: Request) -> dict[str, Any]:
        started = app.state.runs.start_all(held())
        return answer("run-started", **started)

    # -- the passes and the spreadsheet, which are workspace-wide ----------

    @app.post("/api/enrich")
    async def enrich(request: Request) -> dict[str, Any]:
        body = await _body(request)
        started = app.state.runs.start_task(
            "enrich",
            lambda mine, say: api.enrich(
                mine, stale_only=bool(body.get("stale")), search=body.get("search"), progress=say
            ),
            held(),
        )
        return answer("task-started", **started)

    @app.post("/api/extract")
    async def extract(request: Request) -> dict[str, Any]:
        body = await _body(request)
        started = app.state.runs.start_task(
            "extract",
            lambda mine, say: api.extract(
                mine, search=body.get("search"), limit=body.get("limit"), progress=say
            ),
            held(),
        )
        return answer("task-started", **started)

    @app.post("/api/assess")
    async def assess(request: Request) -> dict[str, Any]:
        """Read the properties still in play against what this household said it wants.

        Sends more to the model than any other operation here: the address, the coordinates and the
        photograph, which the extraction pass is structurally forbidden. The control that starts it
        says so before it is pressed; see `settings.js`.
        """
        body = await _body(request)
        started = app.state.runs.start_task(
            "assess",
            lambda mine, say: api.assess(
                mine, search=body.get("search"), limit=body.get("limit"), progress=say
            ),
            held(),
        )
        return answer("task-started", **started)

    @app.get("/api/assessment/{listing_id}")
    def assessment(listing_id: str) -> dict[str, Any]:
        return answer("assessment", **api.assessment_for(held(), listing_id))

    @app.post("/api/deliver")
    async def deliver(request: Request) -> dict[str, Any]:
        started = app.state.runs.start_task(
            "deliver",
            lambda mine, say: api.deliver(mine, progress=say),
            held(),
        )
        return answer("task-started", **started)

    @app.post("/api/export")
    async def export(request: Request) -> dict[str, Any]:
        body = await _body(request)
        written = api.export(
            held(),
            search=body.get("search"),
            template=body.get("template"),
            format=str(body.get("format") or "xlsx"),
            force=bool(body.get("force")),
            include_dropped=bool(body.get("include_dropped")),
        )
        return answer(
            "export",
            path=str(written.path),
            format=written.format,
            template=written.template,
            properties=written.properties,
            areas=written.areas,
            columns=list(written.columns),
            empty_columns={o: list(names) for o, names in written.empty.items()},
            reasons=written.reasons(),
        )

    @app.get("/api/tasks/{name}")
    def task_status(name: str) -> dict[str, Any]:
        return answer("task-status", **app.state.runs.task_status(held(), name))

    @app.get("/api/under-way")
    def under_way() -> dict[str, Any]:
        """Everything happening right now, for the marker every screen carries.

        One ask on one schedule rather than one per surface: six screens polling for themselves is
        six answers that can disagree and six requests where one would do. Read from the store, so a
        pass started from a terminal or by the scheduled job is in it.
        """
        return answer("under-way", passes=api.under_way(held()))

    # -- what this installation has set up ---------------------------------

    @app.get("/api/configuration")
    def configuration() -> dict[str, Any]:
        return answer("configuration", **api.configuration(held()))

    @app.post("/api/configuration")
    async def write_configuration(request: Request) -> dict[str, Any]:
        body = await _body(request)
        values = body.get("set")
        if not isinstance(values, Mapping) or not values:
            raise InvalidInput('Nothing to change: send {"set": {...}}.')
        return answer("configuration", **api.set_configuration(held(), dict(values)))

    @app.get("/api/broadband")
    def broadband() -> dict[str, Any]:
        return answer("broadband", **api.broadband(held()))

    @app.post("/api/broadband")
    async def load_broadband(request: Request) -> dict[str, Any]:
        body = await _body(request)
        started = app.state.runs.start_task(
            "broadband",
            lambda mine, say: api.broadband(mine, state=str(body.get("state") or ""), progress=say),
            held(),
        )
        return answer("task-started", **started)

    @app.get("/api/notes")
    def model_notes() -> dict[str, Any]:
        return answer("notes", **api.model_notes(held()))

    @app.post("/api/notes")
    async def write_model_notes(request: Request) -> dict[str, Any]:
        body = await _body(request)
        return answer("notes", **api.set_model_notes(held(), str(body.get("notes") or "")))

    @app.get("/api/export/templates")
    def templates() -> dict[str, Any]:
        return answer("templates", templates=list(api.export_templates(held())))

    # -- results -----------------------------------------------------------

    @app.get("/api/results/{name}")
    def results(
        name: str, include_dropped: bool = False, include_passed: bool = False
    ) -> dict[str, Any]:
        return answer(
            "results",
            **api.results(
                held(), name, include_dropped=include_dropped, include_passed=include_passed
            ),
        )

    @app.get("/api/passed")
    def passed() -> dict[str, Any]:
        """What the person has passed on, which the results table keeps out of the way.

        The table reaches the same properties through its own toggle, and this is here so the
        capability is addressable rather than only visible: non-negotiable 8 says anything one
        surface can do the other can do, and "list what I said no to" is one of those things.
        """
        rows, count = api.passed(held())
        return answer("passed", passed=list(rows), count=count)

    @app.get("/api/hazard/{layer}")
    def hazard(layer: str, bbox: str, size: str = "256,256") -> Response:
        """One tile of a hazard layer, fetched by this machine rather than by the browser.

        Kept on disk once fetched, so the same part of the country costs nothing to look at
        twice; the browser is told it may keep it too.
        """
        return Response(
            content=api.hazard_tile(held(), layer, bbox, size),
            media_type="image/png",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "public, max-age=604800",
            },
        )

    @app.get("/api/ground/{name}")
    def ground(name: str) -> dict[str, Any]:
        """County lines and town names over the states this run found properties in.

        Separate from the rainfall below because it costs almost nothing and answers at once: the
        names can be on the map while the numbers are still being read.
        """
        return answer("ground", **api.ground(held(), name))

    @app.get("/api/rain/{name}")
    def rainfall(name: str) -> dict[str, Any]:
        """A yearly rainfall average for every county this run touches.

        The first call reads thirty years for each of them and takes a few seconds; every call
        after it is off the disk, because a thirty-year average changes by a hundredth of an inch
        a year.
        """
        return answer("rainfall", **api.rainfall(held(), name))

    @app.get("/api/wind/stations/{name}")
    def wind_stations(name: str) -> dict[str, Any]:
        """Which weather stations cover the states this run found properties in.

        One small list per state, kept once fetched. Separate from the rose itself because a
        page can draw where the stations are the moment it opens and fill in what each one says
        as the answers arrive, which is the difference between a map and a wait.
        """
        return answer("wind_stations", **api.wind_stations(held(), name))

    @app.get("/api/wind/rose/{network}/{station}")
    def wind_rose(network: str, station: str, season: str = "april") -> dict[str, Any]:
        """One station's wind rose, over its whole record rather than over a forecast."""
        return answer("wind_rose", rose=api.wind_rose(held(), network, station, season))

    @app.get("/api/kept")
    def kept() -> dict[str, Any]:
        """The shortlist, the other half of the same judgment the results table writes."""
        rows, count = api.kept(held())
        return answer("kept", kept=list(rows), count=count)

    @app.get("/api/export/{name}")
    def download_export(
        name: str, format: str = "xlsx", include_dropped: bool = False
    ) -> FileResponse:
        """The spreadsheet, downloaded from the page the person is already reading.

        Declared after `/api/export/templates` on purpose: that path would otherwise be
        read as a saved search called `templates`.

        The same core operation the terminal calls, writing to the same place in the
        workspace, so a sheet taken from here and a sheet taken from `homescout export` are
        the same file made the same way. It is sent as well as written: the file staying in
        the workspace is what makes the export findable again without asking for it twice.
        """
        if format not in ("xlsx", "csv"):
            raise InvalidInput("A sheet is written as xlsx or csv.")
        written = api.export(
            held(), search=name, format=format, force=True, include_dropped=include_dropped
        )
        path = Path(getattr(written, "path", written))
        return FileResponse(
            path,
            filename=path.name,
            media_type=(
                "text/csv"
                if format == "csv"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Cache-Control": "no-store"},
        )

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
            # Every annotation field the store declares, so the two surfaces cannot come to
            # disagree about which of them a person may write.
            for name in api.annotation_fields()
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

    # -- the household's own vocabulary -------------------------------------

    @app.get("/api/tags")
    def all_tags() -> dict[str, Any]:
        """Every tag, with how many properties carry it.

        Read whenever somebody is about to tag something, because the choice worth offering is the
        words they already use. A vocabulary you have to retype from memory grows a second
        spelling of every word in it.
        """
        return answer("tags", tags=list(api.tags(held())))

    @app.post("/api/tags")
    async def make_tag(request: Request) -> dict[str, Any]:
        """Add a word to the vocabulary, whether or not a property carries it yet."""
        body = await _body(request)
        return answer("tag", tag=api.create_tag(held(), str(body.get("name", ""))))

    @app.post("/api/tags/{name}/rename")
    async def rename(name: str, request: Request) -> dict[str, Any]:
        """Rename a tag everywhere it is used. Onto an existing name, the two merge."""
        body = await _body(request)
        return answer("tag", tag=api.rename_tag(held(), name, str(body.get("to", ""))))

    @app.delete("/api/tags/{name}")
    def drop_tag(name: str) -> dict[str, Any]:
        """Take a tag out of the vocabulary and off every property carrying it."""
        return answer("tag_deleted", name=name, properties=api.delete_tag(held(), name))

    @app.put("/api/listings/{listing_id}/tags")
    async def set_tags(listing_id: str, request: Request) -> dict[str, Any]:
        """The whole list of tags for one property. Anything not named comes off.

        A PUT and not a POST, and the whole list and not a difference, because that is what the
        control on the page is: a set of boxes, some ticked. Sending what is ticked cannot drift
        from what is shown; sending "add this, remove that" can and eventually does.
        """
        body = await _body(request)
        names = body.get("tags", [])
        if not isinstance(names, list):
            raise InvalidInput("`tags` should be a list of names.")
        return answer(
            "tags", listing_id=listing_id, tags=list(api.set_tags(held(), listing_id, names))
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
        return answer(
            "areas",
            areas=wire.areas(held()),
            places=wire.places(held()),
            matching_kinds=list(api.MATCHING_KINDS),
        )

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
    def installation() -> dict[str, Any]:
        # Not called `settings`: this whole function body is one scope, and a local of that name
        # would shadow the `settings` module the guard above reads.
        return answer("settings", **wire.installation(held()))

    for path, page in wire.PAGES.items():
        _serve_page(app, path, page)
    for old, new in wire.MOVED.items():
        _redirect_page(app, old, new)

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


def _redirect_page(app: FastAPI, old: str, new: str) -> None:
    """A surface that was renamed, still answering at the address it used to have.

    The target is built from the route template with the matched name put into it, never from
    anything in the request beyond that name: a redirect that echoes what it was handed is a
    redirect somebody else can aim. The name has already been matched as one path segment by the
    time this runs, so it cannot carry a slash into the template.
    """

    async def handler(name: str) -> RedirectResponse:
        return RedirectResponse(new.format(name=quote(name, safe="")), status_code=301)

    app.add_api_route(old, handler, methods=["GET"], include_in_schema=False)


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
