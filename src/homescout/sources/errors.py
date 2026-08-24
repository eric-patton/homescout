"""What can go wrong when talking to a listing site.

Two of these are not really errors. `SourceFailed` and `SourceUnavailable` are how an adapter says
what happened to *this* source, and the caller turns them into that source's outcome for the run.
Neither is ever allowed to escape as far as a caller querying a different source, because one site
having a bad afternoon must cost that site's listings and nothing else.
"""

from __future__ import annotations


class SourceError(Exception):
    """Base for everything this package raises."""


class SourceFailed(SourceError):
    """The source was asked and could not answer.

    An error, a timeout, a refusal that outlasted the retries, an unreadable response. The reason is
    written for a person reading a run report, not for a log parser.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SourceUnavailable(SourceError):
    """The source cannot serve this query at all.

    Different from failing, and the difference matters: a failure might succeed tomorrow, while a
    source that has no way to express a drawn polygon will never have one. Reporting the second as
    the first would have the tool retrying forever against a wall.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfigurationError(SourceError):
    """A politeness setting was refused at load time.

    Raised only while reading configuration, never while running, so a value that would make the
    tool rude is caught before it makes a single request.
    """
