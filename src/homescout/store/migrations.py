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
    SCHEMA_V6,
    SCHEMA_V7,
    SCHEMA_V8,
    SCHEMA_V9,
    SCHEMA_V10,
    SCHEMA_V11,
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
    # No triggers: a cache is not history. See the note above `SCHEMA_V6`.
    SCHEMA_V6,
    # Nor here, for the same reason. See the note above `SCHEMA_V7`.
    SCHEMA_V7,
    # One nullable column on an existing table. No trigger: annotations are the one thing here a
    # person is meant to be able to revise.
    SCHEMA_V8,
    # Five more of them, for the same reason and on the same terms.
    SCHEMA_V9,
    # Two tables for the person's own vocabulary. No trigger, for the third time and the same
    # reason: a tag is a thing somebody is meant to be able to take back off a house.
    SCHEMA_V10,
    # What a long operation is doing while it is doing it. A forward-only trigger, the same one
    # `runs` has, because a pass row is a lifecycle. No append-only trigger on the lines: they are
    # the one operational table here, and the note above `SCHEMA_V11` says why that is safe.
    SCHEMA_V11,
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
