"""A mail server that keeps what it was given, and an installation that has one configured.

Nothing here fakes the message. Every test above this line builds a real digest from a real run,
renders it with the real builder, and parses the real MIME the transport was handed. The only thing
substituted is the socket.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from homescout.deliver import register_transport, unregister_transport
from homescout.deliver.mail import MailFailed
from homescout.deliver.settings import DeliverySettings, MailAccount

#: Deliberately obvious, and deliberately a string no other fixture contains, so a test that
#: searches a rendered message for it is searching for something that could only have come from
#: the account.
PASSWORD = "correct-horse-battery-staple"

MAIL_ENVIRONMENT: dict[str, str] = {
    "HOMESCOUT_SMTP_HOST": "smtp.example.invalid",
    "HOMESCOUT_MAIL_FROM": "homescout@example.invalid",
    "HOMESCOUT_MAIL_TO": "me@example.invalid",
    "HOMESCOUT_SMTP_USERNAME": "someone",
    "HOMESCOUT_SMTP_PASSWORD": PASSWORD,
}


def environment(**overrides: str | None) -> dict[str, str]:
    """A configured installation, with anything a test wants changed or removed."""
    values = dict(MAIL_ENVIRONMENT)
    for key, value in overrides.items():
        name = key if key.startswith("HOMESCOUT_") else f"HOMESCOUT_{key.upper()}"
        if value is None:
            values.pop(name, None)
        else:
            values[name] = value
    return values


def account(**overrides: Any) -> MailAccount:
    defaults: dict[str, Any] = {
        "host": "smtp.example.invalid",
        "port": 587,
        "security": "starttls",
        "sender": "homescout@example.invalid",
        "recipients": ("me@example.invalid",),
        "username": "someone",
        "password": PASSWORD,
    }
    defaults.update(overrides)
    return MailAccount(**defaults)


def settings(root: Path, *, mail: bool = True, max_new: int = 25, **overrides: Any) -> Any:
    return DeliverySettings(
        digest_path=Path(overrides.pop("digest_path", root / "digest.json")),
        max_new=max_new,
        account=account(**overrides) if mail else None,
        why_no_mail=None if mail else "no mail account is configured.",
    )


class FakeTransport:
    """A mail server that either keeps the message or refuses it."""

    def __init__(self, fails: str | None = None) -> None:
        self.fails = fails
        self.sent: list[tuple[MailAccount, EmailMessage]] = []

    def send(self, account: MailAccount, message: EmailMessage) -> None:
        if self.fails is not None:
            raise MailFailed(self.fails)
        self.sent.append((account, message))

    @property
    def message(self) -> EmailMessage:
        assert self.sent, "nothing was sent"
        return self.sent[-1][1]


@contextmanager
def sending(transport: FakeTransport | None = None) -> Iterator[FakeTransport]:
    """Put a transport in front of the mail server for the command line to find."""
    fake = transport if transport is not None else FakeTransport()
    register_transport(lambda: fake)
    try:
        yield fake
    finally:
        unregister_transport()


def parts(message: EmailMessage) -> dict[str, Any]:
    """The message pulled apart the way a client would: text, html, and the related images."""
    text = message.get_body(preferencelist=("plain",))
    html = message.get_body(preferencelist=("html",))
    images = [
        part
        for part in message.walk()
        if part.get_content_maintype() == "image"
    ]
    return {
        "text": text.get_content() if text else "",
        "html": html.get_content() if html else "",
        "images": images,
        "cids": {
            (part["Content-ID"] or "").strip("<>"): part.get_payload(decode=True)
            for part in images
        },
    }


def env_file(root: Path, values: Mapping[str, str]) -> Path:
    path = root / ".env"
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8"
    )
    return path
