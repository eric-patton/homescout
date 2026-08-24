"""Handing one message to a server, and nothing else.

Behind a protocol, so every test above this line runs the real message builder and the real
delivery pass against a transport that keeps what it was given. There is exactly one place in this
product that opens a socket to a mail server, and this is it.

Three rules hold here and are worth stating where somebody might simplify them away:

**The certificate is verified.** `ssl.create_default_context()` for both encrypted modes. An
unverified context is one keyword argument away and it turns an encrypted connection into a
decorative one.

**There is no fallback.** A server that does not offer STARTTLS when STARTTLS was asked for is a
failed delivery. Continuing in the clear would send a password across a network to make an error go
away, which is the wrong trade in every direction.

**Plaintext is reachable only by name.** `security: none` exists because a relay on a home network
is a real configuration. Nothing here chooses it.
"""

from __future__ import annotations

import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from typing import Protocol

from .settings import MailAccount

#: Long enough for a slow server on a domestic connection, short enough that a scheduled task does
#: not sit on a dead socket until somebody notices in the morning.
TIMEOUT_SECONDS = 30.0


class MailFailed(Exception):
    """The server would not take the message.

    Always caught by the delivery pass and turned into a recorded outcome. It never escapes to a
    surface, because a run whose results are complete and stored did not fail.
    """


class MailTransport(Protocol):
    def send(self, account: MailAccount, message: EmailMessage) -> None: ...


def without_credential(detail: str, account: MailAccount) -> str:
    """Whatever the server said, minus anything we sent it.

    Nothing in the standard library puts a password in an exception. This is here because the
    assertion "no credential is ever reported" should not depend on that staying true, in this
    library or in whatever somebody swaps in later.

    Applied twice on purpose: here, where the real transport turns an exception into a failure, and
    again where a failure is turned into a durable delivery record. A transport is a substitutable
    part, and the recorded row is the thing that outlives the process.
    """
    if account.password:
        detail = detail.replace(account.password, "***")
    return detail


class SmtpTransport:
    """The real conversation."""

    def __init__(self, timeout: float = TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def send(self, account: MailAccount, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        try:
            if account.security == "ssl":
                server: smtplib.SMTP = smtplib.SMTP_SSL(
                    account.host, account.port, timeout=self.timeout, context=context
                )
            else:
                server = smtplib.SMTP(account.host, account.port, timeout=self.timeout)
            with server:
                if account.security == "starttls":
                    # Raises when the server does not offer it, and that is the intended outcome:
                    # asked for encryption, did not get encryption, did not send anything.
                    server.starttls(context=context)
                if account.username:
                    server.login(account.username, account.password or "")
                server.send_message(message)
        except (smtplib.SMTPException, ssl.SSLError, OSError) as failure:
            raise MailFailed(
                without_credential(f"{type(failure).__name__}: {failure}", account)
            ) from failure


#: How a test, or a later surface, puts something else in front of the mail server. The same shape
#: the saved-search catalog, the merge queue and the boundary provider already use, so there is one
#: way to substitute a dependency in this product rather than four.
_TRANSPORT: Callable[[], MailTransport] | None = None


def register_transport(factory: Callable[[], MailTransport]) -> None:
    global _TRANSPORT
    _TRANSPORT = factory


def unregister_transport() -> None:
    global _TRANSPORT
    _TRANSPORT = None


def default_transport() -> MailTransport:
    """Whatever is registered, or a real SMTP conversation."""
    return _TRANSPORT() if _TRANSPORT is not None else SmtpTransport()
