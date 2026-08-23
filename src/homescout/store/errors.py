"""Errors the store raises.

Every one of these carries a message a person can act on. The store is opened by a scheduled task
that nobody is watching and by a browser the user has open at the same time, so "database is
locked" on its own is not an acceptable thing to report.
"""


class StoreError(Exception):
    """Base for every error this package raises."""


class SchemaTooNewError(StoreError):
    """The file was written by a newer version of HomeScout than this one understands."""

    def __init__(self, found: int, supported: int) -> None:
        self.found = found
        self.supported = supported
        super().__init__(
            f"This database was written by a newer version of HomeScout. "
            f"It is at schema version {found}; this build understands version {supported}. "
            f"Upgrade HomeScout, or point it at a different database file."
        )


class StoreLockedError(StoreError):
    """Another process is holding the database open."""

    def __init__(self, path: str, timeout_seconds: float) -> None:
        self.path = path
        super().__init__(
            f"Could not get access to {path} within {timeout_seconds:g} seconds because another "
            f"process is using it. The usual cause is the HomeScout browser interface being open, "
            f"or another run already in progress. Close it, or wait for that run to finish."
        )


class HistoryIsAppendOnlyError(StoreError):
    """Something tried to rewrite recorded history.

    This is raised when the database's own triggers refuse a write. It is a bug in the caller, not
    a condition to handle: recorded observations are never edited, and corrections are new rows.
    """


class RunNotCompletedError(StoreError):
    """A run that did not finish cannot be used as a comparison baseline."""


class NoBaselineError(StoreError):
    """There is no completed run to compare against."""

    def __init__(self, search_name: str, before: str | None = None) -> None:
        self.search_name = search_name
        when = f" at or before {before}" if before else ""
        super().__init__(
            f"There is no completed run of '{search_name}'{when} to compare against. "
            f"Run the search at least once first."
        )


class UnknownListingError(StoreError):
    """The listing id does not exist."""
