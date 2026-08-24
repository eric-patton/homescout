"""Which sources exist, by name.

The only place in the product that knows a source's name is a string in a saved search. Nothing
else, the run loop and the store included, names a site. Adding one is a single call here, which is
what makes "adding a source means writing one adapter" true rather than aspirational.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import Source
from .politeness import PacedSession

#: A factory rather than an instance, because an adapter is built around one paced session and a
#: run decides which session that is.
Factory = Callable[[PacedSession], Source]

_REGISTRY: dict[str, Factory] = {}


def register(name: str, factory: Factory, *, replace: bool = False) -> None:
    if not replace and name in _REGISTRY:
        raise ValueError(f"a source named {name!r} is already registered")
    _REGISTRY[name] = factory


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)


def create(name: str, session: PacedSession) -> Source:
    try:
        factory = _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise KeyError(f"no source named {name!r} is registered; known sources: {known}") from None
    return factory(session)


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))
