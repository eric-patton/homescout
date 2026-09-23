"""Create and verify a consistent backup of a live HomeScout SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path


def backup(source: Path, output: Path) -> None:
    source = source.resolve(strict=True)
    output = output.resolve()
    if source == output or output.exists():
        raise ValueError("Backup destination must be a new file outside the source path")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original,
            closing(sqlite3.connect(temporary)) as copied,
        ):
            original.backup(copied, pages=500, sleep=0.1)
            result = copied.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise RuntimeError(f"Backup integrity check failed: {result}")
        temporary.rename(output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    backup(args.source, args.output)
    print(f"Verified backup: {args.output}")


if __name__ == "__main__":
    main()
