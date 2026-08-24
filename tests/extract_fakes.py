"""A model server that can be told to behave badly, and the corpus of real prose.

Everything about the model pass is proved against this rather than against a real service, for the
usual two reasons: a suite that needs a credential is a suite most people cannot run, and a service
that answers well today is not a test of what happens when it does not.

The one thing this deliberately does not fake is the paced session. Requests go through the real
`PacedSession` over a transport that answers from memory, so the timeout, the body limit, the
backoff and the honest user agent are the ones the product actually uses.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from homescout.extract import settings
from homescout.records import ListingFields, SourceRow
from homescout.sources.politeness import PacedSession
from homescout.store import SourceOutcome, Store

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "extract" / "descriptions.json"


def corpus() -> list[dict[str, str]]:
    """263 real descriptions, with everything that identified a property taken out."""
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def texts() -> list[str]:
    return [entry["text"] for entry in corpus()]


class Reply:
    """One canned answer, in whatever shape the test needs it to be wrong in."""

    def __init__(self, status: int = 200, body: str | bytes = "") -> None:
        self.status = status
        self._body = body.encode("utf-8") if isinstance(body, str) else body

    def read(self, limit: int) -> bytes:
        from homescout.sources.politeness import BodyTooLarge

        if len(self._body) > limit:
            raise BodyTooLarge
        return self._body

    def header(self, name: str) -> str | None:
        return {"content-type": "application/json"}.get(name.lower())


def answering(values: Mapping[str, tuple[str, str]]) -> str:
    """A well-formed reply asserting these values, each with the quote it is attributed to."""
    return content(json.dumps({k: {"value": v, "quote": q} for k, (v, q) in values.items()}))


def content(text: str) -> str:
    """`text` wrapped in the OpenAI-compatible envelope both backends answer with."""
    return json.dumps(
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        }
    )


class FakeModel:
    """A transport standing in for an OpenAI-compatible server.

    It records every request it was given, which is how the privacy test asks what actually left the
    machine, and it answers with whatever the test handed it.
    """

    def __init__(self, reply: Any = None) -> None:
        #: Either a `Reply`, or something callable taking the request and returning one.
        self.reply = reply if reply is not None else Reply(200, answering({}))
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> Reply:
        self.requests.append(request)
        answer = self.reply(request) if callable(self.reply) else self.reply
        if isinstance(answer, BaseException):
            raise answer
        return answer

    # -- what a test asks it afterwards -------------------------------------

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.body.decode("utf-8")) for r in self.requests]

    def prompt_text(self, index: int = 0) -> str:
        """Everything that was sent as prose, joined, for asking what it contains."""
        return "\n".join(m["content"] for m in self.bodies[index]["messages"])

    @property
    def urls(self) -> list[str]:
        return [r.url for r in self.requests]

    def header(self, name: str, index: int = 0) -> str | None:
        return dict(self.requests[index].headers).get(name)


def session(transport: FakeModel) -> PacedSession:
    """The real paced session over a fake transport, on a clock that only moves when it sleeps.

    The delay is the shipped one rather than zero, because the politeness floor refuses zero and is
    not configurable, which is the right refusal. So time is faked instead of manners.
    """
    from sources_fakes import FakeClock, session_with

    return session_with(transport, clock=FakeClock(), config=settings.pacing())


def environ(**overrides: str) -> dict[str, str]:
    """An environment with a model configured, as a hosted one unless told otherwise."""
    values = {
        "HOMESCOUT_EXTRACT_BASE_URL": "https://models.example.invalid/v1",
        "HOMESCOUT_EXTRACT_MODEL": "test-model",
        "HOMESCOUT_EXTRACT_API_KEY": "sk-not-a-real-key",
    }
    values.update(overrides)
    return values


def described(listing_id: str, description: str | None, **fields: Any) -> SourceRow:
    """One property whose description is the thing under test."""
    values: dict[str, Any] = {
        "price": 250_000,
        "listing_status": "for_sale",
        "beds": 3,
        "baths": 2,
        "address_line": f"{listing_id} Example Road",
        "city": "Portales",
        "state": "NM",
        "postal_code": "88130",
        "description": description,
    }
    values.update(fields)
    return SourceRow(
        source="realtor",
        fields=ListingFields(**values),
        payload={"id": listing_id},
        source_listing_id=listing_id,
    )


class Loaded:
    """A completed run, and how to find the properties in it by the name the test gave them."""

    def __init__(self, run_id: str, by_source_id: Mapping[str, str]) -> None:
        self.run_id = run_id
        self.ids = dict(by_source_id)

    def __getitem__(self, source_listing_id: str) -> str:
        return self.ids[source_listing_id]


def load(store: Store, rows: Iterable[SourceRow], *, search: str = "town") -> Loaded:
    """Record these properties into a store the way a run does."""
    held = list(rows)
    run = store.start_run(search)
    listing_ids = store.record_observations(run.id, "realtor", held) if held else []
    store.record_source_outcome(
        run.id, SourceOutcome(source="realtor", outcome="ok", row_count=len(held))
    )
    store.complete_run(run.id)
    return Loaded(
        run.id,
        {
            row.source_listing_id or "": listing_id
            for row, listing_id in zip(held, listing_ids, strict=False)
        },
    )


def with_descriptions(store: Store, descriptions: Iterable[str | None]) -> Loaded:
    return load(
        store,
        [described(f"p{index:03d}", text) for index, text in enumerate(descriptions, start=1)],
    )


def replies(answers: list[Any]) -> Callable[[Any], Any]:
    """Answer differently on each successive request, so a test can vary one call in a pass."""
    remaining = list(answers)

    def next_one(_request: Any) -> Any:
        return remaining.pop(0) if remaining else Reply(200, answering({}))

    return next_one
