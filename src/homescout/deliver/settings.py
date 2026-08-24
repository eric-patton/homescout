"""Where a report goes, and where its credential comes from.

Two rules decide everything in this module, and both are older than this feature.

**A credential comes from the environment or from a file that is never committed, and from nowhere
else.** The constitution says so and the command line's own options already refuse to carry one.
There is no `--smtp-password` here for a reason worth repeating where somebody might be tempted to
add one: arguments are visible to every other process on the machine, and Windows Task Scheduler
stores a task's arguments as plain text in its own XML, so a password passed as an argument is a
password written to disk in the clear by the thing that was supposed to keep it safe.

**Email is optional.** Product invariant 9 says an unconfigured optional component leaves the tool
fully functional, so no mail account at all is a valid installation that writes its digest and sends
nothing. What is *not* valid is half an account: a host with no recipient is somebody who thinks
they configured email and did not, and finding that out at midnight from a scheduled task is the
failure this module refuses up front.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..errors import InvalidInput

#: Where the digest lands. Defaults beside the database for the same reason the database defaults
#: to the working directory: an installation that keeps its own paths is one less thing to get
#: wrong in a scheduler entry, where a mistake is invisible until a night has been lost.
DIGEST_PATH = "HOMESCOUT_DIGEST_PATH"
DEFAULT_DIGEST_NAME = "digest.json"

SMTP_HOST = "HOMESCOUT_SMTP_HOST"
SMTP_PORT = "HOMESCOUT_SMTP_PORT"
SMTP_SECURITY = "HOMESCOUT_SMTP_SECURITY"
SMTP_USERNAME = "HOMESCOUT_SMTP_USERNAME"
SMTP_PASSWORD = "HOMESCOUT_SMTP_PASSWORD"
MAIL_FROM = "HOMESCOUT_MAIL_FROM"
MAIL_TO = "HOMESCOUT_MAIL_TO"
MAX_NEW = "HOMESCOUT_EMAIL_MAX_NEW"

#: Every variable this feature reads, in the order `.env.example` lists them. Named once so the
#: example file, the documentation and the tests cannot drift apart from the code.
VARIABLES: tuple[str, ...] = (
    DIGEST_PATH,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_SECURITY,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    MAIL_FROM,
    MAIL_TO,
    MAX_NEW,
)

#: The three ways to reach a mail server, and their usual ports. `none` is here because a relay on
#: a home network is a real configuration, not because it is ever a fallback: nothing in this
#: package downgrades to it, and it is reachable only by asking for it by name.
SECURITY: dict[str, int] = {"starttls": 587, "ssl": 465, "none": 25}

#: Gmail's own server, and the two variables a machine that already sends through it will already
#: have. Read as a fallback and only when the host is Gmail's, so the credential cannot follow a
#: typo to somebody else's server. Named here rather than in the browser interface because the
#: interface must not be the only place a capability exists.
GMAIL_HOST = "smtp.gmail.com"
GMAIL_ADDRESS = "GMAIL_ADDRESS"
GMAIL_APP_PASSWORD = "GMAIL_APP_PASSWORD"


def _is_gmail(host: str) -> bool:
    return host.strip().casefold() in (GMAIL_HOST, "smtp.googlemail.com")


def _app_password(raw: str | None) -> str | None:
    """A Google App Password, with the spaces Google shows it with taken out.

    Google presents it as four groups of four and people copy it that way, spaces and all. Refusing
    that would be refusing the only form anybody actually has.
    """
    held = (raw or "").replace(" ", "").strip()
    return held or None
DEFAULT_SECURITY = "starttls"

#: The cap on how many new properties one email lists. More than any ordinary night produces, few
#: enough to scroll on a phone. The first run against a new area is the case this exists for.
DEFAULT_MAX_NEW = 25

ENV_FILE = ".env"


class MailMisconfigured(InvalidInput):
    """Half an account, or a value that cannot go in a message header.

    Invalid input rather than a precondition, because the fix is always in what the operator wrote.
    Raised while the settings are being read, which is before a run starts, which is the whole
    point: the spec asks for a configuration problem to be reported at validation time rather than
    after an hour of throttled requests.
    """


def read_env_file(path: Path) -> dict[str, str]:
    """`KEY=value` lines, and nothing more.

    Deliberately not a dependency and deliberately not a parser. It reads what a person types into
    a `.env` file: a key, an equals sign, a value, one layer of quotes if they used any, blank
    lines and `#` comments ignored. `export KEY=value` is accepted because everybody pastes it.

    No interpolation, no multi-line values, no escapes. A `.env` file that needs those is a file
    that should be an environment.
    """
    found: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            found[key] = value
    return found


def environment(root: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The `.env` file beside the database, with the real environment on top.

    That order and not the other one. A person who exports a variable in the shell they are
    standing in means it, and a file they wrote last month should not quietly win over it.
    """
    values = read_env_file(root / ENV_FILE)
    values.update(environ if environ is not None else os.environ)
    return values


@dataclass(frozen=True, slots=True)
class MailAccount:
    """Everything needed to hand one message to a server.

    Frozen, and never rendered. `__repr__` is overridden because a dataclass's own would put the
    password in every traceback, every debugger session, and every log line somebody adds in a
    hurry, which is exactly how a credential escapes a program that was careful everywhere else.
    """

    host: str
    port: int
    security: str
    sender: str
    recipients: tuple[str, ...]
    username: str | None = None
    password: str | None = None

    def __repr__(self) -> str:
        return (
            f"MailAccount(host={self.host!r}, port={self.port!r}, security={self.security!r}, "
            f"sender={self.sender!r}, recipients={self.recipients!r}, "
            f"username={self.username!r}, password={'<set>' if self.password else None})"
        )


@dataclass(frozen=True, slots=True)
class DeliverySettings:
    """What this installation does with a finished run's report."""

    digest_path: Path
    max_new: int
    account: MailAccount | None = None
    #: Why there is no account, in words a person can act on. Empty when there is one.
    why_no_mail: str | None = None

    @property
    def sends_email(self) -> bool:
        return self.account is not None


def _one_line(name: str, value: str) -> str:
    """A value that is going into a message header, or a refusal.

    A newline in a header value is how a message gets extra headers nobody wrote: an address of
    `me@example.com\\nBcc: elsewhere@example.com` is one string to a person and two headers to a
    mail server. `EmailMessage` refuses it at send time; refusing it here means it is reported
    while somebody is still looking at a terminal.
    """
    if "\n" in value or "\r" in value:
        raise MailMisconfigured(
            f"{name} contains a line break, which cannot go in a message header. "
            f"Put one address per entry, separated by commas."
        )
    return value


def _port_for(values: Mapping[str, str], security: str) -> int:
    raw = (values.get(SMTP_PORT) or "").strip()
    if not raw:
        return SECURITY[security]
    try:
        port = int(raw)
    except ValueError:
        raise MailMisconfigured(f"{SMTP_PORT} wants a whole number, got {raw!r}.") from None
    if not 1 <= port <= 65535:
        raise MailMisconfigured(f"{SMTP_PORT} is {port}, which is not a port number.")
    return port


def _account(values: Mapping[str, str]) -> tuple[MailAccount | None, str | None]:
    """The account, or the reason there is not one.

    Nothing configured is an answer rather than an error (invariant 9). Some of it configured is an
    error, because it is always somebody who believes they set up email.
    """
    host = (values.get(SMTP_HOST) or "").strip()
    sender = (values.get(MAIL_FROM) or "").strip()
    recipients = tuple(
        part.strip() for part in (values.get(MAIL_TO) or "").split(",") if part.strip()
    )
    username = (values.get(SMTP_USERNAME) or "").strip() or None
    password = values.get(SMTP_PASSWORD) or None

    if _is_gmail(host):
        # The same courtesy the model pass extends to OPENAI_API_KEY: an installation that already
        # has a Google App Password for something else should not have to keep a second copy of it
        # here. Scoped to Gmail's own server on purpose. A credential that followed whatever host
        # happened to be configured would be a credential sent wherever a typo pointed.
        sender = sender or (values.get(GMAIL_ADDRESS) or "").strip()
        username = username or (values.get(GMAIL_ADDRESS) or "").strip() or None
        # The spaces come out of whichever variable it was found in: Google shows the password in
        # four groups of four and that is how people paste it.
        password = _app_password(password) or _app_password(values.get(GMAIL_APP_PASSWORD))

    given = {SMTP_HOST: bool(host), MAIL_FROM: bool(sender), MAIL_TO: bool(recipients)}
    if not any(given.values()):
        return None, (
            f"no mail account is configured. Set {SMTP_HOST}, {MAIL_FROM} and {MAIL_TO} in your "
            f"environment or in a .env file to have runs send a digest by email."
        )
    if not all(given.values()):
        missing = ", ".join(name for name, present in given.items() if not present)
        raise MailMisconfigured(
            f"the mail account is incomplete: {missing} is not set. Set all of "
            f"{SMTP_HOST}, {MAIL_FROM} and {MAIL_TO}, or none of them to send no email at all."
        )

    security = (values.get(SMTP_SECURITY) or DEFAULT_SECURITY).strip().lower()
    if security not in SECURITY:
        raise MailMisconfigured(
            f"{SMTP_SECURITY} is {security!r}. It must be one of: {', '.join(SECURITY)}."
        )
    if username and not password:
        raise MailMisconfigured(
            f"{SMTP_USERNAME} is set but {SMTP_PASSWORD} is not. A server that wants a name wants "
            f"a password with it."
        )
    if password and not username:
        raise MailMisconfigured(
            f"{SMTP_PASSWORD} is set but {SMTP_USERNAME} is not, so there is nobody to be."
        )

    return (
        MailAccount(
            host=_one_line(SMTP_HOST, host),
            port=_port_for(values, security),
            security=security,
            sender=_one_line(MAIL_FROM, sender),
            recipients=tuple(_one_line(MAIL_TO, one) for one in recipients),
            username=username,
            password=password,
        ),
        None,
    )


def _max_new(values: Mapping[str, str]) -> int:
    raw = (values.get(MAX_NEW) or "").strip()
    if not raw:
        return DEFAULT_MAX_NEW
    try:
        cap = int(raw)
    except ValueError:
        raise MailMisconfigured(f"{MAX_NEW} wants a whole number, got {raw!r}.") from None
    if cap < 1:
        raise MailMisconfigured(f"{MAX_NEW} is {cap}. An email that lists nothing is not an email.")
    return cap


def load(root: Path, environ: Mapping[str, str] | None = None) -> DeliverySettings:
    """Everything this installation has been told about delivery, validated.

    Every refusal in here happens before a run starts. That is the difference between a scheduled
    task that says "your mail account is missing a recipient" and one that runs for an hour, fetches
    everything correctly, and then fails at the last step with the night's observations already
    made and no way to tell anybody about them.
    """
    values = environment(root, environ)
    account, why = _account(values)
    given = (values.get(DIGEST_PATH) or "").strip()
    return DeliverySettings(
        digest_path=Path(given) if given else root / DEFAULT_DIGEST_NAME,
        max_new=_max_new(values),
        account=account,
        why_no_mail=why,
    )
