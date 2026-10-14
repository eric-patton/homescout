"""Render macOS startup jobs without installing them or copying any credential."""

from __future__ import annotations

import argparse
import plistlib
import re
import shlex
from pathlib import Path, PurePosixPath
from textwrap import dedent

INTERFACE = "net.homescout.interface"
NIGHTLY = "net.homescout.nightly"


def render(
    output: Path, *, user: str, workspace: str, executable: str, user_home: str
) -> None:
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise ValueError("Use the macOS account's short name")
    for value in (workspace, executable, user_home):
        if not value.startswith("/") or "\n" in value or "\r" in value:
            raise ValueError("macOS paths must be absolute and contain no line breaks")
    root = PurePosixPath(workspace)
    jobs = root / "launchd"
    home = PurePosixPath(user_home)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    common = {
        "UserName": user,
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "HOMESCOUT_DB": str(root / "homescout.db"),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }
    interface = {
        **common,
        "Label": INTERFACE,
        "ProgramArguments": ["/bin/bash", str(jobs / "serve.sh")],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ExitTimeOut": 150,
        "StandardOutPath": str(root / "serve.out"),
        "StandardErrorPath": str(root / "serve.err"),
    }
    nightly = {
        **common,
        "Label": NIGHTLY,
        "ProgramArguments": ["/bin/bash", str(jobs / "nightly.sh")],
        "StartCalendarInterval": {"Hour": 3, "Minute": 0},
        "StandardOutPath": str(root / "nightly.log"),
        "StandardErrorPath": str(root / "nightly.err"),
    }
    for label, job in ((INTERFACE, interface), (NIGHTLY, nightly)):
        path = output / f"{label}.plist"
        path.write_bytes(plistlib.dumps(job))
        path.chmod(0o600)

    invocation = shlex.quote(executable)
    serve_script = dedent(f"""\
        #!/bin/bash
        set -eu
        export HOMESCOUT_DB={shlex.quote(str(root / 'homescout.db'))}
        ulimit -n 4096
        printf 'HomeScout open-file limit: %s\\n' "$(ulimit -n)"
        exec {invocation} serve
        """)
    (output / "serve.sh").write_text(serve_script, encoding="utf-8", newline="\n")
    (output / "serve.sh").chmod(0o700)
    nightly_script = dedent(f"""\
        #!/bin/bash
        set -u
        export HOMESCOUT_DB={shlex.quote(str(root / 'homescout.db'))}
        ulimit -n 4096
        printf 'Nightly started: %s\\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        run_status=0
        {invocation} run --all --json --deliver || run_status=$?
        enrich_status=0
        {invocation} enrich --json || enrich_status=$?
        printf 'Nightly finished: run=%s enrich=%s at %s\\n' \\
            "$run_status" "$enrich_status" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        if [ "$run_status" -ne 0 ]; then exit "$run_status"; fi
        exit "$enrich_status"
        """)
    (output / "nightly.sh").write_text(nightly_script, encoding="utf-8", newline="\n")
    (output / "nightly.sh").chmod(0o700)

    # The installer changes only these two jobs. Their processes run as the named ordinary user.
    installer = dedent(f"""\
        #!/bin/bash
        set -euo pipefail
        if [ "$(id -u)" -ne 0 ]; then
            echo 'Run this prepared installer with sudo to enable startup before login.' >&2
            exit 1
        fi
        account={shlex.quote(user)}
        account_uid=$(/usr/bin/id -u "$account")
        source_dir={shlex.quote(str(jobs))}
        user_agents={shlex.quote(str(home / 'Library/LaunchAgents'))}
        for label in {INTERFACE} {NIGHTLY}; do
            /usr/bin/plutil -lint "$source_dir/$label.plist"
        done
        # Refuse to restart the interface during a long operation.
        if /usr/bin/curl -fsS --max-time 10 \\
            -H 'Origin: http://127.0.0.1:47823' -H 'X-Homescout: 1' \\
            http://127.0.0.1:47823/api/under-way > "$source_dir/install-status.json"; then
            /usr/bin/python3 -c '
        import json, sys
        d = json.load(open(sys.argv[1]))
        if d.get("passes"):
            raise SystemExit("HomeScout is busy. Retry after it finishes.")
        ' "$source_dir/install-status.json"
        fi
        for label in {INTERFACE} {NIGHTLY}; do
            /bin/launchctl bootout "gui/$account_uid/$label" 2>/dev/null || true
            /bin/launchctl bootout "system/$label" 2>/dev/null || true
            /bin/rm -f "$user_agents/$label.plist"
            /usr/bin/install -o root -g wheel -m 644 \\
                "$source_dir/$label.plist" "/Library/LaunchDaemons/$label.plist"
            /bin/launchctl enable "system/$label"
            /bin/launchctl bootstrap system "/Library/LaunchDaemons/$label.plist"
        done
        /bin/launchctl print system/{INTERFACE} | /usr/bin/sed -n '1,25p'
        /bin/launchctl print system/{NIGHTLY} | /usr/bin/sed -n '1,25p'
        echo 'HomeScout startup and the 03:00 nightly job are installed.'
        """)
    (output / "install.sh").write_text(installer, encoding="utf-8", newline="\n")
    (output / "install.sh").chmod(0o700)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--user-home", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(
        args.output,
        user=args.user,
        workspace=args.workspace,
        executable=args.executable,
        user_home=args.user_home,
    )
    print(f"Prepared startup jobs in {args.output}; nothing has been installed.")


if __name__ == "__main__":
    main()
