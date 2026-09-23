# Backing up and restoring the workspace

The database uses SQLite WAL mode. Copying `homescout.db` alone while the server is active can omit
committed changes in its WAL file. Use the online backup script from the repository instead.

```powershell
cd C:\repos\homescout
$stamp = Get-Date -Format yyyyMMdd-HHmmss
uv run python scripts/backup_db.py "$env:USERPROFILE\HomeScout\homescout.db" "$env:USERPROFILE\HomeScout\backups\homescout-$stamp.db"
```

The script refuses to overwrite a backup, copies a consistent snapshot, and runs SQLite's full
integrity check before publishing the file. Keep a copy outside this machine as well. Search
definitions and local images are separate files under the workspace and need their own backup.

To restore, stop the `HomeScout interface` scheduled task and the running HomeScout server first.
Preserve the current database and its `-wal` and `-shm` companions together in a separate directory.
Copy the verified backup to `HomeScout\homescout.db`, then start the scheduled task. Confirm
the local interface opens and compare counts and recent runs before deleting any retained files.
Never copy a backup over a database while its server is running.
