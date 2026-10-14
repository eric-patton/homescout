"""The nightly command, restart policy, account and credentials in macOS startup jobs."""

from __future__ import annotations

import importlib.util
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from homescout.cli.main import build_parser


def renderer():
    script = Path(__file__).resolve().parents[1] / "scripts" / "macos_launchd.py"
    spec = importlib.util.spec_from_file_location("macos_launchd", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_macos_jobs_run_as_the_owner_without_embedding_credentials(tmp_path: Path) -> None:
    """feat-012/AC-15: boot supervision and scheduling use absolute paths and no secret."""
    module = renderer()
    workspace = "/Users/eric/Home Scout"
    executable = "/Users/eric/repos/Home Scout/.venv/bin/homescout"
    module.render(
        tmp_path,
        user="eric",
        user_home="/Users/eric",
        workspace=workspace,
        executable=executable,
    )
    jobs = {
        name: plistlib.loads((tmp_path / f"net.homescout.{name}.plist").read_bytes())
        for name in ("interface", "nightly")
    }
    interface, nightly = jobs["interface"], jobs["nightly"]
    assert interface["RunAtLoad"] and interface["KeepAlive"]
    assert interface["ProgramArguments"] == ["/bin/bash", workspace + "/launchd/serve.sh"]
    assert nightly["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert "KeepAlive" not in nightly and "RunAtLoad" not in nightly
    for job in jobs.values():
        assert job["UserName"] == "eric"
        assert job["WorkingDirectory"] == workspace
        assert job["EnvironmentVariables"]["HOMESCOUT_DB"] == workspace + "/homescout.db"
        assert set(job["EnvironmentVariables"]) == {"HOMESCOUT_DB", "PATH"}
        # macOS system-domain resource keys can also change host-wide limits.
        assert "SoftResourceLimits" not in job and "HardResourceLimits" not in job

    serve_lines = (tmp_path / "serve.sh").read_text().splitlines()
    assert "ulimit -n 4096" in serve_lines
    assert shlex.split(serve_lines[-1]) == ["exec", executable, "serve"]

    commands = []
    for line in (tmp_path / "nightly.sh").read_text().splitlines():
        if not line.startswith(shlex.quote(executable) + " "):
            continue
        tokens = shlex.split(line)
        if tokens and tokens[0] == executable:
            arguments = tokens[1 : tokens.index("||")]
            commands.append(build_parser().parse_args(arguments))
    assert [command.command for command in commands] == ["run", "enrich"]
    assert commands[0].all and commands[0].deliver
    assert commands[1].json


@pytest.mark.skipif(sys.platform == "win32", reason="executes the macOS shell wrapper")
@pytest.mark.parametrize(
    "run_code,enrich_code,expected", [(0, 0, 0), (1, 0, 1), (0, 3, 3), (2, 1, 2)]
)
def test_nightly_attempts_both_stages_and_reports_a_failure(
    tmp_path: Path, run_code: int, enrich_code: int, expected: int
) -> None:
    """feat-012/AC-15: degraded search still enriches, and neither stage's failure is hidden."""
    calls = tmp_path / "calls.txt"
    executable = tmp_path / "fake homescout"
    executable.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$1" >> {shlex.quote(str(calls))}\n'
        f'if [ "$1" = run ]; then exit {run_code}; fi\n'
        f"exit {enrich_code}\n"
    )
    executable.chmod(0o700)
    output = tmp_path / "workspace" / "launchd"
    renderer().render(
        output,
        user="eric",
        user_home="/Users/eric",
        workspace=str(output.parent),
        executable=str(executable),
    )
    result = subprocess.run(["/bin/bash", str(output / "nightly.sh")], capture_output=True)
    assert result.returncode == expected
    assert calls.read_text().splitlines() == ["run", "enrich"]
