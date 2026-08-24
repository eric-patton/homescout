"""Talking to listing sites, politely, behind one interface.

Three sources, no supported API between them. This package reduces them all to four members (a name,
what the site will filter on its own side, a search, and one preview image per row) and puts a
politeness gate between the tool and every request it makes.

Two things are worth knowing before reading further:

**An adapter cannot be impolite.** It is handed a `PacedSession` and nothing else, so there is no
code path by which it can make an unpaced request, retry without jitter, or claim to be a browser.
Splitting a query into forty pieces cannot become a burst because there is no way to express one.

**An adapter cannot write anything.** It is never handed a store. What it returns is values, and a
run decides what to record. One site being down therefore costs that site's listings and nothing
else.
"""

from __future__ import annotations

from .base import (
    AddressRadius,
    Area,
    BaseSource,
    BoundingBox,
    Capabilities,
    City,
    County,
    DateRange,
    PointRadius,
    Polygon,
    PostalCode,
    Preview,
    SearchQuery,
    SearchResult,
    Source,
    State,
    Truncation,
)
from .ceiling import Harvest, Page, collect
from .errors import ConfigurationError, SourceError, SourceFailed, SourceUnavailable
from .politeness import (
    DEFAULT_DELAY_SECONDS,
    DELAY_RANGE_SECONDS,
    BodyTooLarge,
    Fetched,
    PacedSession,
    PolitenessConfig,
    Request,
    SourcePolicy,
)
from .realtor import RealtorSource
from .realtor import factory as _realtor_factory
from .redfin import RedfinSource
from .redfin import factory as _redfin_factory
from .registry import create, register, registered, unregister
from .zillow import ZillowSource
from .zillow import factory as _zillow_factory

# Registration is the whole of what adding a source costs. Nothing below this line, and nothing in
# the store, the run loop or the politeness layer, knows how many sources there are.
register("realtor", _realtor_factory, replace=True)
register("zillow", _zillow_factory, replace=True)
register("redfin", _redfin_factory, replace=True)

USER_AGENT = "homescout/0.1.0 (personal listing monitor)"


def default_session(transport: object | None = None, **kwargs: object) -> PacedSession:
    """A session with the shipped defaults, over the real network unless told otherwise."""
    if transport is None:
        from .transport import RequestsTransport

        transport = RequestsTransport()
    return PacedSession(transport, user_agent=USER_AGENT, **kwargs)  # type: ignore[arg-type]


__all__ = [
    "DEFAULT_DELAY_SECONDS",
    "DELAY_RANGE_SECONDS",
    "USER_AGENT",
    "AddressRadius",
    "Area",
    "BaseSource",
    "BodyTooLarge",
    "BoundingBox",
    "Capabilities",
    "City",
    "ConfigurationError",
    "County",
    "DateRange",
    "Fetched",
    "Harvest",
    "PacedSession",
    "Page",
    "PolitenessConfig",
    "PointRadius",
    "Polygon",
    "PostalCode",
    "Preview",
    "RealtorSource",
    "RedfinSource",
    "Request",
    "SearchQuery",
    "SearchResult",
    "Source",
    "SourceError",
    "SourceFailed",
    "SourcePolicy",
    "SourceUnavailable",
    "State",
    "Truncation",
    "ZillowSource",
    "collect",
    "create",
    "default_session",
    "register",
    "registered",
    "unregister",
]
