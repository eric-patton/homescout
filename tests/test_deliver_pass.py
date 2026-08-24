"""Delivery: the file, the silence, and what a refused message does not cost.

The design decision under most of these is silence. A digest that arrives every night whether or
not anything happened trains its reader to ignore it, so the spec asks explicitly for a test that an
unchanged run sends nothing. That test is here, and so is its opposite, because a rule that only
ever suppresses is indistinguishable from a broken sender.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cli_fakes import FakeSource, row, search, workspace
from deliver_fakes import PASSWORD, FakeTransport
from deliver_fakes import settings as configured
from homescout import api, digest
from homescout.deliver import deliver
from homescout.store import Store


def run(store: Store, *, rows, name="portales", outcome="ok", detail=None):
    space = workspace(
        store,
        searches=[search(name)],
        sources={"fake": FakeSource(rows=rows, outcome=outcome, detail=detail)},
    )
    return api.run_search(space, name)


def document(store: Store, *outcomes):
    return digest.build(
        [
            digest.entry(
                store, search_name=o.run.search_name, comparison=o.comparison, outcome=o
            )
            for o in outcomes
        ],
        kind="run",
    )


def test_a_run_that_found_something_writes_the_file_and_sends_the_email(store: Store) -> None:
    """feat-012/AC-2, feat-012/AC-3: both channels, with no interaction."""
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent)
    transport = FakeTransport()

    delivered = deliver(store, document(store, outcome), settings, transport=transport)

    assert delivered.digest.outcome == "written"
    assert settings.digest_path.exists()
    assert delivered.email.outcome == "sent"
    assert len(transport.sent) == 1
    assert transport.sent[0][1]["To"] == "me@example.invalid"


def test_an_unchanged_run_sends_nothing_and_still_writes_the_file(store: Store) -> None:
    """feat-012/AC-3: the criterion asks for this test by name.

    And feat-012/AC-2 in the same breath: "the run happened and found nothing" and "the run did not
    happen" are completely different facts to a scheduled agent, and the file is how it tells them
    apart.
    """
    run(store, rows=[row("a")])
    second = run(store, rows=[row("a")])
    settings = configured(store.path.parent)
    transport = FakeTransport()

    delivered = deliver(store, document(store, second), settings, transport=transport)

    assert transport.sent == [], "an email arrived on a night when nothing happened"
    assert delivered.email.outcome == "suppressed"
    assert delivered.moved == 0
    assert settings.digest_path.exists()
    assert json.loads(settings.digest_path.read_text(encoding="utf-8"))["kind"] == "run"


def test_a_property_that_only_became_flagged_is_worth_an_email(store: Store) -> None:
    """feat-012/AC-3: newly flagged is on the criterion's own list, and it is the interesting one.

    A property that has not changed at all can still become worth looking at because a criterion
    started matching it, which is what happens the night after enrichment fills in a flood zone.
    """
    settings = configured(store.path.parent)
    transport = FakeTransport()
    quiet = {
        "homescout": {"digest_version": 1, "generated_at": "2026-08-24T00:00:00Z"},
        "kind": "run",
        "skipped": [],
        "searches": [
            {
                "name": "portales",
                "run_id": "r2",
                "counts": {"matched": 3, "new": 0, "changed": 0, "gone": 0, "returned": 0,
                           "flagged": 1},
                "new": [],
                "price_changes": [],
                "status_changes": [],
                "other_changes": [],
                "gone": [],
                "returned": [],
                "flagged": [{"listing_id": "x", "address_line": "1 Example Road",
                             "rules": ["in-the-floodplain"]}],
                "sources": [],
            }
        ],
    }

    delivered = deliver(store, quiet, settings, transport=transport)

    assert delivered.moved == 1
    assert delivered.email.outcome == "sent"
    assert "in-the-floodplain" in transport.message.as_string()


def test_a_degraded_run_with_nothing_to_report_stays_silent(store: Store) -> None:
    """feat-012/AC-3, and the spec's edge case: the degradation reaches the digest, not the phone.

    A person does not need waking because a source timed out. A scheduled agent does need to know,
    and it is reading the file and the exit code, which is where it is.
    """
    run(store, rows=[row("a")])
    second = run(store, rows=[row("a")], outcome="failed", detail="the service is down")
    settings = configured(store.path.parent)
    transport = FakeTransport()

    delivered = deliver(store, document(store, second), settings, transport=transport)

    assert transport.sent == []
    assert delivered.email.outcome == "suppressed"
    written = json.loads(settings.digest_path.read_text(encoding="utf-8"))
    assert written["searches"][0]["outcome"] == "degraded"
    assert written["searches"][0]["sources"][0]["outcome"] == "failed"


def test_no_mail_account_still_writes_the_file(store: Store) -> None:
    """feat-012/AC-11: email is optional, and an installation without it is fully functional."""
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent, mail=False)

    delivered = deliver(store, document(store, outcome), settings)

    assert delivered.digest.outcome == "written"
    assert delivered.email.outcome == "skipped"
    assert delivered.failed is False, "nothing broke"
    assert settings.digest_path.exists()


def test_a_refused_message_costs_the_email_and_nothing_else(store: Store) -> None:
    """feat-012/AC-10: the digest is written, the run's results are untouched, and it is recorded.

    The ordering is the guarantee: the file is written before the message is attempted, so a mail
    server that is down cannot cost an automated agent the only machine-readable record that the
    run happened.
    """
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent)
    before = store.snapshots_for_run(outcome.run.id)

    delivered = deliver(
        store,
        document(store, outcome),
        settings,
        transport=FakeTransport(fails="550 mailbox unavailable"),
    )

    assert delivered.email.outcome == "failed"
    assert "550" in (delivered.email.detail or "")
    assert delivered.digest.outcome == "written"
    assert settings.digest_path.exists()
    assert store.snapshots_for_run(outcome.run.id) == before, "the run's results are untouched"


def test_every_delivery_is_recorded(store: Store) -> None:
    """feat-012/AC-10: because the question a person asks the morning after is which silence it was.

    Did last night's run mail me and I missed it, or did it decide there was nothing to say, or does
    this installation not have an account at all? Three different rows.
    """
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent)

    deliver(store, document(store, outcome), settings, transport=FakeTransport())

    written = store.deliveries()
    assert {found.channel: found.outcome for found in written} == {
        "digest": "written",
        "email": "sent",
    }
    assert all(found.run_ids == (outcome.run.id,) for found in written)


def test_a_delivery_record_never_holds_a_credential(store: Store) -> None:
    """feat-012/AC-9: including on the path where the server refused the message."""
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent)

    deliver(
        store,
        document(store, outcome),
        settings,
        transport=FakeTransport(fails=f"535 authentication failed for {PASSWORD}"),
    )

    for found in store.deliveries():
        assert PASSWORD not in f"{found.target} {found.detail}"


def test_a_digest_path_that_cannot_be_written_is_reported(store: Store, tmp_path: Path) -> None:
    """feat-012/AC-2, and the spec's edge case: a scheduler must record a failure, not a success.

    An apparent success with no file is the worst outcome available here, because the agent reading
    the file has no way to tell it from a night with nothing in it.
    """
    outcome = run(store, rows=[row("a")])
    settings = configured(store.path.parent, digest_path=tmp_path / "nowhere" / "digest.json")

    delivered = deliver(store, document(store, outcome), settings, transport=FakeTransport())

    assert delivered.digest.outcome == "failed"
    assert delivered.failed is True
    assert store.deliveries()[-1].outcome == "failed"


def test_the_file_is_replaced_whole_rather_than_written_in_place(store: Store) -> None:
    """feat-012/AC-2: a reader that wakes mid-write gets last night's file, never half of tonight's.

    A scheduled agent polling this path is the entire reason the file exists.
    """
    first = run(store, rows=[row("a")])
    settings = configured(store.path.parent)
    deliver(store, document(store, first), settings, transport=FakeTransport())
    original = settings.digest_path.read_text(encoding="utf-8")

    second = run(store, rows=[row("a"), row("b")])
    deliver(store, document(store, second), settings, transport=FakeTransport())

    assert settings.digest_path.read_text(encoding="utf-8") != original
    assert not list(settings.digest_path.parent.glob("*.partial")), "nothing left behind"


def test_a_delivery_cannot_reach_the_run(store: Store) -> None:
    """feat-012/AC-10: structurally, which is the actual guarantee.

    Asserted as the shape of the call rather than as an observation: a delivery that happened to
    leave the store alone would prove nothing. What this asserts is that delivery is handed a
    document that is already built, so there is no code path from here to a snapshot.
    """
    import inspect

    from homescout.deliver import delivery as module

    source = inspect.getsource(module)
    for forbidden in ("run_search", "record_observations", "complete_run", "start_run"):
        assert forbidden not in source, forbidden
    assert "record_delivery" in source, "the only thing it writes"


def test_a_delivery_record_is_history_and_cannot_be_rewritten(store: Store) -> None:
    """feat-012/AC-10: it is an observation, so this database does not let it be edited.

    A second attempt after a failure is a second row rather than a correction of the first, which
    is what makes "it failed twice and then went out" recoverable from the record.
    """
    store.record_delivery("email", "failed", target="me@example.invalid")
    conn = store.connection

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE deliveries SET outcome = 'sent'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM deliveries")
