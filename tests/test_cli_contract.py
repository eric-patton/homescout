"""The machine contract: streams, codes, and the surface itself.

This is the part an unattended caller depends on and cannot see change. Everything here is asserted
through `main([...])` with both streams captured, because that is exactly what a scheduled task
gets.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli_fakes import FakeSource, invoke, row, search, wired
from homescout.cli.codes import ExitCode, code_for, worst_of
from homescout.cli.main import build_parser
from homescout.errors import InvalidInput, PreconditionNotMet

CREDENTIAL_WORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api-key",
    "apikey",
    "api_key",
    "credential",
    "smtp-pass",
    "auth",
)


def options_of(parser, seen=None):
    """Every option string the parser accepts, at every level."""
    seen = seen if seen is not None else set()
    for action in parser._actions:
        seen.update(action.option_strings)
        for _name, sub in _choices(action):
            options_of(sub, seen)
    return seen


def _choices(action):
    # `choices` is a mapping of names to parsers on a subcommand action, and a plain sequence of
    # allowed values on an ordinary option. Only the first kind has parsers to walk into.
    found = getattr(action, "choices", None)
    if not isinstance(found, dict):
        return
    for name, sub in found.items():
        if hasattr(sub, "_actions"):
            yield name, sub


def subcommands_of(parser):
    for action in parser._actions:
        yield from _choices(action)


# -- exit codes ------------------------------------------------------------


def test_the_five_codes_are_fixed() -> None:
    """feat-003/AC-3: a scheduled task decides from the number alone, so the numbers are the API."""
    assert int(ExitCode.SUCCESS) == 0
    assert int(ExitCode.DEGRADED) == 1
    assert int(ExitCode.INVALID_INPUT) == 2
    assert int(ExitCode.PRECONDITION) == 3
    assert int(ExitCode.INTERNAL_ERROR) == 4
    assert len(ExitCode) == 5


def test_each_kind_of_error_maps_to_one_code() -> None:
    """feat-003/AC-3: the mapping lives in one place, and no command body chooses a number."""
    assert code_for(InvalidInput("no")) is ExitCode.INVALID_INPUT
    assert code_for(PreconditionNotMet("not yet")) is ExitCode.PRECONDITION
    assert code_for(RuntimeError("surprise")) is ExitCode.INTERNAL_ERROR


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ((), ExitCode.SUCCESS),
        ((ExitCode.SUCCESS, ExitCode.SUCCESS), ExitCode.SUCCESS),
        ((ExitCode.SUCCESS, ExitCode.DEGRADED), ExitCode.DEGRADED),
        ((ExitCode.DEGRADED, ExitCode.INVALID_INPUT), ExitCode.INVALID_INPUT),
        ((ExitCode.INVALID_INPUT, ExitCode.INTERNAL_ERROR), ExitCode.INTERNAL_ERROR),
    ],
)
def test_one_invocation_settles_on_the_worst_thing_that_happened(given, expected) -> None:
    """feat-003/AC-3: a file a human has to edit beats a source that had a bad night."""
    assert worst_of(given) is expected


def test_a_usage_error_is_invalid_input(db_path: Path) -> None:
    """feat-003/AC-3: a bad flag and a bad name are the same class of problem."""
    code, out, err = invoke(["run", "--nonsense"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert out == ""
    assert "unrecognized arguments" in err or "unrecognized" in err


# -- streams ---------------------------------------------------------------


def test_machine_output_is_the_whole_of_the_primary_stream(db_path: Path) -> None:
    """feat-003/AC-1, feat-003/AC-2: it parses with no preprocessing, because it is alone there."""
    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b")])}):
        code, out, err = invoke(["run", "portales", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    document = json.loads(out)
    assert document["kind"] == "run"
    assert document["searches"][0]["counts"]["new"] == 2


def test_progress_goes_to_the_secondary_stream(db_path: Path) -> None:
    """feat-003/AC-2: an unattended caller never has to disentangle the two."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        code, out, err = invoke(["run", "portales", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    json.loads(out)  # would raise if a progress line had landed here
    assert "fake: ok, 1 listings" in err


def test_human_output_is_the_default_and_carries_no_document(db_path: Path) -> None:
    """feat-003/AC-21: the terminal is usable by hand without asking for anything."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        code, out, err = invoke(["run", "portales"], db=db_path)

    assert code == ExitCode.SUCCESS
    assert "portales: 1 matched, 1 new" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_output_survives_characters_outside_ascii(db_path: Path) -> None:
    """feat-003/AC-1: on Windows the console encoding is not UTF-8, and addresses do not care."""
    listing = row("a", address_line="123 Cañón Ridge", city="Española")
    with wired([search()], {"fake": FakeSource(rows=[listing])}):
        code, out, _ = invoke(["run", "portales", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    document = json.loads(out)
    assert document["searches"][0]["new"][0]["address_line"] == "123 Cañón Ridge"
    assert "Cañón" in out, "written as itself rather than escaped"


def test_help_is_readable_even_when_machine_output_was_asked_for(db_path: Path) -> None:
    """feat-003/AC-2: help is a usage request, not a result. There is nothing structured to say."""
    code, out, _ = invoke(["--json", "--help"], db=db_path)

    assert code == 0
    assert "usage: homescout" in out


# -- writing to a file -----------------------------------------------------


def test_the_document_can_be_written_to_a_path(db_path: Path, tmp_path: Path) -> None:
    """feat-003/AC-17: which is how a scheduled task hands it to whatever reads it next."""
    target = tmp_path / "digest.json"
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        code, out, _ = invoke(["run", "portales", "--output", str(target)], db=db_path)

    assert code == ExitCode.SUCCESS
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["searches"][0]["counts"]["new"] == 1
    assert "portales: 1 matched" in out, "the primary stream is still human output"


def test_a_missing_directory_is_reported_before_anything_runs(
    db_path: Path, tmp_path: Path
) -> None:
    """feat-003/AC-17: discovering this after an hour of throttled requests is the failure."""
    source = FakeSource(rows=[row("a")])
    with wired([search()], {"fake": source}):
        code, out, err = invoke(
            ["run", "portales", "--output", str(tmp_path / "nope" / "d.json")], db=db_path
        )

    assert code == ExitCode.INVALID_INPUT
    assert "no directory" in err.lower()
    assert source.queries == [], "nothing was fetched"
    assert out == ""


def test_a_write_that_fails_is_reported_without_changing_the_primary_stream(
    db_path: Path, tmp_path: Path
) -> None:
    """feat-003/AC-17: a command asked for readable output does not suddenly emit a document."""
    blocked = tmp_path / "taken"
    blocked.mkdir()  # a directory where a file is wanted: the write fails, the parent exists

    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        code, out, err = invoke(["run", "portales", "--output", str(blocked)], db=db_path)

    assert code == ExitCode.INTERNAL_ERROR
    assert "could not write" in err.lower()
    assert "portales: 1 matched" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


# -- the surface itself ----------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        ["searches", "list"],
        ["searches", "show", "portales"],
        ["searches", "validate", "portales"],
        ["searches", "create", "fresh"],
        ["searches", "edit", "portales", "--set", "sources=fake"],
        ["run", "portales"],
        ["run", "--all"],
        ["changes", "portales"],
        ["annotate", "nobody", "--notes", "x"],
        ["matches", "list"],
        ["matches", "resolve", "nothing", "--same"],
        ["enrich"],
        ["enrich", "--stale", "--search", "portales"],
        ["export"],
        ["export", "--search", "portales"],
        ["show", "nobody"],
        ["areas"],
    ],
)
def test_every_command_in_the_brief_is_reachable(command, db_path: Path) -> None:
    """feat-003/AC-20: the surface is the contract, so all of it exists from the first release.

    Every one of them now has a body, which is what this criterion describes arriving at: a command
    is reachable from the first release and grows one later, without an automated caller having to
    keep a version matrix. `serve` is absent from this list for one reason only: it blocks until it
    is stopped, which is what a server does.
    """
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        code, out, err = invoke([*command, "--json"], db=db_path)

    assert code in {int(c) for c in ExitCode}
    assert code != ExitCode.INTERNAL_ERROR, err


def test_every_command_the_parser_knows_is_built() -> None:
    """feat-003/AC-20, arrived at: every command in the surface now has a body.

    Enrichment used to report itself unbuilt, then export, then the browser interface. This
    criterion describes exactly that happening: a command is reachable from the first release and
    grows a body later, without an automated caller having to know which release it was. The check
    that remains is that none of them still reports itself unbuilt.
    """
    from homescout import api

    unbuilt = [
        name
        for name, value in vars(api).items()
        if callable(value)
        and getattr(value, "__module__", "") == "homescout.api"
        and "NotYetBuilt" in (value.__code__.co_names if hasattr(value, "__code__") else ())
    ]
    assert unbuilt == []


# -- pacing ----------------------------------------------------------------


def test_the_delay_between_requests_can_be_set(db_path: Path) -> None:
    """feat-003/AC-30: the constitution requires a configurable delay, so it is reachable."""
    from homescout import api

    workspace = api.open_workspace(db_path, delay=9.0)
    try:
        assert workspace._paced_session()._config.policy_for("realtor").delay == 9.0
    finally:
        workspace.close()


@pytest.mark.parametrize("delay", ["0.1", "600"])
def test_a_delay_outside_the_permitted_range_is_refused(delay, db_path: Path) -> None:
    """feat-003/AC-30: refused before anything is fetched, and by the source layer's own rule."""
    source = FakeSource(rows=[row("a")])
    with wired([search()], {"fake": source}):
        code, out, err = invoke(["run", "portales", "--delay", delay], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "delay" in err.lower()
    assert source.queries == []


def test_a_delay_that_is_not_a_number_is_invalid_input(db_path: Path) -> None:
    """feat-003/AC-30: the same answer, from the parser rather than from the policy."""
    code, _, err = invoke(["run", "portales", "--delay", "slowly"], db=db_path)

    assert code == ExitCode.INVALID_INPUT


# -- secrets ---------------------------------------------------------------


def test_no_option_anywhere_accepts_a_credential() -> None:
    """feat-003/AC-31: arguments are visible to other processes and land in scheduler config.

    Checked rather than trusted, because the option that breaks this rule will be added by a future
    feature in a hurry, and Windows Task Scheduler stores a command line in plain text.
    """
    parser = build_parser()
    offending = [
        option
        for option in options_of(parser)
        if any(word in option.lower() for word in CREDENTIAL_WORDS)
    ]

    assert offending == []


def test_the_local_server_has_no_way_to_leave_this_machine() -> None:
    """feat-003/AC-31: the constitution binds the server to localhost, so no option can move it."""
    commands = dict(subcommands_of(build_parser()))
    serve = options_of(commands["serve"])

    assert not {"--host", "--bind", "--address", "--public"} & serve


# -- startup ---------------------------------------------------------------


def test_starting_up_does_not_load_the_network_library() -> None:
    """feat-003/AC-3 supporting requirement: a scheduled task's time goes to pacing, not imports.

    One eager import is all it would take. `requests` costs more to load than everything else this
    tool imports put together, and a run that fetches nothing should not pay for it.
    """
    source = str(Path(__file__).resolve().parents[1] / "src")
    probe = (
        f"import sys; sys.path.insert(0, {source!r}); "
        "import homescout.cli.main; "
        "print('requests' in sys.modules)"
    )
    started = time.monotonic()
    finished = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    elapsed = time.monotonic() - started

    assert finished.stdout.strip() == "False"
    assert elapsed < 3.0, f"importing the command line took {elapsed:.1f}s"


def test_the_exit_codes_are_documented_where_someone_will_read_them(db_path: Path) -> None:
    """feat-003/AC-3, gap-001: stable is half of it. The other half is written down.

    Somebody writing the Task Scheduler entry should not have to open the source to learn that 1
    means degraded. Both places are asserted, because the help is what is to hand and the README is
    what gets read first.
    """
    _, help_text, _ = invoke(["--help"], db=db_path)
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")

    for text in (help_text, readme):
        assert "degraded" in text.lower()
        assert "invalid input" in text.lower()
        assert "internal error" in text.lower()
        for code in ExitCode:
            assert str(int(code)) in text


def test_the_precedence_order_accounts_for_every_code() -> None:
    """feat-003/AC-3, gap-003: a code left out of the order falls through to success.

    That is how a run of every saved search which managed none of them once reported that everything
    was fine. The order is asserted to be total so a sixth code cannot be forgotten the same way.
    """
    from homescout.cli.codes import PRECEDENCE

    assert set(PRECEDENCE) == set(ExitCode)
    assert worst_of([ExitCode.PRECONDITION]) is ExitCode.PRECONDITION
    assert worst_of([ExitCode.PRECONDITION, ExitCode.DEGRADED]) is ExitCode.PRECONDITION
    assert worst_of([ExitCode.INVALID_INPUT, ExitCode.PRECONDITION]) is ExitCode.INVALID_INPUT
