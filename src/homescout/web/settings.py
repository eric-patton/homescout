"""Where the interface listens, what names it will answer to, and what the map draws over.

A handful of settings, read through the same `.env`-and-environment loader the digest and the
extraction model already use, so there is one place to look for every setting in this product.

The interesting one is `HOMESCOUT_ALLOWED_HOSTS`, and it is worth reading before changing.

**The server still binds to the loopback address, always.** That has not moved and cannot: nothing
here makes it listen anywhere else, and `serve.serve` refuses a routable bind address outright. What
this setting is for is the other shape, where something on this machine takes a connection from
somewhere and forwards it to the loopback port. A reverse proxy, and in practice `tailscale serve`.

That shape needs one thing from the guard. The request arrives on loopback, as it must, but it
carries the `Host` header the browser sent, which is the proxy's name rather than `127.0.0.1`. The
guard refuses that by design, because refusing a `Host` this server does not answer to is exactly
what stops DNS rebinding: a page on `evil.invalid` whose DNS points here still sends
`Host: evil.invalid`.

So the fix is a list of names, not the removal of the check. Empty by default, which is loopback and
nothing else. A name in it is a name a person deliberately put there, and every name that is not in
it is still refused, so rebinding is still refused.

**None of this adds authentication, because there is none.** Whatever can reach the proxy can use
this. See `docs/tailscale.md`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

#: Where the interface listens on the loopback address. A setting rather than only a flag, so a
#: scheduled task and a person typing `homescout serve` agree without repeating a number.
PORT_VARIABLE = "HOMESCOUT_PORT"
DEFAULT_PORT = 8765

#: Names this server will answer to besides the loopback ones. Comma separated, port optional.
#: Empty by default. See this module's own explanation before adding one.
ALLOWED_HOSTS_VARIABLE = "HOMESCOUT_ALLOWED_HOSTS"

#: A tile source for the map, if the person configured one. Empty by default and deliberately so:
#: asking a tile server for tiles tells it which part of the world is being looked at, and
#: `product-global.md` lists exactly four kinds of outbound traffic this product makes.
TILES_VARIABLE = "HOMESCOUT_MAP_TILES"
TILES_ATTRIBUTION_VARIABLE = "HOMESCOUT_MAP_ATTRIBUTION"

#: A second background for the same map: the photograph from above. Separate from the drawn one
#: rather than a replacement for it, because the two answer different questions about a rural
#: property and somebody looking at land wants both. A drawn map says where the roads go and what
#: the parcel is called. A photograph says what is actually on the ground: whether the trees come up
#: to the house, whether the neighbour is a feedlot, whether the track in is a track.
#:
#: Empty by default and configured exactly like the drawn one, which is the point. This is a second
#: tile server, so it is a second thing being told which part of the world is being looked at, and
#: it gets the same treatment rather than being waved through because the pictures are nice.
SATELLITE_VARIABLE = "HOMESCOUT_MAP_SATELLITE"
SATELLITE_ATTRIBUTION_VARIABLE = "HOMESCOUT_MAP_SATELLITE_ATTRIBUTION"

#: How deep this particular imagery actually goes, which is the one thing that differs between two
#: otherwise interchangeable sources and the one thing neither of them will tell you.
#:
#: Measured, because both services *publish* a maximum of twenty-three and neither means it. The
#: government's imagery answers 404 past zoom sixteen at every New Mexico address tried, downtown
#: Albuquerque included, so it is the whole cache rather than a rural gap. Esri's answers to
#: twenty-one everywhere tried.
#:
#: It matters because of what a tile server does when asked past its own depth: it returns nothing,
#: and nothing paints as a hole. A map that goes blank when somebody zooms in reads as broken,
#: where a picture that goes soft reads as a picture running out, which is the truth. So the deepest
#: real level is recorded and the map stretches that one rather than asking for a level that is not
#: there. Blank means no cap, which is the right default for an address nobody here has measured.
SATELLITE_MAX_ZOOM_VARIABLE = "HOMESCOUT_MAP_SATELLITE_MAX_ZOOM"

VARIABLES: tuple[str, ...] = (
    PORT_VARIABLE,
    ALLOWED_HOSTS_VARIABLE,
    TILES_VARIABLE,
    TILES_ATTRIBUTION_VARIABLE,
    SATELLITE_VARIABLE,
    SATELLITE_ATTRIBUTION_VARIABLE,
    SATELLITE_MAX_ZOOM_VARIABLE,
)


def values(root: Path, environ: Any = None) -> dict[str, str]:
    from ..deliver.settings import environment

    return environment(root, environ)


def port(root: Path, environ: Any = None) -> int:
    """The port to listen on, or the shipped default.

    An unusable value is the default rather than a failure: a server that will not start because of
    a typo in a file is a server somebody discovers is down, and the default always works.
    """
    raw = (values(root, environ).get(PORT_VARIABLE) or "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        found = int(raw)
    except ValueError:
        return DEFAULT_PORT
    return found if 1 <= found <= 65_535 else DEFAULT_PORT


def allowed_hosts(root: Path, environ: Any = None) -> tuple[str, ...]:
    """The names a reverse proxy may present, folded for comparison. Empty unless configured."""
    raw = (values(root, environ).get(ALLOWED_HOSTS_VARIABLE) or "").strip()
    if not raw:
        return ()
    return tuple(
        name.strip().casefold() for name in raw.replace(";", ",").split(",") if name.strip()
    )


def tiles(root: Path, environ: Any = None) -> tuple[str | None, str | None]:
    found = values(root, environ)
    return (
        (found.get(TILES_VARIABLE) or "").strip() or None,
        (found.get(TILES_ATTRIBUTION_VARIABLE) or "").strip() or None,
    )


def satellite(root: Path, environ: Any = None) -> tuple[str | None, str | None]:
    """The photographic background, if one is configured. Read exactly like the drawn one."""
    found = values(root, environ)
    return (
        (found.get(SATELLITE_VARIABLE) or "").strip() or None,
        (found.get(SATELLITE_ATTRIBUTION_VARIABLE) or "").strip() or None,
    )


def satellite_max_zoom(root: Path, environ: Any = None) -> int | None:
    """The deepest zoom the imagery actually has, or nothing if nobody has measured it.

    An unreadable value is nothing rather than a failure, for the reason `port` gives: a map that
    will not draw because of a typo in a file is a map somebody discovers is broken.
    """
    raw = (values(root, environ).get(SATELLITE_MAX_ZOOM_VARIABLE) or "").strip()
    if not raw:
        return None
    try:
        found = int(raw)
    except ValueError:
        return None
    return found if 0 < found <= 24 else None
