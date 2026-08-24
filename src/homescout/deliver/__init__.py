"""Delivery: what happens to a finished run's report.

The run is over by the time anything here is called. This package writes the digest where a
scheduled agent will find it and sends the email a person will read, and it can do neither of those
things wrong in a way that costs the run: it is handed a document that is already built and a store
it only appends a delivery record to.

Email is optional. With no mail account configured this package still writes the file and reports
the email channel as skipped, because product invariant 9 says an unconfigured optional component
leaves the tool fully functional.
"""

from .delivery import ChannelOutcome, DeliveryOutcome, deliver, send_email, write_digest
from .mail import (
    MailFailed,
    MailTransport,
    SmtpTransport,
    register_transport,
    unregister_transport,
)
from .message import build, moved, render, subject
from .settings import (
    VARIABLES,
    DeliverySettings,
    MailAccount,
    MailMisconfigured,
    load,
)

__all__ = [
    "VARIABLES",
    "ChannelOutcome",
    "DeliveryOutcome",
    "DeliverySettings",
    "MailAccount",
    "MailFailed",
    "MailMisconfigured",
    "MailTransport",
    "SmtpTransport",
    "build",
    "deliver",
    "load",
    "moved",
    "render",
    "send_email",
    "register_transport",
    "subject",
    "unregister_transport",
    "write_digest",
]
