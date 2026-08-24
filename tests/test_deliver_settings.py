"""Where a credential may come from, and where it may not.

The rule is a constitution requirement rather than a preference, so these are refusals rather than
absences: it is not enough that nothing currently reads a password from an argument, there has to
be nowhere to put one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deliver_fakes import PASSWORD, env_file, environment
from homescout.deliver import settings as config
from homescout.deliver.settings import MailMisconfigured, load


def test_an_installation_with_nothing_configured_still_has_a_digest_path(tmp_path: Path) -> None:
    """feat-012/AC-11: email is optional, and the file is not.

    Product invariant 9 in this feature's own terms: with no mail account, the tool is fully
    functional and simply sends nothing.
    """
    found = load(tmp_path, {})

    assert found.account is None
    assert found.sends_email is False
    assert found.digest_path == tmp_path / "digest.json"
    assert config.SMTP_HOST in (found.why_no_mail or ""), "it says what to set to turn it on"


def test_the_digest_path_can_be_moved(tmp_path: Path) -> None:
    """feat-012/AC-2: the path a scheduled agent watches is configuration, not an argument."""
    elsewhere = tmp_path / "reports" / "tonight.json"

    found = load(tmp_path, environment(DIGEST_PATH=str(elsewhere)))

    assert found.digest_path == elsewhere


def test_a_complete_account_is_read(tmp_path: Path) -> None:
    """feat-012/AC-9: from the environment, which is the only place it can come from."""
    found = load(tmp_path, environment())

    assert found.sends_email is True
    account = found.account
    assert account is not None
    assert account.host == "smtp.example.invalid"
    assert account.port == 587, "the default for starttls"
    assert account.security == "starttls"
    assert account.recipients == ("me@example.invalid",)
    assert account.password == PASSWORD


def test_an_env_file_beside_the_database_is_read_and_the_environment_beats_it(
    tmp_path: Path,
) -> None:
    """feat-012/AC-9: the constitution names both places, and says which wins.

    A person who exports a variable in the shell they are standing in means it, and a file they
    wrote last month should not quietly win over it.
    """
    env_file(tmp_path, environment(MAIL_TO="from-the-file@example.invalid"))

    from_file = load(tmp_path, {})
    overridden = load(tmp_path, {"HOMESCOUT_MAIL_TO": "from-the-shell@example.invalid"})

    assert from_file.account is not None
    assert from_file.account.recipients == ("from-the-file@example.invalid",)
    assert overridden.account is not None
    assert overridden.account.recipients == ("from-the-shell@example.invalid",)


def test_an_env_file_survives_comments_quotes_and_export(tmp_path: Path) -> None:
    """feat-012/AC-9: because this is what people actually type into one."""
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "# the mail account",
                "",
                'HOMESCOUT_SMTP_HOST="smtp.example.invalid"',
                "export HOMESCOUT_MAIL_FROM='homescout@example.invalid'",
                "HOMESCOUT_MAIL_TO=me@example.invalid , you@example.invalid",
                "not a setting at all",
            ]
        ),
        encoding="utf-8",
    )

    found = load(tmp_path, {})

    assert found.account is not None
    assert found.account.host == "smtp.example.invalid"
    assert found.account.sender == "homescout@example.invalid"
    assert found.account.recipients == ("me@example.invalid", "you@example.invalid")


@pytest.mark.parametrize("missing", ["SMTP_HOST", "MAIL_FROM", "MAIL_TO"])
def test_half_an_account_is_refused_rather_than_ignored(missing: str, tmp_path: Path) -> None:
    """feat-012/AC-9: because it is always somebody who believes they configured email.

    Refused here, which is before a run starts, rather than at send time, which is after a night of
    throttled requests.
    """
    with pytest.raises(MailMisconfigured) as refused:
        load(tmp_path, environment(**{missing: None}))

    assert missing.upper() in str(refused.value)


def test_a_username_without_a_password_is_refused(tmp_path: Path) -> None:
    """feat-012/AC-9: and so is the reverse, which is a copied `.env` with a line deleted."""
    with pytest.raises(MailMisconfigured):
        load(tmp_path, environment(SMTP_PASSWORD=None))
    with pytest.raises(MailMisconfigured):
        load(tmp_path, environment(SMTP_USERNAME=None))


def test_a_recipient_containing_a_line_break_is_refused_at_validation_time(
    tmp_path: Path,
) -> None:
    """feat-012/AC-9: a header value with a newline in it is extra headers nobody wrote.

    `EmailMessage` would refuse it at send time. Refusing it here means it is reported while
    somebody is still looking at a terminal, which is what the spec asks for.
    """
    with pytest.raises(MailMisconfigured, match="line break"):
        load(tmp_path, environment(MAIL_TO="me@example.invalid\nBcc: elsewhere@example.invalid"))


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("SMTP_SECURITY", "whatever-it-takes"),
        ("SMTP_PORT", "not-a-number"),
        ("SMTP_PORT", "70000"),
        ("EMAIL_MAX_NEW", "0"),
    ],
)
def test_a_value_that_cannot_be_what_it_claims_is_refused(
    variable: str, value: str, tmp_path: Path
) -> None:
    """feat-012/AC-9: every one of these is reported before a run rather than during one."""
    with pytest.raises(MailMisconfigured):
        load(tmp_path, environment(**{variable: value}))


def test_the_port_follows_the_security_when_nobody_names_one(tmp_path: Path) -> None:
    for security, port in (("starttls", 587), ("ssl", 465), ("none", 25)):
        found = load(tmp_path, environment(SMTP_SECURITY=security))
        assert found.account is not None
        assert found.account.port == port, security


def test_no_credential_can_be_passed_as_an_argument() -> None:
    """feat-012/AC-9: there is nowhere to put one, which is stronger than nothing reading one.

    Arguments are visible to every other process through the process list, and Windows Task
    Scheduler stores a task's arguments as plain text in its own XML. A password passed as an
    argument is a password written to disk in the clear by the thing that was supposed to keep it.
    """
    from homescout.cli.main import build_parser

    parser = build_parser()
    for attempt in (
        ["run", "--all", "--smtp-password", PASSWORD],
        ["run", "--all", "--password", PASSWORD],
        ["run", "--all", "--smtp-username", "someone"],
    ):
        with pytest.raises(SystemExit) as stopped:
            parser.parse_args(attempt)
        assert stopped.value.code == 2

    text = " ".join(action.option_strings and action.option_strings[0] or "" for action in
                    parser._actions)
    assert "password" not in text.lower()


def test_no_credential_can_be_written_into_a_saved_search(tmp_path: Path) -> None:
    """feat-012/AC-9: and it is a validation problem rather than an ignored key.

    The saved-search validator refuses keys it does not know, so a credential in a definition is
    named with its file and its line rather than silently doing nothing.
    """
    from homescout.search.definition import FileCatalog
    from searches_fakes import write

    write(
        tmp_path / "searches",
        "portales",
        text=(
            "name: portales\n"
            'areas:\n  - {type: zip, value: "88130"}\n'
            "sources: [realtor]\n"
            f"smtp_password: {PASSWORD}\n"
        ),
    )

    problems = FileCatalog(tmp_path / "searches").load("portales").problems()

    assert any("smtp_password" in problem.message for problem in problems)
    assert all(PASSWORD not in problem.message for problem in problems), (
        "and the complaint does not repeat the value back"
    )


def test_the_account_never_prints_its_password() -> None:
    """feat-012/AC-9: a dataclass's own repr would put it in every traceback."""
    from deliver_fakes import account

    shown = repr(account())

    assert PASSWORD not in shown
    assert "<set>" in shown
