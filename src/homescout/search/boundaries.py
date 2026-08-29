"""Where a named place turns into a shape, which is deliberately not here.

A city, a county and a ZIP code are names. Testing whether a house is inside one exactly needs that
name resolved to a boundary, and boundaries are public geospatial data with a cache and a
time-to-live, which is the enrichment feature's whole job (feat-007). Two implementations of that
would mean two caches, two sets of national coverage, and two answers to the same question.

So this module is a port and nothing else. Until enrichment registers a provider, every question
here is answered `None`, which the areas above read as "could not be tested" rather than as "not
inside". That distinction is the entire point: a house nobody could place is kept and counted, not
quietly dropped.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BoundaryProvider(Protocol):
    """Whatever can turn a name into a place. Implemented by enrichment (feat-007)."""

    def boundary(self, kind: str, value: str) -> Any | None:
        """The shape of a named place, as GeoJSON, or None when it cannot say."""
        ...

    def locate(self, place: str) -> tuple[float, float] | None:
        """A place's centre, as (latitude, longitude), or None when it cannot say."""
        ...

    def candidates(self, kind: str, value: str) -> tuple[str, ...]:
        """Every place this name could mean, for reporting an ambiguity rather than picking one."""
        ...


_PROVIDER: BoundaryProvider | None = None

#: One thread's own provider, which wins over the process-wide one for that thread alone.
#:
#: The provider reaches through a database connection, so which one is registered is not a
#: preference: it decides whose connection a boundary lookup uses. The browser interface keeps a
#: single connection for requests and gives a pass that takes minutes a connection of its own, and
#: a pass that filters by area has to resolve geography through the connection it actually holds.
#: Registering that one process-wide would hand the server's threads a connection belonging to
#: another, which is the interleaved-cursor fault the interface's lock exists to prevent.
_HERE = threading.local()


def register_boundaries(provider: BoundaryProvider) -> None:
    global _PROVIDER
    _PROVIDER = provider


def unregister_boundaries() -> None:
    global _PROVIDER
    _PROVIDER = None


@contextmanager
def boundaries_on_this_thread(provider: BoundaryProvider) -> Iterator[None]:
    """Use this provider for the duration, on this thread and no other.

    Restores whatever was there before, so a background pass cannot leave the process resolving
    geography through a connection it has since closed.
    """
    before = getattr(_HERE, "provider", None)
    _HERE.provider = provider
    try:
        yield
    finally:
        _HERE.provider = before


def boundaries() -> BoundaryProvider | None:
    """The registered provider, or None, which is the honest answer today."""
    here = getattr(_HERE, "provider", None)
    if here is not None:
        return here
    return _PROVIDER
