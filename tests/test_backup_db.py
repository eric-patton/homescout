"""A backup of an active WAL database includes committed data and opens independently."""

from __future__ import annotations

import runpy
import sqlite3
from pathlib import Path

import pytest


def test_live_wal_backup_is_verified_and_does_not_overwrite(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "backup_db.py"
    backup = runpy.run_path(str(script))["backup"]
    source = tmp_path / "active.db"
    target = tmp_path / "backup.db"
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE notes (message TEXT NOT NULL)")
        writer.execute("INSERT INTO notes VALUES ('committed in WAL')")
        writer.commit()
        backup(source, target)
    with sqlite3.connect(target) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT message FROM notes").fetchone()[0] == "committed in WAL"
    with pytest.raises(ValueError, match="new file"):
        backup(source, target)
