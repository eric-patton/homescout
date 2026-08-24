"""What leaves this machine, and what a base address is allowed to be.

This is the only path in the whole product that sends anything to a service the user chose rather
than to a listing site or a public dataset, and it sends prose about somebody's house. The
pre-build check rejected the first draft of the plan for not saying what goes in the body, so this
file is the enforcement of the answer: the instruction, the vocabulary, and the description.

The obvious implementation would send a *property*, because a property is what the code is holding.
That would put an address, a price and a search's behaviour into a third party's logs, and it would
cost one line nobody would notice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from extract_fakes import FakeModel, Reply, answering, described, environ, load, session
from homescout.extract import read_prose
from homescout.extract.model import body_for
from homescout.extract.pass_ import run_pass
from homescout.extract.settings import ExtractionMisconfigured, account, without_credential
from homescout.store import Store

#: A description with nothing identifying in it, on a property that has plenty.
PROSE = "A comfortable home on a quiet street, with a large fenced yard and a metal roof."

SECRETS = {
    "the address": "1828 Redwine",
    "the town": "Portales",
    "the price": "185000",
    "the identifier": "realtor-99887766",
    "the coordinates": "34.1862",
    "the link": "listings.example.invalid/1828",
    "the search": "roosevelt-county",
}


def test_only_the_description_leaves_the_machine(store: Store, tmp_path: Path) -> None:
    """Nothing about the property reaches the request. Asserted against the bytes that were sent."""
    load(
        store,
        [
            described(
                "realtor-99887766",
                PROSE,
                address_line="1828 Redwine",
                city="Portales",
                state="NM",
                postal_code="88130",
                price=185_000,
                latitude=34.1862,
                longitude=-103.3452,
                listing_url="https://listings.example.invalid/1828",
            )
        ],
        search="roosevelt-county",
    )
    transport = FakeModel(Reply(200, answering({})))

    run_pass(store, root=tmp_path, environ=environ(), session=session(transport))

    assert len(transport.requests) == 1
    sent = transport.requests[0].body.decode("utf-8")
    for what, secret in SECRETS.items():
        assert secret not in sent, f"{what} was sent to the model"
    assert PROSE in sent, "and the description, which is the whole point, was"


def test_the_request_is_built_from_prose_and_cannot_reach_a_property(tmp_path: Path) -> None:
    """Structural rather than careful: `body_for` is handed a description and a list of names."""
    prose = read_prose(PROSE)
    assert prose is not None
    body = json.loads(body_for(prose, account(tmp_path, environ()), ("roof",)).decode("utf-8"))

    said = json.dumps(body)
    for secret in SECRETS.values():
        assert secret not in said


def test_nothing_but_the_body_carries_the_property_either(store: Store, tmp_path: Path) -> None:
    """The headers and the address are configuration, and configuration knows no listings."""
    load(store, [described("realtor-99887766", PROSE, address_line="1828 Redwine")])
    transport = FakeModel(Reply(200, answering({})))

    run_pass(store, root=tmp_path, environ=environ(), session=session(transport))

    request = transport.requests[0]
    assert request.url == "https://models.example.invalid/v1/chat/completions"
    for value in dict(request.headers).values():
        for secret in SECRETS.values():
            assert secret not in value


# ---------------------------------------------------------------------------
# A request target is configuration, and configuration is checked
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "file:///etc/passwd",
        "data:text/plain,hello",
        "javascript:alert(1)",
        "ftp://models.example.invalid/v1",
        "not a url at all",
        "https://",
    ],
)
def test_a_base_address_that_is_not_a_request_is_refused(address: str, tmp_path: Path) -> None:
    """Before a run starts, and naming the variable, rather than inside a loop over a county."""
    with pytest.raises(ExtractionMisconfigured) as raised:
        account(tmp_path, environ(HOMESCOUT_EXTRACT_BASE_URL=address))
    assert "HOMESCOUT_EXTRACT_BASE_URL" in str(raised.value)


def test_a_plain_http_address_is_allowed_because_a_local_server_is_one(tmp_path: Path) -> None:
    """LM Studio serves plain HTTP on loopback, and refusing that would refuse the local backend."""
    found = account(
        tmp_path,
        environ(
            HOMESCOUT_EXTRACT_BASE_URL="http://localhost:1234/v1",
            HOMESCOUT_EXTRACT_API_KEY="",
            OPENAI_API_KEY="",
        ),
    )
    assert found.endpoint == "http://localhost:1234/v1/chat/completions"


# ---------------------------------------------------------------------------
# The credential
# ---------------------------------------------------------------------------


def test_a_credential_in_a_query_string_is_removed_from_a_message() -> None:
    """Some OpenAI-compatible proxies take a key as a query parameter, and failures carry URLs."""
    from homescout.extract.settings import ModelAccount

    held = ModelAccount("https://proxy.example.invalid/v1", "m", "sk-secret")
    said = without_credential(
        "refused by https://proxy.example.invalid/v1/chat/completions?api_key=sk-secret", held
    )
    assert "sk-secret" not in said
    assert "query removed" in said


def test_a_credential_is_removed_even_where_it_is_not_in_a_url() -> None:
    from homescout.extract.settings import ModelAccount

    held = ModelAccount("https://models.example.invalid/v1", "m", "sk-secret")
    assert "sk-secret" not in without_credential("bad key sk-secret rejected", held)


def test_a_failure_recorded_by_the_pass_carries_no_credential(
    store: Store, tmp_path: Path
) -> None:
    """The recording boundary, not only the transport. Delivery learned this one the hard way."""
    load(store, [described("p1", PROSE)])
    transport = FakeModel(
        RuntimeError("refused by https://models.example.invalid/v1?api_key=sk-not-a-real-key")
    )

    outcome = run_pass(store, root=tmp_path, environ=environ(), session=session(transport))

    assert outcome.failures
    assert all("sk-not-a-real-key" not in failure for failure in outcome.failures)


def test_the_credential_is_never_written_to_the_store(store: Store, tmp_path: Path) -> None:
    """Nothing in this feature has a reason to persist one, so nothing may."""
    load(store, [described("p1", PROSE)])
    run_pass(
        store,
        root=tmp_path,
        environ=environ(),
        session=session(FakeModel(Reply(200, answering({})))),
    )

    rows = store.connection.execute("SELECT * FROM extracted_values").fetchall()
    assert rows, "something was recorded, or this proves nothing"
    for row in rows:
        for value in tuple(row):
            assert "sk-not-a-real-key" not in str(value)
