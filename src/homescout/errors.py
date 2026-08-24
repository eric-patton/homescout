"""The two failures every surface has to tell apart.

A command line returns an exit code and a browser returns a status; both need the same distinction
underneath, and neither should be the place it is decided. So the core raises one of these and the
surface translates. Everything else that goes wrong is unexpected, which is its own answer.
"""

from __future__ import annotations


class HomescoutError(Exception):
    """Base for the errors the core raises deliberately."""


class InvalidInput(HomescoutError):
    """What was asked for cannot be understood or does not exist.

    A misspelled saved search, a delay outside the permitted range, a definition that fails
    validation. The fix is always in what the caller passed.
    """


class PreconditionNotMet(HomescoutError):
    """What was asked for is valid but cannot proceed yet.

    Nothing to compare against, a run already in progress, the database held by another process, a
    capability whose feature is not built. The fix is never in what the caller passed, which is why
    it is a different answer from invalid input.
    """
