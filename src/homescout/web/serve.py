"""Starting the interface, on this machine and nowhere else.

The bind address is the whole of this module's interesting content. It defaults to the loopback
address, it is a parameter rather than a constant so a test can prove the default rather than read
it, and there is a refusal in the way of anything that is not loopback: there is no authentication
here by design, so a routable bind address would put an unauthenticated, mutating API on a network.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from ..errors import InvalidInput

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765  # also `settings.DEFAULT_PORT`, and overridden by HOMESCOUT_PORT


def is_loopback(host: str) -> bool:
    if host.strip().casefold() in ("localhost", "loopback"):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def build(workspace: Any) -> Any:
    """The application, for a caller that wants to drive it without a server."""
    from .app import build as make

    return make(workspace)


def serve(
    workspace: Any,
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    open_browser: bool = False,
) -> None:
    """Run the interface until it is stopped.

    A non-loopback address is refused rather than warned about. The constitution says this tool
    binds to localhost, has no authentication and no multi-user model; an address anybody else can
    reach turns all three of those from a design into a hole.
    """
    if not is_loopback(host):
        raise InvalidInput(
            f"{host!r} is not an address on this machine. This interface has no authentication by "
            "design, so it is only ever served to the machine it runs on. Use 127.0.0.1. "
            "To reach it from elsewhere, put a reverse proxy on this machine in front of it and "
            "name that proxy in HOMESCOUT_ALLOWED_HOSTS. See docs/tailscale.md."
        )

    import uvicorn

    from . import settings as web_settings

    port = port if port is not None else web_settings.port(workspace.root)
    named = web_settings.allowed_hosts(workspace.root)
    app = build(workspace)
    where = f"http://{host}:{port}/"
    if open_browser:
        import webbrowser

        webbrowser.open(where)

    reach = f"; also answering to {', '.join(named)}" if named else "; this machine only"
    print(f"HomeScout is at {where}  (Ctrl+C to stop{reach})")
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
