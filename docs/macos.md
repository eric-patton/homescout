# HomeScout on a Mac

HomeScout can run natively on Apple Silicon with Python 3.13. The database and its workspace move
together; the Windows virtual environment does not. Keep the application bound to loopback and use
Tailscale Serve for other devices, as described in [Tailscale access](tailscale.md).

## Runtime and workspace

Install uv, clone the repository, and install its locked dependencies:

```sh
git clone https://github.com/eric-patton/homescout.git /Users/eric/repos/homescout
cd /Users/eric/repos/homescout
uv sync --locked --dev
```

Use `/Users/eric/HomeScout/homescout.db` as HOMESCOUT_DB. When transferring an existing workspace,
use [the verified SQLite backup procedure](backup-and-restore.md). Do not copy the live database
without its WAL, and do not overwrite a running Mac database. Transfer searches, templates, photos,
exports, cached map data, and backups alongside the verified snapshot. Compare checksums before
starting HomeScout. A copied workspace includes the loaded FCC block index, enrichment, annotations,
assessment results, merge decisions, and immutable listing history in its database.

Place configuration in `/Users/eric/HomeScout/.env`, readable only by the account running HomeScout
(`chmod 600`). A Windows user's environment variables do not move with that file. Transfer any
needed GMAIL_ADDRESS, GMAIL_APP_PASSWORD, HOMESCOUT_FCC_TOKEN, OPENAI_API_KEY, and other configured
HomeScout variables without printing credentials or placing them in command arguments. Use:

```text
HOMESCOUT_PORT=47823
HOMESCOUT_ALLOWED_HOSTS=mac.tail9a8857.ts.net,mac.tail9a8857.ts.net:10000
```

The names above are this installation's names; substitute your own Tailscale DNS name for another
Mac. HOMESCOUT_DB must be supplied to the process or as `--db`, because it selects where the .env
file itself is found. Generated jobs set it explicitly. Existing Windows photo paths are resolved
on macOS without changing their stored records.

## Startup and the nightly job

Generate the files as the ordinary workspace owner:

```sh
cd /Users/eric/repos/homescout
.venv/bin/python scripts/macos_launchd.py \
  --user eric --user-home /Users/eric \
  --workspace /Users/eric/HomeScout \
  --executable /Users/eric/repos/homescout/.venv/bin/homescout \
  --output /Users/eric/HomeScout/launchd
```

This prepares five files and installs no jobs:

- `net.homescout.interface.plist`: starts the loopback interface at boot and restarts it if it exits.
- `net.homescout.nightly.plist`: invokes the nightly wrapper at 03:00 in the Mac's local timezone.
- `serve.sh`: sets the interface's process file limit and starts the existing serve command.
- `nightly.sh`: runs `homescout run --all --json --deliver`, then `homescout enrich --json`, and
  returns a nonzero status if either step fails. Enrichment still runs after a degraded search.
- `install.sh`: installs only these two jobs, after refusing to restart an interface reporting work
  under way. It removes temporary user jobs with these same two labels, if present.

Install when the Mac is idle:

```sh
sudo /bin/bash /Users/eric/HomeScout/launchd/install.sh
```

The installer places the two plists in `/Library/LaunchDaemons`, owned by root. Both processes run
as `eric`, not root. No credential appears in a plist, argument, or generated script. This system
installation is what starts HomeScout before a desktop login. A temporary LaunchAgent can be used
to check the interface while awaiting administrator authentication, but it requires a logged-in
session and is not equivalent to the final boot setup.

The nightly job has no KeepAlive or RunAtLoad setting: it exits after each run and does not restart
into a loop or send a digest when the job is merely loaded. The interface is independent of it.
Both shell wrappers allow 4096 open files in their own process without changing host-wide kernel
limits. The Mac's default of 256 was exhausted by the complete test suite; run macOS validation with
`ulimit -n 4096` to match the jobs' runtime limit.

## Tailscale and verification

Configure Tailscale Serve on the Mac, after checking for existing routes:

```sh
/opt/homebrew/bin/tailscale serve status
/opt/homebrew/bin/tailscale serve --bg --https=10000 http://127.0.0.1:47823
```

This installation's address is `https://mac.tail9a8857.ts.net:10000/`. Keep Serve tailnet-only.
Check this address from another device, including search results, map areas, and saved photographs.
The old Windows machine name does not automatically point to the Mac.

Check the two system jobs and their logs:

```sh
launchctl print system/net.homescout.interface
launchctl print system/net.homescout.nightly
tail -40 /Users/eric/HomeScout/serve.err
tail -40 /Users/eric/HomeScout/nightly.log
tail -40 /Users/eric/HomeScout/nightly.err
```

Test the exact nightly wrapper while no other Mac run is active:

```sh
/bin/bash /Users/eric/HomeScout/launchd/nightly.sh
```

Confirm each source's status, enrichment outcomes, a written digest, and a recorded email outcome.
The current command line also returns 3 when `run --all` deliberately skips an archived or paused
search. Read the `skipped` entries in its JSON before treating that status as an execution failure;
successful active searches and their delivery are still recorded. The wrapper retains this result.
An unchanged run suppresses email by design. A verification email can be sent separately to the
configured recipient to confirm SMTP authentication and delivery. A manual run proves the workflow;
job registration proves the boot and calendar configuration. A reboot or the next 03:00 execution
provides the remaining live startup/schedule observation.

During migration, leave Windows available until Mac verification succeeds. The two databases are
independent snapshots, not synchronized. Use one machine for edits. Before making the Mac primary,
check whether any Windows annotations or search definitions changed after the snapshot; transfer
those changes deliberately instead of overwriting a Mac database that already recorded new runs.
Leave only one nightly schedule active once verification is complete to avoid duplicate emails.

## Removal and rollback

Stop only the two HomeScout jobs and remove their configuration:

```sh
sudo launchctl bootout system/net.homescout.nightly
sudo launchctl bootout system/net.homescout.interface
sudo rm /Library/LaunchDaemons/net.homescout.nightly.plist
sudo rm /Library/LaunchDaemons/net.homescout.interface.plist
/opt/homebrew/bin/tailscale serve --https=10000 off
```

These commands preserve the workspace and repository and do not change other Tailscale routes.
If Windows is still available, use its original address and jobs. If the Mac has received new notes
or other user edits, retain those before reverting to an older Windows snapshot.
