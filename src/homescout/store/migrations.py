"""Forward-only schema migrations.

Eleven further features add tables to this same file, so this exists from the first commit rather
than being retrofitted once it is painful. A file from an older build is migrated forward; a file
from a newer build is refused by name rather than opened hopefully.
"""

from __future__ import annotations

import sqlite3

from .db import schema_version
from .errors import SchemaTooNewError
from .schema import (
    DECISION_TABLES,
    DELIVERY_TABLES,
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_V3,
    SCHEMA_V4,
    SCHEMA_V5,
    SCHEMA_VERSION,
    VERDICT_TABLES,
    append_only_triggers,
)

# Index i produces version i + 1. Never reorder, and never rewrite an entry that has shipped: a
# migration that has run on someone's real database is history too.
MIGRATIONS: tuple[str, ...] = (
    SCHEMA_V1 + "\n" + append_only_triggers(),
    SCHEMA_V2 + "\n" + append_only_triggers(VERDICT_TABLES),
    SCHEMA_V3,
    SCHEMA_V4 + "\n" + append_only_triggers(DELIVERY_TABLES),
    SCHEMA_V5 + "\n" + append_only_triggers(DECISION_TABLES),
)


def _apply(conn: sqlite3.Connection, sql: str, target: int) -> None:
    """Run one migration and stamp the version, atomically.

    The transaction is written into the script rather than issued around it, because running a
    script implicitly commits whatever transaction was already open. Stamping the version inside
    the same transaction is what stops a failure from leaving a half-built schema that claims to be
    a finished one.
    """
    conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {int(target)};\nCOMMIT;")


def migrate(conn: sqlite3.Connection) -> int:
    """Bring the database up to the version this build understands.

    Refuses a file written by a newer build, naming both versions, rather than operating against a
    schema it does not recognize.
    """
    found = schema_version(conn)
    if found > SCHEMA_VERSION:
        raise SchemaTooNewError(found=found, supported=SCHEMA_VERSION)
    if found == SCHEMA_VERSION:
        return found

    for target in range(found + 1, SCHEMA_VERSION + 1):
        try:
            _apply(conn, MIGRATIONS[target - 1], target)
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return SCHEMA_VERSION
