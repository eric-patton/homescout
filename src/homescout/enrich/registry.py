"""Which providers exist, in the same shape the source registry already has.

The pass walks this and never names a provider, which is what makes adding one a new module and a
registration rather than an edit to the pass (AC-1).

Every provider's declared values are checked against the rule engine's namespace at import. That is
a two-way check and both directions have bitten this codebase before: a provider supplying a value
no criterion could name is work nobody can use, and an enriched name the rule engine declares with
nothing filling it is a promise the tool cannot keep.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..rules import namespace as ns
from .provider import Provider
from .providers import Aquifer, Broadband, Elevation, Flood, Wildfire, WildlandUrbanInterface

#: In the order a pass asks them, which is cheapest and most permanent first, so that a slow or
#: flaky service never delays the answers that almost never change.
SHIPPED: tuple[Callable[[], Provider], ...] = (
    Elevation,
    Aquifer,
    Flood,
    Wildfire,
    WildlandUrbanInterface,
    Broadband,
)

_REGISTERED: dict[str, Callable[[], Provider]] = {maker().name: maker for maker in SHIPPED}


def register(name: str, maker: Callable[[], Provider], *, replace: bool = False) -> None:
    if name in _REGISTERED and not replace:
        raise ValueError(f"a provider named {name!r} is already registered")
    _REGISTERED[name] = maker


def unregister(name: str) -> None:
    _REGISTERED.pop(name, None)


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTERED))


def restore_shipped() -> None:
    """Put the shipped providers back, for a test that swapped them out."""
    _REGISTERED.clear()
    _REGISTERED.update({maker().name: maker for maker in SHIPPED})


def create(names: Iterable[str] | None = None) -> tuple[Provider, ...]:
    """Build the named providers, or every registered one."""
    wanted = tuple(names) if names is not None else registered()
    missing = [name for name in wanted if name not in _REGISTERED]
    if missing:
        raise ValueError(f"no provider named {', '.join(sorted(missing))}")
    return tuple(_REGISTERED[name]() for name in wanted)


def _check_against_the_namespace() -> None:
    """Every declared value is a name a criterion can use, and every enriched name has a filler."""
    supplied: set[str] = set()
    for maker in SHIPPED:
        for name in maker().values():
            field = ns.find(name)
            if field is None or field.origin != "enriched":
                raise AssertionError(
                    f"{maker().name} supplies {name!r}, which is not an enriched field in the "
                    "rule engine's namespace. A value no criterion can name is work nobody can use."
                )
            supplied.add(name)

    declared = {name for name, field in ns.FIELDS.items() if field.origin == "enriched"}
    if declared - supplied:
        raise AssertionError(
            f"the rule engine declares enriched fields nothing fills: {sorted(declared - supplied)}"
        )


_check_against_the_namespace()
