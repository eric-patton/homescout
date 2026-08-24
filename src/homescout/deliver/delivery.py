"""What happens to a finished run's report.

Two channels, in this order, and the order is a requirement rather than a preference. The digest
file is written first, so a mail server that refuses the message cannot cost an automated agent the
only machine-readable record that the run happened. Then the email is attempted, and whatever
happens to it happens after the file is already on disk.

Nothing in here can reach the run. It is handed a document that has already been built and a store
it only appends a delivery record to, so "a delivery failure does not alter the run's stored
results" is structural: there is no code path from here to a snapshot.

**Silence is the design decision that matters most.** A digest that arrives every night whether or
not anything happened trains its reader to ignore it, which costs more than sending nothing at all.
So an email goes out only when a run found something to say, and the run that found nothing still
writes its file, because "the run happened and found nothing" and "the run did not happen" are
different facts and the file is how a scheduled agent tells them apart.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..store import Store
from .mail import MailFailed, MailTransport, default_transport, without_credential
from .message import build, moved
from .settings import DeliverySettings


@dataclass(frozen=True, slots=True)
class ChannelOutcome:
    """What happened on one channel.

    `written` and `sent` are the two successes. `suppressed` is a deliberate silence, `skipped` is
    a channel this installation does not have, and `failed` is the only one of the five that is
    news.
    """

    channel: str
    outcome: str
    target: str | None = None
    detail: str | None = None

    @property
    def failed(self) -> bool:
        return self.outcome == "failed"


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    digest: ChannelOutcome
    email: ChannelOutcome
    #: How many properties the digest had something to say about. Zero is why an email was
    #: suppressed, and it is worth reporting rather than inferring.
    moved: int

    @property
    def failed(self) -> bool:
        return self.digest.failed or self.email.failed

    @property
    def channels(self) -> tuple[ChannelOutcome, ...]:
        return (self.digest, self.email)


def _run_ids(document: Mapping[str, Any]) -> tuple[str, ...]:
    found = [
        str(entry.get("run_id"))
        for entry in document.get("searches") or ()
        if isinstance(entry, Mapping) and entry.get("run_id")
    ]
    return tuple(found)


def write_digest(document: Mapping[str, Any], path: Path) -> ChannelOutcome:
    """The file, at the configured path, whatever the run found.

    Written whole and then moved into place, so a reader that wakes up mid-write finds either last
    night's file or tonight's, never half of tonight's. A scheduled agent polling this path is the
    entire reason it exists.
    """
    rendered = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(path.name + ".partial")
    try:
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(path)
    except OSError as failure:
        with suppress(OSError):  # pragma: no branch - nothing further to try either way
            temporary.unlink(missing_ok=True)
        return ChannelOutcome("digest", "failed", str(path), f"{failure}")
    return ChannelOutcome("digest", "written", str(path))


def send_email(
    document: Mapping[str, Any],
    settings: DeliverySettings,
    *,
    transport: MailTransport,
    root: Path | None,
    count: int,
) -> ChannelOutcome:
    account = settings.account
    if account is None:
        return ChannelOutcome("email", "skipped", None, settings.why_no_mail)
    recipients = ", ".join(account.recipients)
    if count == 0:
        return ChannelOutcome(
            "email",
            "suppressed",
            recipients,
            "nothing was new, changed, gone, back, or newly flagged",
        )
    try:
        message = build(
            document,
            sender=account.sender,
            recipients=account.recipients,
            root=root,
            max_new=settings.max_new,
        )
        transport.send(account, message)
    except MailFailed as failure:
        # Scrubbed here as well as in the transport. This is where a failure becomes a row that
        # outlives the process, and the transport that produced it is a substitutable part.
        return ChannelOutcome(
            "email", "failed", recipients, without_credential(str(failure), account)
        )
    return ChannelOutcome("email", "sent", recipients, message["Subject"])


def deliver(
    store: Store,
    document: Mapping[str, Any],
    settings: DeliverySettings,
    *,
    transport: MailTransport | None = None,
    run_ids: Sequence[str] | None = None,
) -> DeliveryOutcome:
    """Write the digest, decide whether to send, send, and record both.

    The recording is the part a person reads the morning after: it says whether last night's run
    mailed them and they missed it, or decided there was nothing worth saying.
    """
    count = moved(document)
    runs = tuple(run_ids) if run_ids is not None else _run_ids(document)

    digest_outcome = write_digest(document, settings.digest_path)
    store.record_delivery(
        digest_outcome.channel,
        digest_outcome.outcome,
        target=digest_outcome.target,
        detail=digest_outcome.detail,
        run_ids=runs,
    )

    email_outcome = send_email(
        document,
        settings,
        transport=transport if transport is not None else default_transport(),
        root=store.path.parent,
        count=count,
    )
    store.record_delivery(
        email_outcome.channel,
        email_outcome.outcome,
        target=email_outcome.target,
        detail=email_outcome.detail,
        run_ids=runs,
    )

    return DeliveryOutcome(digest=digest_outcome, email=email_outcome, moved=count)
