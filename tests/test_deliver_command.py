"""An unattended invocation, end to end, and the things it must never do.

These drive the real argument parser, the real run loop and the real delivery pass, with a mail
server that keeps the message. What is being checked is the contract a Task Scheduler entry is
built on: the flag, the file, the exit code, and the fact that nothing is left running afterwards.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cli_fakes import FakeSource, invoke, row
from deliver_fakes import FakeTransport, environment, sending
from homescout.claim import claim_run
from homescout.cli.main import build_parser
from searches_fakes import write

DOCUMENTATION = Path(__file__).resolve().parents[1] / "docs" / "scheduling.md"


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A saved search on disk, a configured mail account, and nothing else."""
    write(
        tmp_path / "searches",
        "portales",
        text='name: portales\nareas:\n  - {type: zip, value: "88130"}\nsources: [fake]\n',
    )
    for key, value in environment().items():
        monkeypatch.setenv(key, value)
    return tmp_path


@contextmanager
def registered(source: FakeSource) -> Iterator[FakeSource]:
    """Put one source in the real registry, the way an installation has one.

    The saved search comes from a real file through the real catalog, so what these tests drive is
    the wiring a scheduled task actually reaches.
    """
    from homescout.sources import register, unregister

    register("fake", lambda _session, held=source: held, replace=True)
    try:
        yield source
    finally:
        unregister("fake")


def unattended(tmp_path: Path, rows, *args, transport=None, **kwargs):
    """One scheduled invocation, with the real command line."""
    db = tmp_path / "homescout.db"
    with sending(transport) as mail, registered(FakeSource(rows=rows, **kwargs)):
        code, out, err = invoke(["run", "--all", "--json", "--deliver", *args], db=db)
    return code, out, err, mail


def test_a_scheduled_invocation_runs_everything_and_delivers_both(installed: Path) -> None:
    """feat-012/AC-1, feat-012/AC-2: no interaction, no prompt, both reports."""
    code, out, err, mail = unattended(installed, [row("a"), row("b")])

    assert code == 0, err
    answer = json.loads(out)
    assert [entry["name"] for entry in answer["searches"]] == ["portales"]
    assert answer["delivery"]["moved"] == 2
    channels = {found["channel"]: found["outcome"] for found in answer["delivery"]["channels"]}
    assert channels == {"digest": "written", "email": "sent"}
    assert (installed / "digest.json").exists()
    assert len(mail.sent) == 1


def test_the_digest_file_is_the_run_rather_than_an_account_of_delivering_it(
    installed: Path,
) -> None:
    """feat-012/AC-2: a file cannot record whether it was written.

    The invocation's own answer carries the delivery section, because that is a different question
    from what the run found.
    """
    _, out, _, _ = unattended(installed, [row("a")])

    written = json.loads((installed / "digest.json").read_text(encoding="utf-8"))
    printed = json.loads(out)

    assert "delivery" not in written
    assert "delivery" in printed
    assert written["searches"] == printed["searches"]


def test_a_run_without_the_flag_delivers_nothing(installed: Path) -> None:
    """feat-012/AC-2: a person running one search at a terminal does not email themselves.

    Delivery is asked for rather than inferred from a configured mail account, so the scheduler
    entry says what it does and an interactive run stays quiet.
    """
    db = installed / "homescout.db"
    with sending() as mail, registered(FakeSource(rows=[row("a")])):
        code, out, err = invoke(["run", "--all", "--json"], db=db)

    assert code == 0, err
    assert mail.sent == []
    assert not (installed / "digest.json").exists()
    assert "delivery" not in json.loads(out)


def test_an_unchanged_night_writes_the_file_and_sends_nothing(installed: Path) -> None:
    """feat-012/AC-3: and it still exits successfully, because nothing went wrong."""
    unattended(installed, [row("a")])
    code, out, err, mail = unattended(installed, [row("a")])

    assert code == 0, err
    assert mail.sent == []
    channels = {c["channel"]: c["outcome"] for c in json.loads(out)["delivery"]["channels"]}
    assert channels["email"] == "suppressed"
    assert channels["digest"] == "written"


def test_a_failing_source_is_degraded_and_still_delivers(installed: Path) -> None:
    """feat-012/AC-8: the exit code reports the run as degraded, and the digest still lands."""
    code, out, err, _ = unattended(
        installed, [row("a")], outcome="failed", detail="the service is down"
    )

    assert code == 1, err
    answer = json.loads(out)
    assert answer["searches"][0]["sources"][0]["outcome"] == "failed"
    assert (installed / "digest.json").exists()


def test_a_refused_message_is_degraded_and_never_worse(installed: Path) -> None:
    """feat-012/AC-10: the run's results are complete and stored, so the code must not say error.

    What failed is a report about the night, not the night.
    """
    code, out, err, _ = unattended(
        installed, [row("a")], transport=FakeTransport(fails="550 mailbox unavailable")
    )

    assert code == 1, err
    channels = {c["channel"]: c for c in json.loads(out)["delivery"]["channels"]}
    assert channels["email"]["outcome"] == "failed"
    assert channels["digest"]["outcome"] == "written"
    assert (installed / "digest.json").exists()


def test_no_mail_account_is_not_a_failure(installed: Path, monkeypatch) -> None:
    """feat-012/AC-11: an installation without email runs, writes the file, and exits zero."""
    for key in environment():
        monkeypatch.delenv(key, raising=False)

    code, out, err, mail = unattended(installed, [row("a")])

    assert code == 0, err
    assert mail.sent == []
    channels = {c["channel"]: c for c in json.loads(out)["delivery"]["channels"]}
    assert channels["email"]["outcome"] == "skipped"
    assert "HOMESCOUT_SMTP_HOST" in (channels["email"]["detail"] or "")


def test_a_configuration_mistake_is_reported_before_anything_is_fetched(
    installed: Path, monkeypatch
) -> None:
    """feat-012/AC-9: invalid input, in the first second, with nothing run.

    The alternative is a task that fetches all night and then discovers it has nobody to tell.
    """
    monkeypatch.delenv("HOMESCOUT_MAIL_TO")
    source = FakeSource(rows=[row("a")])

    with sending(), registered(source):
        code, _, err = invoke(
            ["run", "--all", "--json", "--deliver"], db=installed / "homescout.db"
        )

    assert code == 2
    assert "HOMESCOUT_MAIL_TO" in err
    assert source.queries == [], "nothing was fetched"


def test_a_digest_path_with_no_directory_is_refused_before_the_run(
    installed: Path, monkeypatch
) -> None:
    """feat-012/AC-2, and the spec's edge case: the scheduler records a failure, not a success."""
    monkeypatch.setenv("HOMESCOUT_DIGEST_PATH", str(installed / "nowhere" / "digest.json"))
    source = FakeSource(rows=[row("a")])

    with sending(), registered(source):
        code, _, err = invoke(
            ["run", "--all", "--json", "--deliver"], db=installed / "homescout.db"
        )

    assert code == 2
    assert "nowhere" in err and "nothing has been run" in err
    assert source.queries == []


def test_two_overlapping_runs_do_not_interleave_and_the_second_mails_nothing(
    installed: Path,
) -> None:
    """feat-012/AC-14: the claim the run loop already holds, seen from a scheduled invocation.

    The second declines rather than waiting: a scheduled task reads the precondition code and tries
    again on its next tick instead of queueing behind a manual run somebody left open, and then
    fetching everything twice.
    """
    with claim_run(installed, "portales"):
        code, out, err, mail = unattended(installed, [row("a")])

    assert code == 3, err
    assert mail.sent == [], "a declined run reported nothing"
    answer = json.loads(out)
    assert answer["skipped"][0]["reason"] == "in progress"
    assert answer["searches"] == []


def test_a_run_after_a_missed_night_compares_against_the_last_completed_run(
    installed: Path,
) -> None:
    """feat-012, the sleeping-machine edge case: the interval is since the last run, not a day.

    A machine asleep at three in the morning misses that run entirely. Nothing is lost, because the
    comparison's baseline is the previous completed run, so a weekend's changes arrive together.
    """
    unattended(installed, [row("a", price=400_000)])
    # Two nights nobody ran. The next run is the next line, and it must see both moves at once.
    _, out, _, mail = unattended(installed, [row("a", price=350_000), row("b")])

    answer = json.loads(out)
    entry = answer["searches"][0]
    assert entry["counts"]["new"] == 1 and entry["counts"]["changed"] == 1
    assert entry["price_changes"][0]["price_change"]["before"] == 400_000
    assert len(mail.sent) == 1, "one email covering the whole interval"


def test_nothing_reads_from_the_console(installed: Path) -> None:
    """feat-012/AC-1: no prompt, structurally.

    A scheduled task has no console to answer one with, so a prompt anywhere in this package would
    hang until somebody noticed the task never finished.
    """
    import homescout

    source = Path(homescout.__file__).parent
    for path in source.rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        assert not re.search(r"\binput\s*\(", body), path
        assert "getpass" not in body, path


def test_nothing_runs_between_runs(installed: Path) -> None:
    """feat-012/AC-13: no daemon, no service, no always-on process.

    Two checks, because either one alone is weak. Nothing in the package imports a scheduler, a
    timer or an event loop, and a full delivering invocation leaves the thread it started with and
    no other. The drift this is really about is somebody adding a `--watch` flag in two years.
    """
    import homescout

    forbidden = ("import sched", "from sched", "threading.Timer", "import asyncio",
                 "from asyncio", "import apscheduler", "import schedule")
    source = Path(homescout.__file__).parent
    for path in source.rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in body, f"{path} imports {name}"

    before = set(threading.enumerate())
    unattended(installed, [row("a")])

    assert set(threading.enumerate()) == before, "an invocation left something running"


def test_the_documented_invocation_is_one_this_tool_accepts() -> None:
    """feat-012/AC-12: documentation that stops parsing is a failing test, not a discovery at 3am.

    Whether the document can be *followed without guessing* is a human judgment nobody has made
    yet. What is checked here is narrower and worth having: every command it tells you to type is
    one that exists.
    """
    text = DOCUMENTATION.read_text(encoding="utf-8")
    parser = build_parser()

    typed = [
        found.strip()
        for found in (
            *re.findall(r'homescout\.exe ([a-z][^"\n]*)"', text),
            *re.findall(r"^homescout ([a-z].*)$", text, re.M),
        )
        if found.strip()
    ]
    assert typed, "the document shows at least one invocation"
    for line in typed:
        parser.parse_args(line.split())


def test_the_documentation_says_what_it_creates_and_how_to_undo_it() -> None:
    """feat-012/AC-12: the criterion's own words, checked as the three things they require."""
    text = DOCUMENTATION.read_text(encoding="utf-8")

    assert "HomeScout nightly" in text, "the exact name of the task it creates"
    assert "schtasks /Create" in text
    assert 'schtasks /Delete /TN "HomeScout nightly" /F' in text, "and how to remove it"
    assert "HOMESCOUT_DB" in text and "setx" in text, "the environment problem"
    assert "C:\\Windows\\System32" in text, "and why a task that works by hand fails on schedule"
