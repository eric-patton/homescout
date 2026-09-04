"""Starting the interface, on this machine and nowhere else.

The bind address is the whole of this module's interesting content. It defaults to the loopback
address, it is a parameter rather than a constant so a test can prove the default rather than read
it, and there is a refusal in the way of anything that is not loopback: there is no authentication
here by design, so a routable bind address would put an unauthenticated, mutating API on a network.
"""

from __future__ import annotations

import ipaddress
import sys
from typing import Any

from ..errors import InvalidInput

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765  # also `settings.DEFAULT_PORT`, and overridden by HOMESCOUT_PORT

#: Windows' own names for the one setting this asks about. `PROCESS_POWER_THROTTLING_STATE` is
#: three unsigned 32-bit integers, a version, which bits are being set and what they are set to;
#: `ProcessPowerThrottling` is its number in `PROCESS_INFORMATION_CLASS`; and the bit is the one
#: that lets the system run this process slowly to save power.
POWER_THROTTLING_VERSION = 1
POWER_THROTTLING_CLASS = 4
EXECUTION_SPEED = 0x1


def at_full_speed() -> bool:
    """Ask Windows not to slow this process down. True if it agreed; False anywhere else.

    Windows 11 moves a process it judges to be background work into its efficiency mode some time
    after the process starts: onto the slow cores, at a reduced clock, everything in it at a
    fraction of the speed. It judges by what it can see, and what it sees of this server when a
    scheduled task starts it is no window and a below-normal priority, which is the profile it
    throttles. Measured on a real workspace with nothing else changed, one results answer went
    from 0.7 seconds in a fresh process to between 3 and 4.8 in the copy that had been up for
    three hours, and back to 0.7 the moment the throttling was lifted. Raising the priority on its
    own changed nothing, so priority is left alone.

    Best effort, on purpose. A Windows build that refuses the call gets a slow server rather than
    no server, and anywhere other than Windows nothing is asked at all.
    """
    return _set_power_throttling(EXECUTION_SPEED, 0)


def power_throttling() -> tuple[int, int] | None:
    """What this process has told Windows about throttling: (which bits, their values).

    A control of zero means nothing has been said and the system decides. None anywhere other
    than Windows, and on a Windows that will not say.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        state = _PowerThrottling()
        state.Version = POWER_THROTTLING_VERSION
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        if not kernel32.GetProcessInformation(
            ctypes.c_void_p(kernel32.GetCurrentProcess()),
            POWER_THROTTLING_CLASS,
            ctypes.byref(state),
            ctypes.sizeof(state),
        ):
            return None
        return int(state.ControlMask), int(state.StateMask)
    except Exception:  # noqa: BLE001 - "cannot tell" is an answer here, and a harmless one
        return None


def _set_power_throttling(control: int, state: int) -> bool:
    """Tell Windows which throttling bits to take from us and what to set them to.

    `control` of zero hands the decision back to the system, which is how a test puts the process
    it runs in back the way it found it.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        wanted = _PowerThrottling()
        wanted.Version = POWER_THROTTLING_VERSION
        wanted.ControlMask = control
        wanted.StateMask = state
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        return bool(
            kernel32.SetProcessInformation(
                ctypes.c_void_p(kernel32.GetCurrentProcess()),
                POWER_THROTTLING_CLASS,
                ctypes.byref(wanted),
                ctypes.sizeof(wanted),
            )
        )
    except Exception:  # noqa: BLE001 - a server that starts slowly beats one that does not start
        return False


def _PowerThrottling() -> Any:  # noqa: N802 - named for the Windows structure it is
    """One `PROCESS_POWER_THROTTLING_STATE`, built where it is used rather than at import."""
    import ctypes

    class PowerThrottlingState(ctypes.Structure):
        _fields_ = [
            ("Version", ctypes.c_uint32),
            ("ControlMask", ctypes.c_uint32),
            ("StateMask", ctypes.c_uint32),
        ]

    return PowerThrottlingState()


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
    # Asked here, on the way in, so that every start passes through it: by hand, from a shortcut,
    # from the scheduled task, or from whatever starts it next.
    at_full_speed()
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
