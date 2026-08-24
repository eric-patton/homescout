"""One real message, through a real mail server.

Marked slow and skipped unless an account is configured, because there is no public SMTP server to
be polite to and nobody else's inbox to send to. Set the variables in `.env.example` and run:

    uv run pytest -m slow tests/test_deliver_live.py

What this catches that nothing else can: a server that refuses the certificate, a provider that
rejects the message shape, and a client that renders the result as something other than an email.
The last one needs a human to look, and this test says so rather than pretending to check it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_fakes import FakeSource, row, search, workspace
from homescout import api, digest
from homescout.deliver import build, load
from homescout.deliver.mail import SmtpTransport
from homescout.store import Store

pytestmark = pytest.mark.slow


@pytest.fixture
def account(tmp_path: Path):
    settings = load(tmp_path)
    if settings.account is None:
        pytest.skip("no mail account configured: " + (settings.why_no_mail or ""))
    return settings.account


def test_a_real_server_accepts_a_real_digest(account, store: Store) -> None:
    """feat-012/AC-4: everything up to the inbox, once, against the account you configured.

    Whether it *looks* right on a phone is the one thing here a test cannot answer. Open it.
    """
    space = workspace(
        store,
        searches=[search("portales")],
        sources={"fake": FakeSource(rows=[row("a", price=400_000), row("b")])},
    )
    first = api.run_search(space, "portales")
    space = workspace(
        store,
        searches=[search("portales")],
        sources={"fake": FakeSource(rows=[row("a", price=372_500)])},
    )
    second = api.run_search(space, "portales")
    assert first.run.id != second.run.id

    document = digest.build(
        [
            digest.entry(
                store,
                search_name="portales",
                comparison=second.comparison,
                outcome=second,
            )
        ],
        kind="run",
    )
    message = build(
        document,
        sender=account.sender,
        recipients=account.recipients,
        root=store.path.parent,
    )

    SmtpTransport().send(account, message)
